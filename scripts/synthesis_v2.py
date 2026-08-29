"""Protocol v2 synthesis -- derived entirely from the frozen artifacts.

Pure, offline and read-only. This module introduces no experimental result, no scorer,
no model call and no protocol amendment. Every number it reports is recomputed from
committed evidence, so a headline figure cannot drift away from the artifact it came
from without a test failing.

The preregistered v2 robustness question:

    Does bounded AlphaClaw continue behaving sensibly when reasonable explicit
    sensory/resident models are substituted while tasks and architecture are held fixed?

The answer is deliberately NOT collapsed into one aggregate accuracy number. The four
conditions measure different things and are reported separately:

``A``   primary condition -- dots sensory + ASICloud MiniMax M3
``B1``  sensory portability -- is the frozen boundary portable to another model family?
``B2``  sensory substitution -- same task and resident, different symbolic evidence
``C``   resident substitution -- same resident-facing evidence, different resident
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

import analyze_condition_a as analyze
import score_handoff

#: Frozen inputs. A digest change here means the synthesis is describing other evidence.
ARTIFACT_DIGESTS = {
    "protocol-v2.json": "b5ee0c3760a9540119526f1c51ac1dc5cc0d6fadc0fe1e378ddf770d3d02557f",
    "screening-v2-B1.json": "847828d469d60269a289f5183d07a69c6afc4c123ef1ad51346490e778e0ab14",
    "benchmark-v2-A.json": "644f36e406df5520f54e6bcb706b891e9dd1ff9094c6c0d59cfb305e68be65ea",
    "benchmark-v2-B2.json": "8b6cc4557b27c8cc2acf7803ca05293b0fd39ca1fe1cc6f89dbe838045fd7d48",
    "benchmark-v2-C.json": "b46ea2ceb4429c15bd3fa5b422d4e47e5a3acdb70467b6c5a3960eee090f6c88",
}

SUPPORTED_CONCLUSION = (
    "Protocol v2 found stronger robustness to sensory-model substitution than to "
    "resident-model substitution under the tested bounded conditions."
)

#: Everything the evidence does NOT support. Kept beside the conclusion on purpose.
NON_CLAIMS = (
    "not a universal ranking of models",
    "not evidence that dots is better than Qwen",
    "not evidence that MiniMax is better than Gemma generally",
    "not evidence that Gemma would fail under a larger reasoning-loop budget",
    "not evidence that sensory substitution can never matter",
)

ONE_TURN_CAVEAT = (
    "This is a one-turn bounded benchmark. A model that spends its one turn on "
    "bookkeeping fails this population; that does not establish its behaviour under a "
    "larger reasoning-loop budget."
)


def load(name: str) -> dict[str, Any]:
    return json.loads((BENCHMARK / name).read_text(encoding="utf-8"))


def digest(name: str) -> str:
    return hashlib.sha256((BENCHMARK / name).read_bytes()).hexdigest()


def artifact_digests_match() -> dict[str, bool]:
    return {name: digest(name) == expected for name, expected in ARTIFACT_DIGESTS.items()}


# --- B1: sensory portability --------------------------------------------------


def b1_summary() -> dict[str, Any]:
    b1 = load("screening-v2-B1.json")
    calls = b1["calls"]
    metrics = b1["metrics"]
    verdicts = [v for c in calls for v in c["verdicts"]]
    unknown = [v for v in verdicts if v["verdict"] == score_handoff.UNKNOWN]
    correct = sum(1 for v in verdicts if v["verdict"] == score_handoff.CORRECT)
    scoreable = sum(1 for v in verdicts if v["verdict"] != score_handoff.UNKNOWN)
    return {
        "sensory_model": b1["requested_model"],
        "attempted_calls": len(calls),
        "succeeded_calls": sum(1 for c in calls if c["request_success"]),
        "schema_compliant_calls": sum(1 for c in calls if c["schema_conformant"]),
        "atomic_facts_expected": len(verdicts),
        "atomic_facts_correct": correct,
        "atomic_facts_scoreable": scoreable,
        "unknown_verdicts": len(unknown),
        "unknown_fact_types": sorted({v["type"] for v in unknown}),
        "scoring_coverage": metrics["scoring_coverage"],
        "relation_lexicon_broadened": "is located to the left of" in
                                      (ROOT / "scripts" / "score_handoff.py").read_text(
                                          encoding="utf-8"),
    }


# --- A: primary condition -----------------------------------------------------


def a_summary() -> dict[str, Any]:
    a = load("benchmark-v2-A.json")
    runs = a["runs"]
    image_only = [r["sensory_score"] for r in runs
                  if r["condition"] == "image_only" and r.get("sensory_score")]
    aggregate = score_handoff.aggregate(image_only)
    verdicts = [v for s in image_only for v in s["verdicts"]]
    failures = [r for r in runs if analyze.classify(r) is not None]
    return {
        "sensory_model": a["sensory_model"],
        "resident": f"{a['resident_provider']}/{a['resident_model']}",
        "text_control": analyze.exact_match_rate(runs, "text_control"),
        "image_text": analyze.exact_match_rate(runs, "image_text"),
        "image_only_facts_correct": sum(
            1 for v in verdicts if v["verdict"] == score_handoff.CORRECT),
        "image_only_facts_expected": len(verdicts),
        "image_only_facts_scoreable": sum(
            1 for v in verdicts if v["verdict"] != score_handoff.UNKNOWN),
        "image_only_scoring_coverage": aggregate["scoring_coverage"],
        "sensory_calls": analyze.sensory_totals(runs)["calls"],
        "decomposition": analyze.decompose(runs),
        "failures": [{"item_id": r["item_id"], "condition": r["condition"],
                      "failure_class": analyze.classify(r)} for r in failures],
        "bound_violations": analyze.bounds_respected(runs),
        "asicloud_calls": (analyze.usage_totals(runs, "boot")["calls"]
                           + analyze.usage_totals(runs, "episode")["calls"]),
    }


def a_distractor_failure() -> dict[str, Any]:
    """The one Condition A failure, stated with its evidence intact."""
    a = load("benchmark-v2-A.json")
    run = next(r for r in a["runs"] if r["item_id"] == "distractor_selection"
               and r["condition"] == "image_text")
    scored = run["sensory_score"]
    return {
        "sensory_evidence_correct": scored["correct"] == scored["expected"] == 4,
        "expected_answer": run["expected_answer"],
        "response": run["response"],
        "failure_class": analyze.classify(run),
        "termination_reason": run["manifest"]["termination_reason"],
    }


# --- B2: sensory substitution -------------------------------------------------


def _transition(a_pass: bool, other_pass: bool) -> str:
    return f"{'PASS' if a_pass else 'FAIL'} -> {'PASS' if other_pass else 'FAIL'}"


def b2_summary() -> dict[str, Any]:
    b2 = load("benchmark-v2-B2.json")
    a = load("benchmark-v2-A.json")
    a_by_item = {r["item_id"]: r for r in a["runs"] if r["condition"] == "image_text"}
    items = {i["item_id"]: i for i in
             json.loads((BENCHMARK / "items.json").read_text(encoding="utf-8"))["items"]}
    b1_calls = load("screening-v2-B1.json")["calls"]

    pairs, transitions = [], 0
    for run in b2["runs"]:
        item_id = run["item_id"]
        a_run = a_by_item[item_id]
        dots = a_run["sensory_score"]
        qwen_call = next(c for c in b1_calls
                         if c["item_id"] == item_id and c["repeat_index"] == 0)
        qwen = score_handoff.score_item(qwen_call["normalized_handoff"],
                                        items[item_id]["facts"])
        changed = bool(a_run["exact_match"]) != bool(run["exact_match"])
        transitions += changed
        pairs.append({
            "item_id": item_id,
            "dots_facts": f"{dots['correct']}/{dots['expected']}",
            "qwen_facts": f"{qwen['correct']}/{qwen['expected']}",
            "dots_all_required_facts": dots["correct"] == dots["expected"],
            "qwen_all_required_facts": qwen["correct"] == qwen["expected"],
            "a_response": a_run["response"], "b2_response": run["response"],
            "transition": _transition(bool(a_run["exact_match"]),
                                      bool(run["exact_match"])),
            "changed": changed,
        })
    return {
        "paired_cases": len(pairs),
        "transitions": transitions,
        "new_sensory_calls": b2["new_sensory_calls"],
        "exact_match": (sum(1 for r in b2["runs"] if r["exact_match"]), len(b2["runs"])),
        "pairs": pairs,
    }


# --- C: resident substitution -------------------------------------------------


def c_summary() -> dict[str, Any]:
    c = load("benchmark-v2-C.json")
    pairs, transitions = [], 0
    cost = tokens_in = tokens_out = 0
    for run in c["runs"]:
        paired = run["paired_condition_a"]
        changed = bool(paired["exact_match"]) != bool(run["exact_match"])
        transitions += changed
        pairs.append({
            "case_id": run["case_id"],
            "payload_byte_equal": paired["payload_equal_to_c"],
            "a_response": paired["response"], "c_response": run["response"],
            "transition": paired["transition"],
            "failure_class": run["failure_class"],
        })
        for receipt in run["provider_usage"]:
            usage = receipt["usage"]
            cost += usage.get("cost", 0.0)
            tokens_in += usage.get("prompt_tokens", 0)
            tokens_out += usage.get("completion_tokens", 0)
    return {
        "resident": f"{c['resident_provider']}/{c['resident_model']}",
        "paired_cases": len(pairs),
        "transitions": transitions,
        "exact_match": (sum(1 for r in c["runs"] if r["exact_match"]), len(c["runs"])),
        "decomposition": c["failure_decomposition"],
        "all_payloads_byte_equal": all(p["payload_byte_equal"] for p in pairs),
        "openrouter_resident_calls": sum(len(r["provider_usage"]) for r in c["runs"]),
        "tokens_in": tokens_in, "tokens_out": tokens_out,
        "actual_cost_usd": round(cost, 6),
        "pairs": pairs,
    }


# --- the failure surface ------------------------------------------------------


def emission_failure_surface() -> dict[str, Any]:
    """Output-channel / skill-selection failures, collected across conditions.

    Reported as a separately measurable surface, NOT as a claim of common cause.
    """
    a = load("benchmark-v2-A.json")
    b2 = load("benchmark-v2-B2.json")
    c = load("benchmark-v2-C.json")

    a_run = next(r for r in a["runs"] if r["item_id"] == "distractor_selection"
                 and r["condition"] == "image_text")
    b2_run = next(r for r in b2["runs"] if r["item_id"] == "distractor_selection")
    c_run = next(r for r in c["runs"] if r["case_id"] == "number_arithmetic:image_text")
    return {
        "cases": [
            {"condition": "A", "sensory": "dots", "resident": "minimax/minimax-m3",
             "item": "distractor_selection", "expected": a_run["expected_answer"],
             "emitted_answer_through_channel": False,
             "failure_class": analyze.classify(a_run)},
            {"condition": "B2", "sensory": "qwen/qwen3.7-flash",
             "resident": "minimax/minimax-m3", "item": "distractor_selection",
             "expected": b2_run["expected_answer"],
             "emitted_answer_through_channel": False,
             "failure_class": "output_contract"},
            {"condition": "C", "sensory": "dots (replayed)",
             "resident": "google/gemma-4-26b-a4b-it",
             "item": "number_arithmetic:image_text",
             "expected": c_run["expected_answer"],
             "emitted_answer_through_channel": False,
             "failure_class": c_run["failure_class"]},
        ],
        "survives_sensory_substitution": True,
        "observed_under_a_second_resident": True,
        "common_cause_established": False,
        "interpretation": (
            "Output-channel / skill-selection behaviour is worth measuring as an "
            "independent failure surface rather than conflating it with perception or "
            "semantic answer formation. These are three cases; no common cause is "
            "established."
        ),
    }


# --- accounting ---------------------------------------------------------------


def ledgers() -> dict[str, Any]:
    """Two billing paths, kept distinct. Artifact-recorded numbers only."""
    a = load("benchmark-v2-A.json")
    b2 = load("benchmark-v2-B2.json")
    b1 = load("screening-v2-B1.json")
    c = c_summary()

    def resident_calls(runs):
        return (analyze.usage_totals(runs, "boot")["calls"]
                + analyze.usage_totals(runs, "episode")["calls"])

    return {
        "asicloud": {
            "A": resident_calls(a["runs"]),
            "B2": resident_calls(b2["runs"]),
            "total": resident_calls(a["runs"]) + resident_calls(b2["runs"]),
        },
        "openrouter_sensory": {
            "B1_qwen_calls": b1["attempted_calls"],
            "A_dots_calls": analyze.sensory_totals(a["runs"])["calls"],
            "B2_new_sensory_calls": b2["new_sensory_calls"],
            "C_sensory_calls": load("benchmark-v2-C.json")["sensory_calls"],
        },
        "openrouter_resident": {
            "C_calls": c["openrouter_resident_calls"],
            "C_tokens_in": c["tokens_in"], "C_tokens_out": c["tokens_out"],
            "C_actual_cost_usd": c["actual_cost_usd"],
        },
    }


def reproducibility() -> dict[str, Any]:
    """Pins shared by every run across every condition."""
    manifests = []
    for name in ("benchmark-v2-A.json", "benchmark-v2-B2.json", "benchmark-v2-C.json"):
        manifests += [r["manifest"] for r in load(name)["runs"] if r.get("manifest")]

    def field(key: str) -> list[str]:
        return sorted({m[key] for m in manifests if key in m})

    scorer = (ROOT / "scripts" / "score_handoff.py").read_text(encoding="utf-8")
    return {
        "artifact_digests": dict(ARTIFACT_DIGESTS),
        "amendments": ["v2.1", "v2.2"],
        "omega_sha": field("omega_sha"),
        "threadkeeper_sha": field("threadkeeper_sha"),
        "stock_omega_image_id": field("omega_image_id"),
        "pins_all_true": all(
            m.get("omega_commit_matches_pin") and m.get("omega_worktree_bytes_match_pin")
            and m.get("threadkeeper_commit_matches_pin")
            and m.get("threadkeeper_worktree_bytes_match_pin") for m in manifests),
        "scorer_sha256": hashlib.sha256(scorer.encode("utf-8")).hexdigest(),
        "relation_lexicon_unbroadened": "is located to the left of" not in scorer,
    }


def synthesis() -> dict[str, Any]:
    return {
        "protocol_version": "v2",
        "question": (
            "Does bounded AlphaClaw continue behaving sensibly when reasonable explicit "
            "sensory/resident models are substituted while tasks and architecture are "
            "held fixed?"),
        "single_aggregate_accuracy_reported": False,
        "A": a_summary(),
        "A_distractor_failure": a_distractor_failure(),
        "B1": b1_summary(),
        "B2": b2_summary(),
        "C": c_summary(),
        "emission_failure_surface": emission_failure_surface(),
        "ledgers": ledgers(),
        "reproducibility": reproducibility(),
        "supported_conclusion": SUPPORTED_CONCLUSION,
        "non_claims": list(NON_CLAIMS),
        "one_turn_caveat": ONE_TURN_CAVEAT,
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
