"""Boot readiness and episode-completion semantics.

Two mistakes are guarded here.

The controller used to gate the handoff on a fixed ``(---------iteration 2)`` marker.
That marker has no handoff meaning: it is the loop's second tick, roughly a second
after boot, and it fires whether or not anything was ever injected. Upstream's
documented boot-readiness signal is the first runtime ``CHARS_SENT:`` line carrying a
byte count, and the count matters because the bare string also appears in the MeTTa
source dump emitted during startup.

Separately, stock Omega emits boot-time channel traffic of its own -- a version
banner among it -- which must never be mistaken for the episode response.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "controller"
if str(CONTROLLER) not in sys.path:
    sys.path.insert(0, str(CONTROLLER))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


runner = _load("omegaboi_readiness", CONTROLLER / "omegaboi.py")

# The bare marker as it appears in the startup source dump, with no byte count.
SOURCE_DUMP_LINE = "(log INFO loop (strings-concat (CHARS_SENT: $len)))"
# A real runtime iteration line, carrying the count.
RUNTIME_LINE = "2026-08-28 04:46:40 | INFO | loop | (CHARS_SENT: 4947 PROMPT: You are...)"
BANNER = "OmegaClaw version=unknown"


class _FakeProcess:
    """Stands in for the container process; alive unless given a return code."""

    def __init__(self, returncode: int | None = None) -> None:
        self.returncode = returncode

    def poll(self) -> int | None:
        return self.returncode


class _FakeServer:
    def __init__(self, messages: list[str]) -> None:
        self._messages = list(messages)

    def getLastMessage(self) -> str:
        return self._messages.pop(0) if self._messages else ""


class _FakeGateway:
    fatal_message = ""
    budget_exhausted = False


# --- readiness signal -------------------------------------------------------


def test_readiness_pattern_requires_a_numeric_byte_count() -> None:
    assert runner.OMEGA_BOOT_READY_PATTERN.search(RUNTIME_LINE)
    assert not runner.OMEGA_BOOT_READY_PATTERN.search(SOURCE_DUMP_LINE)


def test_bare_chars_sent_does_not_satisfy_readiness() -> None:
    """The source dump contains the bare string; matching it would fire early."""
    assert "CHARS_SENT:" in SOURCE_DUMP_LINE
    assert not runner.OMEGA_BOOT_READY_PATTERN.search(SOURCE_DUMP_LINE)


def test_readiness_returns_once_the_numeric_line_appears(tmp_path: Path) -> None:
    log = tmp_path / "container.log"
    log.write_text(SOURCE_DUMP_LINE + "\n" + RUNTIME_LINE + "\n", encoding="utf-8")
    runner._wait_for_boot_readiness(log, _FakeProcess(), timeout=1.0)


def test_readiness_times_out_on_source_dump_alone(tmp_path: Path) -> None:
    log = tmp_path / "container.log"
    log.write_text(SOURCE_DUMP_LINE + "\n", encoding="utf-8")
    with pytest.raises(TimeoutError, match="first metered iteration"):
        runner._wait_for_boot_readiness(log, _FakeProcess(), timeout=0.3)


def test_readiness_fails_fast_when_the_container_exits(tmp_path: Path) -> None:
    log = tmp_path / "container.log"
    log.write_text("", encoding="utf-8")
    with pytest.raises(RuntimeError, match="exited during startup with code 127"):
        runner._wait_for_boot_readiness(log, _FakeProcess(returncode=127), timeout=5.0)


def test_no_fixed_iteration_dependency_remains() -> None:
    """The regression guard: no fixed iteration number may gate the handoff."""
    source = (CONTROLLER / "omegaboi.py").read_text(encoding="utf-8")
    assert "iteration 2" not in source
    assert "_wait_for_log_marker" not in source


def test_readiness_is_awaited_before_the_alpha_envelope_is_sent() -> None:
    source = (CONTROLLER / "omegaboi.py").read_text(encoding="utf-8")
    body = source.split("def run_episode", 1)[1]
    assert body.index("_wait_for_boot_readiness(") < body.index("send_message(rendered")


def test_readiness_and_boot_provider_call_are_separate_waits() -> None:
    """Log readiness and metered boot-call completion are different events."""
    source = (CONTROLLER / "omegaboi.py").read_text(encoding="utf-8")
    body = source.split("def run_episode", 1)[1]
    assert "_wait_for_boot_readiness(" in body
    assert "gateway.wait_for_boot_call(" in body


# --- episode completion -----------------------------------------------------


def test_baseline_is_drained_before_injection() -> None:
    source = (CONTROLLER / "omegaboi.py").read_text(encoding="utf-8")
    body = source.split("def run_episode", 1)[1]
    assert body.index("_drain_messages(server)") < body.index("send_message(rendered")


def test_stale_banner_cannot_satisfy_episode_completion() -> None:
    """A repeat of a pre-injection message is not the episode response."""
    server = _FakeServer([BANNER, "ORANGE"])
    reply, reason, ignored = runner._wait_for_response(
        server, _FakeProcess(), gateway=_FakeGateway(), timeout=2.0, baseline=[BANNER]
    )
    assert reply == "ORANGE"
    assert reason == "responded"
    assert ignored == [BANNER]


def test_a_genuinely_new_message_completes_the_episode() -> None:
    server = _FakeServer(["ORANGE"])
    reply, reason, ignored = runner._wait_for_response(
        server, _FakeProcess(), gateway=_FakeGateway(), timeout=2.0, baseline=[BANNER]
    )
    assert (reply, reason, ignored) == ("ORANGE", "responded", [])


def test_timeout_remains_an_explicit_outcome() -> None:
    reply, reason, _ = runner._wait_for_response(
        _FakeServer([]), _FakeProcess(), gateway=_FakeGateway(), timeout=0.2, baseline=[]
    )
    assert reply is None
    assert reason == "timeout"


def test_container_exit_remains_an_explicit_outcome() -> None:
    reply, reason, _ = runner._wait_for_response(
        _FakeServer([]),
        _FakeProcess(returncode=3),
        gateway=_FakeGateway(),
        timeout=5.0,
        baseline=[],
    )
    assert reply is None
    assert reason == "container_exited_3"


def test_budget_exhaustion_remains_an_explicit_outcome() -> None:
    class Exhausted(_FakeGateway):
        budget_exhausted = True

    reply, reason, _ = runner._wait_for_response(
        _FakeServer(["late"]), _FakeProcess(), gateway=Exhausted(), timeout=5.0, baseline=[]
    )
    assert reply is None
    assert reason == "episode_provider_budget_exhausted"


def test_provider_metering_failure_still_raises() -> None:
    class Fatal(_FakeGateway):
        fatal_message = "upstream exploded"

    with pytest.raises(RuntimeError, match="upstream exploded"):
        runner._wait_for_response(
            _FakeServer([]), _FakeProcess(), gateway=Fatal(), timeout=5.0, baseline=[]
        )


# --- neighbouring guarantees must not regress -------------------------------


def test_typed_bounds_are_untouched_by_this_change() -> None:
    bounds = runner.EpisodeContract(max_reasoning_loops=1).bounds_config(wakeup_interval=960)
    assert bounds == {
        "maxNewInputLoops": 1,
        "maxWakeLoops": 0,
        "maxHistory": 0,
        "wakeupInterval": 960,
    }


def test_tty_and_bounds_mount_are_untouched_by_this_change(tmp_path: Path) -> None:
    command = runner._docker_run_command(
        image=runner.stock_image_tag(),
        container_name="fixture",
        proxy_url="http://host.docker.internal:9/v1/",
        proxy_token="t",
        model="m",
        contract=runner.EpisodeContract(max_reasoning_loops=1),
        timeout=900.0,
        bounds_path=tmp_path / "omega-bounds.yaml",
    )
    assert "-t" in command
    assert "-i" not in command
    assert f"config={runner.OMEGA_BOUNDS_CONTAINER_PATH}" in command
    assert not [a for a in command if a.startswith(("maxNewInputLoops=", "maxHistory="))]
