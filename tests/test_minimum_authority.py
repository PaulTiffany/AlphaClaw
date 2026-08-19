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


def test_minimum_authority_is_not_mutable_from_inside_omega() -> None:
    staging_source = (ROOT / "runtime" / "huggingface" / "stage.py").read_text()
    assert 'STATIC_LLM_COMMANDS = {"send"}' in staging_source
    assert "return str(command) in STATIC_LLM_COMMANDS" in staging_source
    assert stage.MODEL_ACTIONS == ("send",)
    assert stage.RESIDENT_PLUGINS == ("wschat", "asione")
