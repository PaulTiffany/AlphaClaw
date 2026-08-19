"""Run one bounded real-model residency qualification against pinned OmegaClaw."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

try:
    from .build_task import build_task
except ImportError:
    from build_task import build_task

CONTAINER = "omegaclaw"
DEFAULT_TARGET = "/tmp/alphaclaw-qualification.json"
FIXTURE_TEXT = "AlphaClaw Omega residency fixture v1\n"
LITERAL_OBSERVATIONS = ["ALPHA CLAW", "OMEGA RESIDENCY", "FIXTURE 17"]

PROVIDER_CONFIG = {
    "ASIOne": {
        "canonical_key_env": "ASI_ONE_API_KEY",
        "stock_key_env": "ASIONE_API_KEY",
        "default_model": "asi1-mini",
    },
    "ASICloud": {
        "canonical_key_env": "ASI_API_KEY",
        "stock_key_env": "ASI_API_KEY",
        "default_model": "minimax/minimax-m3",
    },
}


def provider_config(provider: str) -> dict[str, str]:
    try:
        return PROVIDER_CONFIG[provider]
    except KeyError as exc:
        raise ValueError(f"unsupported qualification provider: {provider}") from exc


def make_handoff(model: str, provider: str = "ASIOne") -> dict:
    return {
        "schema_version": 1,
        "source": {
            "kind": "deterministic-residency-fixture",
            "sha256": hashlib.sha256(FIXTURE_TEXT.encode("utf-8")).hexdigest(),
        },
        "literal_observations": list(LITERAL_OBSERVATIONS),
        "provenance": {
            "provider": provider,
            "resolved_model": model,
        },
    }


def expected_file(handoff: dict, marker: str) -> dict:
    return {
        "marker": marker,
        "source_sha256": handoff["source"]["sha256"],
        "resolved_model": handoff["provenance"]["resolved_model"],
        "literal_count": len(handoff["literal_observations"]),
    }


def redact(text: str, secrets: list[str]) -> str:
    for secret in secrets:
        if secret:
            text = text.replace(secret, "***")
    return text


def count_llm_calls(logs: str) -> int:
    return len(re.findall(r"CHARS_SENT:\s*\d+", logs))


def docker_logs(container: str = CONTAINER) -> str:
    result = subprocess.run(
        ["docker", "logs", container],
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    )
    return result.stdout + result.stderr


def drain_messages(server, phase: str, transcript: list[dict]) -> list[str]:
    drained: list[str] = []
    while True:
        message = server.getLastMessage()
        if not message:
            return drained
        drained.append(message)
        transcript.append({"phase": phase, "text": message[:4000]})


def wait_for_client(server, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            if server.ping(timeout=1):
                return
        except (OSError, RuntimeError, TimeoutError) as exc:
            last_error = exc
        time.sleep(0.5)
    raise TimeoutError("OmegaClaw test channel did not connect to CommMockServer") from last_error


def read_json_from_container(target: str) -> dict:
    raw = subprocess.check_output(
        ["docker", "exec", CONTAINER, "cat", target],
        text=True,
        stderr=subprocess.STDOUT,
    )
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise TypeError("qualification target must contain a JSON object")
    return value


def run(args: argparse.Namespace) -> int:
    source = args.source.resolve()
    mock_dir = source / "Autotests" / "mock"
    launcher = source / "scripts" / "omegaclaw"
    if not mock_dir.is_dir() or not launcher.is_file():
        raise FileNotFoundError("pinned OmegaClaw source is incomplete")

    sys.path.insert(0, str(mock_dir))
    from comm import COMM_MOCK_PORT, CommMockServer  # type: ignore

    config = provider_config(args.provider)
    canonical_key_env = config["canonical_key_env"]
    stock_key_env = config["stock_key_env"]
    api_key = os.environ.get(canonical_key_env, "")
    if not api_key:
        raise RuntimeError(f"{canonical_key_env} is required")

    marker_message = f"QUALIFIED {args.marker}"
    handoff = make_handoff(args.model, args.provider)
    expected = expected_file(handoff, args.marker)
    task = build_task(handoff, args.marker, args.target)
    transcript: list[dict] = []
    started = False
    qualified = False
    error: str | None = None
    observed: dict | None = None
    final_logs = ""
    calls = 0
    started_at = time.time()

    server = CommMockServer(("0.0.0.0", COMM_MOCK_PORT))
    try:
        env = os.environ.copy()
        env[stock_key_env] = api_key
        env["TEST_SERVER_IP"] = "host.docker.internal"
        env["IMPORT_KB_ON_START"] = "0"
        subprocess.run(
            [
                "bash",
                str(launcher),
                "start",
                "-p",
                args.provider,
                "-m",
                args.model,
                "-t",
                "test",
                "-d",
                args.image,
            ],
            env=env,
            check=True,
        )
        started = True
        wait_for_client(server, args.connect_timeout)
        time.sleep(1)
        drain_messages(server, "prelude", transcript)

        if not server.send_message(task, timeout=10):
            raise RuntimeError("CommMockServer could not deliver qualification task")

        deadline = time.monotonic() + args.timeout
        marker_seen = False
        while time.monotonic() < deadline:
            for message in drain_messages(server, "qualification", transcript):
                if message.strip() == marker_message:
                    marker_seen = True

            final_logs = docker_logs()
            calls = count_llm_calls(final_logs)
            if calls > args.max_calls:
                raise RuntimeError(
                    f"LLM call budget exceeded: observed {calls}, maximum {args.max_calls}"
                )
            if marker_seen:
                break
            time.sleep(0.5)

        if not marker_seen:
            raise TimeoutError(f"did not receive exact terminal marker {marker_message!r}")

        observed = read_json_from_container(args.target)
        if observed != expected:
            raise AssertionError(
                f"qualification file mismatch: expected {expected!r}, observed {observed!r}"
            )
        qualified = True
    except Exception as exc:  # noqa: BLE001 - serialize any bounded attempt failure.
        error = f"{type(exc).__name__}: {exc}"
    finally:
        if started:
            final_logs = docker_logs()
            calls = count_llm_calls(final_logs)
        try:
            server.stop(5)
        finally:
            subprocess.run(
                ["docker", "rm", "-f", CONTAINER],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )

    redacted_logs = redact(
        final_logs,
        [
            api_key,
            os.environ.get(canonical_key_env, ""),
            os.environ.get(stock_key_env, ""),
        ],
    )
    redacted_logs = redacted_logs[-200_000:]
    args.log_output.parent.mkdir(parents=True, exist_ok=True)
    args.log_output.write_text(redacted_logs, encoding="utf-8")

    omega_sha = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    evidence = {
        "schema_version": 1,
        "qualified": qualified,
        "marker": args.marker,
        "provider": args.provider,
        "requested_model": args.model,
        "omega_source_sha": omega_sha,
        "alpha_source_sha": os.environ.get("GITHUB_SHA", ""),
        "target": args.target,
        "expected_file": expected,
        "observed_file": observed,
        "terminal_marker": marker_message,
        "llm_call_count": calls,
        "max_llm_calls": args.max_calls,
        "elapsed_seconds": round(time.time() - started_at, 3),
        "transcript": transcript[-20:],
        "error": error,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if qualified else 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("OmegaClaw-Core"))
    parser.add_argument("--image", default="alphaclaw:residency")
    parser.add_argument("--provider", choices=tuple(PROVIDER_CONFIG), default="ASIOne")
    parser.add_argument("--model")
    parser.add_argument("--marker", required=True)
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--max-calls", type=int, default=8)
    parser.add_argument("--connect-timeout", type=float, default=90)
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/tmp/alphaclaw-residency/evidence.json"),
    )
    parser.add_argument(
        "--log-output",
        type=Path,
        default=Path("/tmp/alphaclaw-residency/omegaclaw.log"),
    )
    args = parser.parse_args()
    if args.max_calls < 1:
        parser.error("--max-calls must be at least 1")
    if args.model is None:
        args.model = provider_config(args.provider)["default_model"]
    raise SystemExit(run(args))


if __name__ == "__main__":
    main()
