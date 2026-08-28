"""Derived analysis for Protocol v2 Condition A.

Pure, offline and read-only. This module derives the failure decomposition and the
aggregate tables from the frozen Condition A artifact. It never performs inference,
never launches a container, never rewrites the artifact and never edits a raw receipt,
an exact-match verdict or a frozen-scorer verdict.

Only DERIVED classification lives here. The inputs it reads -- provider receipts,
``exact_match``, and ``sensory_score`` produced by the frozen scorer -- are treated as
immutable evidence.

Decomposition semantics
-----------------------
Failures are attributed to the earliest broken link in the causal chain
sensing -> reasoning -> emission:

``sensory``
    The handoff was not schema-conformant, or the frozen scorer judged at least one
    atomic fact INCORRECT. An ``unknown`` verdict is NOT a sensory failure: it is
    undecidable, excluded from accuracy and reported as reduced coverage. This matches
    the ruling already applied to condition B1.
``reasoning_composition``
    Sensing was sound and a response was emitted, but the answer is wrong.
``output_contract``
    The episode turn completed, but no valid final response reached the channel, or
    the response is only equivalent to the expected answer after normalisation. A
    recoverable intent is not a pass.
``infrastructure``
    The harness itself failed: container exit, gateway fatal error, budget exhaustion,
    or an episode turn that did not consume exactly one provider call.
``provider_availability``
    The upstream provider refused or was unreachable.

A run that met its exact-match criterion is a pass and is never given a failure class.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import score_handoff

ARTIFACT = ROOT / "benchmark" / "benchmark-v2-A.json"
ITEMS = ROOT / "benchmark" / "items.json"

CONDITIONS = ("text_control", "image_only", "image_text")
EXACT_MATCH_CONDITIONS = ("text_control", "image_text")

SENSORY = "sensory"
REASONING = "reasoning_composition"
OUTPUT_CONTRACT = "output_contract"
INFRASTRUCTURE = "infrastructure"
PROVIDER_AVAILABILITY = "provider_availability"

FAILURE_CLASSES = (SENSORY, REASONING, OUTPUT_CONTRACT,
                   INFRASTRUCTURE, PROVIDER_AVAILABILITY)

#: ``classify`` returns this for a run that passed. Stored as ``null`` in the artifact.
PASSED = None

_AVAILABILITY_MARKERS = ("429", "502", "503", "no endpoints", "rate limit",
                         "unavailable", "upstream")


def normalized(text: str | None) -> str:
    """Casefold and strip every non-alphanumeric character."""
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def label(failure_class: str | None) -> str:
    """Human-readable class name; passes report as ``passed``."""
    return failure_class if failure_class else "passed"


def sensory_failed(run: dict[str, Any]) -> bool:
    """True only for a broken schema or an INCORRECT fact -- never for ``unknown``."""
    scored = run.get("sensory_score")
    if not scored:
        return False
    if not scored.get("schema_conformant"):
        return True
    return any(v["verdict"] == score_handoff.INCORRECT
               for v in scored.get("verdicts", []))


def classify(run: dict[str, Any]) -> str | None:
    """Classify one run. Pure: the run mapping is read, never mutated."""
    manifest = run.get("manifest") or {}
    gateway = manifest.get("provider_gateway") or {}
    error_text = (run.get("controller_error") or "").lower()
    fatal = str(gateway.get("fatal_error") or "").lower()
    reason = str(manifest.get("termination_reason") or "")
    episode_calls = (
        (manifest.get("usage_by_phase") or {}).get("episode") or {}
    ).get("calls", 0)

    # 1. harness / upstream
    if any(marker in error_text + fatal for marker in _AVAILABILITY_MARKERS):
        return PROVIDER_AVAILABILITY
    if (not manifest or gateway.get("fatal_error")
            or reason.startswith("container_exited")
            or reason == "episode_provider_budget_exhausted"
            or episode_calls != 1):
        return INFRASTRUCTURE

    condition = run["condition"]
    broken_sensing = sensory_failed(run)

    # 2. sensing
    if condition == "image_only":
        # Graded solely on the sensory transformation; the agent's utterance is
        # recorded but is deliberately not an exact-match criterion.
        return SENSORY if broken_sensing else PASSED
    if condition == "image_text" and broken_sensing and not run.get("exact_match"):
        return SENSORY

    # A run that met its exact-match criterion is a pass, full stop.
    if run.get("exact_match"):
        return PASSED

    # 3. emission: the episode turn completed but nothing valid reached the channel
    if reason == "timeout" or not (run.get("response") or "").strip():
        return OUTPUT_CONTRACT

    # 4. emission: equivalent only after normalisation -- still a failure
    if normalized(run.get("response")) == normalized(run.get("expected_answer")):
        return OUTPUT_CONTRACT

    # 5. reasoning / composition
    return REASONING


def decompose(runs: list[dict[str, Any]]) -> dict[str, int]:
    """Count runs per failure class. Does not mutate ``runs``."""
    counts = {name: 0 for name in FAILURE_CLASSES}
    counts["passed"] = 0
    for run in runs:
        counts[label(classify(run))] += 1
    return counts


def exact_match_rate(runs: list[dict[str, Any]], condition: str) -> tuple[int, int]:
    subset = [r for r in runs if r["condition"] == condition]
    return sum(1 for r in subset if r.get("exact_match")), len(subset)


def image_only_aggregate(runs: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [r["sensory_score"] for r in runs
              if r["condition"] == "image_only" and r.get("sensory_score")]
    return score_handoff.aggregate(scored) if scored else {}


def conditional_exact_match(runs: list[dict[str, Any]]) -> tuple[int, int]:
    """image+text exact match over runs whose handoff contained no INCORRECT fact."""
    subset = [r for r in runs
              if r["condition"] == "image_text" and not sensory_failed(r)]
    return sum(1 for r in subset if r.get("exact_match")), len(subset)


def usage_totals(runs: list[dict[str, Any]], phase: str) -> dict[str, int]:
    calls = tokens_in = tokens_out = 0
    for run in runs:
        block = ((run.get("manifest") or {}).get("usage_by_phase") or {}).get(phase, {})
        calls += block.get("calls", 0)
        tokens_in += block.get("input_tokens", 0)
        tokens_out += block.get("output_tokens", 0)
    return {"calls": calls, "input_tokens": tokens_in, "output_tokens": tokens_out}


def sensory_totals(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Only runs that actually issued a sensory call are counted."""
    called = [r for r in runs if r.get("sensory_model_resolved")]
    return {
        "calls": len(called),
        "input_tokens": sum(r["sensory_tokens"][0] for r in called),
        "output_tokens": sum(r["sensory_tokens"][1] for r in called),
        "requested_models": sorted({r["sensory_model_requested"] for r in called}),
        "resolved_models": sorted({r["sensory_model_resolved"] for r in called}),
    }


def bounds_respected(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return the runs that broke 1 boot + 1 episode. Empty means every run held."""
    violations = []
    for run in runs:
        usage = (run.get("manifest") or {}).get("usage_by_phase") or {}
        boot = usage.get("boot", {}).get("calls", 0)
        episode = usage.get("episode", {}).get("calls", 0)
        if boot != 1 or episode != 1:
            violations.append({"item_id": run["item_id"], "condition": run["condition"],
                               "boot_calls": boot, "episode_calls": episode})
    return violations


def verify_stored_classes(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Recompute every class and report disagreements with the frozen artifact."""
    mismatches = []
    for run in data["runs"]:
        derived = classify(run)
        if run.get("failure_class") != derived:
            mismatches.append({"item_id": run["item_id"], "condition": run["condition"],
                               "stored": run.get("failure_class"), "derived": derived})
    return mismatches


def load(path: Path = ARTIFACT) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def render(data: dict[str, Any]) -> str:
    runs = data["runs"]
    items = json.loads(ITEMS.read_text(encoding="utf-8"))["items"]
    out: list[str] = []
    width = 26

    out.append(f"{'item':<{width}}{'text control':<26}{'image only':<24}{'image + text':<26}")
    for item in items:
        cells = []
        for condition in CONDITIONS:
            run = next((r for r in runs if r["item_id"] == item["item_id"]
                        and r["condition"] == condition), None)
            if run is None:
                cells.append("(not run)")
                continue
            cls = classify(run)
            suffix = "" if cls is PASSED else f" [{cls}]"
            if condition == "image_only":
                scored = run.get("sensory_score") or {}
                cells.append(f"{scored.get('correct','-')}/{scored.get('expected','-')}"
                             f" facts{suffix}")
            else:
                verdict = "PASS" if run.get("exact_match") else "FAIL"
                text = (run.get("response") or "").strip().replace("\n", " ")[:12]
                cells.append(f"{verdict} {text!r}{suffix}")
        out.append(f"{item['item_id']:<{width}}{cells[0]:<26}{cells[1]:<24}{cells[2]:<26}")

    for condition in EXACT_MATCH_CONDITIONS:
        hit, total = exact_match_rate(runs, condition)
        out.append(f"\n{condition} exact match: {hit}/{total}")

    aggregate = image_only_aggregate(runs)
    out.append("\nimage-only sensory (frozen scorer):")
    for key in ("schema_compliance_rate", "atomic_fact_yield",
                "atomic_fact_accuracy", "scoring_coverage"):
        out.append(f"  {key:<24}{aggregate.get(key)}")

    hit, total = conditional_exact_match(runs)
    out.append(f"\nimage+text exact match | no INCORRECT sensory fact: {hit}/{total}")

    out.append("\nfailure decomposition:")
    for name, count in decompose(runs).items():
        out.append(f"  {name:<24}{count}")

    boot, episode = usage_totals(runs, "boot"), usage_totals(runs, "episode")
    out.append(f"\nASICloud boot   : {boot}")
    out.append(f"ASICloud episode: {episode}")
    out.append(f"sensory         : {sensory_totals(runs)}")
    out.append(f"\nbound violations (1 boot + 1 episode): {bounds_respected(runs) or 'NONE'}")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, default=ARTIFACT)
    parser.add_argument("--verify", action="store_true",
                        help="exit non-zero if stored classes disagree with derivation")
    args = parser.parse_args(argv)

    data = load(args.artifact)
    print(render(data))
    if args.verify:
        mismatches = verify_stored_classes(data)
        if mismatches:
            print(f"\nSTORED/DERIVED MISMATCH: {json.dumps(mismatches, indent=2)}")
            return 1
        print("\nstored failure classes match derivation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
