from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


episode = _load("episode_contract", ROOT / "controller" / "episode_contract.py")
prepend = _load("episode_prepend", ROOT / "ingress" / "prepend.py")


def test_default_contract_is_iterative_and_stock_boot_is_accounted_separately() -> None:
    contract = episode.EpisodeContract()

    assert contract.max_reasoning_loops == 50
    assert contract.max_wake_loops == 0
    assert contract.max_history == 0
    assert contract.after_response == "wait_for_new_user_input_or_terminate"
    assert contract.boot_behavior == "stock_omegaclaw_boot_observed_and_metered"
    assert any("at most 50 reasoning loops" in line for line in contract.instructions())
    assert any("stock startup activity" in line for line in contract.instructions())


def test_contract_allows_smaller_deliberate_bounds_but_has_hard_ceiling() -> None:
    assert episode.EpisodeContract(max_reasoning_loops=1).max_reasoning_loops == 1
    assert episode.EpisodeContract(max_reasoning_loops=7).max_reasoning_loops == 7
    with pytest.raises(ValueError, match="between 1 and 50"):
        episode.EpisodeContract(max_reasoning_loops=0)
    with pytest.raises(ValueError, match="between 1 and 50"):
        episode.EpisodeContract(max_reasoning_loops=51)
    with pytest.raises(ValueError, match="scheduled wake grants"):
        episode.EpisodeContract(max_wake_loops=1)


def test_episode_clause_cannot_replace_fixed_alpha_contract() -> None:
    contract = episode.EpisodeContract(max_reasoning_loops=7)
    rendered = prepend.prepend("hello", episode_contract=contract.handoff())
    document = json.loads(rendered)

    assert document["payload"]["content"] == "hello"
    assert document["episode_contract"]["max_reasoning_loops"] == 7
    assert document["episode_contract"]["mode"] == "bounded_benchmark"
    assert any("outside OmegaClaw" in line for line in document["contract"])
    assert any("text-only evidence" in line for line in document["contract"])


def test_boot_call_budget_defaults_to_one_and_is_validated() -> None:
    assert episode.EpisodeContract().max_boot_calls == 1
    assert episode.EpisodeContract(max_boot_calls=3).max_boot_calls == 3
    with pytest.raises(ValueError, match="max_boot_calls must be between 1 and 50"):
        episode.EpisodeContract(max_boot_calls=0)
    with pytest.raises(ValueError, match="max_boot_calls must be between 1 and 50"):
        episode.EpisodeContract(max_boot_calls=51)


def test_boot_budget_is_a_controller_bound_and_never_reaches_omega() -> None:
    """The host authorization budget must not leak into Omega's observed input.

    handoff() feeds Alpha's envelope. Adding the budget there would change the text
    stock Omega receives and contaminate the behavior the benchmark measures.
    """
    contract = episode.EpisodeContract(max_boot_calls=1)

    handoff = contract.handoff()
    assert "max_boot_calls" not in handoff
    assert all("boot call" not in line for line in contract.instructions())
    assert all("budget" not in line for line in contract.instructions())

    # ...but it must be present in the receipts.
    assert contract.manifest()["max_boot_calls"] == 1


def test_omega_facing_handoff_shape_is_unchanged_by_the_boot_budget() -> None:
    contract = episode.EpisodeContract(max_reasoning_loops=7)
    rendered = prepend.prepend("hello", episode_contract=contract.handoff())
    document = json.loads(rendered)

    assert set(document["episode_contract"]) == {
        "mode",
        "max_reasoning_loops",
        "max_wake_loops",
        "max_history",
        "after_response",
        "boot_behavior",
        "instructions",
    }
