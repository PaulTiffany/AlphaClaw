"""Host-side adapter from provider responses to pinned ThreadKeeper accounting."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
THREADKEEPER_SRC = ROOT / "external" / "ThreadKeeper" / "src"
THREADKEEPER_CONFIG = ROOT / "external" / "ThreadKeeper" / "threadkeeper.config.yaml"


def _load_budget_tracker():
    if not THREADKEEPER_SRC.is_dir():
        raise RuntimeError(f"ThreadKeeper benchmark dependency missing: {THREADKEEPER_SRC}")
    source = str(THREADKEEPER_SRC)
    if source not in sys.path:
        sys.path.insert(0, source)
    from threadkeeper_budget import BudgetTracker

    return BudgetTracker


def _usage_member(usage: dict[str, Any], *names: str) -> int:
    for name in names:
        if name in usage and usage[name] is not None:
            value = int(usage[name])
            if value < 0:
                raise RuntimeError(f"provider response usage has negative {name}")
            return value
    raise RuntimeError(f"provider response usage is missing {'/'.join(names)}")


class ThreadKeeperRecorder:
    """Use ThreadKeeper's recorder without importing its routing or escalation decisions."""

    def __init__(self, *, run_dir: Path, run_id: str) -> None:
        self.run_dir = run_dir
        self.run_id = run_id
        self.usage_log = run_dir / "usage.jsonl"
        self.raw_usage_log = run_dir / "provider_usage.jsonl"
        self.usage_log.touch(exist_ok=True)
        self.raw_usage_log.touch(exist_ok=True)

        BudgetTracker = _load_budget_tracker()
        self.tracker = BudgetTracker(
            config_path=str(THREADKEEPER_CONFIG),
            usage_log=str(self.usage_log),
            escalation_log=str(run_dir / "unused-escalations.jsonl"),
        )

    def record(
        self,
        *,
        provider: str,
        model: str,
        phase: str,
        response_payload: dict[str, Any],
    ) -> None:
        usage = response_payload.get("usage")
        if not isinstance(usage, dict):
            raise RuntimeError("provider response did not include usage accounting")

        input_tokens = _usage_member(usage, "prompt_tokens", "input_tokens")
        output_tokens = _usage_member(usage, "completion_tokens", "output_tokens")
        normalized = SimpleNamespace(
            usage=SimpleNamespace(
                prompt_tokens=input_tokens,
                completion_tokens=output_tokens,
            )
        )

        before = self.usage_log.stat().st_size
        self.tracker.record_from_openai_response(
            node_role=f"omega_{phase}",
            model=model,
            resp=normalized,
            thread_id=self.run_id,
        )
        after = self.usage_log.stat().st_size
        if after <= before:
            raise RuntimeError("ThreadKeeper did not persist the provider usage record")

        raw_record = {
            "ts": time.time(),
            "thread_id": self.run_id,
            "node_role": f"omega_{phase}",
            "phase": phase,
            "provider": provider,
            "model": model,
            "usage": usage,
        }
        try:
            with self.raw_usage_log.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(raw_record, sort_keys=True, default=str) + "\n")
        except OSError as exc:
            raise RuntimeError("could not persist raw provider usage") from exc
