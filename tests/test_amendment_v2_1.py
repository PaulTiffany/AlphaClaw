"""Protocol Amendment v2.1 -- B2 replay-source selection.

Offline. The central property under test: B2 source selection depends only on
``repeat_index == 0`` and schema conformance, never on scorer output.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


a21 = _load("amendment_v2_1_mod", SCRIPTS / "amendment_v2_1.py")
v2 = _load("protocol_v2_a21", SCRIPTS / "protocol_v2.py")

B1_ARTIFACT = ROOT / "benchmark" / "screening-v2-B1.json"
B1_SHA = "847828d469d60269a289f5183d07a69c6afc4c123ef1ad51346490e778e0ab14"


def _call(item, repeat, *, schema=True, payload="PAYLOAD", correct=0, expected=3):
    return {
        "item_id": item,
        "repeat_index": repeat,
        "schema_conformant": schema,
        "handoff_payload": payload,
        "handoff_payload_sha256": hashlib.sha256(payload.encode()).hexdigest() if payload else None,
        "requested_model": "qwen/qwen3.7-flash",
        "resolved_model": "qwen/qwen3.7-flash",
        "source_sha256": "img",
        "correct": correct,
        "expected": expected,
    }


# --- the rule ---------------------------------------------------------------


def test_replay_repeat_index_is_zero() -> None:
    assert a21.B2_REPLAY_REPEAT_INDEX == 0


def test_selects_repeat_zero_even_when_repeat_one_scored_better() -> None:
    """The decisive property: selection is blind to score."""
    calls = [
        _call("ocr_count", 0, payload="FROM_R0", correct=0),
        _call("ocr_count", 1, payload="FROM_R1", correct=3),
    ]
    chosen = a21.select_b2_source(calls, "ocr_count")
    assert chosen["repeat_index"] == 0
    assert chosen["handoff_payload"] == "FROM_R0"


def test_selects_repeat_zero_even_when_repeat_zero_scored_worse() -> None:
    calls = [
        _call("ocr_count", 0, payload="FROM_R0", correct=1, expected=3),
        _call("ocr_count", 1, payload="FROM_R1", correct=3, expected=3),
    ]
    assert a21.select_b2_source(calls, "ocr_count")["handoff_payload"] == "FROM_R0"


def test_no_fall_through_to_repeat_one_when_repeat_zero_unusable() -> None:
    calls = [
        _call("ocr_count", 0, schema=False, payload=None),
        _call("ocr_count", 1, payload="FROM_R1"),
    ]
    with pytest.raises(a21.B2SourceUnavailable, match="must not fall through to repeat 1"):
        a21.select_b2_source(calls, "ocr_count")


def test_missing_repeat_zero_is_unavailable_not_substituted() -> None:
    calls = [_call("ocr_count", 1, payload="FROM_R1")]
    with pytest.raises(a21.B2SourceUnavailable):
        a21.select_b2_source(calls, "ocr_count")


def test_empty_payload_at_repeat_zero_is_unavailable() -> None:
    calls = [_call("ocr_count", 0, payload=None), _call("ocr_count", 1, payload="R1")]
    with pytest.raises(a21.B2SourceUnavailable):
        a21.select_b2_source(calls, "ocr_count")


def test_usability_ignores_score_entirely() -> None:
    zero_score = _call("x", 0, correct=0, expected=5)
    assert a21.is_usable_source(zero_score) is True


def test_plan_records_unavailability_rather_than_substituting() -> None:
    calls = [
        _call("ocr_count", 0, payload="A"),
        _call("distractor_selection", 0, schema=False, payload=None),
        _call("distractor_selection", 1, payload="B"),
        _call("multi_fact_composition", 0, payload="C"),
    ]
    plan = a21.build_b2_plan(calls, v2.B2_ITEMS)
    assert [s["item_id"] for s in plan["selected"]] == ["ocr_count", "multi_fact_composition"]
    assert [u["item_id"] for u in plan["unavailable"]] == ["distractor_selection"]
    assert all(s["repeat_index"] == 0 for s in plan["selected"])


# --- selection must not consult scoring fields -------------------------------


def test_selector_source_never_reads_prohibited_fields() -> None:
    source = (SCRIPTS / "amendment_v2_1.py").read_text(encoding="utf-8")
    body = source.split("def select_b2_source", 1)[1].split("def build_b2_plan", 1)[0]
    usable = source.split("def is_usable_source", 1)[1].split("def select_b2_source", 1)[0]
    for field in ("verdicts", "atomic_fact", "scoring_coverage", "expected_answer"):
        assert field not in body, field
        assert field not in usable, field
    # 'correct' must not gate selection
    assert '"correct"' not in usable
    assert '"correct"' not in body


def test_prohibitions_are_declared() -> None:
    spec = a21.specification()
    assert spec["quality_based_selection_prohibited"] is True
    assert spec["fall_through_to_repeat_1_prohibited"] is True
    assert "replication evidence only" in spec["repeat_1_role"]
    for field in ("correct", "verdicts", "atomic_fact_accuracy", "expected_answer"):
        assert field in spec["prohibited_selection_fields"]


# --- linkage to the immutable B1 artifact -----------------------------------


def test_b1_artifact_is_unchanged() -> None:
    assert hashlib.sha256(B1_ARTIFACT.read_bytes()).hexdigest() == B1_SHA


def test_rule_applied_to_the_real_b1_artifact_yields_three_repeat_zero_sources() -> None:
    b1 = json.loads(B1_ARTIFACT.read_text(encoding="utf-8"))
    plan = a21.build_b2_plan(b1["calls"], v2.B2_ITEMS)
    assert plan["unavailable"] == []
    assert [s["item_id"] for s in plan["selected"]] == list(v2.B2_ITEMS)
    assert all(s["repeat_index"] == 0 for s in plan["selected"])
    assert all(s["sensory_model"] == "qwen/qwen3.7-flash" for s in plan["selected"])
    # payload digests must match what B1 recorded
    for chosen in plan["selected"]:
        assert chosen["handoff_payload_sha256"] == hashlib.sha256(
            chosen["handoff_payload"].encode("utf-8")
        ).hexdigest()


# --- scope: nothing else changed --------------------------------------------


def test_v2_conditions_and_caps_unchanged() -> None:
    assert v2.B2_ITEMS == ("ocr_count", "distractor_selection", "multi_fact_composition")
    assert v2.SENSORY_ALTERNATE == "qwen/qwen3.7-flash"
    assert v2.RESIDENT_PRIMARY_MODEL == "minimax/minimax-m3"
    assert v2.ASICLOUD_MAX_CALLS == 42
    v2.validate()


def test_scorer_and_boundary_untouched_by_this_amendment() -> None:
    scorer = (SCRIPTS / "score_handoff.py").read_text(encoding="utf-8").lower()
    boundary = (ROOT / "ingress" / "openrouter_image.py").read_text(encoding="utf-8").lower()
    for token in ("amendment", "repeat_index", "b2_replay"):
        assert token not in scorer, token
        assert token not in boundary, token


def test_relation_lexicon_was_not_broadened_after_b1() -> None:
    """Qwen's 'is located to the left of' must remain unmapped, hence unknown."""
    scorer = _load("score_handoff_a21", SCRIPTS / "score_handoff.py")
    assert "is located to the left of" not in scorer.LEFT_OF_FORMS
    assert "is located to the right of" not in scorer.RIGHT_OF_FORMS
    b1 = json.loads(B1_ARTIFACT.read_text(encoding="utf-8"))
    unknowns = [
        (c["item_id"], c["repeat_index"])
        for c in b1["calls"]
        for v in c["verdicts"]
        if v["verdict"] == "unknown"
    ]
    assert unknowns == [("spatial_relation", 0), ("spatial_relation", 1)]
    assert b1["metrics"]["scoring_coverage"] == pytest.approx(40 / 42)
