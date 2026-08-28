"""Protocol v2 preregistration -- offline tests.

No network, no provider, no container. The replay path is exercised end to end with
an injected fake sensory runner, so byte identity is proven without inference.
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
for extra in (SCRIPTS, ROOT / "ingress"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


v2 = _load("protocol_v2_mod", SCRIPTS / "protocol_v2.py")
replay = _load("replay_handoff_mod", SCRIPTS / "replay_handoff.py")
pipe = _load("pipe_v2", ROOT / "ingress" / "pipe.py")

# v1 / v1.1 artifact digests, asserted unchanged by this amendment.
V1_SHA = "c1b39cbe17d0039f59bb9b1aa2b215696602986e4602e66be356b6b6a35b7efb"

HANDOFF = {
    "observation": {
        "literal": ["Five blue squares in a row", "Black text reading M4"],
        "entities": [{"label": "M4", "kind": "text"}],
        "relations": [],
        "interpretations": [],
        "uncertainty": [],
        "unresolved": [],
    },
    "source": {"sha256": "origimage", "mime_type": "image/png"},
    "schema_version": 1,
}
RULE = (
    "Reply with the token shown, then the number of squares. Use uppercase for the "
    "token and digits only for the count. Reply with no spaces and no other text."
)


def _fake_runner(path, model, api_key):
    return HANDOFF, {
        "model": model,
        "input_tokens": 1,
        "output_tokens": 1,
        "timestamp": "t",
        "source_sha256": "origimage",
    }


# --- named conditions -------------------------------------------------------


def test_exact_model_ids() -> None:
    assert v2.SENSORY_PRIMARY == "dots-studio/dots-3-note-preview:free"
    assert v2.SENSORY_ALTERNATE == "qwen/qwen3.7-flash"
    assert v2.RESIDENT_PRIMARY_PROVIDER == "asicloud"
    assert v2.RESIDENT_PRIMARY_MODEL == "minimax/minimax-m3"
    assert v2.RESIDENT_ALTERNATE_PROVIDER == "openrouter"
    assert v2.RESIDENT_ALTERNATE_MODEL == "google/gemma-4-26b-a4b-it"


def test_forbidden_models_are_barred() -> None:
    for barred in ("openrouter/free", "google/gemma-4-26b-a4b-it:free",
                   "google/gemma-4-31b-it:free"):
        assert barred in v2.FORBIDDEN_MODELS
    named = {v2.SENSORY_PRIMARY, v2.SENSORY_ALTERNATE,
             v2.RESIDENT_PRIMARY_MODEL, v2.RESIDENT_ALTERNATE_MODEL}
    assert not (named & v2.FORBIDDEN_MODELS)


def test_no_automatic_fallback_or_substitution() -> None:
    policy = v2.specification()["policy"]
    assert policy["automatic_fallback_model"] is False
    assert policy["substitute_on_unavailable"] is False
    assert policy["retry_until_pass"] is False
    assert policy["availability_failures_are_evidence"] is True


# --- the exact matrix -------------------------------------------------------


def test_condition_matrix_is_exact() -> None:
    by_id = {c["condition_id"]: c for c in v2.CONDITIONS}
    assert set(by_id) == {"A", "B1", "B2", "C"}

    a = by_id["A"]
    assert (a["sensory_model"], a["resident_model"]) == (v2.SENSORY_PRIMARY,
                                                         v2.RESIDENT_PRIMARY_MODEL)
    assert (a["sensory_calls"], a["boot_calls"], a["episode_calls"]) == (12, 18, 18)

    b1 = by_id["B1"]
    assert b1["sensory_model"] == v2.SENSORY_ALTERNATE
    assert (b1["sensory_calls"], b1["boot_calls"], b1["episode_calls"]) == (12, 0, 0)
    assert b1["resident_model"] is None

    b2 = by_id["B2"]
    assert b2["resident_model"] == v2.RESIDENT_PRIMARY_MODEL
    assert (b2["sensory_calls"], b2["boot_calls"], b2["episode_calls"]) == (0, 3, 3)
    assert b2["uses_replay"] is True and b2["replay_source"] == "B1"

    c = by_id["C"]
    assert c["resident_model"] == v2.RESIDENT_ALTERNATE_MODEL
    assert c["resident_provider"] == "openrouter"
    assert (c["sensory_calls"], c["boot_calls"], c["episode_calls"]) == (0, 3, 3)
    assert c["uses_replay"] is True and c["replay_source"] == "A"


def test_b2_scientific_question_is_sufficiency_not_sampling() -> None:
    b2 = next(c for c in v2.CONDITIONS if c["condition_id"] == "B2")
    q = b2["question"]
    assert "sufficient" in q
    assert "same fixed MiniMax resident reasoner" in q
    assert "different sensory sample" not in q


def test_preselected_items_are_fixed() -> None:
    assert v2.B2_ITEMS == ("ocr_count", "distractor_selection", "multi_fact_composition")
    assert v2.C_CONDITIONS == (
        ("number_arithmetic", "text_control"),
        ("ocr_count", "image_text"),
        ("number_arithmetic", "image_text"),
    )
    # C spans one text-only control, one composition, one resident-reasoning task
    assert sum(1 for _, cond in v2.C_CONDITIONS if cond == "text_control") == 1


def test_preselected_items_exist_in_ground_truth() -> None:
    items = {i["item_id"] for i in
             json.loads((ROOT / "benchmark" / "items.json").read_text(encoding="utf-8"))["items"]}
    assert set(v2.B2_ITEMS) <= items
    assert {i for i, _ in v2.C_CONDITIONS} <= items


def test_replaying_conditions_make_no_sensory_call() -> None:
    for c in v2.CONDITIONS:
        if c["uses_replay"]:
            assert c["sensory_calls"] == 0, c["condition_id"]


# --- caps -------------------------------------------------------------------


def test_asicloud_cap_is_42_and_matches_the_matrix() -> None:
    assert v2.ASICLOUD_MAX_CALLS == 42
    budget = v2.asicloud_call_budget()
    assert budget["A"] == 36
    assert budget["B2"] == 6
    assert budget["total"] == 42
    # condition C bills OpenRouter, not the sponsored allocation
    assert "C" not in budget


def test_previous_cap_recorded_and_raised_explicitly() -> None:
    caps = v2.specification()["caps"]
    assert caps["asicloud_previous_cap"] == 36
    assert caps["asicloud_max_calls"] == 42


def test_token_caps_are_stated() -> None:
    assert v2.ASICLOUD_MAX_INPUT_TOKENS == 124_572
    assert v2.ASICLOUD_MAX_OUTPUT_TOKENS == 21_714


def test_openrouter_budget_split() -> None:
    budget = v2.openrouter_call_budget()
    assert budget["paid"] == 18   # B1 sensory 12 + C resident 6
    assert budget["free"] == 12   # condition A dots sensory
    assert v2.PROJECTED_OPENROUTER_COST_USD == pytest.approx(0.0054)
    assert "not a guaranteed invoice" in v2.specification()["caps"]["cost_note"]


def test_validate_rejects_matrix_drift(monkeypatch) -> None:
    monkeypatch.setattr(v2, "ASICLOUD_MAX_CALLS", 41)
    with pytest.raises(ValueError, match="cap is 41"):
        v2.validate()


# --- replay: byte identity ---------------------------------------------------


def test_replay_reproduces_the_alpha_envelope_byte_for_byte(tmp_path: Path) -> None:
    """The core proof: same evidence, no second sensory call."""
    image = tmp_path / "stim.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 32)

    live_env, live_trace = pipe.prepare(
        text=RULE, input_file=image, model="m", api_key="k", image_runner=_fake_runner
    )
    original_payload = json.loads(live_env)["payload"]["content"]

    replay_path = replay.write_replay_payload(original_payload, tmp_path / "handoff.json")
    replay_env, replay_trace = pipe.prepare(input_file=replay_path)

    assert replay_env == live_env
    report = replay.verify_replay_identity(
        original_payload=original_payload, replay_path=replay_path, envelope=replay_env
    )
    assert report["identical"] is True
    replay.assert_replay_valid(report)

    # and the replay genuinely performed no perception
    assert live_trace["sensory_inference"] is True
    assert replay_trace["sensory_inference"] is False
    assert "sensory_trace" not in replay_trace


def test_replay_receipt_semantics_are_recorded_not_disguised(tmp_path: Path) -> None:
    payload = json.dumps({"human_text": RULE, "sensory_handoff": HANDOFF},
                         ensure_ascii=False, sort_keys=True)
    path = replay.write_replay_payload(payload, tmp_path / "h.json")
    _, trace = pipe.prepare(input_file=path)
    assert trace["route"] == pipe.TEXT_PASSTHROUGH
    assert trace["sensory_inference"] is False
    assert trace["source_sha256"] == hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def test_identity_failure_stops_before_inference(tmp_path: Path) -> None:
    path = replay.write_replay_payload("original payload", tmp_path / "h.json")
    envelope = json.dumps({"payload": {"content": "tampered payload"}})
    report = replay.verify_replay_identity(
        original_payload="original payload", replay_path=path, envelope=envelope
    )
    assert report["identical"] is False
    with pytest.raises(ValueError, match="must not.*proceed to provider inference"):
        replay.assert_replay_valid(report)


def test_write_replay_payload_does_not_normalise(tmp_path: Path) -> None:
    quirky = '{"b":1,"a":2}   \n\n'
    path = replay.write_replay_payload(quirky, tmp_path / "q.json")
    assert path.read_text(encoding="utf-8") == quirky


# --- replay: provenance ------------------------------------------------------


def test_provenance_carries_every_required_field() -> None:
    prov = replay.build_provenance(
        replayed_from="A",
        origin_run_id="20260828T163256Z-4082212669",
        original_image_sha256="9fffa97ac76f34c6",
        sensory_model=v2.SENSORY_PRIMARY,
        payload="payload",
    )
    for field in v2.REPLAY_PROVENANCE_FIELDS:
        assert prov[field], field
    replay.validate_provenance(prov)
    assert prov["is_native_text_condition"] is False
    assert prov["handoff_payload_sha256"] == hashlib.sha256(b"payload").hexdigest()


def test_missing_provenance_is_rejected() -> None:
    with pytest.raises(ValueError, match="missing provenance fields"):
        replay.validate_provenance({"replayed_from": "A"})


def test_replay_may_never_be_labelled_a_native_text_condition() -> None:
    prov = replay.build_provenance(
        replayed_from="A", origin_run_id="r", original_image_sha256="s",
        sensory_model="m", payload="p",
    )
    prov["is_native_text_condition"] = True
    with pytest.raises(ValueError, match="never be recorded as a native text condition"):
        replay.validate_provenance(prov)
    assert v2.specification()["replay"]["is_native_text_condition"] is False


# --- v1 / v1.1 and frozen material unchanged --------------------------------


def test_v1_artifact_unchanged() -> None:
    digest = hashlib.sha256((ROOT / "benchmark" / "screening.json").read_bytes()).hexdigest()
    assert digest == V1_SHA


def test_v1_1_artifact_present_and_links_to_v1() -> None:
    art = json.loads((ROOT / "benchmark" / "screening-v1.1.json").read_text(encoding="utf-8"))
    assert art["amendment"] == "v1.1"
    assert art["linkage"]["original_artifact_sha256"] == V1_SHA


def test_v2_does_not_touch_stimuli_or_scorer() -> None:
    suite = _load("suite_v2", SCRIPTS / "make_benchmark_suite.py")
    pinned = json.loads((ROOT / "benchmark" / "items.json").read_text(encoding="utf-8"))
    by_id = {i["item_id"]: i["image_sha256"] for i in pinned["items"]}
    for item in suite.build_suite()["items"]:
        assert item["image_sha256"] == by_id[item["item_id"]]
    scorer_src = (SCRIPTS / "score_handoff.py").read_text(encoding="utf-8")
    for token in ("qwen", "gemma", "protocol_v2", "replay"):
        assert token not in scorer_src.lower(), token


def test_sensory_boundary_unchanged_by_v2() -> None:
    src = (ROOT / "ingress" / "openrouter_image.py").read_text(encoding="utf-8")
    assert "AlphaClaw's perception boundary" in src
    assert '"response_format": {"type": "json_object"}' in src
    for token in ("qwen", "gemma", "protocol_v2"):
        assert token not in src.lower(), token


def test_v1_selection_rule_does_not_select_among_v2_conditions() -> None:
    note = v2.specification()["models"]["note"]
    assert "not tournament candidates" in note
    assert "do not select among v2 conditions" in note


def test_chronology_is_documented() -> None:
    chron = v2.specification()["chronology"]
    assert set(chron) >= {"v1", "v1.1", "v2", "preregistered_before"}
    assert "availability recovery only" in chron["v1.1"]
