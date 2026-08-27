from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


profile = _load("omega_profile", ROOT / "controller" / "omega_profile.py")
inspector = _load("inspect_omega", ROOT / "controller" / "inspect_omega.py")


def test_controller_is_separate_from_alpha_boundary() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    controller_readme = (ROOT / "controller" / "README.md").read_text(encoding="utf-8")

    assert "AlphaClaw is a small sensory tool" in readme
    assert "It is deliberately **not AlphaClaw**" in readme
    assert "This directory is **not AlphaClaw**" in controller_readme
    assert "perception != authority != inference" in controller_readme


def test_profile_constants_are_bounded() -> None:
    assert profile.MAX_NEW_INPUT_LOOPS == 50
    assert profile.MAX_WAKE_LOOPS == 0
    assert profile.MAX_HISTORY == 0
    assert tuple(profile.CHANNELS) == ("mockchannel", "wschat")
    assert "mockprovider" in profile.PROVIDERS


def test_config_reduction_is_exact_local_and_parameterized(tmp_path: Path) -> None:
    source = ROOT / "OmegaClaw-Core" / "config" / "config.yaml"
    config = tmp_path / "config.yaml"
    shutil.copy2(source, config)

    original = source.read_text(encoding="utf-8")
    profile.restrict_config(config, max_new_input_loops=13)
    reduced = config.read_text(encoding="utf-8")

    assert "maxNewInputLoops: 13" in reduced
    assert "maxWakeLoops: 0" in reduced
    assert "maxHistory: 0" in reduced
    assert source.read_text(encoding="utf-8") == original


def test_send_mechanically_ends_current_episode_grant(tmp_path: Path) -> None:
    channels = tmp_path / "channels.metta"
    shutil.copy2(ROOT / "OmegaClaw-Core" / "src" / "channels.metta", channels)

    profile.restrict_send_termination(channels)
    reduced = channels.read_text(encoding="utf-8")

    assert "A response ends the current benchmark inference grant" in reduced
    assert "(change-state! &loops 0)" in reduced


def test_plugin_profile_loads_only_selected_channel_and_provider(tmp_path: Path) -> None:
    source = ROOT / "OmegaClaw-Core" / "config" / "plugins.yaml"
    plugins = tmp_path / "plugins.yaml"
    shutil.copy2(source, plugins)

    profile.restrict_plugins(plugins, "mockchannel", "mockprovider")
    reduced = plugins.read_text(encoding="utf-8")

    assert reduced.count("- name: ") == 2
    assert "- name: mockchannel" in reduced
    assert "- name: mockprovider" in reduced
    assert "- name: workflow" not in reduced
    assert "- name: openclaw" not in reduced


def test_model_action_surface_reduces_to_send(tmp_path: Path) -> None:
    upstream_helper = ROOT / "OmegaClaw-Core" / "src" / "helper.py"
    upstream_skills = ROOT / "OmegaClaw-Core" / "src" / "skills.metta"
    helper = tmp_path / "helper.py"
    skills = tmp_path / "skills.metta"
    shutil.copy2(upstream_helper, helper)
    shutil.copy2(upstream_skills, skills)

    profile.restrict_model_actions(helper, skills)
    helper_text = helper.read_text(encoding="utf-8")
    skills_text = skills.read_text(encoding="utf-8")

    assert 'STATIC_LLM_COMMANDS = {"send"}' in helper_text
    assert "LLM_COMMANDS.add" not in helper_text
    assert '"- Send message to user: send string"' in skills_text
    assert "Execute shell command" not in skills_text
    assert "Search the web" not in skills_text
    assert "Execute MeTTa expression" not in skills_text


def test_history_prompt_and_logs_are_reduced(tmp_path: Path) -> None:
    memory = tmp_path / "memory.metta"
    prompt = tmp_path / "prompt.txt"
    loop = tmp_path / "loop.metta"
    provider = tmp_path / "lib_llm_ext.py"
    shutil.copy2(ROOT / "OmegaClaw-Core" / "src" / "memory.metta", memory)
    shutil.copy2(ROOT / "OmegaClaw-Core" / "memory" / "prompt.txt", prompt)
    shutil.copy2(ROOT / "OmegaClaw-Core" / "src" / "loop.metta", loop)
    shutil.copy2(ROOT / "OmegaClaw-Core" / "providers" / "lib_llm_ext.py", provider)

    profile.disable_persistent_history(memory)
    profile.restrict_prompt(prompt)
    profile.sanitize_logging(loop, provider)

    assert "persistent history writes disabled" in memory.read_text(encoding="utf-8")
    assert prompt.read_text(encoding="utf-8") == profile.RESIDENT_PROMPT
    assert '(log INFO "loop" $lastmessage)' not in loop.read_text(encoding="utf-8")
    assert 'raw={raw!r}' not in provider.read_text(encoding="utf-8")


def test_profile_can_install_benchmark_only_threadkeeper_meter(tmp_path: Path) -> None:
    destination = tmp_path / "profiled"
    profile.apply_profile(
        ROOT / "OmegaClaw-Core",
        destination,
        channel="mockchannel",
        provider="asione",
        max_new_input_loops=3,
        meter=True,
    )

    assert (destination / "providers" / "alphaclaw_benchmark_meter.py").is_file()
    assert "record_openai_response" in (destination / "providers" / "lib_llm_ext.py").read_text()
    assert "record_openai_response" in (destination / "providers" / "asione.py").read_text()
    assert "record_responses_api" in (destination / "providers" / "openai.py").read_text()
    assert "maxNewInputLoops: 3" in (destination / "config" / "config.yaml").read_text()


def test_inspector_reports_state_without_certifying() -> None:
    report = inspector.inspect(ROOT / "OmegaClaw-Core")

    assert report["claim"] == "observed source state only; not a safety certificate or authorization"
    assert report["subject"]["sha"] == profile.OMEGA_SHA
    assert report["dynamic_command_registration_present"] is True
    assert report["dynamic_skill_surface_present"] is True
    assert report["persistent_history_writer_present"] is True
    json.dumps(report)


def test_recursive_self_improvement_cannot_self_authorize_authority_growth() -> None:
    philosophy = (ROOT / "PHILOSOPHY.md").read_text(encoding="utf-8")
    controller_source = (ROOT / "controller" / "omega_profile.py").read_text(encoding="utf-8")

    assert "## Capability is not permission" in philosophy
    assert "recursive proposal} \\neq \\text{recursive authorization" in philosophy
    assert "certified} \\neq \\text{authorized} \\neq \\text{worth doing" in philosophy
    assert "No high-consequence actuator without an independently authorized gate" in philosophy
    assert 'STATIC_LLM_COMMANDS = {"send"}' in controller_source
    assert "return str(command) in STATIC_LLM_COMMANDS" in controller_source


def test_chad_philosophy_preserves_operator_slack_and_fallibility() -> None:
    philosophy = (ROOT / "PHILOSOPHY.md").read_text(encoding="utf-8")

    assert "## Leave room to be wrong" in philosophy
    assert "Do not bite off more than you can chew." in philosophy
    assert "Do not make yourself the only thing holding the work together." in philosophy
    assert "Take care of the operator." in philosophy
    assert "recoverable progress" in philosophy
    assert "## This philosophy may also be wrong" in philosophy
    assert "Do not defend something merely because it is yours." in philosophy