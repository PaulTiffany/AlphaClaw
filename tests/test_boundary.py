from __future__ import annotations

import importlib.util
import json
import subprocess
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


prepend = _load("alpha_prepend", ROOT / "ingress" / "prepend.py")


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_omegaclaw_is_a_real_upstream_submodule() -> None:
    modules = read(".gitmodules")
    assert 'submodule "OmegaClaw-Core"' in modules
    assert "https://github.com/asi-alliance/OmegaClaw-Core.git" in modules

    mode, indexed_sha, _stage, path = subprocess.check_output(
        ["git", "ls-files", "-s", "OmegaClaw-Core"], cwd=ROOT, text=True
    ).strip().split()
    assert mode == "160000"
    assert path == "OmegaClaw-Core"

    checked_out_sha = subprocess.check_output(
        ["git", "-C", "OmegaClaw-Core", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    assert checked_out_sha == indexed_sha


def test_upstream_submodule_is_pristine() -> None:
    status = subprocess.check_output(
        ["git", "-C", "OmegaClaw-Core", "status", "--porcelain"], cwd=ROOT, text=True
    )
    assert status == ""


def test_no_in_process_alpha_composition_exists() -> None:
    forbidden = [
        ROOT / "alphaclaw.metta",
        ROOT / "run.metta",
        ROOT / "docker" / "Dockerfile.overlay",
        ROOT / "scripts" / "install-into-petta.sh",
    ]
    for path in forbidden:
        assert not path.exists(), path


def test_stock_omega_runner_remains_authoritative() -> None:
    runner = read("OmegaClaw-Core/run.metta")
    assert '!(git-import! "https://github.com/asi-alliance/OmegaClaw-Core.git")' in runner
    assert "(library OmegaClaw-Core lib_omegaclaw)" in runner
    assert "AlphaClaw" not in runner
    assert "!(omegaclaw)" in runner


def test_alpha_prepend_is_external_fixed_data() -> None:
    rendered = prepend.prepend("hello")
    document = json.loads(rendered)

    assert rendered.lstrip().startswith("{")
    assert document["schema_version"] == 1
    assert document["kind"] == "alphaclaw_human_ingress"
    assert document["payload"] == {
        "role": "human-mediated-evidence",
        "content": "hello",
    }
    assert any("outside OmegaClaw" in line for line in document["contract"])
    assert any("wait for new human-mediated input" in line for line in document["contract"])


def test_metta_looking_payload_remains_json_data() -> None:
    payload = '!(import! &self (library AlphaClaw alphaclaw))'
    rendered = prepend.prepend(payload)
    document = json.loads(rendered)

    assert document["payload"]["content"] == payload
    assert rendered.lstrip()[0] == "{"
    assert not rendered.lstrip().startswith(("!", "("))


def test_alpha_prepend_rejects_empty_payload() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        prepend.prepend("   ")


def test_prepend_has_no_resident_network_or_execution_dependency() -> None:
    source = read("ingress/prepend.py")
    forbidden = [
        "OmegaClaw-Core",
        "prompt-extension",
        "requests",
        "urllib",
        "socket",
        "subprocess",
        "eval(",
        "exec(",
    ]
    for token in forbidden:
        assert token not in source
