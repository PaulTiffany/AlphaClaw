"""Isolated one-shot ThreadKeeper accounting worker.

This process receives token counts only. It does not receive provider credentials,
prompt text, model response text, Docker control, or Alpha envelopes.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


def _load_budget_tracker(module_path: Path):
    if not module_path.is_file():
        raise RuntimeError(f"pinned ThreadKeeper module missing: {module_path}")
    spec = importlib.util.spec_from_file_location(
        "alphaclaw_pinned_threadkeeper_budget",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load pinned ThreadKeeper accounting module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.BudgetTracker


def _require_int(payload: dict[str, Any], key: str) -> int:
    value = int(payload[key])
    if value < 0:
        raise ValueError(f"{key} must be non-negative")
    return value


def run(payload: dict[str, Any]) -> dict[str, Any]:
    module_path = Path(str(payload["threadkeeper_module"])).resolve()
    config_path = Path(str(payload["config_path"])).resolve()
    usage_log = Path(str(payload["usage_log"])).resolve()
    escalation_log = Path(str(payload["escalation_log"])).resolve()
    run_id = str(payload["run_id"])
    node_role = str(payload["node_role"])
    model = str(payload["model"])
    input_tokens = _require_int(payload, "input_tokens")
    output_tokens = _require_int(payload, "output_tokens")

    if not run_id or not node_role or not model:
        raise ValueError("run_id, node_role, and model must be non-empty")

    usage_log.parent.mkdir(parents=True, exist_ok=True)
    usage_log.touch(exist_ok=True)
    before = usage_log.stat().st_size

    BudgetTracker = _load_budget_tracker(module_path)
    tracker = BudgetTracker(
        config_path=str(config_path),
        usage_log=str(usage_log),
        escalation_log=str(escalation_log),
    )
    response = SimpleNamespace(
        usage=SimpleNamespace(
            prompt_tokens=input_tokens,
            completion_tokens=output_tokens,
        )
    )
    tracker.record_from_openai_response(
        node_role=node_role,
        model=model,
        resp=response,
        thread_id=run_id,
    )

    after = usage_log.stat().st_size
    if after <= before:
        raise RuntimeError("ThreadKeeper did not persist the accounting record")

    return {
        "ok": True,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "bytes_appended": after - before,
    }


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise TypeError("worker input must be a JSON object")
        result = run(payload)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1

    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
