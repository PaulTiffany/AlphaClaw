from __future__ import annotations

import importlib.util
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


stage = _load("minimum_authority_stage", ROOT / "runtime" / "huggingface" / "stage.py")


def test_resident_does_not_persist_or_recall_history() -> None:
    entrypoint = (ROOT / "runtime" / "huggingface" / "hf_entrypoint.sh").read_text()
    runtime_config = (ROOT / "runtime" / "huggingface" / "alphaclaw-runtime.yaml").read_text()

    assert stage.PERSIST_HISTORY is False
    assert stage.HISTORY_CHARS == 0
    assert "maxHistory: 0" in runtime_config
    assert "readonly ALPHACLAW_PERSIST_HISTORY=0" in entrypoint
    assert "readonly ALPHACLAW_MAX_HISTORY_CHARS=0" in entrypoint
    assert "persistent history writes disabled" in entrypoint


def test_staged_history_writer_is_noop(tmp_path: Path) -> None:
    upstream = ROOT / "OmegaClaw-Core" / "src" / "memory.metta"
    memory = tmp_path / "memory.metta"
    shutil.copy2(upstream, memory)

    original = upstream.read_text(encoding="utf-8")
    assert "append-file-raw" in original
    assert "./memory/history.metta" in original

    stage.disable_persistent_history(memory)
    staged = memory.read_text(encoding="utf-8")

    expected = """(= (appendToHistory $addition)
   ; AlphaClaw staged boundary: persistent history writes disabled.
   True)"""
    assert expected in staged
    assert upstream.read_text(encoding="utf-8") == original


def test_staged_prompt_removes_autonomous_and_unavailable_capability_instructions(
    tmp_path: Path,
) -> None:
    upstream = ROOT / "OmegaClaw-Core" / "memory" / "prompt.txt"
    prompt = tmp_path / "prompt.txt"
    shutil.copy2(upstream, prompt)

    original = upstream.read_text(encoding="utf-8")
    for phrase in (
        "choose your own goals",
        "Keep memories and useful created skills",
        "ALWAYS query before responding anything",
        "Take at least 5 agent cycles",
    ):
        assert phrase in original

    stage.restrict_resident_prompt(prompt)
    staged = prompt.read_text(encoding="utf-8")
    assert staged == stage.RESIDENT_PROMPT
    assert "Your only model-directed action is: send string." in staged
    assert "Do not create goals beyond responding to the current human-mediated input." in staged
    for phrase in (
        "choose your own goals",
        "Keep memories and useful created skills",
        "ALWAYS query before responding anything",
        "Take at least 5 agent cycles",
    ):
        assert phrase not in staged
    assert upstream.read_text(encoding="utf-8") == original


def test_staged_runtime_logs_keep_structure_not_conversation_content(tmp_path: Path) -> None:
    upstream_loop = ROOT / "OmegaClaw-Core" / "src" / "loop.metta"
    upstream_provider = ROOT / "OmegaClaw-Core" / "providers" / "lib_llm_ext.py"
    loop = tmp_path / "loop.metta"
    provider = tmp_path / "lib_llm_ext.py"
    shutil.copy2(upstream_loop, loop)
    shutil.copy2(upstream_provider, provider)

    original_loop = upstream_loop.read_text(encoding="utf-8")
    original_provider = upstream_provider.read_text(encoding="utf-8")
    assert '(log INFO "loop" $lastmessage)' in original_loop
    assert '(CHARS_SENT: (string_length $send) $send)' in original_loop
    assert 'raw={raw!r}' in original_provider

    stage.sanitize_runtime_logging(loop, provider)
    staged_loop = loop.read_text(encoding="utf-8")
    staged_provider = provider.read_text(encoding="utf-8")

    assert '(HUMAN-MSG-CHARS: (string_length $msg))' in staged_loop
    assert '(CHARS_SENT: (string_length $send))' in staged_loop
    assert "RESPONSE-PARSED" in staged_loop
    assert "COMMAND-RESULTS-AVAILABLE" in staged_loop
    assert '(log INFO "loop" $lastmessage)' not in staged_loop
    assert '(CHARS_SENT: (string_length $send) $send)' not in staged_loop
    assert 'raw={raw!r}' not in staged_provider
    assert "chars={len(raw or '')}" in staged_provider

    assert upstream_loop.read_text(encoding="utf-8") == original_loop
    assert upstream_provider.read_text(encoding="utf-8") == original_provider


def test_entrypoint_declares_conversation_content_logging_off() -> None:
    entrypoint = (ROOT / "runtime" / "huggingface" / "hf_entrypoint.sh").read_text()
    assert "readonly ALPHACLAW_LOG_CONVERSATION_CONTENT=0" in entrypoint
    assert "prompt bodies would be logged" in entrypoint
    assert "human messages would be logged" in entrypoint
    assert "raw model responses would be logged" in entrypoint
    assert "autonomous or unavailable-capability prompt survived" in entrypoint


def test_minimum_authority_is_not_mutable_from_inside_omega() -> None:
    staging_source = (ROOT / "runtime" / "huggingface" / "stage.py").read_text()
    assert 'STATIC_LLM_COMMANDS = {"send"}' in staging_source
    assert "return str(command) in STATIC_LLM_COMMANDS" in staging_source
    assert stage.MODEL_ACTIONS == ("send",)
    assert stage.RESIDENT_PLUGINS == ("wschat", "asione")


def test_recursive_self_improvement_cannot_self_authorize_authority_growth() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    decision = (ROOT / "docs" / "security-minimum-authority.md").read_text(encoding="utf-8")
    staging_source = (ROOT / "runtime" / "huggingface" / "stage.py").read_text(encoding="utf-8")

    assert "recursive proposal != recursive authorization" in readme
    assert "descendant authority <= externally granted ancestor authority" in readme
    assert "propose -> self-evaluate -> self-deploy -> widen authority -> recurse" in readme
    assert "A model's own judgment" in decision
    assert "not\nauthorization to deploy it" in decision

    # Policy is backed by the concrete resident authority boundary, not only prose.
    assert 'STATIC_LLM_COMMANDS = {"send"}' in staging_source
    assert "return str(command) in STATIC_LLM_COMMANDS" in staging_source
    assert stage.MODEL_ACTIONS == ("send",)
    assert stage.RESIDENT_PLUGINS == ("wschat", "asione")
    assert stage.BOOT_CYCLES == 0
    assert stage.WAKE_CYCLES == 0
    assert stage.PERSIST_HISTORY is False


def test_chad_philosophy_preserves_slack_and_authority_distinctions() -> None:
    philosophy = (ROOT / "PHILOSOPHY.md").read_text(encoding="utf-8")

    # Human/operator slack: leave room for error and recovery instead of heroic closure.
    assert "## Leave room to be wrong" in philosophy
    assert "Do not bite off more than you can chew." in philosophy
    assert "Do not make yourself the only thing holding the work together." in philosophy
    assert "Take care of the operator." in philosophy
    assert "recoverable progress" in philosophy
    assert "one failure} \\not\\Rightarrow \\text{total collapse" in philosophy

    # Jevons / RSI authority separation.
    assert "## Capability is not permission" in philosophy
    assert "recursive proposal} \\neq \\text{recursive authorization" in philosophy
    assert "certified} \\neq \\text{authorized} \\neq \\text{worth doing" in philosophy
    assert "No high-consequence actuator without an independently authorized gate" in philosophy

    # The philosophy must preserve fallibility rather than turn itself into a closed doctrine.
    assert "## This philosophy may also be wrong" in philosophy
    assert "Do not defend something merely because it is yours." in philosophy
