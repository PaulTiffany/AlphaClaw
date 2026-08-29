"""Protocol v3-A results -- frozen evidence and derived comparisons.

Offline. No network, no container, no provider call, no judge.

The point of these tests is not that V3-A found an effect. It did not. They pin the raw
evidence, prove the derived comparisons are recomputable, and prove the artifact carries
its own non-attribution and variance limits.
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

import analyze_condition_a as v2_analyze
import analyze_v3a as analyze
import representation_v3


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


p3 = _load("protocol_v3_results", SCRIPTS / "protocol_v3.py")

ARTIFACT = ROOT / "benchmark" / "benchmark-v3-A.json"
ARTIFACT_SHA = "98ab018e8f8dcb2de405e21a800239583968c7832b1a8665cd31686072ad6552"
A_SHA = "644f36e406df5520f54e6bcb706b891e9dd1ff9094c6c0d59cfb305e68be65ea"


@pytest.fixture(scope="module")
def data():
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def runs(data):
    return data["runs"]


# --- frozen evidence ----------------------------------------------------------


def test_artifact_digest_is_frozen() -> None:
    assert hashlib.sha256(ARTIFACT.read_bytes()).hexdigest() == ARTIFACT_SHA


def test_v2_evidence_untouched() -> None:
    assert hashlib.sha256(
        (ROOT / "benchmark" / "benchmark-v2-A.json").read_bytes()).hexdigest() == A_SHA


def test_eighteen_runs_matching_the_preregistered_matrix(data, runs) -> None:
    assert data["section"] == "V3-A"
    assert data["attempted_runs"] == 18
    assert len(runs) == 18
    planned = {(r["case_id"], r["representation"], r["turn_budget"])
               for r in p3.v3a_runs()}
    executed = {(r["case_id"], r["representation"], r["turn_budget"]) for r in runs}
    assert executed == planned


def test_every_run_passed_preflight_before_its_call(runs) -> None:
    for run in runs:
        assert run["preflight_passed"] is True, run["case_id"]
        assert run["provider_call_made"] is True
        assert all(run["preflight_checks"].values())


def test_r1_was_byte_identical_to_the_frozen_v2_payload(runs) -> None:
    for run in runs:
        if run["representation"] == "R1_full_symbolic":
            assert run["preflight_checks"]["r1_byte_identical_to_frozen_v2"] is True


def test_delivered_envelope_carried_the_intended_representation(runs) -> None:
    for run in runs:
        assert run["envelope_payload_sha256"] == run["representation_sha256"]
        assert run["envelope_matches_payload"] is True


# --- no sensory, no fallback, no retry ----------------------------------------


def test_zero_sensory_calls(data, runs) -> None:
    assert data["sensory_calls"] == 0
    assert analyze.sensory_calls(runs) == 0
    for run in runs:
        ingress = run["manifest"]["ingress"]
        assert ingress["sensory_inference"] is False
        assert "sensory_trace" not in ingress


def test_only_the_preregistered_models_were_used(runs) -> None:
    for run in runs:
        model = run["requested_model"]
        assert model in ("minimax/minimax-m3", "google/gemma-4-26b-a4b-it")
        assert run["manifest"]["requested_model"] == model
        for receipt in run["provider_usage"]:
            assert receipt["model"] == model


def test_no_fallback_model_anywhere(data) -> None:
    blob = json.dumps(data)
    for forbidden in ("z-ai/glm-5.2", "openrouter/free", "qwen/qwen3.7-flash"):
        assert forbidden not in blob, forbidden


def test_one_run_per_cell_no_retries(runs) -> None:
    keys = [(r["case_id"], r["representation"], r["turn_budget"]) for r in runs]
    assert len(keys) == len(set(keys))


# --- budgets ------------------------------------------------------------------


def test_within_the_preregistered_v3a_budget(runs) -> None:
    usage = analyze.usage(runs)
    assert usage["ASICloud"]["calls"] == 19 <= p3.V3A_ASICLOUD_MAX_CALLS
    assert usage["OpenRouter"]["calls"] == 24 <= p3.V3A_OPENROUTER_MAX_CALLS
    total_cost = sum(block["cost"] for block in usage.values())
    assert total_cost <= p3.V3A_MAX_COST_USD


def test_episode_calls_never_exceed_the_turn_budget(runs) -> None:
    for run in runs:
        episode = run["manifest"]["usage_by_phase"]["episode"]["calls"]
        assert 1 <= episode <= run["turn_budget"], run["case_id"]
        assert run["manifest"]["usage_by_phase"]["boot"]["calls"] == 1


def test_v2_asicloud_ledger_untouched() -> None:
    v2 = json.loads(
        (ROOT / "benchmark" / "benchmark-v2-A.json").read_text(encoding="utf-8"))
    assert v2["resident_provider"] == "asicloud"
    b2 = json.loads(
        (ROOT / "benchmark" / "benchmark-v2-B2.json").read_text(encoding="utf-8"))
    assert b2["condition_id"] == "B2"


# --- the turn-aware classifier ------------------------------------------------


def test_two_turn_runs_are_not_mislabelled_infrastructure(runs, data) -> None:
    """The decisive correction: exit 3 on a spent two-turn budget is not a harness fault."""
    two_turn = [r for r in runs if r["turn_budget"] == 2]
    assert len(two_turn) == 9
    assert all(analyze.classify(r) != analyze.INFRASTRUCTURE for r in two_turn)
    assert data["failure_decomposition"]["infrastructure"] == 0


def test_v2_classifier_would_have_mislabelled_them(runs) -> None:
    """Shows exactly why a v3-specific classifier was needed, without changing v2."""
    two_turn_multi = [r for r in runs if r["turn_budget"] == 2
                      and r["manifest"]["usage_by_phase"]["episode"]["calls"] == 2]
    assert two_turn_multi
    for run in two_turn_multi:
        assert v2_analyze.classify(run) == v2_analyze.INFRASTRUCTURE
        assert analyze.classify(run) != v2_analyze.INFRASTRUCTURE


def test_v2_classifier_source_unchanged() -> None:
    source = (SCRIPTS / "analyze_condition_a.py").read_text(encoding="utf-8")
    assert "turn_budget" not in source
    assert "episode_calls != 1" in source


def test_stored_classes_match_the_derivation(runs) -> None:
    for run in runs:
        assert run["failure_class"] == analyze.classify(run), run["case_id"]


def test_decomposition_is_reproducible(data, runs) -> None:
    assert analyze.decompose(runs) == data["failure_decomposition"]
    assert data["failure_decomposition"]["passed"] == 7
    assert data["failure_decomposition"]["reasoning_composition"] == 9
    assert data["failure_decomposition"]["output_contract"] == 2
    assert data["failure_decomposition"]["sensory"] == 0


# --- instruction-position receipts --------------------------------------------


def test_receipts_record_positions_not_salience(runs) -> None:
    for run in runs:
        receipt = run["instruction_position_receipt"]
        assert receipt["salience_score_reported"] is False
        assert receipt["per_segment_tokens_available"] is False
        assert receipt["components"]["alpha_instruction"]["found"] is True


def test_receipts_show_the_prepend_is_operationally_distant(runs) -> None:
    distances = [r["instruction_position_receipt"]
                 ["chars_between_alpha_instruction_and_human_task"] for r in runs]
    assert all(d is not None and d > 1000 for d in distances)


def test_receipts_record_match_mode_and_missing_omega_context(runs) -> None:
    """Envelope-level receipts cannot see stock Omega's prompt; that is recorded, not faked."""
    modes = {r["instruction_position_receipt"]["components"]["symbolic_evidence"]
             ["matched_form"] for r in runs
             if r["instruction_position_receipt"]["components"]["symbolic_evidence"]["found"]}
    assert modes <= {"literal", "json_escaped"}
    assert all(r["instruction_position_receipt"]["omega_context_located"] is False
               for r in runs)


# --- paired comparisons -------------------------------------------------------


def test_representation_pairs_are_recomputable(data, runs) -> None:
    assert analyze.representation_pairs(runs) == data["representation_pairs"]
    assert len(data["representation_pairs"]) == 12


def test_turn_pairs_are_recomputable(data, runs) -> None:
    assert analyze.turn_pairs(runs) == data["turn_pairs"]
    assert len(data["turn_pairs"]) == 9


def test_transitions_occur_in_both_directions(data) -> None:
    """The central negative result: the manipulations do not move outcomes consistently."""
    for pairs in (data["representation_pairs"], data["turn_pairs"]):
        transitions = {p["transition"] for p in pairs}
        assert "PASS -> FAIL" in transitions
        assert "FAIL -> PASS" in transitions


def test_internal_token_without_a_correct_answer_is_preserved(data) -> None:
    rows = data["internal_token_without_correct_answer"]
    assert len(rows) == 2
    for row in rows:
        assert row["case_id"] == "A1"
        assert row["valid_send"] is False
        assert row["failure_class"] == analyze.OUTPUT_CONTRACT


# --- the artifact carries its own limits --------------------------------------


def test_artifact_states_the_variance_limitation(data) -> None:
    limit = data["statistical_limitation"]
    assert limit["repeats_per_cell"] == 1
    assert "BOTH directions" in limit["finding"]
    assert "No representation effect and no scheduling effect is claimed" in \
        limit["consequence"]
    assert "requires repeats" in limit["consequence"]


def test_artifact_carries_the_non_attribution_constraint(data) -> None:
    assert "unless the experiment actually isolates it" in data["attribution_constraint"]
    assert "Alpha -> resident -> stock Omega" in data["attribution_constraint"]


def test_derived_analysis_chronology_is_documented(data) -> None:
    derived = data["derived_analysis"]
    assert "mislabels every two-turn V3-A run" in derived["why_not_the_v2_classifier"]
    assert "untouched" in derived["why_not_the_v2_classifier"]
    assert "not a harness failure" in derived["exit_code_3_meaning"]
    assert derived["answer_leakage_amendment"].startswith("v3.1")


def test_leak_check_amendment_still_applies_to_every_variant(runs) -> None:
    items = {i["item_id"]: i for i in json.loads(
        (ROOT / "benchmark" / "items.json").read_text(encoding="utf-8"))["items"]}
    assert representation_v3.LEAK_CHECK_VERSION == "v3.1-word-boundary"
    for run in runs:
        assert run["preflight_checks"]["no_expected_answer_leakage"] is True
        expected = items[run["item_id"]]["expected_answer"]
        assert not representation_v3.leaks_answer(
            json.dumps(run["transform_manifest"] or {}), expected)


def test_v3b_execution_did_not_contaminate_v3a(data) -> None:
    """V3-B has since run on a different population and model; V3-A stays as frozen."""
    assert data["section"] == "V3-A"
    blob = json.dumps(data)
    for token in ("qwen/qwen3.7-flash", "chain_a", "chain_b", "E1_multimodal_resident"):
        assert token not in blob, token
