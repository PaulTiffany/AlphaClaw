"""Protocol v2 Condition A -- frozen results and derived decomposition.

Offline. No network, no container, no provider call. These tests pin the frozen
artifact and prove that the DERIVED failure decomposition matches its already-declared
semantics without ever altering raw receipts, exact-match verdicts or frozen-scorer
verdicts.
"""

from __future__ import annotations

import copy
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


analyze = _load("analyze_condition_a_mod", SCRIPTS / "analyze_condition_a.py")
scorer = _load("score_handoff_condA", SCRIPTS / "score_handoff.py")

ARTIFACT = ROOT / "benchmark" / "benchmark-v2-A.json"
ARTIFACT_SHA = "644f36e406df5520f54e6bcb706b891e9dd1ff9094c6c0d59cfb305e68be65ea"
B1_SHA = "847828d469d60269a289f5183d07a69c6afc4c123ef1ad51346490e778e0ab14"

FAILED_RUN = ("distractor_selection", "image_text")


@pytest.fixture(scope="module")
def data():
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def runs(data):
    return data["runs"]


def _run(runs, item_id, condition):
    return next(r for r in runs
                if r["item_id"] == item_id and r["condition"] == condition)


# --- synthetic classifier semantics ------------------------------------------


def _synthetic(condition, *, verdicts, exact=None, response="X",
               expected="X", reason="responded", episode_calls=1):
    return {
        "item_id": "synthetic", "condition": condition,
        "expected_answer": expected, "response": response, "exact_match": exact,
        "controller_error": None,
        "sensory_score": {"schema_conformant": True, "verdicts": verdicts,
                          "correct": sum(1 for v in verdicts if v["verdict"] == "correct"),
                          "expected": len(verdicts)},
        "manifest": {
            "termination_reason": reason,
            "usage_by_phase": {"boot": {"calls": 1},
                               "episode": {"calls": episode_calls}},
            "provider_gateway": {"fatal_error": None},
        },
    }


def test_unknown_verdict_is_not_a_sensory_failure() -> None:
    """The decisive property: undecidable is not wrong."""
    run = _synthetic("image_only", verdicts=[{"verdict": "correct"},
                                             {"verdict": "unknown"}])
    assert analyze.sensory_failed(run) is False
    assert analyze.classify(run) is analyze.PASSED


def test_incorrect_verdict_is_a_sensory_failure() -> None:
    run = _synthetic("image_only", verdicts=[{"verdict": "correct"},
                                             {"verdict": "incorrect"}])
    assert analyze.sensory_failed(run) is True
    assert analyze.classify(run) == analyze.SENSORY


def test_non_conformant_schema_is_a_sensory_failure() -> None:
    run = _synthetic("image_only", verdicts=[])
    run["sensory_score"]["schema_conformant"] = False
    assert analyze.classify(run) == analyze.SENSORY


def test_exact_match_pass_has_class_passed() -> None:
    run = _synthetic("image_text", verdicts=[{"verdict": "correct"}], exact=True)
    assert analyze.classify(run) is analyze.PASSED
    assert analyze.label(analyze.classify(run)) == "passed"


def test_exact_match_pass_stays_passed_even_with_an_unknown_fact() -> None:
    """Bug 2 regression: a passing run must never carry a failure class."""
    run = _synthetic("image_text", verdicts=[{"verdict": "correct"},
                                             {"verdict": "unknown"}], exact=True)
    assert analyze.classify(run) is analyze.PASSED


def test_correct_handoff_with_no_final_emission_is_output_contract() -> None:
    """Sensing sound, episode turn spent, nothing valid on the channel."""
    run = _synthetic("image_text", verdicts=[{"verdict": "correct"}], exact=False,
                     response=None, expected="RED", reason="timeout")
    assert analyze.sensory_failed(run) is False
    assert analyze.classify(run) == analyze.OUTPUT_CONTRACT


def test_normalisation_equivalent_answer_is_still_output_contract_not_a_pass() -> None:
    run = _synthetic("text_control", verdicts=[], exact=False,
                     response="K7 3", expected="K73")
    assert analyze.classify(run) == analyze.OUTPUT_CONTRACT


def test_wrong_answer_with_sound_sensing_is_reasoning_composition() -> None:
    run = _synthetic("image_text", verdicts=[{"verdict": "correct"}], exact=False,
                     response="BLUE", expected="RED")
    assert analyze.classify(run) == analyze.REASONING


def test_broken_bound_is_infrastructure_not_a_task_failure() -> None:
    run = _synthetic("text_control", verdicts=[], exact=False, episode_calls=2)
    assert analyze.classify(run) == analyze.INFRASTRUCTURE


def test_upstream_error_is_provider_availability() -> None:
    run = _synthetic("text_control", verdicts=[], exact=False)
    run["controller_error"] = "provider returned 503 Service Unavailable"
    assert analyze.classify(run) == analyze.PROVIDER_AVAILABILITY


# --- the classifier must never mutate evidence -------------------------------


def test_analysis_never_mutates_raw_results_or_scorer_verdicts(data) -> None:
    before = copy.deepcopy(data)
    runs = data["runs"]
    analyze.decompose(runs)
    analyze.image_only_aggregate(runs)
    analyze.conditional_exact_match(runs)
    analyze.usage_totals(runs, "boot")
    analyze.usage_totals(runs, "episode")
    analyze.sensory_totals(runs)
    analyze.bounds_respected(runs)
    analyze.render(data)
    for run in runs:
        analyze.classify(run)
    assert data == before


def test_analyzer_module_performs_no_inference_and_no_container_work() -> None:
    source = (SCRIPTS / "analyze_condition_a.py").read_text(encoding="utf-8").lower()
    for token in ("requests", "urllib", "http", "subprocess", "docker",
                  "openrouter_image", "api_key"):
        assert token not in source, token


def test_analyzer_does_not_write_the_artifact() -> None:
    """No write path at all: read-only by construction, not merely by intent."""
    import re as _re
    source = (SCRIPTS / "analyze_condition_a.py").read_text(encoding="utf-8")
    for token in ("write_text", "write_bytes", "unlink", "os.remove", "shutil"):
        assert token not in source, token
    # json.dumps (serialise to string) is fine; json.dump (write to a file) is not.
    assert _re.search(r"json\.dump\s*\(", source) is None
    assert _re.search(r"open\s*\([^)]*[\"']w", source) is None


# --- the real frozen artifact -------------------------------------------------


def test_artifact_digest_is_frozen() -> None:
    assert hashlib.sha256(ARTIFACT.read_bytes()).hexdigest() == ARTIFACT_SHA


def test_b1_artifact_still_unchanged() -> None:
    b1 = ROOT / "benchmark" / "screening-v2-B1.json"
    assert hashlib.sha256(b1.read_bytes()).hexdigest() == B1_SHA


def test_eighteen_runs_across_the_matched_three_conditions(runs) -> None:
    assert len(runs) == 18
    for condition in analyze.CONDITIONS:
        assert sum(1 for r in runs if r["condition"] == condition) == 6


def test_stored_failure_classes_match_derivation(data) -> None:
    """The committed decomposition is reproducible from the committed evidence."""
    assert analyze.verify_stored_classes(data) == []


def test_headline_results(runs) -> None:
    assert analyze.exact_match_rate(runs, "text_control") == (6, 6)
    assert analyze.exact_match_rate(runs, "image_text") == (5, 6)
    assert analyze.conditional_exact_match(runs) == (5, 6)

    aggregate = analyze.image_only_aggregate(runs)
    assert aggregate["schema_compliance_rate"] == 1.0
    assert aggregate["atomic_fact_accuracy"] == 1.0
    assert aggregate["atomic_fact_yield"] == pytest.approx(20 / 21)
    assert aggregate["scoring_coverage"] == pytest.approx(20 / 21)


def test_decomposition_is_exactly_one_output_contract_failure(runs) -> None:
    assert analyze.decompose(runs) == {
        "sensory": 0, "reasoning_composition": 0, "output_contract": 1,
        "infrastructure": 0, "provider_availability": 0, "passed": 17,
    }


def test_every_run_obeyed_one_boot_and_one_episode(runs) -> None:
    assert analyze.bounds_respected(runs) == []
    assert analyze.usage_totals(runs, "boot")["calls"] == 18
    assert analyze.usage_totals(runs, "episode")["calls"] == 18


def test_protocol_v2_caps_respected(runs) -> None:
    v2 = _load("protocol_v2_condA", SCRIPTS / "protocol_v2.py")
    boot = analyze.usage_totals(runs, "boot")
    episode = analyze.usage_totals(runs, "episode")
    assert boot["calls"] + episode["calls"] == 36 <= v2.ASICLOUD_MAX_CALLS
    assert (boot["input_tokens"] + episode["input_tokens"]) <= v2.ASICLOUD_MAX_INPUT_TOKENS
    assert (boot["output_tokens"] + episode["output_tokens"]) <= v2.ASICLOUD_MAX_OUTPUT_TOKENS


def test_sensory_model_was_the_preregistered_one_on_every_call(runs) -> None:
    v2 = _load("protocol_v2_condA_b", SCRIPTS / "protocol_v2.py")
    totals = analyze.sensory_totals(runs)
    assert totals["calls"] == 12
    assert totals["requested_models"] == [v2.SENSORY_PRIMARY]
    assert totals["resolved_models"] == [v2.SENSORY_PRIMARY]
    assert v2.SENSORY_PRIMARY not in v2.FORBIDDEN_MODELS


def test_resident_model_was_the_preregistered_one(data) -> None:
    v2 = _load("protocol_v2_condA_c", SCRIPTS / "protocol_v2.py")
    assert data["resident_provider"] == v2.RESIDENT_PRIMARY_PROVIDER
    assert data["resident_model"] == v2.RESIDENT_PRIMARY_MODEL


# --- the single failure, preserved exactly ------------------------------------


def test_the_failed_run_is_preserved_as_an_output_contract_failure(runs) -> None:
    run = _run(runs, *FAILED_RUN)
    assert run["expected_answer"] == "RED"
    assert run["exact_match"] is False
    assert run["response"] is None
    assert run["failure_class"] == analyze.OUTPUT_CONTRACT
    assert run["manifest"]["status"] == "terminated_without_response"
    assert run["manifest"]["termination_reason"] == "timeout"
    assert run["manifest"]["response_present"] is False


def test_the_failed_run_had_a_fully_correct_sensory_handoff(runs) -> None:
    """Sensing was not the broken link -- that distinction is preserved."""
    scored = _run(runs, *FAILED_RUN)["sensory_score"]
    assert scored["schema_conformant"] is True
    assert scored["correct"] == scored["expected"] == 4
    assert not any(v["verdict"] != "correct" for v in scored["verdicts"])


def test_the_failed_run_is_not_rounded_up_to_a_pass(runs) -> None:
    """The answer is recoverable from logs. That must not make it a pass."""
    run = _run(runs, *FAILED_RUN)
    assert analyze.classify(run) != analyze.PASSED
    assert analyze.label(analyze.classify(run)) == "output_contract"
    assert run["exact_match"] is not True


# --- lifecycle observation ----------------------------------------------------


def test_lifecycle_observation_is_recorded_and_not_a_bound_violation(data) -> None:
    observation = data["lifecycle_observations"][0]
    assert observation["run_id"] == "20260828T211157Z-f2ed870c3f"
    assert observation["provider_calls_during_idle_interval"] == 0
    assert observation["boot_calls"] == 1
    assert observation["episode_calls"] == 1
    assert observation["protocol_violation"] is False
    assert observation["violation_checks"]["extra_provider_call"] is False
    assert observation["violation_checks"]["corrupted_receipt_or_accounting"] is False
    assert observation["violation_checks"]["failed_teardown_affecting_later_runs"] is False


def test_lifecycle_chronology_correction_is_preserved(data) -> None:
    """The ticks followed the failed emission, not a successful response."""
    text = data["lifecycle_observations"][0]["correction_to_initial_framing"]
    assert "did NOT follow a completed response" in text


# --- frozen scorer observation ------------------------------------------------


def test_relation_lexicon_was_not_broadened_for_condition_a() -> None:
    assert "is located to the left of" not in scorer.LEFT_OF_FORMS
    assert "is located to the right of" not in scorer.RIGHT_OF_FORMS


def test_spatial_relation_verdicts_remain_unknown(runs) -> None:
    for condition in ("image_only", "image_text"):
        verdicts = _run(runs, "spatial_relation", condition)["sensory_score"]["verdicts"]
        relation = [v for v in verdicts if v["fact"]["type"] == "relation"]
        assert [v["verdict"] for v in relation] == ["unknown"]


def test_scorer_limitation_recorded_as_cross_model_coverage_gap(data) -> None:
    observation = data["frozen_scorer_observation"]
    assert observation["lexicon_broadened_in_v2"] is False
    assert observation["not"] == "a corrected sensory result"
    assert "coverage limitation" in observation["finding"]


# --- derived-analysis chronology ----------------------------------------------


def test_classifier_correction_chronology_is_documented(data) -> None:
    derived = data["derived_analysis"]
    descriptions = " ".join(c["description"].lower()
                            for c in derived["corrections_after_the_experimental_runs"])
    assert "misclassified as sensory failures" in descriptions
    assert "exact-match criterion was still being assigned a failure class" in descriptions
    assert derived["reruns_or_additional_inference"].startswith("none")
    unchanged = " ".join(derived["unchanged_by_the_corrections"]).lower()
    assert "raw provider receipts" in unchanged
    assert "exact-match verdicts" in unchanged
    assert "frozen sensory-scorer verdicts" in unchanged


def test_condition_a_artifact_contains_only_condition_a_runs(data, runs) -> None:
    """B2 has since run, so the invariant is that A's artifact stayed pure -- every run
    is a Condition A run on the dots sensory model. The B1/Qwen mention in the scorer
    observation is a cross-model citation, not a result."""
    assert data["condition_id"] == "A"
    v2 = _load("protocol_v2_condA_d", SCRIPTS / "protocol_v2.py")
    assert analyze.sensory_totals(runs)["resolved_models"] == [v2.SENSORY_PRIMARY]
    assert all(r["sensory_model_resolved"] != v2.SENSORY_ALTERNATE
               for r in runs if r.get("sensory_model_resolved"))
    assert all(r["condition"] in analyze.CONDITIONS for r in runs)


def test_condition_c_still_not_run() -> None:
    assert not (ROOT / "benchmark" / "benchmark-v2-C.json").exists()
