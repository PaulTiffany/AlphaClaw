"""Derived analysis for Protocol v3-A. Pure, offline, read-only.

The v2 classifier in ``analyze_condition_a`` encodes a one-turn architecture: it treats
any run whose episode-call count is not exactly 1 as infrastructure. V3-A deliberately
runs a two-turn diagnostic control, so applying that rule unchanged mislabels every
two-turn run. This module generalises the SAME causal chain from "exactly one episode
call" to "within the run's permitted turn budget" and changes nothing else.

The v2 classifier is not modified; v2 artifacts keep their frozen classifications.

Attribution constraint carried from the preregistration: the failure surface spans
Alpha representation/instruction -> resident model -> stock OmegaClaw skill/action
contract. Nothing here names a cause; it reports what changed when one factor moved.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import analyze_condition_a as v2_analyze

ARTIFACT = ROOT / "benchmark" / "benchmark-v3-A.json"

SENSORY = v2_analyze.SENSORY
REASONING = v2_analyze.REASONING
OUTPUT_CONTRACT = v2_analyze.OUTPUT_CONTRACT
INFRASTRUCTURE = v2_analyze.INFRASTRUCTURE
PROVIDER_AVAILABILITY = v2_analyze.PROVIDER_AVAILABILITY
PASSED = v2_analyze.PASSED

FAILURE_CLASSES = v2_analyze.FAILURE_CLASSES

#: Terminal states that mean "the run spent its permitted turns", not "the harness broke".
BUDGET_TERMINAL_REASONS = ("episode_provider_budget_exhausted",)


def normalized(text: str | None) -> str:
    return v2_analyze.normalized(text)


def label(failure_class: str | None) -> str:
    return v2_analyze.label(failure_class)


def classify(run: dict[str, Any]) -> str | None:
    """Turn-aware classification. Same chain as v2, generalised to N permitted turns."""
    manifest = run.get("manifest") or {}
    gateway = manifest.get("provider_gateway") or {}
    error_text = (run.get("controller_error") or "").lower()
    fatal = str(gateway.get("fatal_error") or "").lower()
    reason = str(manifest.get("termination_reason") or "")
    budget = int(run.get("turn_budget") or 1)
    episode_calls = (
        (manifest.get("usage_by_phase") or {}).get("episode") or {}
    ).get("calls", 0)

    # 1. harness / upstream
    if any(marker in error_text + fatal for marker in v2_analyze._AVAILABILITY_MARKERS):
        return PROVIDER_AVAILABILITY
    if (not manifest or gateway.get("fatal_error")
            or reason.startswith("container_exited")
            or not 1 <= episode_calls <= budget):
        return INFRASTRUCTURE

    # 2. the run met its criterion
    if run.get("exact_match"):
        return PASSED

    # 3. emission: permitted turns spent, nothing valid on the channel
    response = (run.get("response") or "").strip()
    if reason == "timeout" or reason in BUDGET_TERMINAL_REASONS or not response:
        return OUTPUT_CONTRACT

    # 4. emission: equivalent only after normalisation
    if normalized(response) == normalized(run.get("expected_answer")):
        return OUTPUT_CONTRACT

    # 5. reasoning / composition
    return REASONING


def load(path: Path = ARTIFACT) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def key(run: dict[str, Any]) -> tuple[str, str | None, int]:
    return (run["case_id"], run["representation"], run["turn_budget"])


def outcome(run: dict[str, Any]) -> dict[str, Any]:
    log = run.get("log_analysis") or {}
    return {
        "case_id": run["case_id"],
        "representation": run["representation"],
        "turn_budget": run["turn_budget"],
        "response": run.get("response"),
        "exact_match": bool(run.get("exact_match")),
        "valid_send": bool(log.get("valid_send_emitted")),
        "expected_token_internally": bool(log.get("expected_token_present_internally")),
        "first_turn_with_expected_token": log.get("first_turn_with_expected_token"),
        "first_turn_with_valid_send": log.get("first_turn_with_valid_send"),
        "prompted_turns_observed": log.get("prompted_turns_observed"),
        "raw_idle_ticks": log.get("raw_idle_ticks"),
        "failure_class": classify(run),
        "episode_calls": ((run.get("manifest") or {}).get("usage_by_phase") or {})
                         .get("episode", {}).get("calls"),
        "termination_reason": (run.get("manifest") or {}).get("termination_reason"),
    }


def representation_pairs(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """R1 vs R2/R3/R4, holding resident, task, facts and turn budget fixed."""
    by_key = {key(r): r for r in runs}
    pairs = []
    for run in runs:
        if run["representation"] in (None, "R1_full_symbolic"):
            continue
        baseline = by_key.get((run["case_id"], "R1_full_symbolic", run["turn_budget"]))
        if baseline is None:
            continue
        a, b = bool(baseline.get("exact_match")), bool(run.get("exact_match"))
        pairs.append({
            "case_id": run["case_id"],
            "turn_budget": run["turn_budget"],
            "baseline": "R1_full_symbolic",
            "variant": run["representation"],
            "r1_exact_match": a,
            "variant_exact_match": b,
            "transition": f"{'PASS' if a else 'FAIL'} -> {'PASS' if b else 'FAIL'}",
            "changed": a != b,
        })
    return pairs


def turn_pairs(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """1 turn vs 2 turns, holding representation and resident fixed."""
    by_key = {key(r): r for r in runs}
    pairs = []
    for run in runs:
        if run["turn_budget"] != 1:
            continue
        two = by_key.get((run["case_id"], run["representation"], 2))
        if two is None:
            continue
        a, b = bool(run.get("exact_match")), bool(two.get("exact_match"))
        pairs.append({
            "case_id": run["case_id"],
            "representation": run["representation"],
            "one_turn_exact_match": a,
            "two_turn_exact_match": b,
            "transition": f"{'PASS' if a else 'FAIL'} -> {'PASS' if b else 'FAIL'}",
            "changed": a != b,
        })
    return pairs


def internal_versus_emitted(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Runs where the correct token existed internally but no valid answer emerged."""
    rows = []
    for run in runs:
        log = run.get("log_analysis") or {}
        if log.get("expected_token_present_internally") and not run.get("exact_match"):
            rows.append({
                "case_id": run["case_id"],
                "representation": run["representation"],
                "turn_budget": run["turn_budget"],
                "valid_send": bool(log.get("valid_send_emitted")),
                "response": run.get("response"),
                "failure_class": classify(run),
            })
    return rows


def decompose(runs: list[dict[str, Any]]) -> dict[str, int]:
    counts = {name: 0 for name in FAILURE_CLASSES}
    counts["passed"] = 0
    for run in runs:
        counts[label(classify(run))] += 1
    return counts


def usage(runs: list[dict[str, Any]]) -> dict[str, Any]:
    per_provider: dict[str, dict[str, Any]] = {}
    for run in runs:
        for receipt in run.get("provider_usage", []):
            block = per_provider.setdefault(
                receipt["provider"],
                {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost": 0.0,
                 "models": set(), "phases": {"boot": 0, "episode": 0}})
            block["calls"] += 1
            block["models"].add(receipt["model"])
            block["phases"][receipt["phase"]] += 1
            u = receipt["usage"]
            block["input_tokens"] += u.get("prompt_tokens", 0)
            block["output_tokens"] += u.get("completion_tokens", 0)
            block["cost"] += u.get("cost", 0.0) or 0.0
    for block in per_provider.values():
        block["models"] = sorted(block["models"])
        block["cost"] = round(block["cost"], 6)
    return per_provider


def sensory_calls(runs: list[dict[str, Any]]) -> int:
    total = 0
    for run in runs:
        ingress = (run.get("manifest") or {}).get("ingress") or {}
        if ingress.get("sensory_inference"):
            total += 1
        total += 1 if "sensory_trace" in ingress else 0
    return total


def render(data: dict[str, Any]) -> str:
    runs = data["runs"]
    out = ["case/representation/turns        exact  send  token  class            resp"]
    for run in runs:
        row = outcome(run)
        name = f"{row['case_id']}/{row['representation'] or 'native_text'}/{row['turn_budget']}t"
        response = " ".join((row["response"] or "").split())[:28]
        out.append(f"{name:<32} {row['exact_match']!s:<6} "
                   f"{row['valid_send']!s:<5} "
                   f"{row['expected_token_internally']!s:<6} "
                   f"{label(row['failure_class']):<16} {response!r}")
    out.append(f"\ndecomposition: {json.dumps(decompose(runs))}")
    out.append(f"sensory calls: {sensory_calls(runs)}")
    return "\n".join(out)


def main() -> int:
    data = load()
    print(render(data))
    print(f"\nusage: {json.dumps(usage(data['runs']), indent=2)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
