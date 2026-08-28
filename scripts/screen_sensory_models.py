"""Screen candidate sensory models against the deterministic benchmark suite.

OpenRouter only. This harness never touches ASICloud, never starts Omega, never
starts a container, and never runs the controller. It exists so the sensory model can
be selected by the pre-registered rule BEFORE any downstream AlphaClaw result is
observed.

Model identifiers must be explicit. ``openrouter/free`` is rejected: it is a
nondeterministic router, and two byte-identical perception requests were observed
reaching two different models with different contract compliance. The exact sensory
model is part of the experimental condition.

Reuses the frozen sensory boundary in ``ingress/openrouter_image.py`` unchanged, so
what is screened is the system under test rather than a reimplementation.

Usage:
    python scripts/screen_sensory_models.py --stimuli benchmark/stimuli \\
        --ground-truth benchmark/items.json --output benchmark/screening.json \\
        --repeats 2
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ingress"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import openrouter_image
import score_handoff

CANDIDATE_MODELS = (
    "dots-studio/dots-3-note-preview:free",
    "google/gemma-4-26b-a4b-it:free",
    "google/gemma-4-31b-it:free",
)

FORBIDDEN_MODELS = frozenset({"openrouter/free"})


def screen_model(
    model_id: str,
    items: list[dict],
    stimuli: Path,
    api_key: str,
    repeats: int,
    runner=openrouter_image.run,
) -> dict:
    """Run every item ``repeats`` times through one explicit sensory model."""
    if model_id in FORBIDDEN_MODELS:
        raise ValueError(f"{model_id} is a nondeterministic router, not a benchmark condition")

    per_repeat: list[list[dict]] = []
    calls: list[dict] = []
    for _ in range(repeats):
        scored_this_repeat = []
        for item in items:
            image = stimuli / item["image_filename"]
            record = {
                "item_id": item["item_id"],
                "requested_model": model_id,
                "resolved_model": None,
                "request_success": False,
                "error": None,
                "input_tokens": 0,
                "output_tokens": 0,
            }
            try:
                handoff, trace = runner(image, model_id, api_key)
                record["request_success"] = True
                record["resolved_model"] = trace.get("model")
                record["input_tokens"] = trace.get("input_tokens", 0)
                record["output_tokens"] = trace.get("output_tokens", 0)
            except Exception as exc:  # noqa: BLE001 - a failed call is benchmark evidence
                handoff = None
                record["error"] = f"{type(exc).__name__}: {exc}"

            scored = score_handoff.score_item(handoff, item["facts"])
            record.update(
                {
                    "schema_conformant": scored["schema_conformant"],
                    "correct": scored["correct"],
                    "scoreable": scored["scoreable"],
                    "expected": scored["expected"],
                    "handoff": handoff,
                }
            )
            calls.append(record)
            scored_this_repeat.append(scored)
        per_repeat.append(scored_this_repeat)

    flat = [s for repeat in per_repeat for s in repeat]
    agg = score_handoff.aggregate(flat)
    outputs = [c["output_tokens"] for c in calls]
    return {
        "model_id": model_id,
        "repeats": repeats,
        **agg,
        "repeat_stability": score_handoff.repeat_stability(per_repeat),
        "mean_output_tokens": statistics.mean(outputs) if outputs else 0.0,
        "mean_input_tokens": statistics.mean([c["input_tokens"] for c in calls]) if calls else 0.0,
        "resolved_models": sorted({c["resolved_model"] for c in calls if c["resolved_model"]}),
        "request_failures": sum(1 for c in calls if not c["request_success"]),
        "calls_detail": calls,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stimuli", type=Path, required=True)
    parser.add_argument("--ground-truth", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--models", nargs="*", default=list(CANDIDATE_MODELS))
    args = parser.parse_args()

    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        print("OPENROUTER_API_KEY is required for sensory screening", file=sys.stderr)
        return 1

    doc = json.loads(args.ground_truth.read_text(encoding="utf-8"))
    items = doc["items"]

    summaries = []
    for model_id in args.models:
        print(f"screening {model_id} ...", flush=True)
        summaries.append(screen_model(model_id, items, args.stimuli, api_key, args.repeats))

    selected = score_handoff.select_sensory_model(
        [
            {
                "model_id": s["model_id"],
                "atomic_fact_yield": s["atomic_fact_yield"],
                "schema_compliance_rate": s["schema_compliance_rate"],
                "repeat_stability": s["repeat_stability"],
                "mean_output_tokens": s["mean_output_tokens"],
            }
            for s in summaries
        ]
    )

    report = {
        "schema_version": 1,
        "selection_rule": score_handoff.SELECTION_RULE,
        "candidates": summaries,
        "selected_model": selected["model_id"],
        "ground_truth_total_facts": doc["total_atomic_facts"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for s in summaries:
        print(
            f"  {s['model_id']:<40} yield={s['atomic_fact_yield']:.3f} "
            f"schema={s['schema_compliance_rate']:.3f} "
            f"stability={s['repeat_stability']} "
            f"out_tokens={s['mean_output_tokens']:.0f}"
        )
    print(f"selected: {selected['model_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
