"""Protocol v3 synthesis -- every headline recomputed from frozen evidence.

Offline. No network, no container, no provider call, no judge.

The governing rule: no headline value may appear in the synthesis or in the results
documentation without a test deriving it from the committed artifacts. These tests
recompute each figure independently of the prose that quotes it, and separately guard
the phrasing the evidence does and does not support.
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

import analyze_v3a
import analyze_v3b
import synthesis_v3 as syn

README = ROOT / "controller" / "README.md"


@pytest.fixture(scope="module")
def result():
    return syn.synthesis()


# --- frozen inputs ------------------------------------------------------------


def test_every_frozen_artifact_digest_matches() -> None:
    assert syn.artifact_digests_match() == {n: True for n in syn.ARTIFACT_DIGESTS}


def test_digest_constants_equal_the_files_on_disk() -> None:
    for name, expected in syn.ARTIFACT_DIGESTS.items():
        actual = hashlib.sha256((ROOT / "benchmark" / name).read_bytes()).hexdigest()
        assert actual == expected, name


def test_synthesis_module_performs_no_inference() -> None:
    import ast

    banned = {"requests", "urllib", "socket", "http", "httpx", "subprocess", "docker"}
    source = (SCRIPTS / "synthesis_v3.py").read_text(encoding="utf-8")
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert not (imported & banned)
    assert "write_text" not in source and "write_bytes" not in source


# --- V3-A, recomputed ---------------------------------------------------------


def test_v3a_matrix_is_eighteen_runs_with_zero_sensory_calls(result) -> None:
    block = result["V3A"]
    assert block["runs_executed"] == 18
    assert block["all_preflights_passed"] is True
    assert block["sensory_calls"] == 0
    assert block["repeats_per_cell"] == 1


def test_v3a_decomposition_recomputed_independently(result) -> None:
    data = analyze_v3a.load()
    assert result["V3A"]["decomposition"] == analyze_v3a.decompose(data["runs"])
    assert result["V3A"]["decomposition"] == {
        "sensory": 0, "reasoning_composition": 9, "output_contract": 2,
        "infrastructure": 0, "provider_availability": 0, "passed": 7}


def test_v3a_transitions_run_in_both_directions(result) -> None:
    block = result["V3A"]
    for key in ("representation_pair_transitions", "turn_pair_transitions"):
        assert "PASS -> FAIL" in block[key], key
        assert "FAIL -> PASS" in block[key], key
    assert block["transitions_in_both_directions"] is True


def test_v3a_signature_reproduced_twice_under_minimax(result) -> None:
    rows = result["V3A"]["correct_token_without_valid_send"]
    assert result["V3A"]["signature_reproduction_count"] == 2 == len(rows)
    assert all(row["case_id"] == "A1" for row in rows)      # A1 is the MiniMax case
    assert all(row["failure_class"] == "output_contract" for row in rows)


def test_v3a_claims_no_unique_cause(result) -> None:
    block = result["V3A"]
    assert block["unique_cause_isolated"] is False
    assert block["conclusion"] == syn.V3A_CONCLUSION
    assert "did not isolate a unique cause" in block["conclusion"]
    assert "reproduced" in block["conclusion"]
    assert "repeats sufficient" in block["limitation"]


def test_v3a_failure_surface_is_the_whole_seam(result) -> None:
    assert result["V3A"]["failure_surface"] == [
        "Alpha representation / instruction", "resident model",
        "stock OmegaClaw skill/action contract"]


def test_v3a_language_does_not_oversell_the_negative_result(result) -> None:
    """The banned readings are recorded as non-claims, not asserted."""
    non_claims = " ".join(result["non_claims"]).lower()
    for phrase in ("not that alphaclaw is unstable",
                   "not that the architecture failed",
                   "not that the symbolic handoff is unreliable",
                   "not that representation does not matter",
                   "not that turn budget does not matter"):
        assert phrase in non_claims, phrase


# --- V3-B architecture, recomputed --------------------------------------------


def test_v3b_avoidance_table(result) -> None:
    rows = {r["depth"]: r for r in result["V3B_architecture"]["by_depth"]}
    for depth, e1, avoided, fraction in ((1, 1, 0, 0.0), (2, 2, 1, 0.5),
                                         (4, 4, 3, 0.75), (8, 8, 7, 0.875)):
        assert rows[depth]["e1_multimodal"] == e1
        assert rows[depth]["e2_multimodal"] == 1
        assert rows[depth]["avoided"] == avoided
        assert rows[depth]["avoidance_fraction"] == pytest.approx(fraction)
        assert rows[depth]["receipts_match_expectation"] is True


def test_v3b_e2_multimodal_is_always_one(result) -> None:
    block = result["V3B_architecture"]
    assert block["e2_multimodal_calls_per_episode"] == [1]
    assert block["max_avoidance_fraction"] == pytest.approx(0.875)
    assert block["receipts_match_at_every_depth"] is True
    assert block["price_independent"] is True
    assert block["conclusion"] == syn.V3B_ARCHITECTURE_CONCLUSION


def test_v3b_avoidance_recomputed_from_the_artifact() -> None:
    rows = analyze_v3b.multimodal_avoidance(analyze_v3b.load())
    assert [r["expected_avoided"] for r in rows] == [0, 1, 3, 7]
    assert all(r["receipts_match_expectation"] for r in rows)


# --- V3-B measured dollars ----------------------------------------------------


def test_measured_savings_by_depth(result) -> None:
    rows = {r["depth"]: r for r in result["V3B_measured"]["by_depth"]}
    assert rows[1]["alphaclaw_cheaper"] is False
    assert rows[1]["measured_savings_fraction"] == pytest.approx(-0.027, abs=5e-4)
    assert rows[2]["measured_savings_fraction"] == pytest.approx(0.220, abs=5e-4)
    assert rows[4]["measured_savings_fraction"] == pytest.approx(0.380, abs=5e-4)
    assert rows[8]["measured_savings_fraction"] == pytest.approx(0.371, abs=5e-4)
    for depth in (2, 4, 8):
        assert rows[depth]["alphaclaw_cheaper"] is True


def test_sign_change_is_observed_and_not_interpolated(result) -> None:
    block = result["V3B_measured"]
    assert block["depths_dearer"] == [1]
    assert block["depths_cheaper"] == [2, 4, 8]
    assert block["observed_sign_change"] is True
    assert block["interpolated_break_even_point"] is None
    assert block["sign_change_statement"] == \
        "The measured sign changed between N=1 and N=2."


def test_shallow_depth_loss_is_framed_as_the_hypothesis_not_a_refutation(result) -> None:
    block = result["V3B_measured"]
    assert block["mixed_results_characterisation"] is False
    assert "part of the hypothesis" in block["amortisation_note"]
    assert block["conclusion"] == syn.V3B_MEASURED_CONCLUSION


def test_no_estimated_dollar_values_are_reported(result) -> None:
    assert result["V3B_measured"]["estimated_values_reported"] is False
    assert result["V3B_measured"]["cost_provenance"] == "measured"


# --- V3-B success-adjusted utility --------------------------------------------


def test_equal_success_comparisons_at_depth_four_and_eight(result) -> None:
    rows = {r["depth"]: r for r in result["V3B_utility"]["equal_success_comparisons"]}
    for depth, e1, e2 in ((4, 0.000394, 0.000245), (8, 0.000750, 0.000472)):
        assert rows[depth]["successful_episodes"] == 2
        assert rows[depth]["e1_cost_per_success"] == pytest.approx(e1, abs=5e-7)
        assert rows[depth]["e2_cost_per_success"] == pytest.approx(e2, abs=5e-7)
        assert rows[depth]["e2_cheaper_per_success"] is True
    assert result["V3B_utility"]["strongest_equal_success_depths"] == [4, 8]


def test_no_superiority_claimed_at_depth_two(result) -> None:
    """Depth 2 has one comparable item; it must not carry the utility claim."""
    block = result["V3B_utility"]
    assert block["superiority_claimed_at_depth_2"] is False
    assert 2 not in block["strongest_equal_success_depths"]
    rows = {r["depth"]: r for r in block["equal_success_comparisons"]}
    assert rows[2]["successful_episodes"] == 1


def test_utility_reports_its_denominators(result) -> None:
    block = result["V3B_utility"]
    assert block["denominators_reported"] is True
    for row in block["by_arm_depth"]:
        if row["successful_episodes"]:
            assert row["cost_per_successful_episode"] == pytest.approx(
                row["measured_cost_usd"] / row["successful_episodes"])
        else:
            assert row["cost_per_successful_episode"] is None
    assert block["conclusion"] == syn.V3B_UTILITY_CONCLUSION


# --- availability -------------------------------------------------------------


def test_availability_burst_is_not_an_accuracy_failure(result) -> None:
    block = result["V3B_availability"]
    assert block["availability_failures"] == 4
    assert block["failure_episode_indices"] == [2, 3, 4, 5]
    assert block["contiguous"] is True
    assert block["successes"] == 20
    assert block["incorrect_answers"] == 0
    assert block["classified_as_incorrect_answers"] is False
    assert block["alphaclaw_specific"] is False
    assert block["evidence_of_architecture_instability"] is False
    assert block["retried"] is False


def test_call_reconciliation(result) -> None:
    block = result["V3B_availability"]
    assert block["planned_calls"] == 98
    assert block["calls_not_issued"] == 4
    assert block["actual_calls"] == 94
    assert block["reconciles"] is True


def test_all_completed_episodes_produced_correct_answers(result) -> None:
    """The clause the headline depends on -- asserted, not assumed."""
    block = result["V3B_availability"]
    assert block["completed_episodes"] == 20
    assert block["completed_episodes_all_correct"] is True
    data = analyze_v3b.load()
    completed = [e for e in data["episodes"] if e["terminated"] == "completed"]
    assert len(completed) == 20
    assert all(e["exact_match"] for e in completed)
    assert block["statement"] == syn.AVAILABILITY_STATEMENT


# --- E2 boundary --------------------------------------------------------------


def test_e2_boundary_invariants(result) -> None:
    block = result["V3B_sensory_boundary"]
    assert block["episodes"] == 8
    assert block["one_perception_per_episode"] is True
    assert block["no_image_after_perception"] is True
    assert block["handoff_reused_identically"] is True
    assert block["handoff_repaired_or_replaced"] is False


def test_seven_of_eight_handoffs_complete_and_the_eighth_was_availability(result) -> None:
    block = result["V3B_sensory_boundary"]
    assert block["handoffs_with_all_required_facts"] == 7
    assert block["completed_episodes"] == 7
    assert block["completed_handoffs_all_complete"] is True
    assert block["incomplete_handoff_was_availability_failure"] is True
    assert block["statement"] == syn.E2_BOUNDARY_STATEMENT


# --- combined narrative -------------------------------------------------------


def test_v3_is_not_collapsed_into_one_score(result) -> None:
    assert result["single_aggregate_v3_score_reported"] is False
    assert result["findings_are_independent"] is True
    assert "V3A" in result and "V3B_architecture" in result
    # Structural, not textual: the only key mentioning a score must be the boolean
    # declaration that none is reported, and it must be False.
    score_keys = [k for k in result if "score" in k.lower()]
    assert score_keys == ["single_aggregate_v3_score_reported"]
    assert result["single_aggregate_v3_score_reported"] is False
    numeric = [k for k, v in result.items()
               if isinstance(v, (int, float)) and not isinstance(v, bool)]
    assert numeric == [], numeric


def test_combined_conclusion_is_the_supported_one(result) -> None:
    text = result["combined_conclusion"]
    assert "did not isolate a unique cause" in text
    assert "87.5% multimodal-call avoidance at depth 8" in text
    assert "slightly more expensive at depth 1" in text
    assert "cheaper at depths 2, 4 and 8" in text
    assert "reducing measured cost per successful episode" in text
    assert "mixed" not in text.lower()


def test_headline_is_mechanically_true(result) -> None:
    headline = result["headline"]
    assert "87.5%" in headline
    assert "depths 2-8" in headline
    assert "all completed episodes" in headline
    # every clause is independently derivable
    assert result["V3B_architecture"]["max_avoidance_fraction"] == pytest.approx(0.875)
    assert result["V3B_measured"]["depths_cheaper"] == [2, 4, 8]
    assert result["V3B_availability"]["completed_episodes_all_correct"] is True


def test_non_claims_are_carried_beside_the_conclusion(result) -> None:
    non_claims = " ".join(result["non_claims"]).lower()
    for phrase in ("always cheaper", "universally more accurate",
                   "break-even point is universally n=2",
                   "qwen pricing generalises", "perception-once architectures"):
        assert phrase in non_claims, phrase


def test_v2_to_v3_arc_is_narrow_and_does_not_rewrite_v2(result) -> None:
    arc = result["v2_to_v3"]
    assert arc["v2_rewritten"] is False
    established = " ".join(arc["v2_established"]).lower()
    assert "0/3 paired outcome transitions" in established
    assert "3/3 pass->fail" in established
    questions = [row["question"] for row in arc["arc"]]
    assert any("V2:" in q for q in questions)
    assert any("V3-A:" in q for q in questions)
    assert any("V3-B:" in q for q in questions)


# --- documentation may not drift ----------------------------------------------


def test_readme_quotes_only_derived_numbers(result) -> None:
    text = README.read_text(encoding="utf-8")
    section = re.sub(r"\s+", " ", text[text.index("## Protocol v3 -- synthesis"):])
    for value in ("87.5%", "0.000394", "0.000245", "0.000750", "0.000472",
                  "20", "94", "98"):
        assert value in section, value


def test_readme_carries_the_non_claims_and_avoids_mixed_framing() -> None:
    text = README.read_text(encoding="utf-8")
    section = text[text.index("## Protocol v3 -- synthesis"):]
    flat = re.sub(r"\s+", " ", section.replace("*", "")).lower()
    for phrase in ("always cheaper", "universally more accurate",
                   "did not isolate a unique cause"):
        assert phrase in flat, phrase
    assert "mixed results" not in flat


def test_readme_does_not_report_a_single_v3_score() -> None:
    text = README.read_text(encoding="utf-8")
    section = text[text.index("## Protocol v3 -- synthesis"):].lower()
    for banned in ("overall v3 score", "combined v3 score", "aggregate v3 score"):
        assert banned not in section, banned


def test_upstream_results_untouched_by_the_synthesis() -> None:
    for name in ("benchmark-v3-A.json", "benchmark-v3-B.json"):
        assert hashlib.sha256(
            (ROOT / "benchmark" / name).read_bytes()).hexdigest() == \
            syn.ARTIFACT_DIGESTS[name]
    scorer = (SCRIPTS / "score_handoff.py").read_text(encoding="utf-8")
    assert "is located to the left of" not in scorer
    assert json.loads(
        (ROOT / "benchmark" / "benchmark-v3-A.json").read_text(encoding="utf-8")
    )["section"] == "V3-A"
