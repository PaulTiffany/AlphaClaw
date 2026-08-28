"""Run one bounded, metered AlphaClaw -> stock OmegaClaw benchmark episode.

OmegaClaw is never rewritten. The controller builds/reuses one Docker image from
the exact pinned upstream tree, starts a fresh container for each episode, uses
Omega's native runtime configuration, meters provider traffic on the host, and
tears the container down after the first post-handoff user response or failure.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import shutil
import subprocess
import sys
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

from episode_contract import DEFAULT_MAX_REASONING_LOOPS, EpisodeContract
from provider_proxy import UPSTREAMS, MeteredProviderGateway
from threadkeeper_meter import ThreadKeeperRecorder

OMEGA_SHA = "3d711e4b9f5254ae94f31123ca242f60cfd97d29"
THREADKEEPER_SHA = "a64de99e10f9f8078d25bff511b44fd71819e931"
COMM_CHANNEL = "test"
HOST_ALIAS = "host.docker.internal"
OMEGA_PROVIDER = "OpenAIAPI"
OMEGA_BOUNDS_CONTAINER_PATH = "/etc/alphaclaw-bounds.yaml"
OMEGA_BOUNDS_FILENAME = "omega-bounds.yaml"


def _git_output(*args: str, cwd: Path = ROOT) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


@dataclass(frozen=True)
class PinVerification:
    """Two independent provenance facts about a pinned benchmark dependency.

    A matching commit does not imply matching bytes. Git's line-ending filters can
    rewrite a checked-out working tree while `git status` still reports it clean, so
    the two facts are measured and reported separately.
    """

    path: str
    commit: str
    commit_matches_pin: bool
    worktree_bytes_match_pin: bool
    mismatched_paths: tuple[str, ...] = ()
    unverifiable_paths: tuple[str, ...] = ()


_RENORMALIZE_HINT = (
    "git status cannot detect this when core.autocrlf rewrites line endings. "
    "Restore the pinned bytes with:\n"
    "  git -C {path} config core.autocrlf false\n"
    "  git -C {path} config core.eol lf\n"
    "  git -C {path} rm --cached -rq .\n"
    "  git -C {path} reset --hard HEAD"
)


def _tracked_blobs(module: Path) -> tuple[list[tuple[str, str]], list[str]]:
    raw = subprocess.run(
        ["git", "-C", str(module), "ls-tree", "-r", "-z", "HEAD"],
        stdout=subprocess.PIPE,
        check=True,
    ).stdout.decode("utf-8", "surrogateescape")

    regular: list[tuple[str, str]] = []
    unverifiable: list[str] = []
    for record in raw.split("\0"):
        if not record:
            continue
        meta, _, path = record.partition("\t")
        mode, _kind, blob_sha = meta.split()
        # Newlines would corrupt --stdin-paths framing; non-regular modes (symlinks,
        # nested gitlinks) cannot be compared as plain file bytes. Neither is silently
        # skipped: both are surfaced so the caller fails loudly instead of passing.
        if mode not in ("100644", "100755") or "\n" in path:
            unverifiable.append(path)
            continue
        regular.append((blob_sha, path))
    return regular, unverifiable


def worktree_byte_mismatches(module: Path) -> tuple[list[str], list[str]]:
    """Compare every tracked regular file's raw bytes against its pinned blob.

    Uses `git hash-object --no-filters` deliberately: the filtered form applies the
    same CRLF conversion that produced the drift, so it would report a corrupted tree
    as matching. Returns (mismatched_paths, unverifiable_paths).
    """
    regular, unverifiable = _tracked_blobs(module)

    missing = [path for _, path in regular if not (module / path).is_file()]
    present = [(sha, path) for sha, path in regular if (module / path).is_file()]

    mismatched = list(missing)
    if present:
        result = subprocess.run(
            ["git", "-C", str(module), "hash-object", "--no-filters", "--stdin-paths"],
            input="\n".join(path for _, path in present) + "\n",
            stdout=subprocess.PIPE,
            text=True,
            check=True,
        )
        hashed = result.stdout.split()
        if len(hashed) != len(present):
            raise RuntimeError(
                f"{module}: hashed {len(hashed)} of {len(present)} tracked files"
            )
        mismatched.extend(
            path for (expected, path), actual in zip(present, hashed) if expected != actual
        )
    return sorted(mismatched), sorted(unverifiable)


def inspect_gitlink(path: str, expected_sha: str) -> PinVerification:
    """Report commit and raw-byte provenance independently, without raising on drift."""
    module = ROOT / path
    if not module.is_dir():
        raise RuntimeError(f"submodule is not initialized: {path}")

    parts = _git_output("ls-files", "-s", path).split()
    if len(parts) != 4 or parts[0] != "160000":
        raise RuntimeError(f"{path} is not a Git submodule gitlink")
    indexed_sha = parts[1]
    checked_out_sha = _git_output("-C", str(module), "rev-parse", "HEAD")

    mismatched, unverifiable = worktree_byte_mismatches(module)
    return PinVerification(
        path=path,
        commit=checked_out_sha,
        commit_matches_pin=indexed_sha == expected_sha and checked_out_sha == expected_sha,
        worktree_bytes_match_pin=not mismatched and not unverifiable,
        mismatched_paths=tuple(mismatched),
        unverifiable_paths=tuple(unverifiable),
    )


def _verify_gitlink(path: str, expected_sha: str) -> PinVerification:
    verification = inspect_gitlink(path, expected_sha)
    module = ROOT / path

    if not verification.commit_matches_pin:
        indexed_sha = _git_output("ls-files", "-s", path).split()[1]
        raise RuntimeError(
            f"{path} pin mismatch: expected {expected_sha}, "
            f"indexed {indexed_sha}, checked out {verification.commit}"
        )
    if _git_output("-C", str(module), "status", "--porcelain"):
        raise RuntimeError(f"{path} benchmark dependency is dirty")
    if verification.unverifiable_paths:
        listed = ", ".join(verification.unverifiable_paths[:5])
        raise RuntimeError(
            f"{path} has {len(verification.unverifiable_paths)} tracked entries whose "
            f"bytes cannot be verified ({listed}); refusing to treat the tree as pinned"
        )
    if not verification.worktree_bytes_match_pin:
        listed = ", ".join(verification.mismatched_paths[:5])
        more = "" if len(verification.mismatched_paths) <= 5 else ", ..."
        raise RuntimeError(
            f"{path} working tree bytes differ from the pinned blobs for "
            f"{len(verification.mismatched_paths)} file(s) ({listed}{more}). "
            + _RENORMALIZE_HINT.format(path=path)
        )
    return verification


def verify_omega() -> PinVerification:
    return _verify_gitlink("OmegaClaw-Core", OMEGA_SHA)


def verify_threadkeeper() -> PinVerification:
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
    # Byte-faithful pin verification runs ahead of the build boundary on purpose: a
    # CRLF-rewritten checkout poisons the cache key of Dockerfile's requirements.txt
    # COPY, which forces the multi-GB torch and embedding-model layers to rebuild.
    # Failing here costs a second; failing after the build costs gigabytes of cache.
    verify_omega()
    image = stock_image_tag()
    existing = _docker_image_id(image)
    if existing is not None and not rebuild:
        return image, existing
    # The existing image is deliberately NOT removed before rebuilding. Deleting it
    # frees no build cache, and it would discard the last-known-good image if the
    # rebuild fails. `docker build` re-tags in place on success and leaves the prior
    # image intact on failure.
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
    """Drain messages already emitted by stock Omega; do not wait for new ones."""
    messages: list[str] = []
    while True:
        value = server.getLastMessage()
        if not value:
            return messages
        messages.append(value)


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
    bounds_path: Path,
) -> list[str]:
    return [
        "docker",
        "run",
        "--rm",
        # Allocate a pseudo-TTY. Stock Omega's entrypoint drops nginx to www-data
        # (entrypoint.sh) and its config logs to /dev/stderr (proxy/nginx.conf.template).
        # Without a TTY, fd 2 is a root-owned pipe (mode 0300) that www-data cannot
        # reopen, so nginx dies with [emerg] open() "/dev/stderr" failed (13: Permission
        # denied) before the benchmark channel ever connects. With a TTY, fd 2 is
        # /dev/pts/0 in group tty, which upstream already grants via
        # `usermod -a -G tty www-data` in its Dockerfile.
        #
        # This is stdio plumbing only: it grants no privilege and weakens no sandbox.
        # The failure reproduces with every containment flag removed, so none of them
        # were ever implicated. No -i: Omega reads from the comm channel, not stdin.
        "-t",
        "--name",
        container_name,
        # The numeric episode bounds travel as a read-only YAML file selected through
        # Omega's own `config=` argument, never as command-line overrides. Omega's
        # src/config.py applies no type coercion to argv, so a numeric bound passed
        # there arrives in src/loop.metta as a string and dies in is/2 arithmetic.
        # Only the config file is parsed by yaml.safe_load, which yields real ints.
        # Mounted outside /tmp, /var/tmp and /run because those are tmpfs and would
        # shadow the file.
        "-v",
        f"{bounds_path}:{OMEGA_BOUNDS_CONTAINER_PATH}:ro",
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
        f"config={OMEGA_BOUNDS_CONTAINER_PATH}",
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
    # Both dependencies are verified for commit AND raw bytes before any Docker work
    # and before the isolated ThreadKeeper witness is constructed or executed.
    omega_pin = verify_omega()
    threadkeeper_pin = verify_threadkeeper()
    omega_sha = omega_pin.commit
    threadkeeper_sha = threadkeeper_pin.commit
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
        max_boot_calls=contract.max_boot_calls,
        recorder=recorder,
    )

    # Typed numeric bounds, written beside the receipts and mounted read-only. The
    # file itself is evidence: the manifest records its digest so a run's declared
    # bounds can be checked against the bytes Omega actually loaded.
    wakeup_interval = max(60, int(timeout) + 60)
    bounds = contract.bounds_config(wakeup_interval=wakeup_interval)
    bounds_path = run_dir / OMEGA_BOUNDS_FILENAME
    bounds_path.write_text(
        contract.bounds_yaml(wakeup_interval=wakeup_interval), encoding="utf-8"
    )
    # Stock Omega drops to an unprivileged user before reading configuration.
    bounds_path.chmod(0o644)
    bounds_sha256 = hashlib.sha256(bounds_path.read_bytes()).hexdigest()

    manifest: dict[str, Any] = {
        "run_id": run_id,
        "status": "preparing",
        "bounded_controller": True,
        "omega_bounds": bounds,
        "omega_bounds_source": "yaml_config_file",
        "omega_bounds_container_path": OMEGA_BOUNDS_CONTAINER_PATH,
        "omega_bounds_sha256": bounds_sha256,
        # Measured, not asserted: derived from the raw-byte comparison above.
        "omega_source_modified": not omega_pin.worktree_bytes_match_pin,
        "omega_commit_matches_pin": omega_pin.commit_matches_pin,
        "omega_worktree_bytes_match_pin": omega_pin.worktree_bytes_match_pin,
        "threadkeeper_commit_matches_pin": threadkeeper_pin.commit_matches_pin,
        "threadkeeper_worktree_bytes_match_pin": threadkeeper_pin.worktree_bytes_match_pin,
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
    startup_messages: list[str] = []
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
                bounds_path=bounds_path,
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

        # The current provider request was reserved as boot before its response
        # existed. Classify all future requests as episode now, then queue Alpha
        # synchronously while Omega is still processing that boot response.
        gateway.mark_episode_started()
        if not server.send_message(rendered, timeout=10):
            raise RuntimeError("OmegaBoi benchmark channel rejected the Alpha envelope")

        # An extremely fast episode request may already be waiting at the host
        # gateway, but it cannot reach the real provider until we release it.
        # That lets us separate stock boot-time public messages without racing a
        # post-handoff user response.
        _wait_for_log_marker(
            container_log,
            "(---------iteration 2)",
            process,
            min(timeout, 30.0),
        )
        startup_messages = _drain_messages(server)
        gateway.release_episode_calls()

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
    if phases.get("boot", {}).get("calls", 0) > contract.max_boot_calls:
        raise RuntimeError("benchmark exceeded its declared stock-boot provider-call budget")
    if phases.get("boot", {}).get("calls", 0) < 1:
        raise RuntimeError("benchmark did not record stock Omega boot usage")

    if response is not None:
        (run_dir / "response.txt").write_text(response + "\n", encoding="utf-8")

    # A run in which the controller refused boot-phase provider authorization is a
    # disclosed controller-bound failure condition, not a normal bounded episode,
    # even when a response arrived.
    boot_budget_exhausted = bool(gateway_state.get("boot_budget_exhausted"))
    if boot_budget_exhausted:
        status = "boot_budget_exhausted"
    elif response is not None:
        status = "completed"
    else:
        status = "terminated_without_response"

    manifest.update(
        {
            "status": status,
            "boot_budget_exhausted": boot_budget_exhausted,
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
    parser.add_argument("--max-loops", type=int, default=DEFAULT_MAX_REASONING_LOOPS)
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
    if manifest.get("boot_budget_exhausted"):
        return 3
    return 0 if manifest.get("response_present") else 2


if __name__ == "__main__":
    raise SystemExit(main())
