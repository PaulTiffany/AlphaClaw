"""Run one bounded, metered AlphaClaw -> stock OmegaClaw benchmark episode.

OmegaClaw is never rewritten. The controller builds/reuses one Docker image from
the exact pinned upstream tree, starts a fresh container for each episode, uses
Omega's native runtime configuration, meters provider traffic on the host, and
tears the container down after the first post-handoff user response or failure.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
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
from provider_proxy import UPSTREAMS, MeteredProviderGateway
from threadkeeper_meter import ThreadKeeperRecorder

OMEGA_SHA = "3d711e4b9f5254ae94f31123ca242f60cfd97d29"
THREADKEEPER_SHA = "a64de99e10f9f8078d25bff511b44fd71819e931"
COMM_CHANNEL = "test"
HOST_ALIAS = "host.docker.internal"
OMEGA_PROVIDER = "OpenAIAPI"
STARTUP_SETTLE_SECONDS = 0.25


def _git_output(*args: str, cwd: Path = ROOT) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def _verify_gitlink(path: str, expected_sha: str) -> str:
    module = ROOT / path
    if not module.is_dir():
        raise RuntimeError(f"submodule is not initialized: {path}")

    parts = _git_output("ls-files", "-s", path).split()
    if len(parts) != 4 or parts[0] != "160000":
        raise RuntimeError(f"{path} is not a Git submodule gitlink")
    indexed_sha = parts[1]
    checked_out_sha = _git_output("-C", str(module), "rev-parse", "HEAD")
    if indexed_sha != expected_sha or checked_out_sha != expected_sha:
        raise RuntimeError(
            f"{path} pin mismatch: expected {expected_sha}, "
            f"indexed {indexed_sha}, checked out {checked_out_sha}"
        )
    if _git_output("-C", str(module), "status", "--porcelain"):
        raise RuntimeError(f"{path} benchmark dependency is dirty")
    return checked_out_sha


def verify_omega() -> str:
    return _verify_gitlink("OmegaClaw-Core", OMEGA_SHA)


def verify_threadkeeper() -> str:
    return _verify_gitlink("external/ThreadKeeper", THREADKEEPER_SHA)


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
    (path / "usage.jsonl").touch()
    (path / "provider_usage.jsonl").touch()


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


def usage_by_phase(path: Path) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for row in _read_jsonl(path):
        phase = str(row.get("phase", "unknown"))
        usage = row.get("usage") or {}
        if not isinstance(usage, dict):
            usage = {}
        bucket = result.setdefault(
            phase,
            {"calls": 0, "input_tokens": 0, "output_tokens": 0},
        )
        bucket["calls"] += 1
        bucket["input_tokens"] += int(
            usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0
        )
        bucket["output_tokens"] += int(
            usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0
        )
    return result


def stock_image_tag() -> str:
    return f"alphaclaw-omega-stock:{OMEGA_SHA[:12]}"


def _docker_image_id(image: str) -> str | None:
    result = subprocess.run(
        ["docker", "image", "inspect", "--format", "{{.Id}}", image],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def ensure_stock_image(*, rebuild: bool = False) -> tuple[str, str]:
    verify_omega()
    image = stock_image_tag()
    existing = _docker_image_id(image)
    if existing is not None and not rebuild:
        return image, existing
    if rebuild and existing is not None:
        subprocess.run(
            ["docker", "image", "rm", "--force", image],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
    subprocess.run(
        ["docker", "build", "-t", image, str(ROOT / "OmegaClaw-Core")],
        check=True,
    )
    built = _docker_image_id(image)
    if built is None:
        raise RuntimeError("stock Omega Docker build completed without an inspectable image")
    return image, built


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


def _wait_for_log_marker(
    path: Path,
    marker: str,
    process: subprocess.Popen[str],
    timeout: float,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"OmegaBoi container exited during startup with code {process.returncode}")
        try:
            if marker in path.read_text(encoding="utf-8", errors="replace"):
                return
        except OSError:
            pass
        time.sleep(0.05)
    raise TimeoutError(f"OmegaBoi did not reach expected stock loop marker: {marker}")


def _drain_messages(server: Any) -> list[str]:
    messages: list[str] = []
    deadline = time.monotonic() + STARTUP_SETTLE_SECONDS
    while time.monotonic() < deadline:
        value = server.getLastMessage()
        if value:
            messages.append(value)
            continue
        time.sleep(0.025)
    return messages


def _wait_for_response(
    server: Any,
    process: subprocess.Popen[str],
    *,
    gateway: MeteredProviderGateway,
    timeout: float,
) -> tuple[str | None, str]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if gateway.fatal_message:
            raise RuntimeError(f"provider metering failed: {gateway.fatal_message}")
        if gateway.budget_exhausted:
            return None, "episode_provider_budget_exhausted"
        reply = server.getLastMessage()
        if reply:
            return reply, "responded"
        if process.poll() is not None:
            return None, f"container_exited_{process.returncode}"
        time.sleep(0.05)
    return None, "timeout"


def _docker_run_command(
    *,
    image: str,
    container_name: str,
    proxy_url: str,
    proxy_token: str,
    model: str,
    contract: EpisodeContract,
    timeout: float,
) -> list[str]:
    wakeup_interval = max(60, int(timeout) + 60)
    return [
        "docker",
        "run",
        "--rm",
        "--name",
        container_name,
        "--security-opt",
        "no-new-privileges:true",
        "--init",
        "--add-host",
        f"{HOST_ALIAS}:host-gateway",
        "--tmpfs",
        "/tmp:size=64m,mode=1777",
        "--tmpfs",
        "/var/tmp:size=64m,mode=1777",
        "--tmpfs",
        "/run:size=16m,mode=755",
        "-e",
        f"TEST_SERVER_IP={HOST_ALIAS}",
        "-e",
        f"OPENAIAPI_API_KEY={proxy_token}",
        "-e",
        "IMPORT_KB_ON_START=0",
        image,
        f"commchannel={COMM_CHANNEL}",
        f"provider={OMEGA_PROVIDER}",
        "embeddingprovider=Local",
        "api_token_var=OPENAIAPI_API_KEY",
        f"openaiapi_url={proxy_url}",
        f"model={model}",
        f"maxNewInputLoops={contract.max_reasoning_loops}",
        f"maxWakeLoops={contract.max_wake_loops}",
        f"maxHistory={contract.max_history}",
        f"wakeupInterval={wakeup_interval}",
        "securityPolicyPath=/PeTTa/repos/OmegaClaw-Core/profile/policy.yaml",
        "memoryDirectory=$MEMORY_DIR",
    ]


def _stop_container(name: str) -> None:
    subprocess.run(
        ["docker", "stop", "--time", "2", name],
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
    rebuild_image: bool = False,
) -> dict[str, Any]:
    if provider_name not in UPSTREAMS:
        raise ValueError(f"unsupported real provider: {provider_name}")
    upstream = UPSTREAMS[provider_name]
    api_key = os.environ.get(upstream.api_key_env, "").strip()
    if not api_key:
        raise RuntimeError(f"{upstream.api_key_env} is required for provider {provider_name}")
    upstream_url = openaiapi_url if provider_name == "openaiapi" else upstream.base_url
    if not upstream_url:
        raise RuntimeError("--openaiapi-url is required for provider openaiapi")
    resolved_model = model or upstream.default_model
    if shutil.which("docker") is None:
        raise RuntimeError("docker is required for bounded OmegaBoi benchmark runs")
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    contract = EpisodeContract(max_reasoning_loops=max_loops)
    omega_sha = verify_omega()
    threadkeeper_sha = verify_threadkeeper()
    image, image_id = ensure_stock_image(rebuild=rebuild_image)
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

    recorder = ThreadKeeperRecorder(run_dir=run_dir, run_id=run_id)
    gateway = MeteredProviderGateway(
        upstream=upstream,
        api_key=api_key,
        base_url=upstream_url,
        model=resolved_model,
        max_episode_calls=contract.max_reasoning_loops,
        recorder=recorder,
    )

    manifest: dict[str, Any] = {
        "run_id": run_id,
        "status": "preparing",
        "bounded_controller": True,
        "omega_source_modified": False,
        "alpha_git_sha": _alpha_git_sha(),
        "omega_sha": omega_sha,
        "omega_image": image,
        "omega_image_id": image_id,
        "threadkeeper_sha": threadkeeper_sha,
        "omega_provider": OMEGA_PROVIDER,
        "upstream_provider": upstream.display_name,
        "requested_model": resolved_model,
        "episode_contract": contract.manifest(),
        "ingress": ingress_trace,
        "started_at": datetime.now(UTC).isoformat(),
    }
    _write_json(run_dir / "manifest.json", manifest)

    container_name = f"alphaclaw-omegaboi-{uuid.uuid4().hex[:12]}"
    process: subprocess.Popen[str] | None = None
    server = None
    log_handle = None
    response: str | None = None
    termination_reason = "controller_error"
    proxy_url = gateway.start()

    try:
        server_type, port = _load_comm_mock(ROOT / "OmegaClaw-Core")
        server = server_type(("0.0.0.0", port))
        container_log = run_dir / "container.log"
        log_handle = container_log.open("w", encoding="utf-8")
        process = subprocess.Popen(
            _docker_run_command(
                image=image,
                container_name=container_name,
                proxy_url=proxy_url,
                proxy_token=gateway.proxy_token,
                model=resolved_model,
                contract=contract,
                timeout=timeout,
            ),
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            text=True,
        )

        _wait_for_agent(server, process, min(timeout, 120.0))
        if not gateway.wait_for_boot_call(min(timeout, 180.0)):
            if gateway.fatal_message:
                raise RuntimeError(f"stock Omega boot provider call failed: {gateway.fatal_message}")
            raise TimeoutError("stock Omega produced no metered boot provider call")
        _wait_for_log_marker(
            container_log,
            "(---------iteration 2)",
            process,
            min(timeout, 30.0),
        )
        startup_messages = _drain_messages(server)

        gateway.mark_episode_started()
        if not server.send_message(rendered, timeout=10):
            raise RuntimeError("OmegaBoi benchmark channel rejected the Alpha envelope")

        response, termination_reason = _wait_for_response(
            server,
            process,
            gateway=gateway,
            timeout=timeout,
        )
    finally:
        _stop_container(container_name)
        if process is not None:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        if log_handle is not None:
            log_handle.close()
        if server is not None:
            server.stop(5)
        gateway.stop()

    usage = usage_summary(run_dir / "usage.jsonl")
    phases = usage_by_phase(run_dir / "provider_usage.jsonl")
    gateway_state = gateway.snapshot()
    if phases.get("episode", {}).get("calls", 0) > contract.max_reasoning_loops:
        raise RuntimeError("benchmark exceeded its declared post-handoff provider-call budget")
    if phases.get("boot", {}).get("calls", 0) < 1:
        raise RuntimeError("benchmark did not record stock Omega boot usage")

    if response is not None:
        (run_dir / "response.txt").write_text(response + "\n", encoding="utf-8")

    manifest.update(
        {
            "status": "completed" if response is not None else "terminated_without_response",
            "termination_reason": termination_reason,
            "usage": usage,
            "usage_by_phase": phases,
            "provider_gateway": gateway_state,
            "startup_messages": startup_messages,
            "response_present": response is not None,
            "ended_at": datetime.now(UTC).isoformat(),
        }
    )
    _write_json(run_dir / "manifest.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text")
    source.add_argument("--input-file", type=Path)
    parser.add_argument("--provider", choices=tuple(UPSTREAMS), required=True)
    parser.add_argument("--model")
    parser.add_argument("--sensory-model", default=openrouter_image.DEFAULT_MODEL)
    parser.add_argument("--max-loops", type=int, default=1)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--timeout", type=float, default=900.0)
    parser.add_argument("--openaiapi-url")
    parser.add_argument("--rebuild-image", action="store_true")
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
            rebuild_image=args.rebuild_image,
        )
    except (OSError, RuntimeError, subprocess.SubprocessError, TimeoutError, ValueError) as exc:
        print(f"OmegaBoi benchmark failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0 if manifest.get("response_present") else 2


if __name__ == "__main__":
    raise SystemExit(main())
