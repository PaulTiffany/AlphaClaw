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
    assert stage.LIFE_CYCLES == 8
    assert stage.WAKE_CYCLES == 0


def test_generated_dockerfile_preserves_pin_and_public_surface() -> None:
    dockerfile = stage.render_dockerfile()
    assert f"ARG CHROMADB_REF={stage.CHROMADB_SHA}" in dockerfile
    assert 'checkout --detach "${CHROMADB_REF}"' in dockerfile
    assert "cmake --build build --config Release --parallel 1" in dockerfile
    assert "cmake --build build --config Release --parallel \\\n" not in dockerfile
    assert "EXPOSE 7860" in dockerfile
    assert 'ENTRYPOINT ["/opt/alphaclaw-hf/entrypoint.sh"]' in dockerfile
    assert "OmegaClaw-Core/proxy/*" in dockerfile
    assert "error_log /tmp/nginx-error.log warn;" in dockerfile
    assert "access_log /tmp/nginx-access.log;" in dockerfile
    assert "s#error_log /dev/stderr warn;#" in dockerfile
    assert "s#access_log /dev/stdout;#" in dockerfile
    assert "COPY alphaclaw-runtime.yaml /opt/alphaclaw-hf/alphaclaw-runtime.yaml" in dockerfile
    assert "ENV OMEGACLAW_config=/opt/alphaclaw-hf/alphaclaw-runtime.yaml" in dockerfile


def test_residency_dockerfile_uses_stock_omega_entrypoint_but_same_alpha_config() -> None:
    dockerfile = stage.render_residency_dockerfile()
    assert 'ENTRYPOINT ["/PeTTa/repos/OmegaClaw-Core/entrypoint.sh"]' in dockerfile
    assert 'ENTRYPOINT ["/opt/alphaclaw-hf/entrypoint.sh"]' not in dockerfile
    assert "ENV OMEGACLAW_config=/opt/alphaclaw-hf/alphaclaw-runtime.yaml" in dockerfile


def test_staged_omega_entrypoint_preserves_alpha_config(tmp_path: Path) -> None:
    entrypoint = tmp_path / "entrypoint.sh"
    entrypoint.write_text(
        'SAFE_VARS="HOME USER PATH HOSTNAME TERM LANG LC_ALL \\\n'
        '  PYTHONDONTWRITEBYTECODE PYTHONUNBUFFERED"\n',
        encoding="utf-8",
    )
    stage.preserve_alpha_config_through_privilege_drop(entrypoint)
    text = entrypoint.read_text(encoding="utf-8")
    assert "LC_ALL OMEGACLAW_config" in text


def test_default_resident_is_asi_one_mini_with_hard_life_cap() -> None:
    entrypoint = (ROOT / "runtime" / "huggingface" / "hf_entrypoint.sh").read_text()
    runtime_config = (ROOT / "runtime" / "huggingface" / "alphaclaw-runtime.yaml").read_text()

    assert "health.py" in entrypoint
    assert "ASI_ONE_API_KEY" in entrypoint
    assert "ASIONE_API_KEY" in entrypoint
    assert "provider=ASIOne" in entrypoint
    assert "model=asi1-mini" in entrypoint
    assert "readonly ALPHACLAW_MAX_NEW_INPUT_LOOPS=8" in entrypoint
    assert "readonly ALPHACLAW_MAX_WAKE_LOOPS=0" in entrypoint
    assert "maxNewInputLoops: 8" in runtime_config
    assert "maxWakeLoops: 0" in runtime_config
    assert "provider=ASICloud" not in entrypoint
    assert "minimax/minimax-m3" not in entrypoint
    assert "commchannel=websocket" in entrypoint
    assert "8080" not in entrypoint


def test_hf_entrypoint_preflights_staged_libraries_before_health() -> None:
    entrypoint = (ROOT / "runtime" / "huggingface" / "hf_entrypoint.sh").read_text()
    omega_check = "test -f /PeTTa/repos/OmegaClaw-Core/lib_omegaclaw.metta"
    alpha_check = "test -f /PeTTa/repos/AlphaClaw/alphaclaw.metta"
    health_start = "python3 /opt/alphaclaw-hf/health.py &"
    assert omega_check in entrypoint
    assert alpha_check in entrypoint
    assert entrypoint.index(omega_check) < entrypoint.index(health_start)
    assert entrypoint.index(alpha_check) < entrypoint.index(health_start)


def test_runtime_log_redaction() -> None:
    text = manage.redact("alpha secret-a omega secret-b", ("secret-a", "secret-b"))
    assert text == "alpha [REDACTED] omega [REDACTED]"


def test_runtime_error_is_witnessed_before_fail_closed_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setenv("ASI_ONE_API_KEY", "asi-secret")
    monkeypatch.setenv("OMEGA_WS_TOKEN", "ws-secret")
    monkeypatch.setattr(manage, "synchronize", lambda api, repo_id, private: None)
    monkeypatch.setattr(
        manage,
        "emit_runtime_logs",
        lambda api, repo_id, secrets: calls.append("runtime-logs"),
    )
    monkeypatch.setattr(
        manage,
        "revoke_runtime_authority",
        lambda api, repo_id: calls.append("revoke"),
    )

    class API:
        def add_space_secret(self, **kwargs):
            return None

        def add_space_variable(self, **kwargs):
            return None

        def restart_space(self, repo_id: str):
            return None

        def wait_for_space(self, **kwargs):
            return type("Runtime", (), {"stage": "RUNTIME_ERROR"})()

    with pytest.raises(RuntimeError, match="final stage=RUNTIME_ERROR"):
        manage.turn_on(API(), "PaulTiffany/omega", True)

    assert calls == ["runtime-logs", "revoke"]


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
