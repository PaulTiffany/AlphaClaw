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


def test_default_contract_is_fifty_loops_and_no_wakeups() -> None:
    contract = episode.EpisodeContract()

    assert contract.max_reasoning_loops == 50
    assert contract.max_wake_loops == 0
    assert contract.max_history == 0
    assert contract.after_response == "wait_for_new_user_input_or_terminate"
    assert any("at most 50 total reasoning loops" in line for line in contract.instructions())
    assert any("inference grant ends" in line for line in contract.instructions())


def test_contract_rejects_autonomous_wakeups_or_empty_budget() -> None:
    with pytest.raises(ValueError, match="positive"):
        episode.EpisodeContract(max_reasoning_loops=0)
    with pytest.raises(ValueError, match="wake loops"):
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
