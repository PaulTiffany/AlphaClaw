from __future__ import annotations

import importlib.util
from contextlib import contextmanager
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "controller" / "omega_mock_bridge.py"
SPEC = importlib.util.spec_from_file_location("omega_mock_bridge", SOURCE)
BRIDGE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(BRIDGE)


class FakeServer:
    def __init__(self, reply: str = "Omega reply") -> None:
        self.reply = reply
        self.sent: list[str] = []

    def send_message(self, message: str, timeout: float = 30.0) -> bool:
        self.sent.append(message)
        return True

    def getLastMessage(self) -> str:
        return self.reply


def test_exchange_sends_exact_alpha_envelope_once() -> None:
    server = FakeServer()

    @contextmanager
    def factory(address, timeout):
        assert address == ("127.0.0.1", 9766)
        assert timeout == 1.0
        yield server

    envelope = '{"kind":"alphaclaw_human_ingress"}\n'
    reply = BRIDGE.exchange(
        envelope,
        server_factory=factory,
        address=("127.0.0.1", 9766),
        timeout=1.0,
    )

    assert server.sent == [envelope]
    assert reply == "Omega reply"


def test_exchange_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        BRIDGE.exchange(
            "   ",
            server_factory=lambda *_args, **_kwargs: None,
            address=("127.0.0.1", 9766),
            timeout=1.0,
        )


def test_bridge_loads_upstream_native_mock_transport() -> None:
    factory, port = BRIDGE.load_mock_transport(ROOT / "OmegaClaw-Core")

    assert callable(factory)
    assert port == 9766
