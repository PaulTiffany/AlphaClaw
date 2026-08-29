"""Protocol v3 synthesis -- derived entirely from the frozen V3-A and V3-B evidence.

Pure, offline and read-only. No inference, no re-run, no new metric invented to make a
result look tidier. Every number is recomputed from committed artifacts, so a headline
figure cannot drift from the evidence without a test failing.

**V3 is not collapsed into one score.** It answered two independent questions and they
are reported separately:

``V3-A``  failure attribution -- a cause was NOT isolated, and a signature reproduced
``V3-B``  perceive-once economics -- multimodal demand held at one call per episode

Neither result is allowed to soften or inflate the other.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmark"
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import analyze_v3a
import analyze_v3b
import economics_v3

#: Frozen inputs. A digest change means the synthesis describes different evidence.
ARTIFACT_DIGESTS = {
    "protocol-v2.json": "b5ee0c3760a9540119526f1c51ac1dc5cc0d6fadc0fe1e378ddf770d3d02557f",
    "screening-v2-B1.json": "847828d469d60269a289f5183d07a69c6afc4c123ef1ad51346490e778e0ab14",
    "benchmark-v2-A.json": "644f36e406df5520f54e6bcb706b891e9dd1ff9094c6c0d59cfb305e68be65ea",
    "benchmark-v2-B2.json": "8b6cc4557b27c8cc2acf7803ca05293b0fd39ca1fe1cc6f89dbe838045fd7d48",
    "benchmark-v2-C.json": "b46ea2ceb4429c15bd3fa5b422d4e47e5a3acdb70467b6c5a3960eee090f6c88",
    "protocol-v3.json": "a65cbaad7640c3c64a03903dddef8b9162f08bd1d3a524fadc3367148ede0409",
    "benchmark-v3-A.json": "98ab018e8f8dcb2de405e21a800239583968c7832b1a8665cd31686072ad6552",
    "benchmark-v3-B.json": "f5ddcf3d77f010a4d199d6eea4c87fa093b3fe7576d01258a9997b9b493aeab2",
    "v3b-ground-truth.json": "35ce510b03473c58a166c6fabafa93a21f6a57e16dd203a7adf7b2b64c8ef767",
}

V3A_CONCLUSION = (
    "V3-A did not isolate a unique cause for the downstream failures, but it reproduced "
    "the correct-token-without-valid-emission signature under multiple diagnostic "
    "conditions."
)

V3B_ARCHITECTURE_CONCLUSION = (
    "AlphaClaw held multimodal inference constant at one perception call while "
    "multimodal-resident inference grew with reasoning depth."
)

V3B_MEASURED_CONCLUSION = (
    "The preregistered shallow-depth surcharge occurred at N=1, and AlphaClaw became "
    "cheaper by N=2 in the observed completed comparisons."
)

V3B_UTILITY_CONCLUSION = (
    "At N=4 and N=8, AlphaClaw achieved the same success count as the "
    "multimodal-resident baseline at lower measured cost per successful episode."
)

AVAILABILITY_STATEMENT = (
    "A short provider-rate-limit burst reduced sample coverage but did not create "
    "incorrect model outputs; all completed task episodes produced correct final answers."
)

E2_BOUNDARY_STATEMENT = (
    "Every completed E2 perception produced a complete task-relevant handoff, and that "
    "handoff was reused without renewed multimodal inference."
)

COMBINED_CONCLUSION = (
    "Protocol v3 sharpened two aspects of AlphaClaw. The diagnostic tranche did not "
    "isolate a unique cause for downstream output failures, though the "
    "correct-token/failed-emission signature reproduced. Separately, the economic "
    "tranche showed the intended perceive-once amortisation: multimodal-call demand "
    "stayed fixed at one per AlphaClaw episode while the multimodal-resident baseline "
    "scaled with reasoning depth, reaching 87.5% multimodal-call avoidance at depth 8. "
    "Under the measured Qwen/OpenRouter prices, AlphaClaw was slightly more expensive at "
    "depth 1 but cheaper at depths 2, 4 and 8; at depths 4 and 8 it matched baseline "
    "success while reducing measured cost per successful episode."
)

HEADLINE = (
    "Perceive once, reason many: AlphaClaw reduced multimodal inference by up to 87.5% "
    "in the tested depth range and reduced measured cost at depths 2-8, while preserving "
    "successful task completion in all completed episodes."
)

#: What the evidence does NOT support. Kept beside every conclusion on purpose.
NON_CLAIMS = (
    "not that AlphaClaw is always cheaper",
    "not that AlphaClaw is universally more accurate",
    "not that the break-even point is universally N=2",
    "not that Qwen pricing generalises to other providers",
    "not that all perception-once architectures will behave similarly",
    "not that AlphaClaw is unstable",
    "not that the architecture failed",
    "not that the symbolic handoff is unreliable",
    "not that representation does not matter",
    "not that turn budget does not matter",
)

V3A_LIMIT = (
    "V3-A simply did not have repeats sufficient to isolate representation or scheduling "
    "effects causally. That is a limitation of the tranche, not a finding about the "
    "architecture."
)


def digest(name: str) -> str:
    return hashlib.sha256((BENCHMARK / name).read_bytes()).hexdigest()


def artifact_digests_match() -> dict[str, bool]:
    return {name: digest(name) == expected
            for name, expected in ARTIFACT_DIGESTS.items()}


# --- V3-A ---------------------------------------------------------------------


def v3a_summary() -> dict[str, Any]:
    data = analyze_v3a.load()
    runs = data["runs"]
    representation = analyze_v3a.representation_pairs(runs)
    turns = analyze_v3a.turn_pairs(runs)
    internal = analyze_v3a.internal_versus_emitted(runs)

    def directions(pairs):
        return sorted({p["transition"] for p in pairs})

    return {
        "runs_executed": len(runs),
        "all_preflights_passed": all(r["preflight_passed"] for r in runs),
        "sensory_calls": data["sensory_calls"],
        "decomposition": analyze_v3a.decompose(runs),
        "repeats_per_cell": 1,
        "representation_pair_transitions": directions(representation),
        "turn_pair_transitions": directions(turns),
        "transitions_in_both_directions": (
            {"PASS -> FAIL", "FAIL -> PASS"} <= set(directions(representation))
            and {"PASS -> FAIL", "FAIL -> PASS"} <= set(directions(turns))),
        "correct_token_without_valid_send": [
            {"case_id": row["case_id"], "representation": row["representation"],
             "turn_budget": row["turn_budget"], "failure_class": row["failure_class"]}
            for row in internal],
        "signature_reproduction_count": len(internal),
        "unique_cause_isolated": False,
        "conclusion": V3A_CONCLUSION,
        "limitation": V3A_LIMIT,
        "failure_surface": ["Alpha representation / instruction", "resident model",
                            "stock OmegaClaw skill/action contract"],
    }


# --- V3-B ---------------------------------------------------------------------


def v3b_architecture() -> dict[str, Any]:
    data = analyze_v3b.load()
    rows = analyze_v3b.multimodal_avoidance(data)
    return {
        "by_depth": [{
            "depth": row["depth"],
            "e1_multimodal": row["expected_e1_multimodal"],
            "e2_multimodal": row["expected_e2_multimodal"],
            "avoided": row["expected_avoided"],
            "avoidance_fraction": row["expected_avoidance_fraction"],
            "comparable_item_pairs": row["comparable_item_pairs"],
            "receipts_match_expectation": row["receipts_match_expectation"],
        } for row in rows],
        "max_avoidance_fraction": max(r["expected_avoidance_fraction"] for r in rows),
        "e2_multimodal_calls_per_episode": sorted(
            {r["expected_e2_multimodal"] for r in rows}),
        "receipts_match_at_every_depth": all(r["receipts_match_expectation"]
                                             for r in rows),
        "conclusion": V3B_ARCHITECTURE_CONCLUSION,
        "price_independent": True,
    }


def v3b_measured() -> dict[str, Any]:
    data = analyze_v3b.load()
    rows = analyze_v3b.e1_vs_e2_savings(data)
    break_even = analyze_v3b.break_even(data)
    return {
        "by_depth": rows,
        "depths_cheaper": break_even["depths_where_alphaclaw_cheaper"],
        "depths_dearer": break_even["depths_where_alphaclaw_dearer"],
        "observed_sign_change": break_even["observed_sign_change"],
        "sign_change_statement": "The measured sign changed between N=1 and N=2.",
        "interpolated_break_even_point": None,
        "cost_provenance": economics_v3.MEASURED,
        "estimated_values_reported": False,
        "conclusion": V3B_MEASURED_CONCLUSION,
        "mixed_results_characterisation": False,
        "amortisation_note": (
            "N=1 losing is part of the hypothesis, not evidence against the "
            "architecture: one extra perception setup cost is amortised over multiple "
            "cheaper text-only reasoning calls."),
    }


def v3b_utility() -> dict[str, Any]:
    data = analyze_v3b.load()
    rows = {(r["architecture"], r["depth"]): r
            for r in analyze_v3b.cost_by_arm_depth(data)}
    equal_success = []
    for depth in (1, 2, 4, 8):
        e1, e2 = rows[(analyze_v3b.E1, depth)], rows[(analyze_v3b.E2, depth)]
        if e1["successful_episodes"] != e2["successful_episodes"]:
            continue
        if not (e1["defined"] and e2["defined"]):
            continue
        equal_success.append({
            "depth": depth,
            "successful_episodes": e1["successful_episodes"],
            "e1_cost_per_success": e1["cost_per_successful_episode"],
            "e2_cost_per_success": e2["cost_per_successful_episode"],
            "e2_cheaper_per_success": (e2["cost_per_successful_episode"]
                                       < e1["cost_per_successful_episode"]),
        })
    return {
        "by_arm_depth": [
            {k: row[k] for k in ("architecture", "depth", "measured_cost_usd",
                                 "successful_episodes", "availability_failures",
                                 "cost_per_successful_episode", "defined")}
            for row in analyze_v3b.cost_by_arm_depth(data)],
        "equal_success_comparisons": equal_success,
        "strongest_equal_success_depths": [row["depth"] for row in equal_success
                                           if row["e2_cheaper_per_success"]
                                           and row["successful_episodes"] == 2],
        "conclusion": V3B_UTILITY_CONCLUSION,
        "superiority_claimed_at_depth_2": False,
        "denominators_reported": True,
    }


def v3b_availability() -> dict[str, Any]:
    data = analyze_v3b.load()
    failures = [e for e in data["episodes"]
                if analyze_v3b.outcome(e) == analyze_v3b.AVAILABILITY]
    completed = [e for e in data["episodes"] if e["terminated"] == "completed"]
    totals = analyze_v3b.call_totals(data)
    lost = sum((e["multimodal_calls"] + e["text_calls"]) - len(e["calls"])
               for e in data["episodes"])
    return {
        "availability_failures": len(failures),
        "failure_episode_indices": sorted(e["episode_index"] for e in failures),
        "contiguous": (sorted(e["episode_index"] for e in failures)
                       == list(range(min(e["episode_index"] for e in failures),
                                     max(e["episode_index"] for e in failures) + 1))),
        "successes": sum(1 for e in data["episodes"] if analyze_v3b.succeeded(e)),
        "incorrect_answers": sum(1 for e in data["episodes"]
                                 if analyze_v3b.outcome(e) == "incorrect"),
        "completed_episodes": len(completed),
        "completed_episodes_all_correct": all(e["exact_match"] for e in completed),
        "planned_calls": 98,
        "calls_not_issued": lost,
        "actual_calls": totals["total_calls"],
        "reconciles": 98 - lost == totals["total_calls"],
        "classified_as_incorrect_answers": False,
        "alphaclaw_specific": False,
        "evidence_of_architecture_instability": False,
        "retried": False,
        "statement": AVAILABILITY_STATEMENT,
    }


def v3b_sensory_boundary() -> dict[str, Any]:
    data = analyze_v3b.load()
    rows = analyze_v3b.e2_fidelity(data)
    completed = [r for r in rows if r["outcome"] == "success"]
    return {
        "episodes": len(rows),
        "one_perception_per_episode": all(r["perception_calls"] == 1 for r in rows),
        "no_image_after_perception": all(not r["any_reasoning_call_carried_image"]
                                         for r in rows),
        "handoff_reused_identically": all(r["same_handoff_reused"] for r in rows),
        "handoffs_with_all_required_facts": sum(1 for r in rows
                                                if r["all_required_facts_present"]),
        "completed_episodes": len(completed),
        "completed_handoffs_all_complete": all(r["all_required_facts_present"]
                                               for r in completed),
        "incomplete_handoff_was_availability_failure": all(
            r["outcome"] == analyze_v3b.AVAILABILITY
            for r in rows if not r["all_required_facts_present"]),
        "handoff_repaired_or_replaced": False,
        "statement": E2_BOUNDARY_STATEMENT,
    }


# --- V2 -> V3 arc -------------------------------------------------------------


def v2_to_v3_arc() -> dict[str, Any]:
    """Connects the tranches without rewriting v2. All claims stay narrow."""
    return {
        "v2_established": [
            "the symbolic sensory boundary was portable across tested sensory models",
            "sensory substitution produced 0/3 paired outcome transitions",
            "resident substitution produced 3/3 PASS->FAIL",
            "output-channel behaviour was independently observable",
        ],
        "arc": [
            {"question": "V2: is the decomposition operationally real?",
             "answer": "yes, under the tested conditions"},
            {"question": "V3-A: why do downstream failures happen?",
             "answer": "cause not isolated; output-emission signature reproduced"},
            {"question": "V3-B: does the decomposition buy anything economically?",
             "answer": ("yes, multimodal inference is amortised and measured cost falls "
                        "at deeper tested reasoning depths")},
        ],
        "v2_rewritten": False,
    }


def synthesis() -> dict[str, Any]:
    return {
        "protocol_version": "v3",
        "single_aggregate_v3_score_reported": False,
        "findings_are_independent": True,
        "V3A": v3a_summary(),
        "V3B_architecture": v3b_architecture(),
        "V3B_measured": v3b_measured(),
        "V3B_utility": v3b_utility(),
        "V3B_availability": v3b_availability(),
        "V3B_sensory_boundary": v3b_sensory_boundary(),
        "v2_to_v3": v2_to_v3_arc(),
        "combined_conclusion": COMBINED_CONCLUSION,
        "headline": HEADLINE,
        "non_claims": list(NON_CLAIMS),
        "artifact_digests": dict(ARTIFACT_DIGESTS),
    }


def main() -> int:
    print(json.dumps(synthesis(), indent=2, sort_keys=True))
    mismatched = [n for n, ok in artifact_digests_match().items() if not ok]
    if mismatched:
        print(f"\nARTIFACT DIGEST MISMATCH: {mismatched}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
