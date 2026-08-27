"""Run one bounded, metered AlphaClaw -> OmegaClaw benchmark episode.

The default supported experiment is intentionally finite: one fresh profiled
Omega container, one human-mediated input, at most N reasoning calls, one user
response, then teardown. Running upstream OmegaClaw without these bounds is an
explicitly different population and is outside this benchmark runner.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INGRESS_DIR = ROOT / "ingress"
if str(INGRESS_DIR) not in sys.path:
    sys.path.insert(0, str(INGRESS_DIR))

import openrouter_image
import pipe as ingress_pipe

from episode_contract import EpisodeContract
import omega_profile

THREADKEEPER_SHA = "a64de99e10f9f8078d25bff511b44fd71819e931"
COMM_CHANNEL = "test"
HOST_ALIAS = "host.docker.internal"
STARTUP_DRAIN_SECONDS = 0.5
BUDGET_RESPONSE_GRACE_SECONDS = 5.0


@dataclass(frozen=True)
class ProviderSpec:
    plugin: str
    runtime_name: str
    api_key_env: str


PROVIDERS = {
    "asione": ProviderSpec("asione", "ASIOne", "ASIONE_API_KEY"),
    "openrouter": ProviderSpec("openrouter", "OpenRouter", "OPENROUTER_API_KEY"),
    "openai": ProviderSpec("openai", "OpenAI", "OPENAI_API_KEY"),
    "openaiapi": ProviderSpec("openaiapi", "OpenAIAPI", "OPENAIAPI_API_KEY"),
}


def _git_output(*args: str, cwd: Path = ROOT) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def verify_threadkeeper() -> str:
    """Verify the benchmark accounting dependency is the exact pinned clean gitlink."""
    module = ROOT / "external" / "ThreadKeeper"
    if not module.is_dir():
        raise RuntimeError("ThreadKeeper submodule is not initialized")

    parts = _git_output("ls-files", "-s", "external/ThreadKeeper").split()
    if len(parts) != 4 or parts[0] != "160000":
        raise RuntimeError("external/ThreadKeeper is not a Git submodule gitlink")
    indexed_sha = parts[1]
    checked_out_sha = _git_output("-C", str(module), "rev-parse", "HEAD")
    if indexed_sha != THREADKEEPER_SHA or checked_out_sha != THREADKEEPER_SHA:
        raise RuntimeError(
            "ThreadKeeper pin mismatch: "
            f"expected {THREADKEEPER_SHA}, indexed {indexed_sha}, checked out {checked_out_sha}"
        )
    if _git_output("-C", str(module), "status", "--porcelain"):
        raise RuntimeError("ThreadKeeper benchmark dependency is dirty")
    return checked_out_sha


def _alpha_git_sha() -> str:
    try:
        return _git_output("rev-parse", "HEAD")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _new_run_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{uuid.uuid4().hex[:10]}"


def _prepare_output_dir(path: Path, run_id: str) -> None:
    path.mkdir(parents=True, exist_ok=False)
    (path / "run_id").write_text(run_id, encoding="utf-8")
    for name in ("usage.jsonl", "provider_usage.jsonl"):
        target = path / name
        target.touch()
        target.chmod(0o666)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise RuntimeError(f"non-object benchmark record in {path}")
        rows.append(value)
    return rows


def usage_summary(path: Path) -> dict[str, int]:
    rows = _read_jsonl(path)
    return {
        "calls": len(rows),
        "input_tokens": sum(int(row.get("input_tokens", 0) or 0) for row in rows),
        "output_tokens": sum(int(row.get("output_tokens", 0) or 0) for row in rows),
    }


def _load_comm_mock(omega_source: Path):
    source = str(omega_source.resolve())
    if source not in sys.path:
        sys.path.insert(0, source)
    module = importlib.import_module("Autotests.mock.comm")
    return module.CommMockServer, int(module.COMM_MOCK_PORT)


def _wait_for_agent(server: Any, process: subprocess.Popen[str], timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"OmegaBoi container exited during startup with code {process.returncode}")
        try:
            if server.ping(timeout=0.5):
                return
        except Exception:
            pass
        time.sleep(0.1)
    raise TimeoutError("OmegaBoi did not connect to the benchmark channel")


def _drain_startup_messages(server: Any) -> None:
    deadline = time.monotonic() + STARTUP_DRAIN_SECONDS
    while time.monotonic() < deadline:
        while server.getLastMessage():
            pass
        time.sleep(0.05)


def _wait_for_response(
    server: Any,
    process: subprocess.Popen[str],
    *,
    usage_log: Path,
    contract: EpisodeContract,
    timeout: float,
) -> tuple[str | None, str]:
    deadline = time.monotonic() + timeout
    budget_reached_at: float | None = None

    while time.monotonic() < deadline:
        reply = server.getLastMessage()
        if reply:
            return reply, "responded"
        if process.poll() is not None:
            return None, f"container_exited_{process.returncode}"

        calls = usage_summary(usage_log)["calls"]
        if calls > contract.max_reasoning_loops:
            raise RuntimeError(
                f"mechanical loop bound violated: {calls} provider calls > "
                f"{contract.max_reasoning_loops}"
            )
        if calls == contract.max_reasoning_loops:
            if budget_reached_at is None:
                budget_reached_at = time.monotonic()
            elif time.monotonic() - budget_reached_at >= BUDGET_RESPONSE_GRACE_SECONDS:
                return None, "budget_exhausted_without_response"
        time.sleep(0.05)

    return None, "timeout"


def _docker_run_command(
    *,
    image: str,
    container_name: str,
    output_dir: Path,
    threadkeeper_dir: Path,
    provider: ProviderSpec,
    model: str | None,
    openaiapi_url: str | None,
) -> list[str]:
    command = [
        "docker",
        "run",
        "--rm",
        "--name",
        container_name,
        "--add-host",
        f"{HOST_ALIAS}:host-gateway",
        "-e",
        f"TEST_SERVER_IP={HOST_ALIAS}",
        "-e",
        provider.api_key_env,
        "-v",
        f"{threadkeeper_dir.resolve()}:/ThreadKeeper:ro",
        "-v",
        f"{output_dir.resolve()}:/benchmark",
        image,
        f"commchannel={COMM_CHANNEL}",
        f"provider={provider.runtime_name}",
    ]
    if model:
        command.append(f"model={model}")
    if provider.plugin == "openaiapi" and openaiapi_url:
        command.append(f"openaiapi_url={openaiapi_url}")
    return command


def _stop_container(name: str) -> None:
    subprocess.run(
        ["docker", "stop", "--time", "2", name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def _remove_image(image: str) -> None:
    subprocess.run(
        ["docker", "image", "rm", "--force", image],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def run_episode(
    *,
    text: str | None,
    input_file: Path | None,
    provider_name: str,
    model: str | None,
    sensory_model: str,
    max_loops: int,
    output_dir: Path | None,
    timeout: float,
    openaiapi_url: str | None = None,
    keep_image: bool = False,
) -> dict[str, Any]:
    if provider_name not in PROVIDERS:
        raise ValueError(f"unsupported real provider: {provider_name}")
    provider = PROVIDERS[provider_name]
    if not os.environ.get(provider.api_key_env, "").strip():
        raise RuntimeError(f"{provider.api_key_env} is required for provider {provider_name}")
    if shutil.which("docker") is None:
        raise RuntimeError("docker is required for bounded OmegaBoi benchmark runs")
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    contract = EpisodeContract(max_reasoning_loops=max_loops)
    threadkeeper_sha = verify_threadkeeper()
    run_id = _new_run_id()
    run_dir = output_dir or (ROOT / "benchmark-runs" / run_id)
    _prepare_output_dir(run_dir, run_id)

    rendered, ingress_trace = ingress_pipe.prepare(
        text=text,
        input_file=input_file,
        model=sensory_model,
        api_key=os.environ.get("OPENROUTER_API_KEY", ""),
        episode_contract=contract.handoff(),
    )
    (run_dir / "alpha-envelope.json").write_text(rendered, encoding="utf-8")
    _write_json(run_dir / "ingress-trace.json", ingress_trace)

    manifest: dict[str, Any] = {
        "run_id": run_id,
        "status": "preparing",
        "bounded_controller": True,
        "alpha_git_sha": _alpha_git_sha(),
        "omega_sha": omega_profile.OMEGA_SHA,
        "threadkeeper_sha": threadkeeper_sha,
        "provider": provider.runtime_name,
        "requested_model": model,
        "episode_contract": contract.manifest(),
        "ingress": ingress_trace,
        "started_at": datetime.now(UTC).isoformat(),
    }
    _write_json(run_dir / "manifest.json", manifest)

    image = f"alphaclaw-omegaboi:{run_id.lower()}"
    container_name = f"alphaclaw-omegaboi-{uuid.uuid4().hex[:12]}"
    process: subprocess.Popen[str] | None = None
    server = None
    response: str | None = None
    termination_reason = "controller_error"

    try:
        with tempfile.TemporaryDirectory(prefix="alphaclaw-omegaboi-") as temp:
            profiled = Path(temp) / "OmegaClaw-Core"
            omega_profile.apply_profile(
                ROOT / "OmegaClaw-Core",
                profiled,
                channel="mockchannel",
                provider=provider.plugin,
                max_new_input_loops=contract.max_reasoning_loops,
                meter=True,
            )

            subprocess.run(
                ["docker", "build", "-t", image, str(profiled)],
                check=True,
            )

            server_type, port = _load_comm_mock(ROOT / "OmegaClaw-Core")
            server = server_type(("0.0.0.0", port))
            log_handle = (run_dir / "container.log").open("w", encoding="utf-8")
            try:
                process = subprocess.Popen(
                    _docker_run_command(
                        image=image,
                        container_name=container_name,
                        output_dir=run_dir,
                        threadkeeper_dir=ROOT / "external" / "ThreadKeeper",
                        provider=provider,
                        model=model,
                        openaiapi_url=openaiapi_url,
                    ),
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                _wait_for_agent(server, process, min(timeout, 120.0))
                _drain_startup_messages(server)
                if not server.send_message(rendered, timeout=10):
                    raise RuntimeError("OmegaBoi benchmark channel rejected the Alpha envelope")

                response, termination_reason = _wait_for_response(
                    server,
                    process,
                    usage_log=run_dir / "usage.jsonl",
                    contract=contract,
                    timeout=timeout,
                )
            finally:
                _stop_container(container_name)
                if process is not None:
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                log_handle.close()
                if server is not None:
                    server.stop(5)

        usage = usage_summary(run_dir / "usage.jsonl")
        raw_usage = _read_jsonl(run_dir / "provider_usage.jsonl")
        if usage["calls"] == 0:
            raise RuntimeError("benchmark produced no ThreadKeeper provider-usage records")
        if usage["calls"] > contract.max_reasoning_loops:
            raise RuntimeError("benchmark exceeded its declared reasoning-loop budget")
        if len(raw_usage) != usage["calls"]:
            raise RuntimeError("raw provider usage and ThreadKeeper call counts disagree")

        if response is not None:
            (run_dir / "response.txt").write_text(response + "\n", encoding="utf-8")

        manifest.update(
            {
                "status": "completed" if response is not None else "terminated_without_response",
                "termination_reason": termination_reason,
                "usage": usage,
                "response_present": response is not None,
                "ended_at": datetime.now(UTC).isoformat(),
            }
        )
        _write_json(run_dir / "manifest.json", manifest)
        return manifest
    except Exception as exc:
        manifest.update(
            {
                "status": "failed",
                "termination_reason": termination_reason,
                "error": str(exc),
                "usage": usage_summary(run_dir / "usage.jsonl"),
                "ended_at": datetime.now(UTC).isoformat(),
            }
        )
        _write_json(run_dir / "manifest.json", manifest)
        raise
    finally:
        _stop_container(container_name)
        if not keep_image:
            _remove_image(image)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text")
    source.add_argument("--input-file", type=Path)
    parser.add_argument("--provider", choices=tuple(PROVIDERS), required=True)
    parser.add_argument("--model")
    parser.add_argument("--sensory-model", default=openrouter_image.DEFAULT_MODEL)
    parser.add_argument("--max-loops", type=int, default=50)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--timeout", type=float, default=900.0)
    parser.add_argument("--openaiapi-url")
    parser.add_argument("--keep-image", action="store_true")
    args = parser.parse_args()

    try:
        manifest = run_episode(
            text=args.text,
            input_file=args.input_file,
            provider_name=args.provider,
            model=args.model,
            sensory_model=args.sensory_model,
            max_loops=args.max_loops,
            output_dir=args.output_dir,
            timeout=args.timeout,
            openaiapi_url=args.openaiapi_url,
            keep_image=args.keep_image,
        )
    except (OSError, RuntimeError, subprocess.SubprocessError, TimeoutError, ValueError) as exc:
        print(f"OmegaBoi benchmark failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0 if manifest.get("response_present") else 2


if __name__ == "__main__":
    raise SystemExit(main())