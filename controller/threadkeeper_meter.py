"""Benchmark-only adapter from Omega provider responses to ThreadKeeper accounting.

This file is copied into disposable profiled Omega trees by the controller. It
uses the pinned ThreadKeeper submodule only for recording/accounting. Missing
provider usage invalidates the benchmark instead of being treated as zero.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

THREADKEEPER_SRC = Path("/ThreadKeeper/src")
THREADKEEPER_CONFIG = Path("/ThreadKeeper/threadkeeper.config.yaml")
BENCHMARK_DIR = Path("/benchmark")
RUN_ID_FILE = BENCHMARK_DIR / "run_id"
USAGE_LOG = BENCHMARK_DIR / "usage.jsonl"
RAW_USAGE_LOG = BENCHMARK_DIR / "provider_usage.jsonl"


def _load_budget_tracker():
    if not THREADKEEPER_SRC.is_dir():
        raise RuntimeError(f"ThreadKeeper benchmark dependency missing: {THREADKEEPER_SRC}")
    source = str(THREADKEEPER_SRC)
    if source not in sys.path:
        sys.path.insert(0, source)
    from threadkeeper_budget import BudgetTracker

    return BudgetTracker


def _run_id() -> str:
    try:
        value = RUN_ID_FILE.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError("benchmark run_id is unavailable") from exc
    if not value:
        raise RuntimeError("benchmark run_id is empty")
    return value


def _usage_member(usage: Any, name: str) -> int:
    value = usage.get(name) if isinstance(usage, dict) else getattr(usage, name, None)
    if value is None:
        raise RuntimeError(f"provider response usage is missing {name}")
    value = int(value)
    if value < 0:
        raise RuntimeError(f"provider response usage has negative {name}")
    return value


def _raw_usage(usage: Any) -> dict[str, Any]:
    if isinstance(usage, dict):
        return dict(usage)
    model_dump = getattr(usage, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        if isinstance(dumped, dict):
            return dumped
    to_dict = getattr(usage, "to_dict", None)
    if callable(to_dict):
        dumped = to_dict()
        if isinstance(dumped, dict):
            return dumped
    return {
        "prompt_tokens": _usage_member(usage, "prompt_tokens"),
        "completion_tokens": _usage_member(usage, "completion_tokens"),
        "total_tokens": getattr(usage, "total_tokens", None),
    }


def record_openai_response(model: str, response: Any) -> None:
    """Record one real provider call through Larry Greenblatt's accounting seam.

    ThreadKeeper's runtime-oriented recorder intentionally degrades safely on
    write errors. Benchmarking needs the opposite semantic, so this adapter
    validates provider usage first and verifies the JSONL write happened.
    """
    usage = getattr(response, "usage", None)
    if usage is None:
        raise RuntimeError("provider response did not include usage accounting")

    _usage_member(usage, "prompt_tokens")
    _usage_member(usage, "completion_tokens")
    run_id = _run_id()

    BenchmarkTracker = _load_budget_tracker()
    tracker = BenchmarkTracker(
        config_path=str(THREADKEEPER_CONFIG),
        usage_log=str(USAGE_LOG),
        escalation_log=str(BENCHMARK_DIR / "unused-escalations.jsonl"),
    )

    before = USAGE_LOG.stat().st_size if USAGE_LOG.exists() else 0
    tracker.record_from_openai_response(
        node_role="omega_reasoning",
        model=model,
        resp=response,
        thread_id=run_id,
    )
    after = USAGE_LOG.stat().st_size if USAGE_LOG.exists() else 0
    if after <= before:
        raise RuntimeError("ThreadKeeper did not persist the provider usage record")

    raw_record = {
        "ts": time.time(),
        "thread_id": run_id,
        "node_role": "omega_reasoning",
        "model": model,
        "usage": _raw_usage(usage),
    }
    try:
        with RAW_USAGE_LOG.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(raw_record, sort_keys=True) + "\n")
    except OSError as exc:
        raise RuntimeError("could not persist raw provider usage") from exc
