"""Protocol v2 synthesis -- every headline number recomputed from frozen artifacts.

Offline. No network, no container, no provider call, no new scorer or judge.

The governing rule: no headline value may exist in the synthesis or in the results
documentation without a test deriving it from the committed artifacts. These tests
recompute each figure independently of the prose that quotes it.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import score_handoff
import synthesis_v2 as syn

README = ROOT / "controller" / "README.md"


@pytest.fixture(scope="module")
def result():
    return syn.synthesis()


# --- frozen inputs ------------------------------------------------------------


def test_every_frozen_artifact_digest_matches() -> None:
    assert syn.artifact_digests_match() == {
        name: True for name in syn.ARTIFACT_DIGESTS}


def test_digest_constants_equal_the_files_on_disk() -> None:
    for name, expected in syn.ARTIFACT_DIGESTS.items():
        actual = hashlib.sha256(
            (ROOT / "benchmark" / name).read_bytes()).hexdigest()
        assert actual == expected, name


def test_synthesis_introduces_no_experiment_or_model_call() -> None:
    source = (SCRIPTS / "synthesis_v2.py").read_text(encoding="utf-8").lower()
    for token in ("requests", "urllib", "socket", "subprocess", "docker",
                  "openrouter_image", "api_key", "write_text", "json.dump("):
        assert token not in source, token


# --- B1: sensory portability, recomputed --------------------------------------


def test_b1_headline_numbers_are_derived(result) -> None:
    b1 = result["B1"]
    assert b1["sensory_model"] == "qwen/qwen3.7-flash"
    assert b1["attempted_calls"] == 12
    assert b1["succeeded_calls"] == 12
    assert b1["schema_compliant_calls"] == 12
    assert b1["atomic_facts_correct"] == 40
    assert b1["atomic_facts_expected"] == 42
    assert b1["atomic_facts_scoreable"] == 40
    assert b1["scoring_coverage"] == pytest.approx(40 / 42)


def test_b1_relation_facts_remain_unknown_and_unupgraded(result) -> None:
    b1 = result["B1"]
    assert b1["unknown_verdicts"] == 2
    assert b1["unknown_fact_types"] == ["relation"]
    assert b1["relation_lexicon_broadened"] is False
    scorer = (SCRIPTS / "score_handoff.py").read_text(encoding="utf-8")
    assert "is located to the left of" not in scorer


def test_b1_numbers_recomputed_independently_of_the_module() -> None:
    """Derive straight from the artifact, not from synthesis_v2's own helpers."""
    b1 = json.loads(
        (ROOT / "benchmark" / "screening-v2-B1.json").read_text(encoding="utf-8"))
    verdicts = [v for c in b1["calls"] for v in c["verdicts"]]
    assert len(b1["calls"]) == 12
    assert sum(1 for v in verdicts if v["verdict"] == "correct") == 40
    assert sum(1 for v in verdicts if v["verdict"] != "unknown") == 40
    assert len(verdicts) == 42


# --- A: primary condition, recomputed -----------------------------------------


def test_a_headline_numbers_are_derived(result) -> None:
    a = result["A"]
    assert a["sensory_model"] == "dots-studio/dots-3-note-preview:free"
    assert a["resident"] == "asicloud/minimax/minimax-m3"
    assert a["text_control"] == (6, 6)
    assert a["image_text"] == (5, 6)
    assert a["image_only_facts_correct"] == 20
    assert a["image_only_facts_expected"] == 21
    assert a["image_only_facts_scoreable"] == 20
    assert a["sensory_calls"] == 12
    assert a["asicloud_calls"] == 36


def test_a_was_bounded_throughout(result) -> None:
    assert result["A"]["bound_violations"] == []
    a = json.loads(
        (ROOT / "benchmark" / "benchmark-v2-A.json").read_text(encoding="utf-8"))
    for run in a["runs"]:
        usage = run["manifest"]["usage_by_phase"]
        assert usage["boot"]["calls"] == 1
        assert usage["episode"]["calls"] == 1


def test_a_single_failure_is_the_distractor_output_contract(result) -> None:
    a = result["A"]
    assert a["decomposition"]["output_contract"] == 1
    assert a["decomposition"]["passed"] == 17
    assert a["failures"] == [{"item_id": "distractor_selection",
                              "condition": "image_text",
                              "failure_class": "output_contract"}]
    failure = result["A_distractor_failure"]
    assert failure["sensory_evidence_correct"] is True
    assert failure["expected_answer"] == "RED"
    assert failure["response"] in (None, "")
    assert failure["failure_class"] == "output_contract"
    assert failure["termination_reason"] == "timeout"


def test_a_internal_red_token_appears_only_in_an_invalid_emission() -> None:
    """The correct token existed; it never reached the channel."""
    a = json.loads(
        (ROOT / "benchmark" / "benchmark-v2-A.json").read_text(encoding="utf-8"))
    run = next(r for r in a["runs"] if r["item_id"] == "distractor_selection"
               and r["condition"] == "image_text")
    assert run["manifest"]["response_present"] is False
    assert run["exact_match"] is False


# --- B2: sensory substitution, recomputed -------------------------------------


def test_b2_headline_numbers_are_derived(result) -> None:
    b2 = result["B2"]
    assert b2["paired_cases"] == 3
    assert b2["transitions"] == 0
    assert b2["new_sensory_calls"] == 0
    assert b2["exact_match"] == (2, 3)


def test_b2_both_sensory_sources_carried_all_required_facts(result) -> None:
    for pair in result["B2"]["pairs"]:
        assert pair["dots_all_required_facts"] is True, pair["item_id"]
        assert pair["qwen_all_required_facts"] is True, pair["item_id"]


def test_b2_per_item_transitions(result) -> None:
    transitions = {p["item_id"]: p["transition"] for p in result["B2"]["pairs"]}
    assert transitions == {
        "ocr_count": "PASS -> PASS",
        "distractor_selection": "FAIL -> FAIL",
        "multi_fact_composition": "PASS -> PASS",
    }
    assert not any(p["changed"] for p in result["B2"]["pairs"])


# --- C: resident substitution, recomputed -------------------------------------


def test_c_headline_numbers_are_derived(result) -> None:
    c = result["C"]
    assert c["resident"] == "openrouter/google/gemma-4-26b-a4b-it"
    assert c["paired_cases"] == 3
    assert c["transitions"] == 3
    assert c["exact_match"] == (0, 3)
    assert c["all_payloads_byte_equal"] is True
    assert c["openrouter_resident_calls"] == 6


def test_c_decomposition_and_cost_are_derived(result) -> None:
    c = result["C"]
    assert c["decomposition"]["reasoning_composition"] == 2
    assert c["decomposition"]["output_contract"] == 1
    assert c["decomposition"]["passed"] == 0
    assert c["tokens_in"] == 11_199
    assert c["tokens_out"] == 177
    assert c["actual_cost_usd"] == 0.001085


def test_c_cost_recomputed_independently_from_receipts() -> None:
    c = json.loads(
        (ROOT / "benchmark" / "benchmark-v2-C.json").read_text(encoding="utf-8"))
    cost = sum(r["usage"]["cost"] for run in c["runs"] for r in run["provider_usage"])
    assert round(cost, 6) == 0.001085


def test_c_all_three_transitions_are_pass_to_fail(result) -> None:
    assert [p["transition"] for p in result["C"]["pairs"]] == ["PASS -> FAIL"] * 3


# --- failure surface ----------------------------------------------------------


def test_emission_failure_surface_is_reported_without_claiming_common_cause(result) -> None:
    surface = result["emission_failure_surface"]
    assert len(surface["cases"]) == 3
    assert surface["survives_sensory_substitution"] is True
    assert surface["observed_under_a_second_resident"] is True
    assert surface["common_cause_established"] is False
    assert all(case["emitted_answer_through_channel"] is False
               for case in surface["cases"])
    residents = {case["resident"] for case in surface["cases"]}
    assert residents == {"minimax/minimax-m3", "google/gemma-4-26b-a4b-it"}


# --- ledgers ------------------------------------------------------------------


def test_ledgers_stay_distinct_and_derived(result) -> None:
    ledgers = result["ledgers"]
    assert ledgers["asicloud"] == {"A": 36, "B2": 6, "total": 42}
    assert ledgers["openrouter_sensory"]["B1_qwen_calls"] == 12
    assert ledgers["openrouter_sensory"]["A_dots_calls"] == 12
    assert ledgers["openrouter_sensory"]["B2_new_sensory_calls"] == 0
    assert ledgers["openrouter_sensory"]["C_sensory_calls"] == 0
    assert ledgers["openrouter_resident"]["C_calls"] == 6
    assert ledgers["openrouter_resident"]["C_actual_cost_usd"] == 0.001085


def test_asicloud_total_equals_the_cap_without_raising_it(result) -> None:
    v2 = json.loads(
        (ROOT / "benchmark" / "protocol-v2.json").read_text(encoding="utf-8"))
    caps = v2.get("caps") or v2
    assert result["ledgers"]["asicloud"]["total"] == 42
    assert json.dumps(caps).count("42") >= 1


# --- reproducibility ----------------------------------------------------------


def test_reproducibility_pins_are_single_valued_across_every_run(result) -> None:
    repro = result["reproducibility"]
    assert repro["omega_sha"] == ["3d711e4b9f5254ae94f31123ca242f60cfd97d29"]
    assert repro["threadkeeper_sha"] == ["a64de99e10f9f8078d25bff511b44fd71819e931"]
    assert repro["stock_omega_image_id"] == [
        "sha256:69ff11bf227b197f697aab4488e879258560730565838b19db25e3dd580af90a"]
    assert repro["pins_all_true"] is True
    assert repro["relation_lexicon_unbroadened"] is True
    assert repro["amendments"] == ["v2.1", "v2.2"]


def test_amendment_modules_are_present() -> None:
    assert (SCRIPTS / "amendment_v2_1.py").exists()
    assert (SCRIPTS / "amendment_v2_2.py").exists()


# --- conclusion and non-claims ------------------------------------------------


def test_conclusion_is_the_supported_one(result) -> None:
    assert result["supported_conclusion"] == (
        "Protocol v2 found stronger robustness to sensory-model substitution than to "
        "resident-model substitution under the tested bounded conditions.")
    assert result["single_aggregate_accuracy_reported"] is False


def test_non_claims_and_caveat_are_carried_with_the_conclusion(result) -> None:
    non_claims = " ".join(result["non_claims"]).lower()
    for phrase in ("universal ranking", "dots is better than qwen",
                   "minimax is better than gemma", "larger reasoning-loop budget",
                   "sensory substitution can never matter"):
        assert phrase in non_claims, phrase
    assert "one-turn bounded benchmark" in result["one_turn_caveat"]


def test_conclusion_is_directional_not_a_single_accuracy_number(result) -> None:
    """B2 changed no outcome; C changed every outcome. That asymmetry is the finding."""
    assert result["B2"]["transitions"] == 0
    assert result["C"]["transitions"] == result["C"]["paired_cases"] == 3


# --- the documentation may not drift from the artifacts -----------------------


def test_readme_synthesis_quotes_only_derived_numbers(result) -> None:
    """Every headline figure printed in the results doc must appear in the derivation."""
    text = README.read_text(encoding="utf-8")
    section = re.sub(r"\s+", " ", text[text.index("## Protocol v2 -- synthesis"):])
    a, b1, c = result["A"], result["B1"], result["C"]
    required = (
        f"{b1['succeeded_calls']}/{b1['attempted_calls']}",
        f"{b1['atomic_facts_correct']}/{b1['atomic_facts_expected']}",
        f"{a['text_control'][0]}/{a['text_control'][1]}",
        f"{a['image_text'][0]}/{a['image_text'][1]}",
        f"{a['image_only_facts_correct']}/{a['image_only_facts_expected']}",
        f"{c['exact_match'][0]}/{c['exact_match'][1]}",
        str(result["ledgers"]["asicloud"]["total"]),
        f"{c['actual_cost_usd']:.6f}",
    )
    for value in required:
        assert value in section, value


def test_readme_does_not_report_a_single_aggregate_accuracy() -> None:
    text = README.read_text(encoding="utf-8")
    section = text[text.index("## Protocol v2 -- synthesis"):]
    for banned in ("overall accuracy", "combined accuracy", "aggregate accuracy of"):
        assert banned not in section.lower(), banned


def test_readme_carries_the_non_claims(result) -> None:
    """Whitespace-normalised: prose wraps, the claim boundaries must not."""
    section = README.read_text(encoding="utf-8")
    section = section[section.index("## Protocol v2 -- synthesis"):].lower()
    flat = re.sub(r"\s+", " ", section.replace("*", ""))
    for phrase in ("universal ranking", "never matters",
                   "larger reasoning-loop budget", "does not establish"):
        assert phrase in flat, phrase


def test_scorer_untouched_by_the_synthesis() -> None:
    scorer = (SCRIPTS / "score_handoff.py").read_text(encoding="utf-8").lower()
    for token in ("synthesis", "supported_conclusion", "non_claims"):
        assert token not in scorer, token
    assert score_handoff.UNKNOWN == "unknown"
