"""Runtime-flag regressions for the fresh stock Omega container.

Stock Omega's entrypoint drops nginx to www-data and its config logs to /dev/stderr.
Whether that open() succeeds depends entirely on how Docker attached fd 2, so the
controller's runtime flags are load-bearing for startup, not just for containment.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import tempfile
import sys
import uuid
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


runner = _load("omegaboi_runtime", CONTROLLER / "omegaboi.py")

# Reproduces the stock startup condition: nginx loading a config whose error_log is
# /dev/stderr, running as www-data exactly as OmegaClaw-Core/entrypoint.sh does.
NGINX_PROBE = (
    "printf 'error_log /dev/stderr warn;\npid /tmp/nginx.pid;\nevents {}\nhttp {}\n'"
    " > /tmp/alphaclaw-probe.conf; chmod 0644 /tmp/alphaclaw-probe.conf;"
    " su www-data -s /bin/sh -c 'nginx -t -c /tmp/alphaclaw-probe.conf'"
)


# A real bounds file on disk: the command mounts it, so the Docker-backed probes
# below need it to exist rather than letting Docker invent an empty directory.
_CONTRACT = runner.EpisodeContract(max_reasoning_loops=1)
_BOUNDS_FILE = Path(tempfile.mkdtemp(prefix="alphaclaw-runtime-")) / "omega-bounds.yaml"
_BOUNDS_FILE.write_text(_CONTRACT.bounds_yaml(wakeup_interval=180), encoding="utf-8")
_BOUNDS_FILE.chmod(0o644)


def _command(**overrides) -> list[str]:
    params = {
        "image": runner.stock_image_tag(),
        "container_name": "fixture",
        "proxy_url": "http://host.docker.internal:9999/v1/",
        "proxy_token": "token",
        "model": "model",
        "contract": _CONTRACT,
        "timeout": 120.0,
        "bounds_path": _BOUNDS_FILE,
    }
    params.update(overrides)
    return runner._docker_run_command(**params)


def test_command_allocates_a_tty() -> None:
    assert "-t" in _command()


def test_command_does_not_attach_stdin() -> None:
    """Omega reads from the benchmark channel, never stdin."""
    command = _command()
    assert "-i" not in command
    assert "-it" not in command


def test_tty_flag_does_not_displace_any_containment_flag() -> None:
    command = _command()
    assert "--rm" in command
    assert "--init" in command
    assert "no-new-privileges:true" in command
    assert "/tmp:size=64m,mode=1777" in command
    assert "/var/tmp:size=64m,mode=1777" in command
    assert "/run:size=16m,mode=755" in command
    assert "host.docker.internal:host-gateway" in command


def test_tty_precedes_the_image_argument() -> None:
    """Docker only accepts run flags before the image name."""
    command = _command()
    assert command.index("-t") < command.index(runner.stock_image_tag())


# --- Docker-backed reproduction ------------------------------------------------
# Skipped unless the pinned stock image is already present locally. These never
# build an image, never start Omega, and never contact a provider.


def _stock_image_available() -> bool:
    if shutil.which("docker") is None:
        return False
    return runner._docker_image_id(runner.stock_image_tag()) is not None


requires_stock_image = pytest.mark.skipif(
    not _stock_image_available(),
    reason="pinned stock Omega image not present locally",
)


def _run_probe(*, with_tty: bool) -> subprocess.CompletedProcess[str]:
    """Run the nginx probe under the controller's real runtime flags."""
    image = runner.stock_image_tag()
    command = _command(container_name=f"alphaclaw-probe-{uuid.uuid4().hex[:10]}")
    prefix = command[: command.index(image)]
    if not with_tty:
        prefix = [flag for flag in prefix if flag != "-t"]

    return subprocess.run(
        [*prefix, "--entrypoint", "/bin/sh", image, "-c", NGINX_PROBE],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=180,
        check=False,
    )


@requires_stock_image
def test_stock_nginx_dev_stderr_succeeds_under_full_runtime_flags() -> None:
    """The regression: stock nginx must load its config under our real flag set."""
    result = _run_probe(with_tty=True)
    assert result.returncode == 0, result.stdout
    assert "Permission denied" not in result.stdout


@requires_stock_image
def test_stock_nginx_dev_stderr_fails_without_tty() -> None:
    """The failure this flag fixes, reproduced by removing only the TTY."""
    result = _run_probe(with_tty=False)
    assert result.returncode != 0
    assert '/dev/stderr" failed (13: Permission denied)' in result.stdout


@requires_stock_image
def test_containment_flags_are_not_what_gated_startup() -> None:
    """Removing every hardening flag must not fix it; only the TTY does.

    Guards against a future 'fix' that weakens the sandbox instead.
    """
    image = runner.stock_image_tag()
    result = subprocess.run(
        ["docker", "run", "--rm", "--entrypoint", "/bin/sh", image, "-c", NGINX_PROBE],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=180,
        check=False,
    )
    assert result.returncode != 0
    assert '/dev/stderr" failed (13: Permission denied)' in result.stdout
