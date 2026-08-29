"""Derived analysis for Protocol v3-B. Pure, offline, read-only.

Every headline figure is recomputed from the raw receipts in
``benchmark/benchmark-v3-B.json``. Nothing here re-runs a call, repairs a perception
output, or substitutes a catalog estimate for a missing receipt cost.

Three results are kept strictly apart, per the preregistration:

``A`` architecture-invariant call reduction  -- multimodal calls avoided, durable
``B`` measured current-price savings         -- receipt dollars, provider/price dependent
``C`` success-adjusted utility               -- cost per SUCCESSFUL episode

They are never collapsed into one "economic score". A cheaper failing arm is never
reported as superior, and a cell with zero successes has an UNDEFINED cost per success --
not zero, not infinity.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import economics_v3

ARTIFACT = ROOT / "benchmark" / "benchmark-v3-B.json"
GROUND_TRUTH = ROOT / "benchmark" / "v3b-ground-truth.json"

E1 = economics_v3.E1_MULTIMODAL_RESIDENT
E2 = economics_v3.E2_ALPHACLAW
E3 = economics_v3.E3_TEXT_ORACLE

AVAILABILITY = "provider_availability"


def load(path: Path = ARTIFACT) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def ground_truth() -> dict[str, Any]:
    return json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))


def episodes(data: dict[str, Any]) -> list[dict[str, Any]]:
    return data["episodes"]


# --- outcome classification ---------------------------------------------------


def outcome(episode: dict[str, Any]) -> str:
    """``success``, ``provider_availability`` or ``incorrect``. No judge."""
    if episode["terminated"] != "completed":
        errors = " ".join(str(call.get("error") or "") for call in episode["calls"])
        return AVAILABILITY if any(marker in errors for marker in
                                   ("429", "502", "503", "rate-limited",
                                    "temporarily")) else "infrastructure"
    return "success" if episode["exact_match"] else "incorrect"


def succeeded(episode: dict[str, Any]) -> bool:
    return outcome(episode) == "success"


# --- observed call structure --------------------------------------------------


def is_reasoning(call: dict[str, Any]) -> bool:
    """A reasoning call carries a step index; the perception call does not.

    The receipt's ``kind`` field records MODALITY (multimodal / text), so role is read
    from the presence of ``step`` rather than from ``kind``.
    """
    return call.get("step") is not None


def observed_calls(episode: dict[str, Any]) -> dict[str, int]:
    calls = episode["calls"]
    return {
        "multimodal_calls": sum(1 for c in calls if c["kind"] == "multimodal"),
        "text_calls": sum(1 for c in calls if c["kind"] == "text"),
        "perception_calls": sum(1 for c in calls if not is_reasoning(c)),
        "reasoning_calls": sum(1 for c in calls if is_reasoning(c)),
        "reasoning_calls_with_image": sum(1 for c in calls
                                          if is_reasoning(c) and c["carries_image"]),
        "total_calls": len(calls),
    }


def call_totals(data: dict[str, Any]) -> dict[str, Any]:
    by_arm: dict[str, dict[str, int]] = {}
    for episode in episodes(data):
        counts = observed_calls(episode)
        block = by_arm.setdefault(episode["architecture"],
                                  {"multimodal_calls": 0, "text_calls": 0,
                                   "perception_calls": 0, "episodes": 0})
        block["multimodal_calls"] += counts["multimodal_calls"]
        block["text_calls"] += counts["text_calls"]
        block["perception_calls"] += counts["perception_calls"]
        block["episodes"] += 1
    totals = {
        "by_arm": by_arm,
        "multimodal_calls": sum(b["multimodal_calls"] for b in by_arm.values()),
        "text_calls": sum(b["text_calls"] for b in by_arm.values()),
    }
    totals["total_calls"] = totals["multimodal_calls"] + totals["text_calls"]
    return totals


# --- A. architecture-invariant call reduction ---------------------------------


def multimodal_avoidance(data: dict[str, Any]) -> list[dict[str, Any]]:
    """E1 vs E2 multimodal calls per depth, observed against the frozen expectation.

    Only episodes where BOTH arms completed are comparable; a depth with an
    availability failure on either side is reported as not comparable rather than
    quietly averaged.
    """
    rows = []
    for depth in ground_truth()["depths"]:
        expected = economics_v3.expected_call_structure(depth)
        pairs = []
        for item in ground_truth()["items"]:
            e1 = _find(data, E1, item["item_id"], depth)
            e2 = _find(data, E2, item["item_id"], depth)
            if e1 is None or e2 is None:
                continue
            if outcome(e1) == AVAILABILITY or outcome(e2) == AVAILABILITY:
                continue
            pairs.append((observed_calls(e1)["multimodal_calls"],
                          observed_calls(e2)["multimodal_calls"]))
        comparable = len(pairs)
        rows.append({
            "depth": depth,
            "comparable_item_pairs": comparable,
            "expected_e1_multimodal": expected[E1]["multimodal_calls"],
            "expected_e2_multimodal": expected[E2]["multimodal_calls"],
            "expected_avoided": expected["multimodal_calls_avoided"],
            "expected_avoidance_fraction": expected["multimodal_avoidance_fraction"],
            "observed_e1_multimodal": [a for a, _ in pairs],
            "observed_e2_multimodal": [b for _, b in pairs],
            "observed_avoided": [a - b for a, b in pairs],
            "receipts_match_expectation": all(
                a == expected[E1]["multimodal_calls"]
                and b == expected[E2]["multimodal_calls"] for a, b in pairs),
        })
    return rows


def _find(data: dict[str, Any], arm: str, item_id: str,
          depth: int) -> dict[str, Any] | None:
    for episode in episodes(data):
        if (episode["architecture"] == arm and episode["item_id"] == item_id
                and episode["depth"] == depth):
            return episode
    return None


# --- B. measured current-price cost -------------------------------------------


def episode_cost(episode: dict[str, Any]) -> dict[str, Any]:
    """Sum receipt dollars. Any call without a receipt cost makes the total partial."""
    cost, tokens_in, tokens_out, missing = 0.0, 0, 0, 0
    for call in episode["calls"]:
        if call.get("cost_available"):
            cost += float(call["cost"])
        elif call.get("error") is None:
            missing += 1
        tokens_in += call.get("input_tokens") or 0
        tokens_out += call.get("output_tokens") or 0
    return {
        "measured_cost_usd": round(cost, 8),
        "input_tokens": tokens_in,
        "output_tokens": tokens_out,
        "calls_without_receipt_cost": missing,
        "cost_complete": missing == 0,
        "cost_provenance": economics_v3.MEASURED,
    }


def cost_by_arm_depth(data: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for arm in economics_v3.ARCHITECTURES:
        for depth in ground_truth()["depths"]:
            cells = [e for e in episodes(data)
                     if e["architecture"] == arm and e["depth"] == depth]
            costs = [episode_cost(e) for e in cells]
            successes = [e for e in cells if succeeded(e)]
            total = round(sum(c["measured_cost_usd"] for c in costs), 8)
            rows.append({
                "architecture": arm,
                "depth": depth,
                "episodes": len(cells),
                "successful_episodes": len(successes),
                "availability_failures": sum(1 for e in cells
                                             if outcome(e) == AVAILABILITY),
                "measured_cost_usd": total,
                "input_tokens": sum(c["input_tokens"] for c in costs),
                "output_tokens": sum(c["output_tokens"] for c in costs),
                "cost_complete": all(c["cost_complete"] for c in costs),
                **economics_v3.cost_per_successful_episode(
                    total_cost=total, successful_episodes=len(successes),
                    provenance=economics_v3.MEASURED),
            })
    return rows


def e1_vs_e2_savings(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Measured dollar difference per depth over episodes BOTH arms completed."""
    rows = []
    for depth in ground_truth()["depths"]:
        e1_cost = e2_cost = 0.0
        pairs = 0
        for item in ground_truth()["items"]:
            e1 = _find(data, E1, item["item_id"], depth)
            e2 = _find(data, E2, item["item_id"], depth)
            if not e1 or not e2:
                continue
            if outcome(e1) == AVAILABILITY or outcome(e2) == AVAILABILITY:
                continue
            e1_cost += episode_cost(e1)["measured_cost_usd"]
            e2_cost += episode_cost(e2)["measured_cost_usd"]
            pairs += 1
        rows.append({
            "depth": depth,
            "comparable_item_pairs": pairs,
            "e1_measured_cost_usd": round(e1_cost, 8),
            "e2_measured_cost_usd": round(e2_cost, 8),
            "measured_savings_usd": round(e1_cost - e2_cost, 8),
            "measured_savings_fraction": (round(1 - e2_cost / e1_cost, 6)
                                          if e1_cost else None),
            "alphaclaw_cheaper": (e2_cost < e1_cost) if pairs else None,
            "cost_provenance": economics_v3.MEASURED,
        })
    return rows


def break_even(data: dict[str, Any]) -> dict[str, Any]:
    """Observed sign change across the frozen depths. No interpolation."""
    rows = [r for r in e1_vs_e2_savings(data) if r["comparable_item_pairs"]]
    cheaper = [r["depth"] for r in rows if r["alphaclaw_cheaper"]]
    dearer = [r["depth"] for r in rows if r["alphaclaw_cheaper"] is False]
    return {
        "depths_where_alphaclaw_cheaper": cheaper,
        "depths_where_alphaclaw_dearer": dearer,
        "observed_sign_change": bool(cheaper and dearer),
        "interpolated_break_even_point": None,
        "note": ("Observed behaviour across the frozen depths only. No break-even point "
                 "is interpolated; any such figure would be an estimate, and none is "
                 "reported."),
    }


# --- C. success-adjusted utility ----------------------------------------------


def success_table(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [{
        "episode_index": e["episode_index"],
        "architecture": e["architecture"],
        "item_id": e["item_id"],
        "depth": e["depth"],
        "expected_answer": e["expected_answer"],
        "final_response": e["final_response"],
        "exact_match": bool(e["exact_match"]),
        "outcome": outcome(e),
        "terminated": e["terminated"],
    } for e in episodes(data)]


def success_by_arm_depth(data: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for arm in economics_v3.ARCHITECTURES:
        for depth in ground_truth()["depths"]:
            cells = [e for e in episodes(data)
                     if e["architecture"] == arm and e["depth"] == depth]
            rows.append({
                "architecture": arm, "depth": depth,
                "attempted": len(cells),
                "successful": sum(1 for e in cells if succeeded(e)),
                "incorrect": sum(1 for e in cells if outcome(e) == "incorrect"),
                "availability_failures": sum(1 for e in cells
                                             if outcome(e) == AVAILABILITY),
            })
    return rows


# --- E2 integrity -------------------------------------------------------------


def e2_fidelity(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Perception fidelity and handoff reuse. Perception output is never repaired."""
    truth = {item["item_id"]: item for item in ground_truth()["items"]}
    rows = []
    for episode in episodes(data):
        if episode["architecture"] != E2:
            continue
        handoff = episode.get("handoff") or {}
        raw = handoff.get("raw") or ""
        parsed, facts_correct = None, False
        try:
            parsed = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
            numbers = (parsed.get("observation") or {}).get("numbers_left_to_right")
            facts_correct = numbers == truth[episode["item_id"]]["integers"]
        except (ValueError, KeyError, AttributeError):
            parsed = None

        reasoning = [c for c in episode["calls"] if is_reasoning(c)]
        evidence_digests = {c.get("evidence_sha256") for c in reasoning}
        rows.append({
            "item_id": episode["item_id"],
            "depth": episode["depth"],
            "perception_calls": sum(1 for c in episode["calls"]
                                    if not is_reasoning(c)),
            "handoff_sha256": handoff.get("raw_sha256"),
            "handoff_parsed": parsed is not None,
            "all_required_facts_present": facts_correct,
            "reasoning_calls": len(reasoning),
            "distinct_evidence_digests": len(evidence_digests),
            "same_handoff_reused": len(evidence_digests) <= 1,
            "handoff_matches_reasoning_evidence": evidence_digests <= {
                handoff.get("raw_sha256")},
            "any_reasoning_call_carried_image": any(c["carries_image"]
                                                    for c in reasoning),
            "outcome": outcome(episode),
        })
    return rows


# --- integrity ----------------------------------------------------------------


def model_receipts(data: dict[str, Any]) -> dict[str, Any]:
    requested, resolved = set(), set()
    for episode in episodes(data):
        for call in episode["calls"]:
            requested.add(call.get("requested_model"))
            if call.get("resolved_model"):
                resolved.add(call["resolved_model"])
    return {"requested": sorted(x for x in requested if x),
            "resolved": sorted(resolved)}


def totals(data: dict[str, Any]) -> dict[str, Any]:
    cost = tokens_in = tokens_out = 0.0
    missing = 0
    for episode in episodes(data):
        block = episode_cost(episode)
        cost += block["measured_cost_usd"]
        tokens_in += block["input_tokens"]
        tokens_out += block["output_tokens"]
        missing += block["calls_without_receipt_cost"]
    calls = call_totals(data)
    return {
        "multimodal_calls": calls["multimodal_calls"],
        "text_calls": calls["text_calls"],
        "total_calls": calls["total_calls"],
        "input_tokens": int(tokens_in),
        "output_tokens": int(tokens_out),
        "measured_cost_usd": round(cost, 8),
        "calls_without_receipt_cost": missing,
        "cost_provenance": economics_v3.MEASURED,
        "estimated_values_reported": False,
    }


def render(data: dict[str, Any]) -> str:
    out = ["arm  item      N  outcome                match  response"]
    for row in success_table(data):
        out.append(f"{row['architecture'][:2]:<4} {row['item_id']:<9} "
                   f"{row['depth']:<2} {row['outcome']:<22} "
                   f"{row['exact_match']!s:<6} {(row['final_response'] or '').strip()[:10]!r}")
    out.append(f"\ntotals: {json.dumps(totals(data))}")
    out.append(f"models: {json.dumps(model_receipts(data))}")
    return "\n".join(out)


def main() -> int:
    data = load()
    print(render(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
