"""Deliver one prepared Alpha text envelope to an already running local Omega mock channel."""

from __future__ import annotations

import argparse
import importlib
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

DEFAULT_TIMEOUT = 30.0


def load_mock_transport(omega_source: Path) -> tuple[Callable[..., Any], int]:
    """Load the pinned Omega test-channel server from the supplied working tree."""
    if not omega_source.is_dir():
        raise ValueError(f"OmegaClaw source is missing: {omega_source}")
    source = str(omega_source.resolve())
    if source not in sys.path:
        sys.path.insert(0, source)
    module = importlib.import_module("Autotests.mock.comm")
    return module.comm_mock_server, int(module.COMM_MOCK_PORT)


def exchange(
    message: str,
    *,
    server_factory: Callable[..., Any],
    address: tuple[str, int],
    timeout: float = DEFAULT_TIMEOUT,
) -> str:
    """Send exactly one text message to Omega and return its first non-empty reply."""
    if not message.strip():
        raise ValueError("Alpha envelope must not be empty")
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    deadline = time.monotonic() + timeout
    with server_factory(address, timeout=timeout) as server:
        if not server.send_message(message, timeout=timeout):
            raise RuntimeError("Omega mock channel rejected Alpha envelope")

        while time.monotonic() < deadline:
            reply = server.getLastMessage()
            if reply:
                return reply
            time.sleep(0.05)

    raise TimeoutError("Omega did not return a response before timeout")


def deliver(
    message: str,
    *,
    omega_source: Path,
    bind_host: str = "0.0.0.0",
    timeout: float = DEFAULT_TIMEOUT,
) -> str:
    server_factory, port = load_mock_transport(omega_source)
    return exchange(
        message,
        server_factory=server_factory,
        address=(bind_host, port),
        timeout=timeout,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--omega-source", type=Path, required=True)
    parser.add_argument("--input-file", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--bind-host", default="0.0.0.0")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    args = parser.parse_args()

    try:
        if args.input_file is None:
            message = sys.stdin.read()
        else:
            message = args.input_file.read_text(encoding="utf-8")
        reply = deliver(
            message,
            omega_source=args.omega_source,
            bind_host=args.bind_host,
            timeout=args.timeout,
        )
    except (ImportError, OSError, RuntimeError, TimeoutError, ValueError) as exc:
        print(f"Omega bridge failed: {exc}", file=sys.stderr)
        return 1

    if args.output is None:
        print(reply)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(reply + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
