"""Protocol Amendment v2.2 -- B2 composition replay.

Offline. No network, no container, no provider call, no sensory runner.

The central property: composing the frozen human instruction with the frozen B1
repeat-0 handoff produces byte-identically the payload -- and the Alpha envelope -- that
the live image+text route would produce if handed that same handoff.
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
INGRESS = ROOT / "ingress"
for extra in (SCRIPTS, INGRESS, ROOT / "controller"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import pipe


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


a22 = _load("amendment_v2_2_mod", SCRIPTS / "amendment_v2_2.py")
a21 = _load("amendment_v2_1_a22", SCRIPTS / "amendment_v2_1.py")
v2 = _load("protocol_v2_a22", SCRIPTS / "protocol_v2.py")
episode_contract = _load("episode_contract_a22", ROOT / "controller" / "episode_contract.py")
suite = _load("make_benchmark_suite_a22", SCRIPTS / "make_benchmark_suite.py")

B1_ARTIFACT = ROOT / "benchmark" / "screening-v2-B1.json"
B1_SHA = "847828d469d60269a289f5183d07a69c6afc4c123ef1ad51346490e778e0ab14"


@pytest.fixture(scope="module")
def stimuli(tmp_path_factory):
    """Regenerate the deterministic stimuli locally so the proof never skips."""
    out = tmp_path_factory.mktemp("alphaclaw-suite")
    suite.build_suite(out)
    return out


@pytest.fixture(scope="module")
def items():
    raw = json.loads((ROOT / "benchmark" / "items.json").read_text(encoding="utf-8"))
    return {i["item_id"]: i for i in raw["items"]}


@pytest.fixture(scope="module")
def sources():
    """The three frozen B1 repeat-0 replay sources, selected by the v2.1 rule."""
    b1 = json.loads(B1_ARTIFACT.read_text(encoding="utf-8"))
    plan = a21.build_b2_plan(b1["calls"], v2.B2_ITEMS)
    assert plan["unavailable"] == []
    return {s["item_id"]: s for s in plan["selected"]}


class _ExplodingRunner:
    """Any call to this is a sensory call, which the amendment forbids."""

    def __init__(self):
        self.calls = 0

    def __call__(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError("composition replay must never invoke a sensory runner")


# --- frozen constituents ------------------------------------------------------


def test_b1_artifact_unchanged() -> None:
    assert hashlib.sha256(B1_ARTIFACT.read_bytes()).hexdigest() == B1_SHA


def test_raw_handoff_digests_remain_exact(sources) -> None:
    for item_id, expected in a22.FROZEN_HANDOFF_SHA256.items():
        payload = sources[item_id]["handoff_payload"]
        assert a22.sha256_text(payload) == expected
        assert sources[item_id]["handoff_payload_sha256"] == expected
        assert sources[item_id]["repeat_index"] == a21.B2_REPLAY_REPEAT_INDEX


def test_human_text_digests_match_the_frozen_benchmark_items(items) -> None:
    for item_id, expected in a22.FROZEN_HUMAN_TEXT_SHA256.items():
        assert a22.sha256_text(items[item_id]["rule_text"]) == expected


def test_frozen_text_matches_what_condition_a_actually_delivered(items) -> None:
    """distractor_selection's text_sha256 was recorded in a Condition A manifest."""
    condition_a = json.loads(
        (ROOT / "benchmark" / "benchmark-v2-A.json").read_text(encoding="utf-8"))
    run = next(r for r in condition_a["runs"]
               if r["item_id"] == "distractor_selection" and r["condition"] == "image_text")
    assert (run["manifest"]["ingress"]["text_sha256"]
            == a22.FROZEN_HUMAN_TEXT_SHA256["distractor_selection"])


# --- the mechanical equivalence proof -----------------------------------------


@pytest.mark.parametrize("item_id", ["ocr_count", "distractor_selection",
                                     "multi_fact_composition"])
def test_composed_payload_equals_live_route_output(item_id, items, sources,
                                                  stimuli) -> None:
    """same text + same handoff -> same combined payload -> same Alpha envelope."""
    image = stimuli / items[item_id]["image_filename"]
    assert image.exists(), "deterministic stimulus must be regenerable"
    assert (hashlib.sha256(image.read_bytes()).hexdigest()
            == items[item_id]["image_sha256"]), "stimulus digest drifted"

    handoff_payload = sources[item_id]["handoff_payload"]
    text = items[item_id]["rule_text"]
    handoff_object = json.loads(handoff_payload)

    # 1. the LIVE combined route, with a fake runner returning that exact handoff
    def fake_runner(path, model, api_key):
        return handoff_object, {"model": "fake", "input_tokens": 0, "output_tokens": 0}

    live_payload, live_trace = pipe.route_image_with_text(
        image, text, model="fake", api_key="fake-key", image_runner=fake_runner)

    # 2. the REPLAY composition, from frozen constituents only
    replay_payload = a22.compose_replay_payload(
        human_text=text, handoff_payload=handoff_payload)

    # 3. combined payload bytes identical
    assert replay_payload == live_payload
    assert a22.sha256_text(replay_payload) == a22.sha256_text(live_payload)

    # 4. Alpha envelope bytes identical under the same episode contract
    contract = episode_contract.EpisodeContract(max_reasoning_loops=1).handoff()
    live_envelope = pipe.alpha_prepend.prepend(live_payload, episode_contract=contract)
    replay_envelope = pipe.alpha_prepend.prepend(replay_payload, episode_contract=contract)
    assert replay_envelope == live_envelope
    assert json.loads(replay_envelope)["payload"]["content"] == live_payload
    assert live_trace["sensory_inference"] is True  # the live route did perceive


def test_composition_uses_the_same_serialisation_as_the_live_route() -> None:
    source = (INGRESS / "pipe.py").read_text(encoding="utf-8")
    combined = source.split("def route_image_with_text", 1)[1]
    assert '"human_text": text, "sensory_handoff": handoff' in combined
    assert "ensure_ascii=False" in combined
    assert "sort_keys=True" in combined
    assert a22.COMPOSITION_KWARGS == {"ensure_ascii": False, "sort_keys": True}


# --- the composer performs no perception --------------------------------------


def test_composer_makes_zero_sensory_calls(items, sources) -> None:
    runner = _ExplodingRunner()
    payload = a22.compose_replay_payload(
        human_text=items["ocr_count"]["rule_text"],
        handoff_payload=sources["ocr_count"]["handoff_payload"])
    assert runner.calls == 0
    assert json.loads(payload)["sensory_handoff"]


def test_composer_source_has_no_provider_or_image_path() -> None:
    source = (SCRIPTS / "amendment_v2_2.py").read_text(encoding="utf-8").lower()
    for token in ("requests", "urllib", "http", "socket", "openrouter",
                  "image_runner", "api_key", "subprocess", "docker"):
        assert token not in source, token


# --- tamper detection ---------------------------------------------------------


def test_one_changed_byte_of_handoff_fails_validation(items, sources) -> None:
    tampered = sources["ocr_count"]["handoff_payload"].replace("square", "squarE", 1)
    assert tampered != sources["ocr_count"]["handoff_payload"]
    report = a22.verify_constituents(
        item_id="ocr_count", human_text=items["ocr_count"]["rule_text"],
        handoff_payload=tampered)
    assert report["handoff_matches"] is False
    assert report["valid"] is False
    with pytest.raises(a22.CompositionInvalid, match="must not proceed to provider inference"):
        a22.assert_constituents_valid(report)


def test_changed_task_text_fails_validation(items, sources) -> None:
    report = a22.verify_constituents(
        item_id="ocr_count",
        human_text=items["ocr_count"]["rule_text"] + " Please.",
        handoff_payload=sources["ocr_count"]["handoff_payload"])
    assert report["human_text_matches"] is False
    assert report["valid"] is False
    with pytest.raises(a22.CompositionInvalid):
        a22.assert_constituents_valid(report)


def test_unmodified_constituents_validate(items, sources) -> None:
    for item_id in v2.B2_ITEMS:
        report = a22.verify_constituents(
            item_id=item_id, human_text=items[item_id]["rule_text"],
            handoff_payload=sources[item_id]["handoff_payload"])
        assert report["valid"] is True
        a22.assert_constituents_valid(report)


def test_no_fallback_to_repeat_one(sources) -> None:
    b1 = json.loads(B1_ARTIFACT.read_text(encoding="utf-8"))
    calls = [c for c in b1["calls"] if c["item_id"] == "ocr_count"
             and c["repeat_index"] == 1]
    assert calls, "repeat 1 exists in B1"
    for item_id in v2.B2_ITEMS:
        assert sources[item_id]["repeat_index"] == 0
    with pytest.raises(a21.B2SourceUnavailable):
        a21.select_b2_source(calls, "ocr_count")  # repeat 1 alone is not a source


# --- provenance ---------------------------------------------------------------


def test_provenance_carries_every_required_field(items, sources) -> None:
    item_id = "multi_fact_composition"
    text = items[item_id]["rule_text"]
    handoff_payload = sources[item_id]["handoff_payload"]
    composed = a22.compose_replay_payload(human_text=text, handoff_payload=handoff_payload)
    provenance = a22.build_provenance(
        item_id=item_id, replayed_from="B1", origin_run_id="B1",
        original_image_sha256=items[item_id]["image_sha256"],
        sensory_model=sources[item_id]["sensory_model"],
        human_text=text, handoff_payload=handoff_payload, composed_payload=composed)
    a22.validate_provenance(provenance)
    for field in a22.REQUIRED_PROVENANCE_FIELDS:
        assert provenance[field]
    assert provenance["handoff_payload_sha256"] == a22.FROZEN_HANDOFF_SHA256[item_id]
    assert provenance["human_text_sha256"] == a22.FROZEN_HUMAN_TEXT_SHA256[item_id]
    assert provenance["composed_payload_sha256"] == a22.sha256_text(composed)
    assert provenance["sensory_model"] == v2.SENSORY_ALTERNATE


def test_replay_remains_explicitly_non_native_text(items, sources) -> None:
    provenance = a22.build_provenance(
        item_id="ocr_count", replayed_from="B1", origin_run_id="B1",
        original_image_sha256=items["ocr_count"]["image_sha256"],
        sensory_model="qwen/qwen3.7-flash",
        human_text=items["ocr_count"]["rule_text"],
        handoff_payload=sources["ocr_count"]["handoff_payload"],
        composed_payload="x")
    assert provenance["is_native_text_condition"] is False
    assert provenance["sensory_inference"] is False

    provenance["is_native_text_condition"] = True
    with pytest.raises(a22.CompositionInvalid, match="native text condition"):
        a22.validate_provenance(provenance)

    provenance["is_native_text_condition"] = False
    provenance["sensory_inference"] = True
    with pytest.raises(a22.CompositionInvalid, match="perception"):
        a22.validate_provenance(provenance)


# --- scope --------------------------------------------------------------------


def test_amendment_forbids_the_raw_handoff_equality_claim() -> None:
    spec = a22.specification()
    assert spec["raw_handoff_equality_claim_prohibited"] is True
    assert spec["sensory_calls"] == 0
    assert spec["live_ingress_changed"] is False
    assert "does NOT equal the raw B1 handoff" in spec["byte_identity_invariant"]


def test_nothing_else_changed() -> None:
    assert v2.B2_ITEMS == ("ocr_count", "distractor_selection", "multi_fact_composition")
    assert v2.SENSORY_ALTERNATE == "qwen/qwen3.7-flash"
    assert v2.RESIDENT_PRIMARY_MODEL == "minimax/minimax-m3"
    assert v2.ASICLOUD_MAX_CALLS == 42
    assert a21.B2_REPLAY_REPEAT_INDEX == 0
    v2.validate()


def test_scorer_and_boundary_untouched_by_this_amendment() -> None:
    scorer = (SCRIPTS / "score_handoff.py").read_text(encoding="utf-8").lower()
    boundary = (INGRESS / "openrouter_image.py").read_text(encoding="utf-8").lower()
    for token in ("amendment", "compose_replay", "human_text_sha256"):
        assert token not in scorer, token
        assert token not in boundary, token


def test_live_ingress_still_refuses_a_non_image_combined_input(tmp_path) -> None:
    """Normal ingress behaviour is unchanged: no silent JSON multimodal replay."""
    payload = tmp_path / "handoff.json"
    payload.write_text('{"observation": {"literal": []}}', encoding="utf-8")
    with pytest.raises(ValueError, match="requires an image"):
        pipe.route_image_with_text(payload, "some text", model="m", api_key="k")


def test_no_b2_result_artifact_exists_yet() -> None:
    assert not (ROOT / "benchmark" / "benchmark-v2-B2.json").exists()
