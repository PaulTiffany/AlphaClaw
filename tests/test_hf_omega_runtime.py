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


stage = _load("stage", ROOT / "runtime" / "huggingface" / "stage.py")
manage = _load("omega_hf_manage", ROOT / "runtime" / "huggingface" / "manage_space.py")


def test_hf_runtime_constants_match_pinned_residency() -> None:
    assert stage.OMEGA_SHA == "3d711e4b9f5254ae94f31123ca242f60cfd97d29"
    assert stage.CHROMADB_SHA == "218484875d5d1bfb217a9a03d3983dc1ed9d406c"
    assert stage.PROVIDER == "ASIOne"
    assert stage.MODEL == "asi1-mini"


def test_generated_dockerfile_preserves_pin_and_public_surface() -> None:
    dockerfile = stage.render_dockerfile()
    assert f"ARG CHROMADB_REF={stage.CHROMADB_SHA}" in dockerfile
    assert 'checkout --detach "${CHROMADB_REF}"' in dockerfile
    assert "EXPOSE 7860" in dockerfile
    assert 'ENTRYPOINT ["/opt/alphaclaw-hf/entrypoint.sh"]' in dockerfile
    assert "OmegaClaw-Core/proxy/*" in dockerfile


def test_residency_dockerfile_uses_stock_omega_entrypoint() -> None:
    dockerfile = stage.render_residency_dockerfile()
    assert 'ENTRYPOINT ["/PeTTa/repos/OmegaClaw-Core/entrypoint.sh"]' in dockerfile
    assert 'ENTRYPOINT ["/opt/alphaclaw-hf/entrypoint.sh"]' not in dockerfile


def test_health_server_is_only_explicit_public_surface() -> None:
    entrypoint = (ROOT / "runtime" / "huggingface" / "hf_entrypoint.sh").read_text()
    assert "health.py" in entrypoint
    assert "ASIONE_API_KEY" in entrypoint
    assert "provider=ASIOne" in entrypoint
    assert "model=asi1-mini" in entrypoint
    assert "commchannel=websocket" in entrypoint
    assert "8080" not in entrypoint


def test_off_revokes_secret_before_pause() -> None:
    calls: list[tuple[str, str | None]] = []

    class API:
        def get_space_secrets(self, repo_id: str):
            calls.append(("get_space_secrets", repo_id))
            if any(call[0] == "delete_space_secret" for call in calls):
                return {}
            return {manage.ASI_SECRET: object(), manage.WS_SECRET: object()}

        def delete_space_secret(self, repo_id: str, key: str):
            calls.append(("delete_space_secret", key))

        def pause_space(self, repo_id: str):
            calls.append(("pause_space", repo_id))

        def get_space_runtime(self, repo_id: str):
            calls.append(("get_space_runtime", repo_id))
            return type(
                "Runtime",
                (),
                {
                    "stage": "PAUSED",
                    "hardware": "cpu-basic",
                    "requested_hardware": "cpu-basic",
                },
            )()

    result = manage.turn_off(API(), "PaulTiffany/omega")
    pause_index = calls.index(("pause_space", "PaulTiffany/omega"))
    delete_indexes = [i for i, call in enumerate(calls) if call[0] == "delete_space_secret"]
    assert delete_indexes
    assert max(delete_indexes) < pause_index
    assert result["asi_secret_present"] is False


def test_stage_rejects_wrong_omega_pin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(stage, "git_head", lambda path: "wrong")
    with pytest.raises(RuntimeError, match="pin mismatch"):
        stage.validate_source()
