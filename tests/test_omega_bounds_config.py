"""The numeric episode bounds must reach Omega as YAML-typed configuration.

Omega's src/config.py applies no type coercion to command-line or environment
overrides (`dict[kv[0]] = kv[1]`), while the config file goes through
yaml.safe_load. src/config.metta hands the resolved value straight to
src/loop.metta, which uses it arithmetically. A numeric bound passed on argv
therefore arrives as a string and kills the agent with

    ERROR: [Thread main] .../main.pl:23: user:main is/2:
           Arithmetic: `'0'/0' is not a function

so these bounds must travel through a config file and never through argv.
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


runner = _load("omegaboi_bounds", CONTROLLER / "omegaboi.py")
episode = _load("episode_contract_bounds", CONTROLLER / "episode_contract.py")

NUMERIC_BOUND_KEYS = ("maxNewInputLoops", "maxWakeLoops", "maxHistory", "wakeupInterval")


def _command(tmp_path: Path, **overrides) -> list[str]:
    params = {
        "image": runner.stock_image_tag(),
        "container_name": "fixture",
        "proxy_url": "http://host.docker.internal:9999/v1/",
        "proxy_token": "token",
        "model": "model",
        "contract": runner.EpisodeContract(max_reasoning_loops=1),
        "timeout": 900.0,
        "bounds_path": tmp_path / "omega-bounds.yaml",
    }
    params.update(overrides)
    return runner._docker_run_command(**params)


def test_bounds_config_values_come_from_the_contract() -> None:
    contract = episode.EpisodeContract(max_reasoning_loops=1)
    bounds = contract.bounds_config(wakeup_interval=960)
    assert bounds == {
        "maxNewInputLoops": 1,
        "maxWakeLoops": 0,
        "maxHistory": 0,
        "wakeupInterval": 960,
    }


def test_every_bound_is_an_int_not_a_string() -> None:
    """The whole point: yaml.safe_load must yield ints, not strings."""
    bounds = episode.EpisodeContract(max_reasoning_loops=3).bounds_config(wakeup_interval=120)
    for key, value in bounds.items():
        assert isinstance(value, int), f"{key} is {type(value).__name__}, not int"
        assert not isinstance(value, bool)


def test_rendered_yaml_round_trips_to_ints() -> None:
    yaml = pytest.importorskip("yaml")
    contract = episode.EpisodeContract(max_reasoning_loops=1)
    loaded = yaml.safe_load(contract.bounds_yaml(wakeup_interval=960))
    assert loaded == contract.bounds_config(wakeup_interval=960)
    for key in NUMERIC_BOUND_KEYS:
        assert isinstance(loaded[key], int)


def test_yaml_is_minimal_and_carries_only_the_numeric_bounds() -> None:
    """Selecting a config file replaces Omega's whole config, so keep it minimal."""
    yaml = pytest.importorskip("yaml")
    loaded = yaml.safe_load(
        episode.EpisodeContract(max_reasoning_loops=1).bounds_yaml(wakeup_interval=960)
    )
    assert set(loaded) == set(NUMERIC_BOUND_KEYS)


def test_wakeup_interval_must_be_positive() -> None:
    with pytest.raises(ValueError, match="wakeup_interval must be positive"):
        episode.EpisodeContract().bounds_config(wakeup_interval=0)


def test_numeric_bounds_are_never_passed_on_the_command_line(tmp_path: Path) -> None:
    """The regression guard: argv is untyped and kills the agent."""
    command = _command(tmp_path)
    for key in NUMERIC_BOUND_KEYS:
        offenders = [arg for arg in command if arg.startswith(f"{key}=")]
        assert not offenders, f"{key} passed as an untyped CLI override: {offenders}"


def test_command_mounts_the_bounds_file_read_only(tmp_path: Path) -> None:
    command = _command(tmp_path)
    mount = f"{tmp_path / 'omega-bounds.yaml'}:{runner.OMEGA_BOUNDS_CONTAINER_PATH}:ro"
    assert "-v" in command
    assert mount in command


def test_command_selects_the_file_with_omegas_config_argument(tmp_path: Path) -> None:
    command = _command(tmp_path)
    assert f"config={runner.OMEGA_BOUNDS_CONTAINER_PATH}" in command


def test_mount_precedes_the_image_argument(tmp_path: Path) -> None:
    command = _command(tmp_path)
    assert command.index("-v") < command.index(runner.stock_image_tag())


def test_bounds_file_is_not_mounted_under_a_tmpfs_path() -> None:
    """tmpfs mounts at /tmp, /var/tmp and /run would shadow the file."""
    for shadowed in ("/tmp/", "/var/tmp/", "/run/"):
        assert not runner.OMEGA_BOUNDS_CONTAINER_PATH.startswith(shadowed)


def test_provider_channel_and_model_arguments_are_preserved(tmp_path: Path) -> None:
    """String-valued CLI args still work and still outrank the config file."""
    command = _command(tmp_path)
    assert "commchannel=test" in command
    assert "provider=OpenAIAPI" in command
    assert "embeddingprovider=Local" in command
    assert "api_token_var=OPENAIAPI_API_KEY" in command
    assert "model=model" in command
    assert "securityPolicyPath=/PeTTa/repos/OmegaClaw-Core/profile/policy.yaml" in command


def test_docker_hardening_is_unchanged(tmp_path: Path) -> None:
    command = _command(tmp_path)
    assert "--rm" in command
    assert "--init" in command
    assert "no-new-privileges:true" in command
    assert "/tmp:size=64m,mode=1777" in command
    assert "/var/tmp:size=64m,mode=1777" in command
    assert "/run:size=16m,mode=755" in command
    assert "host.docker.internal:host-gateway" in command


def test_manifest_states_bounds_semantics_without_overclaiming() -> None:
    semantics = episode.EpisodeContract(max_reasoning_loops=1).manifest()["bounds_semantics"]
    assert "not raw loop ticks" in semantics["maxNewInputLoops"]
    assert "HUMAN-MSG" in semantics["maxHistory"]
    assert "wake-driven" in semantics["maxWakeLoops"]
    assert "external metering gateway" in semantics["provider_calls"]
    assert "five skills" in semantics["skill_executions"]


def test_bounds_semantics_stay_out_of_the_omega_facing_handoff() -> None:
    """Receipt wording must not leak into the envelope Omega receives."""
    handoff = episode.EpisodeContract(max_reasoning_loops=1).handoff()
    assert "bounds_semantics" not in handoff
    assert "maxNewInputLoops" not in handoff
