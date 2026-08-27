"""Host-side adapter to isolated pinned ThreadKeeper accounting."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
THREADKEEPER_MODULE = ROOT / "external" / "ThreadKeeper" / "src" / "threadkeeper_budget.py"
THREADKEEPER_CONFIG = ROOT / "external" / "ThreadKeeper" / "threadkeeper.config.yaml"
WORKER = Path(__file__).with_name("threadkeeper_worker.py")

_ENV_ALLOWLIST = (
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "WINDIR",
    "COMSPEC",
    "TEMP",
    "TMP",
    "TMPDIR",
)


def _usage_member(usage: dict[str, Any], *names: str) -> int:
    for name in names:
        if name in usage and usage[name] is not None:
            value = int(usage[name])
            if value < 0:
                raise RuntimeError(f"provider response usage has negative {name}")
            return value
    raise RuntimeError(f"provider response usage is missing {'/'.join(names)}")


def sanitized_worker_env() -> dict[str, str]:
    """Return the small environment inherited by third-party accounting code."""
    return {key: os.environ[key] for key in _ENV_ALLOWLIST if key in os.environ}


def worker_command() -> list[str]:
    """Use Python isolated mode so cwd/user-site/PYTHON* cannot widen imports."""
    return [sys.executable, "-I", str(WORKER)]


class ThreadKeeperRecorder:
    """Invoke ThreadKeeper as a one-shot accounting witness, never as controller code."""

    def __init__(self, *, run_dir: Path, run_id: str) -> None:
        self.run_dir = run_dir.resolve()
        self.run_id = run_id
        self.usage_log = self.run_dir / "usage.jsonl"
        self.raw_usage_log = self.run_dir / "provider_usage.jsonl"
        self.usage_log.touch(exist_ok=True)
        self.raw_usage_log.touch(exist_ok=True)

        if not THREADKEEPER_MODULE.is_file():
            raise RuntimeError(f"ThreadKeeper benchmark dependency missing: {THREADKEEPER_MODULE}")
        if not WORKER.is_file():
            raise RuntimeError(f"ThreadKeeper worker missing: {WORKER}")

    def record(
        self,
        *,
        provider: str,
        model: str,
        phase: str,
        response_payload: dict[str, Any],
    ) -> None:
        """Send token counts only to the isolated ThreadKeeper worker."""
        del provider  # Provider identity remains in the controller-owned raw receipt.
        usage = response_payload.get("usage")
        if not isinstance(usage, dict):
            raise TypeError("provider response did not include usage accounting")

        request = {
            "threadkeeper_module": str(THREADKEEPER_MODULE.resolve()),
            "config_path": str(THREADKEEPER_CONFIG.resolve()),
            "usage_log": str(self.usage_log),
            "escalation_log": str(self.run_dir / "unused-escalations.jsonl"),
            "run_id": self.run_id,
            "node_role": f"omega_{phase}",
            "model": model,
            "input_tokens": _usage_member(usage, "prompt_tokens", "input_tokens"),
            "output_tokens": _usage_member(usage, "completion_tokens", "output_tokens"),
        }

        result = subprocess.run(
            worker_command(),
            input=json.dumps(request, sort_keys=True),
            capture_output=True,
            text=True,
            cwd=self.run_dir,
            env=sanitized_worker_env(),
            timeout=30,
            check=False,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()[:1000]
            raise RuntimeError(f"isolated ThreadKeeper accounting failed: {detail}")

        try:
            response = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("isolated ThreadKeeper worker returned invalid JSON") from exc
        if not isinstance(response, dict) or response.get("ok") is not True:
            raise RuntimeError("isolated ThreadKeeper worker did not confirm accounting")
