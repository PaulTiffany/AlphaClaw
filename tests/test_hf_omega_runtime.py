from __future__ import annotations

import importlib.util
import shutil
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


def test_hf_runtime_constants_match_minimum_authority_residency() -> None:
    assert stage.OMEGA_SHA == "3d711e4b9f5254ae94f31123ca242f60cfd97d29"
    assert stage.CHROMADB_SHA == "218484875d5d1bfb217a9a03d3983dc1ed9d406c"
    assert stage.PROVIDER == "ASIOne"
    assert stage.MODEL == "asi1-mini"
    assert stage.BOOT_CYCLES == 0
    assert stage.LIFE_CYCLES == 8
    assert stage.WAKE_CYCLES == 0
    assert stage.HISTORY_CHARS == 0
    assert stage.MODEL_ACTIONS == ("send",)
    assert stage.RESIDENT_PLUGINS == ("wschat", "asione")
    assert manage.RESIDENT_SPACE_ID == "PaulTiffany/alphaclaw-omega"


def test_generated_dockerfile_is_stock_omega_plus_boundary_bindings() -> None:
    dockerfile = stage.render_dockerfile()
    assert f"ARG CHROMADB_REF={stage.CHROMADB_SHA}" in dockerfile
    assert 'checkout --detach "${CHROMADB_REF}"' in dockerfile
    assert "cmake --build build --config Release --parallel 1" in dockerfile
    assert "EXPOSE 7860" in dockerfile
    assert 'ENTRYPOINT ["/opt/alphaclaw-hf/entrypoint.sh"]' in dockerfile
    assert "OmegaClaw-Core/proxy/*" in dockerfile
    assert "error_log /tmp/nginx-error.log warn;" in dockerfile
    assert "access_log /tmp/nginx-access.log;" in dockerfile
    assert "COPY alphaclaw-runtime.yaml /opt/alphaclaw-hf/alphaclaw-runtime.yaml" in dockerfile
    assert "ENV OMEGACLAW_config=/opt/alphaclaw-hf/alphaclaw-runtime.yaml" in dockerfile
    assert "COPY alphaclaw.metta" not in dockerfile
    assert "COPY run.metta" not in dockerfile
    assert "mkdir -p /PeTTa/repos/AlphaClaw" not in dockerfile
    assert "test ! -e /PeTTa/repos/AlphaClaw" in dockerfile


def test_residency_dockerfile_uses_stock_omega_entrypoint() -> None:
    dockerfile = stage.render_residency_dockerfile()
    assert 'ENTRYPOINT ["/PeTTa/repos/OmegaClaw-Core/entrypoint.sh"]' in dockerfile
    assert 'ENTRYPOINT ["/opt/alphaclaw-hf/entrypoint.sh"]' not in dockerfile
    assert "ENV OMEGACLAW_config=/opt/alphaclaw-hf/alphaclaw-runtime.yaml" in dockerfile


def test_staged_omega_entrypoint_preserves_runtime_config(tmp_path: Path) -> None:
    entrypoint = tmp_path / "entrypoint.sh"
    entrypoint.write_text(
        'SAFE_VARS="HOME USER PATH HOSTNAME TERM LANG LC_ALL \\\n'
        '  PYTHONDONTWRITEBYTECODE PYTHONUNBUFFERED"\n',
        encoding="utf-8",
    )
    stage.preserve_runtime_config_through_privilege_drop(entrypoint)
    text = entrypoint.read_text(encoding="utf-8")
    assert "LC_ALL OMEGACLAW_config" in text


def test_human_gate_starts_zero_and_refills_on_first_new_message(tmp_path: Path) -> None:
    upstream = ROOT / "OmegaClaw-Core" / "src" / "loop.metta"
    loop = tmp_path / "loop.metta"
    shutil.copy2(upstream, loop)

    original = upstream.read_text(encoding="utf-8")
    assert original.count("(change-state! &loops (maxNewInputLoops))") == 2
    assert "(if (and (> $k 1) $msgnew)" in original

    stage.require_human_input_before_inference(loop)
    transformed = loop.read_text(encoding="utf-8")

    assert "AlphaClaw embodiment gate: boot grants no inference authority" in transformed
    assert transformed.count("(change-state! &loops 0)") == 1
    assert "(change-state! &nextWakeAt (+ (get_time) (wakeupInterval)))" in transformed
    assert transformed.count("(change-state! &loops (maxNewInputLoops))") == 1
    assert "(if (and (> $k 1) $msgnew)" not in transformed
    assert "(if $msgnew" in transformed
    assert upstream.read_text(encoding="utf-8") == original


def test_staged_plugin_allowlist_contains_only_channel_and_provider(tmp_path: Path) -> None:
    upstream = ROOT / "OmegaClaw-Core" / "config" / "plugins.yaml"
    plugins = tmp_path / "plugins.yaml"
    shutil.copy2(upstream, plugins)

    original = upstream.read_text(encoding="utf-8")
    assert "- name: workflow" in original
    assert "- name: openclaw" in original
    assert "- name: openrouter" in original

    stage.restrict_resident_plugins(plugins)
    staged = plugins.read_text(encoding="utf-8")
    names = [
        line.removeprefix("- name: ").strip()
        for line in staged.splitlines()
        if line.startswith("- name: ")
    ]
    assert names == ["wschat", "asione"]
    assert "workflow" not in staged
    assert "openclaw" not in staged
    assert "openrouter" not in staged
    assert upstream.read_text(encoding="utf-8") == original


def test_staged_model_action_surface_is_send_only(tmp_path: Path) -> None:
    upstream_helper = ROOT / "OmegaClaw-Core" / "src" / "helper.py"
    upstream_skills = ROOT / "OmegaClaw-Core" / "src" / "skills.metta"
    helper = tmp_path / "helper.py"
    skills = tmp_path / "skills.metta"
    shutil.copy2(upstream_helper, helper)
    shutil.copy2(upstream_skills, skills)

    original_helper = upstream_helper.read_text(encoding="utf-8")
    original_skills = upstream_skills.read_text(encoding="utf-8")
    assert '"shell"' in original_helper
    assert '"metta"' in original_helper
    assert "Execute shell command" in original_skills

    stage.restrict_model_action_surface(helper, skills)
    staged_helper = helper.read_text(encoding="utf-8")
    staged_skills = skills.read_text(encoding="utf-8")

    assert 'STATIC_LLM_COMMANDS = {"send"}' in staged_helper
    assert "LLM_COMMANDS.add" not in staged_helper
    assert "return str(command) in STATIC_LLM_COMMANDS" in staged_helper
    assert '(= (getSkills)\n   (getStaticSkills))' in staged_skills
    assert '"- Send message to user: send string"' in staged_skills
    assert "Execute shell command" not in staged_skills
    assert "Search the web" not in staged_skills
    assert "Execute MeTTa expression" not in staged_skills
    assert upstream_helper.read_text(encoding="utf-8") == original_helper
    assert upstream_skills.read_text(encoding="utf-8") == original_skills


def test_default_resident_is_asi_one_mini_with_minimum_authority() -> None:
    entrypoint = (ROOT / "runtime" / "huggingface" / "hf_entrypoint.sh").read_text()
    runtime_config = (ROOT / "runtime" / "huggingface" / "alphaclaw-runtime.yaml").read_text()

    assert "health.py" in entrypoint
    assert "ASI_ONE_API_KEY" in entrypoint
    assert "ASIONE_API_KEY" in entrypoint
    assert "provider=ASIOne" in entrypoint
    assert "model=asi1-mini" in entrypoint
    assert "readonly ALPHACLAW_BOOT_LOOPS=0" in entrypoint
    assert "readonly ALPHACLAW_MAX_NEW_INPUT_LOOPS=8" in entrypoint
    assert "readonly ALPHACLAW_MAX_WAKE_LOOPS=0" in entrypoint
    assert "readonly ALPHACLAW_MAX_HISTORY_CHARS=0" in entrypoint
    assert "readonly ALPHACLAW_MODEL_ACTIONS=send" in entrypoint
    assert "readonly ALPHACLAW_RESIDENT_PLUGINS=wschat,asione" in entrypoint
    assert "maxNewInputLoops: 8" in runtime_config
    assert "maxWakeLoops: 0" in runtime_config
    assert "maxHistory: 0" in runtime_config
    assert "provider=ASICloud" not in entrypoint
    assert "minimax/minimax-m3" not in entrypoint
    assert "commchannel=websocket" in entrypoint
    assert "8080" not in entrypoint


def test_hf_entrypoint_guards_boundary_before_health() -> None:
    entrypoint = (ROOT / "runtime" / "huggingface" / "hf_entrypoint.sh").read_text()
    health_start = "python3 /opt/alphaclaw-hf/health.py &"
    required_before_health = [
        "test ! -e /PeTTa/repos/AlphaClaw",
        "OPENROUTER_API_KEY",
        "ASI_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "MINIMAX_API_KEY",
        "grep -Fc '(change-state! &loops 0)'",
        "grep -Fc '(change-state! &loops (maxNewInputLoops))'",
        "first-iteration human input would not refill authority",
        "collapse (eval (loadOmegaClawPlugin))",
        "once (eval (loadOmegaClawPlugin))",
        'names != ["wschat", "asione"]',
        'helper.STATIC_LLM_COMMANDS != {"send"}',
        'helper.add_llm_command("shell")',
        'helper.balance_parentheses("shell env")',
        "grep -Fq 'maxHistory: 0'",
        "OMEGA_WS_URL must use wss://",
    ]
    for token in required_before_health:
        assert token in entrypoint
        assert entrypoint.index(token) < entrypoint.index(health_start)
    assert "alphaclaw.metta" not in entrypoint


def test_forbidden_secret_set_excludes_resident_authority() -> None:
    assert manage.ASI_SECRET not in manage.FORBIDDEN_RESIDENT_SECRET_KEYS
    assert manage.WS_SECRET not in manage.FORBIDDEN_RESIDENT_SECRET_KEYS
    assert {"OPENROUTER_API_KEY", "ASI_API_KEY"} <= manage.FORBIDDEN_RESIDENT_SECRET_KEYS


def test_controller_has_no_configurable_space_target() -> None:
    source = (ROOT / "runtime" / "huggingface" / "manage_space.py").read_text()
    workflow = (ROOT / ".github" / "workflows" / "omega-space.yml").read_text()
    assert "HF_OMEGA_SPACE_ID" not in source
    assert "HF_OMEGA_SPACE_ID" not in workflow
    assert manage.RESIDENT_SPACE_ID in source


def test_scrub_forbidden_resident_secrets() -> None:
    secrets = {
        manage.ASI_SECRET: object(),
        "OPENROUTER_API_KEY": object(),
        "ASI_API_KEY": object(),
    }
    deleted: list[str] = []

    class API:
        def get_space_secrets(self, repo_id: str):
            return dict(secrets)

        def delete_space_secret(self, repo_id: str, key: str):
            deleted.append(key)
            secrets.pop(key, None)

    manage.scrub_forbidden_resident_secrets(API(), manage.RESIDENT_SPACE_ID)
    assert set(deleted) == {"OPENROUTER_API_KEY", "ASI_API_KEY"}
    assert set(secrets) == {manage.ASI_SECRET}


def test_turn_on_scrubs_forbidden_secrets_before_restart(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ASI_ONE_API_KEY", "asi-secret")
    monkeypatch.setenv("OMEGA_WS_URL", "wss://example.invalid/omega")
    monkeypatch.setenv("OMEGA_WS_TOKEN", "ws-secret")
    monkeypatch.setattr(manage, "synchronize", lambda api, repo_id, private: None)

    events: list[str] = []
    secrets: dict[str, object] = {"OPENROUTER_API_KEY": object()}

    class API:
        def get_space_secrets(self, repo_id: str):
            return dict(secrets)

        def delete_space_secret(self, repo_id: str, key: str):
            events.append(f"delete:{key}")
            secrets.pop(key, None)

        def add_space_secret(self, repo_id: str, key: str, value: str, description: str):
            events.append(f"add:{key}")
            secrets[key] = object()

        def add_space_variable(self, **kwargs):
            return None

        def restart_space(self, repo_id: str):
            events.append("restart")

        def wait_for_space(self, **kwargs):
            return type(
                "Runtime",
                (),
                {
                    "stage": "RUNNING",
                    "hardware": "cpu-basic",
                    "requested_hardware": "cpu-basic",
                },
            )()

    result = manage.turn_on(API(), manage.RESIDENT_SPACE_ID, True)
    assert events.index("delete:OPENROUTER_API_KEY") < events.index("restart")
    assert result["space_id"] == manage.RESIDENT_SPACE_ID
    assert result["forbidden_resident_secrets"] == []
    assert result["asi_secret_present"] is True


def test_turn_on_rejects_wrong_space_before_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASI_ONE_API_KEY", "asi-secret")
    called = False

    def synchronize(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(manage, "synchronize", synchronize)
    with pytest.raises(RuntimeError, match="resident Space is fixed"):
        manage.turn_on(object(), "someone/else", True)
    assert called is False


def test_turn_on_rejects_plaintext_websocket_before_sync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ASI_ONE_API_KEY", "asi-secret")
    monkeypatch.setenv("OMEGA_WS_URL", "ws://example.invalid/omega")
    called = False

    def synchronize(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(manage, "synchronize", synchronize)
    with pytest.raises(RuntimeError, match="must start with wss://"):
        manage.turn_on(object(), manage.RESIDENT_SPACE_ID, True)
    assert called is False


def test_runtime_log_redaction() -> None:
    text = manage.redact("alpha secret-a omega secret-b", ("secret-a", "secret-b"))
    assert text == "alpha [REDACTED] omega [REDACTED]"


def test_runtime_error_is_witnessed_before_fail_closed_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setenv("ASI_ONE_API_KEY", "asi-secret")
    monkeypatch.delenv("OMEGA_WS_URL", raising=False)
    monkeypatch.delenv("OMEGA_WS_TOKEN", raising=False)
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

    secrets: dict[str, object] = {}

    class API:
        def get_space_secrets(self, repo_id: str):
            return dict(secrets)

        def delete_space_secret(self, repo_id: str, key: str):
            secrets.pop(key, None)

        def add_space_secret(self, repo_id: str, key: str, value: str, description: str):
            secrets[key] = object()

        def add_space_variable(self, **kwargs):
            return None

        def restart_space(self, repo_id: str):
            return None

        def wait_for_space(self, **kwargs):
            return type("Runtime", (), {"stage": "RUNTIME_ERROR"})()

    with pytest.raises(RuntimeError, match="final stage=RUNTIME_ERROR"):
        manage.turn_on(API(), manage.RESIDENT_SPACE_ID, True)

    assert calls == ["runtime-logs", "revoke"]


def test_off_revokes_all_resident_and_forbidden_secrets_before_pause() -> None:
    calls: list[tuple[str, str | None]] = []
    secrets = {
        manage.ASI_SECRET: object(),
        manage.WS_SECRET: object(),
        "OPENROUTER_API_KEY": object(),
        "ASI_API_KEY": object(),
    }

    class API:
        def get_space_secrets(self, repo_id: str):
            calls.append(("get_space_secrets", repo_id))
            return dict(secrets)

        def delete_space_secret(self, repo_id: str, key: str):
            calls.append(("delete_space_secret", key))
            secrets.pop(key, None)

        def pause_space(self, repo_id: str):
            calls.append(("pause_space", repo_id))

        def get_space_runtime(self, repo_id: str):
            return type(
                "Runtime",
                (),
                {
                    "stage": "PAUSED",
                    "hardware": "cpu-basic",
                    "requested_hardware": "cpu-basic",
                },
            )()

    result = manage.turn_off(API(), manage.RESIDENT_SPACE_ID)
    pause_index = calls.index(("pause_space", manage.RESIDENT_SPACE_ID))
    delete_indexes = [i for i, call in enumerate(calls) if call[0] == "delete_space_secret"]
    assert delete_indexes
    assert max(delete_indexes) < pause_index
    assert result["asi_secret_present"] is False
    assert result["forbidden_resident_secrets"] == []
    assert secrets == {}


def test_stage_rejects_wrong_omega_pin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(stage, "git_head", lambda path: "wrong")
    with pytest.raises(RuntimeError, match="pin mismatch"):
        stage.validate_source()
