from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


stage = _load("stage_plugin_once", ROOT / "runtime" / "huggingface" / "stage.py")

PINNED = "(let $rcs (collapse (eval (loadOmegaClawPlugin))) ())"
COMMITTED = "(let $rcs (collapse (once (eval (loadOmegaClawPlugin)))) ())"


def test_pinned_omega_still_exposes_enumerating_plugin_initializer() -> None:
    text = (ROOT / "OmegaClaw-Core" / "src" / "plugin.metta").read_text(encoding="utf-8")
    assert text.count(PINNED) == 1
    assert COMMITTED not in text


def test_staging_commits_effectful_plugin_initializer_once(tmp_path: Path) -> None:
    plugin_loader = tmp_path / "plugin.metta"
    plugin_loader.write_text(
        (ROOT / "OmegaClaw-Core" / "src" / "plugin.metta").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    stage.commit_metta_plugin_initializers(plugin_loader)

    text = plugin_loader.read_text(encoding="utf-8")
    assert PINNED not in text
    assert text.count(COMMITTED) == 1


def test_staging_fails_closed_if_pinned_plugin_loader_moves(tmp_path: Path) -> None:
    plugin_loader = tmp_path / "plugin.metta"
    plugin_loader.write_text("(= (loadMettaPlugin) changed)\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="plugin initializer changed"):
        stage.commit_metta_plugin_initializers(plugin_loader)
