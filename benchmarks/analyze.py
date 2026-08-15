from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

MULTIMODAL_ROLES = {"multimodal_ingress", "multimodal_tool"}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
            if not isinstance(item, dict):
                raise ValueError(f"{path}:{lineno}: each JSONL row must be an object")
            records.append(item)
    return records


def read_rates(path: Path | None) -> dict[str, dict[str, float]]:
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    models = data.get("models", {})
    if not isinstance(models, dict):
        raise ValueError("rate card must contain an object named 'models'")
    return models


def summarize(records: list[dict[str, Any]], rates: dict[str, dict[str, float]]) -> dict[str, Any]:
    role_calls: Counter[str] = Counter()
    model_calls: Counter[str] = Counter()
    role_tokens: dict[str, dict[str, int]] = defaultdict(lambda: {"input": 0, "output": 0})
    total_input = 0
    total_output = 0
    estimated_cost = 0.0
    priced_calls = 0
    unpriced_calls = 0

    for row in records:
        role = str(row.get("node_role") or "unspecified")
        model = str(row.get("model") or "unspecified")
        input_tokens = int(row.get("input_tokens") or 0)
        output_tokens = int(row.get("output_tokens") or 0)

        role_calls[role] += 1
        model_calls[model] += 1
        role_tokens[role]["input"] += input_tokens
        role_tokens[role]["output"] += output_tokens
        total_input += input_tokens
        total_output += output_tokens

        rate = rates.get(model)
        if rate is None:
            unpriced_calls += 1
            continue
        estimated_cost += (
            input_tokens * float(rate.get("input_per_million", 0.0))
            + output_tokens * float(rate.get("output_per_million", 0.0))
        ) / 1_000_000
        priced_calls += 1

    multimodal_calls = sum(role_calls[role] for role in MULTIMODAL_ROLES)

    return {
        "calls": len(records),
        "multimodal_calls": multimodal_calls,
        "input_tokens": total_input,
        "output_tokens": total_output,
        "total_tokens": total_input + total_output,
        "calls_by_role": dict(sorted(role_calls.items())),
        "tokens_by_role": dict(sorted(role_tokens.items())),
        "calls_by_model": dict(sorted(model_calls.items())),
        "estimated_cost_usd": round(estimated_cost, 8) if priced_calls else None,
        "priced_calls": priced_calls,
        "unpriced_calls": unpriced_calls,
    }


def compare(
    baseline_path: Path,
    alpha_path: Path,
    rates_path: Path | None = None,
) -> dict[str, Any]:
    rates = read_rates(rates_path)
    baseline = summarize(read_jsonl(baseline_path), rates)
    alpha = summarize(read_jsonl(alpha_path), rates)

    delta: dict[str, Any] = {}
    for key in ("calls", "multimodal_calls", "input_tokens", "output_tokens", "total_tokens"):
        delta[key] = alpha[key] - baseline[key]

    if baseline["estimated_cost_usd"] is not None and alpha["estimated_cost_usd"] is not None:
        delta["estimated_cost_usd"] = round(
            alpha["estimated_cost_usd"] - baseline["estimated_cost_usd"], 8
        )
    else:
        delta["estimated_cost_usd"] = None

    return {"baseline": baseline, "alpha": alpha, "alpha_minus_baseline": delta}


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare OmegaClaw and AlphaClaw usage traces")
    parser.add_argument("--baseline", type=Path, required=True, help="Omega baseline JSONL trace")
    parser.add_argument("--alpha", type=Path, required=True, help="Alpha treatment JSONL trace")
    parser.add_argument("--rates", type=Path, help="Optional explicit model rate card")
    args = parser.parse_args()

    print(json.dumps(compare(args.baseline, args.alpha, args.rates), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
