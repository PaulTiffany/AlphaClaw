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


def test_runtime_constants_are_minimum_authority() -> None:
    assert stage.OMEGA_SHA == "3d711e4b9f5254ae94f31123ca242f60cfd97d29"
    assert stage.PROVIDER == "ASIOne"
    assert stage.MODEL == "asi1-mini"
    assert (stage.BOOT_CYCLES, stage.LIFE_CYCLES, stage.WAKE_CYCLES) == (0, 8, 0)
    assert stage.HISTORY_CHARS == 0
    assert stage.PERSIST_HISTORY is False
    assert stage.MODEL_ACTIONS == ("send",)
    assert stage.RESIDENT_PLUGINS == ("wschat", "asione")
    assert manage.RESIDENT_SPACE_ID == "PaulTiffany/alphaclaw-omega"
    assert manage.RESIDENT_WS_URL == ""


def test_generated_image_contains_no_alpha_runtime() -> None:
    dockerfile = stage.render_dockerfile()
    assert f"ARG CHROMADB_REF={stage.CHROMADB_SHA}" in dockerfile
    assert 'ENTRYPOINT ["/opt/alphaclaw-hf/entrypoint.sh"]' in dockerfile
    assert "COPY alphaclaw.metta" not in dockerfile
    assert "COPY run.metta" not in dockerfile
    assert "mkdir -p /PeTTa/repos/AlphaClaw" not in dockerfile
    assert "test ! -e /PeTTa/repos/AlphaClaw" in dockerfile


def test_human_gate_starts_zero_and_refills_first_new_message(tmp_path: Path) -> None:
    upstream = ROOT / "OmegaClaw-Core" / "src" / "loop.metta"
    loop = tmp_path / "loop.metta"
    shutil.copy2(upstream, loop)
    original = upstream.read_text(encoding="utf-8")

    assert original.count("(change-state! &loops (maxNewInputLoops))") == 2
    assert "(if (and (> $k 1) $msgnew)" in original

    stage.require_human_input_before_inference(loop)
    transformed = loop.read_text(encoding="utf-8")
    assert transformed.count("(change-state! &loops 0)") == 1
    assert transformed.count("(change-state! &loops (maxNewInputLoops))") == 1
    assert "(if (and (> $k 1) $msgnew)" not in transformed
    assert "(if $msgnew" in transformed
    assert upstream.read_text(encoding="utf-8") == original


def test_plugin_allowlist_is_exactly_channel_and_provider(tmp_path: Path) -> None:
    upstream = ROOT / "OmegaClaw-Core" / "config" / "plugins.yaml"
    plugins = tmp_path / "plugins.yaml"
    shutil.copy2(upstream, plugins)
    original = upstream.read_text(encoding="utf-8")
    assert "- name: workflow" in original
    assert "- name: openclaw" in original

    stage.restrict_resident_plugins(plugins)
    names = [
        line.removeprefix("- name: ").strip()
        for line in plugins.read_text(encoding="utf-8").splitlines()
        if line.startswith("- name: ")
    ]
    assert names == ["wschat", "asione"]
    assert upstream.read_text(encoding="utf-8") == original


def test_model_action_surface_is_send_only(tmp_path: Path) -> None:
    upstream_helper = ROOT / "OmegaClaw-Core" / "src" / "helper.py"
    upstream_skills = ROOT / "OmegaClaw-Core" / "src" / "skills.metta"
    helper = tmp_path / "helper.py"
    skills = tmp_path / "skills.metta"
    shutil.copy2(upstream_helper, helper)
    shutil.copy2(upstream_skills, skills)

    stage.restrict_model_action_surface(helper, skills)
    helper_text = helper.read_text(encoding="utf-8")
    skills_text = skills.read_text(encoding="utf-8")
    assert 'STATIC_LLM_COMMANDS = {"send"}' in helper_text
    assert "LLM_COMMANDS.add" not in helper_text
    assert "return str(command) in STATIC_LLM_COMMANDS" in helper_text
    assert '"- Send message to user: send string"' in skills_text
    for forbidden in ("Execute shell command", "Search the web", "Execute MeTTa expression"):
        assert forbidden not in skills_text


def test_entrypoint_guards_minimum_authority_before_health() -> None:
    entrypoint = (ROOT / "runtime" / "huggingface" / "hf_entrypoint.sh").read_text()
    health_start = entrypoint.index("python3 /opt/alphaclaw-hf/health.py &")
    for token in (
        "test ! -e /PeTTa/repos/AlphaClaw",
        "first-iteration human input would not refill authority",
        'names != ["wschat", "asione"]',
        'helper.STATIC_LLM_COMMANDS != {"send"}',
        'helper.add_llm_command("shell")',
        'helper.balance_parentheses("shell env")',
        "persistent history writes disabled",
        "maxHistory: 0",
        "prompt bodies would be logged",
        "human messages would be logged",
        "raw model responses would be logged",
        "OMEGA_WS_URL must use wss://",
    ):
        assert token in entrypoint
        assert entrypoint.index(token) < health_start


def test_controller_has_no_mutable_space_or_ws_destination() -> None:
    source = (ROOT / "runtime" / "huggingface" / "manage_space.py").read_text()
    workflow = (ROOT / ".github" / "workflows" / "omega-space.yml").read_text()
    assert "HF_OMEGA_SPACE_ID" not in source
    assert "HF_OMEGA_SPACE_ID" not in workflow
    assert "vars.OMEGA_WS_URL" not in workflow
    assert "OMEGA_WS_URL:" not in workflow
    assert 'RESIDENT_WS_URL = ""' in source


def test_activation_is_disabled_until_ws_sink_is_source_pinned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ASI_ONE_API_KEY", "asi-secret")
    called = False

    def synchronize(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(manage, "synchronize", synchronize)
    with pytest.raises(RuntimeError, match="not source-pinned; activation disabled"):
        manage.turn_on(object(), manage.RESIDENT_SPACE_ID, True)
    assert called is False


def test_source_pinned_ws_sink_must_use_tls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASI_ONE_API_KEY", "asi-secret")
    monkeypatch.setattr(manage, "RESIDENT_WS_URL", "ws://example.invalid/omega")
    called = False

    def synchronize(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(manage, "synchronize", synchronize)
    with pytest.raises(RuntimeError, match="source-pinned resident WSS endpoint"):
        manage.turn_on(object(), manage.RESIDENT_SPACE_ID, True)
    assert called is False


def test_activation_scrubs_forbidden_secrets_before_restart(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ASI_ONE_API_KEY", "asi-secret")
    monkeypatch.setenv("OMEGA_WS_TOKEN", "ws-secret")
    monkeypatch.setattr(manage, "RESIDENT_WS_URL", "wss://example.invalid/omega")
    monkeypatch.setattr(manage, "synchronize", lambda api, repo_id, private: None)

    events: list[str] = []
    secrets: dict[str, object] = {"OPENROUTER_API_KEY": object()}
    variables: dict[str, str] = {}

    class API:
        def get_space_secrets(self, repo_id: str):
            return dict(secrets)

        def delete_space_secret(self, repo_id: str, key: str):
            events.append(f"delete:{key}")
            secrets.pop(key, None)

        def add_space_secret(self, repo_id: str, key: str, value: str, description: str):
            events.append(f"add:{key}")
            secrets[key] = object()

        def add_space_variable(self, repo_id: str, key: str, value: str, description: str):
            variables[key] = value

        def restart_space(self, repo_id: str):
            events.append("restart")

        def wait_for_space(self, **kwargs):
            return type(
                "Runtime",
                (),
                {"stage": "RUNNING", "hardware": "cpu-basic", "requested_hardware": "cpu-basic"},
            )()

    result = manage.turn_on(API(), manage.RESIDENT_SPACE_ID, True)
    assert events.index("delete:OPENROUTER_API_KEY") < events.index("restart")
    assert variables[manage.WS_VARIABLE] == "wss://example.invalid/omega"
    assert result["ws_endpoint_pinned"] is True
    assert result["forbidden_resident_secrets"] == []


def test_wrong_space_is_rejected_before_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASI_ONE_API_KEY", "asi-secret")
    monkeypatch.setattr(manage, "RESIDENT_WS_URL", "wss://example.invalid/omega")
    called = False

    def synchronize(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(manage, "synchronize", synchronize)
    with pytest.raises(RuntimeError, match="resident Space is fixed"):
        manage.turn_on(object(), "someone/else", True)
    assert called is False


def test_off_revokes_all_runtime_credentials_before_pause() -> None:
    calls: list[tuple[str, str | None]] = []
    secrets = {
        manage.ASI_SECRET: object(),
        manage.WS_SECRET: object(),
        "OPENROUTER_API_KEY": object(),
        "ASI_API_KEY": object(),
    }

    class API:
        def get_space_secrets(self, repo_id: str):
            return dict(secrets)

        def delete_space_secret(self, repo_id: str, key: str):
            calls.append(("delete", key))
            secrets.pop(key, None)

        def pause_space(self, repo_id: str):
            calls.append(("pause", repo_id))

        def get_space_runtime(self, repo_id: str):
            return type(
                "Runtime",
                (),
                {"stage": "PAUSED", "hardware": "cpu-basic", "requested_hardware": "cpu-basic"},
            )()

    result = manage.turn_off(API(), manage.RESIDENT_SPACE_ID)
    pause_index = calls.index(("pause", manage.RESIDENT_SPACE_ID))
    assert all(i < pause_index for i, call in enumerate(calls) if call[0] == "delete")
    assert secrets == {}
    assert result["asi_secret_present"] is False


def test_runtime_log_redaction() -> None:
    assert manage.redact("a secret-a b secret-b", ("secret-a", "secret-b")) == (
        "a [REDACTED] b [REDACTED]"
    )


def test_stage_rejects_wrong_omega_pin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(stage, "git_head", lambda path: "wrong")
    with pytest.raises(RuntimeError, match="pin mismatch"):
        stage.validate_source()
