"""Create a disposable bounded OmegaClaw tree for AlphaClaw benchmarks.

This program is not AlphaClaw and is not an OmegaClaw fork. It is experimental
apparatus: it transforms one exact pinned OmegaClaw source tree for a bounded,
human-initiated benchmark episode and fails closed if upstream mechanics move.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

OMEGA_SHA = "3d711e4b9f5254ae94f31123ca242f60cfd97d29"
MAX_NEW_INPUT_LOOPS = 50
MAX_WAKE_LOOPS = 0
MAX_HISTORY = 0

CHANNELS = {
    "mockchannel": ("python", "{REPO}/channels"),
    "wschat": ("python", "{REPO}/channels"),
}
PROVIDERS = {
    "mockprovider": ("python", "{REPO}/providers"),
    "asione": ("python", "{REPO}/providers"),
    "openrouter": ("python", "{REPO}/providers"),
    "openai": ("python", "{REPO}/providers"),
    "openaiapi": ("python", "{REPO}/providers"),
}

RESIDENT_PROMPT = """You are a bounded OmegaClaw text-inference process responding to the current human-mediated input.
Reason from the current input and ephemeral working state only.
Your only model-directed action is: send string.
Use send to communicate a useful response to the human.
Do not assume or attempt shell, web, file, memory, dynamic-skill, plugin, or other unavailable capabilities.
Do not create goals beyond responding to the current human-mediated input.
If information is insufficient, send what is missing rather than inventing evidence or capabilities.
"""


def git_head(path: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(path), "rev-parse", "HEAD"], text=True
    ).strip()


def validate_source(source: Path) -> None:
    if not source.is_dir():
        raise RuntimeError(f"OmegaClaw source is missing: {source}")
    observed = git_head(source)
    if observed != OMEGA_SHA:
        raise RuntimeError(f"OmegaClaw pin mismatch: expected {OMEGA_SHA}, observed {observed}")
    dirty = subprocess.check_output(
        ["git", "-C", str(source), "status", "--porcelain"], text=True
    ).strip()
    if dirty:
        raise RuntimeError("OmegaClaw source is dirty")


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"OmegaClaw {label} changed; refusing transform")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def restrict_loop(loop: Path) -> None:
    text = loop.read_text(encoding="utf-8")
    old = (
        '          (change-state! &lastresults "")\n'
        '          (change-state! &loops (maxNewInputLoops))\n'
        '          ))'
    )
    new = (
        '          (change-state! &lastresults "")\n'
        '          ; Benchmark controller gate: boot grants no inference authority.\n'
        '          ; Genuinely new human input refills the finite episode budget below.\n'
        '          (change-state! &loops 0)\n'
        '          (change-state! &nextWakeAt (+ (get_time) (wakeupInterval)))\n'
        '          ))'
    )
    if text.count(old) != 1:
        raise RuntimeError("OmegaClaw initLoop changed; refusing boot-gate transform")
    text = text.replace(old, new, 1)

    refill_gate = "(if (and (> $k 1) $msgnew)"
    if text.count(refill_gate) != 1:
        raise RuntimeError("OmegaClaw human-input refill gate changed")
    text = text.replace(refill_gate, "(if $msgnew", 1)
    if text.count("(change-state! &loops (maxNewInputLoops))") != 1:
        raise RuntimeError("OmegaClaw human-input refill path changed")
    loop.write_text(text, encoding="utf-8")


def restrict_config(config: Path, *, max_new_input_loops: int = MAX_NEW_INPUT_LOOPS) -> None:
    if max_new_input_loops <= 0:
        raise ValueError("max_new_input_loops must be positive")
    replacements = {
        "maxNewInputLoops: 50": f"maxNewInputLoops: {max_new_input_loops}",
        "maxWakeLoops: 1": f"maxWakeLoops: {MAX_WAKE_LOOPS}",
        "maxHistory: 30000": f"maxHistory: {MAX_HISTORY}",
    }
    text = config.read_text(encoding="utf-8")
    for old, new in replacements.items():
        if text.count(old) != 1:
            raise RuntimeError(f"OmegaClaw config changed; missing exact setting {old!r}")
        text = text.replace(old, new, 1)
    config.write_text(text, encoding="utf-8")


def restrict_send_termination(channels: Path) -> None:
    """A successful send mechanically consumes the rest of this episode's grant."""
    old = """(= (send $msg)
   (if (!= $msg (get-state &lastsend))
       (progn (change-state! &lastsend $msg)
              (let $safemsg (string-replace $msg  "\\n" "\\\\n")
                   (let $temp (cut) (commChannelSend $safemsg)))) _))
"""
    new = """(= (send $msg)
   (if (!= $msg (get-state &lastsend))
       (progn (change-state! &lastsend $msg)
              (let $safemsg (string-replace $msg  "\\n" "\\\\n")
                   (let $temp (cut)
                        (progn (commChannelSend $safemsg)
                               ; A response ends the current benchmark inference grant.
                               (change-state! &loops 0))))) _))
"""
    replace_once(channels, old, new, "send termination gate")


def plugin_record(name: str, loader: str, location: str) -> str:
    return f'- name: {name}\n  loader: {loader}\n  location: "{location}"\n'


def restrict_plugins(plugin_config: Path, channel: str, provider: str) -> None:
    if channel not in CHANNELS:
        raise ValueError(f"unsupported channel: {channel}")
    if provider not in PROVIDERS:
        raise ValueError(f"unsupported provider: {provider}")

    source = plugin_config.read_text(encoding="utf-8")
    for name in (channel, provider, "workflow", "openclaw"):
        if f"- name: {name}\n" not in source:
            raise RuntimeError(f"OmegaClaw plugin registry changed; missing {name!r}")

    records = [
        "# Generated by controller/omega_profile.py.\n",
        "# Only the selected communication channel and inference provider are loadable.\n",
        plugin_record(channel, *CHANNELS[channel]),
        "\n",
        plugin_record(provider, *PROVIDERS[provider]),
    ]
    plugin_config.write_text("".join(records), encoding="utf-8")


def restrict_model_actions(helper: Path, skills: Path) -> None:
    helper_text = helper.read_text(encoding="utf-8")
    start = helper_text.find("STATIC_LLM_COMMANDS = {")
    end = helper_text.find("\nLLM_COMMANDS = set(STATIC_LLM_COMMANDS)", start)
    if start < 0 or end < 0:
        raise RuntimeError("OmegaClaw static command registry changed")
    original = helper_text[start:end]
    for command in ('"send"', '"shell"', '"metta"', '"websearch"', '"write-file"'):
        if command not in original:
            raise RuntimeError("OmegaClaw command registry lost an expected command")
    helper_text = helper_text[:start] + 'STATIC_LLM_COMMANDS = {"send"}' + helper_text[end:]

    old_add = """def add_llm_command(command):
    LLM_COMMANDS.add(str(command))
    return True
"""
    new_add = """def add_llm_command(command):
    # Authority is fixed by the external controller, not mutable Omega state.
    return str(command) in STATIC_LLM_COMMANDS
"""
    if helper_text.count(old_add) != 1:
        raise RuntimeError("OmegaClaw dynamic command registration changed")
    helper.write_text(helper_text.replace(old_add, new_add, 1), encoding="utf-8")

    skills_text = skills.read_text(encoding="utf-8")
    old_skills = """(= (getSkills)
   (let $static (getStaticSkills)
     (collapse (superpose ((superpose $static) (dynamic-skill $_))))))
"""
    new_skills = """(= (getSkills)
   (getStaticSkills))
"""
    if skills_text.count(old_skills) != 1:
        raise RuntimeError("OmegaClaw skill aggregation changed")
    skills_text = skills_text.replace(old_skills, new_skills, 1)

    static_start = skills_text.find("(= (getStaticSkills)")
    static_end = skills_text.find("\n    ; TODO add load-plugin/unload-plugin skills", static_start)
    if static_start < 0 or static_end < 0:
        raise RuntimeError("OmegaClaw static skill description block changed")
    minimal = """(= (getStaticSkills)
   ("- Send message to user: send string"))
"""
    skills.write_text(
        skills_text[:static_start] + minimal + skills_text[static_end:], encoding="utf-8"
    )


def disable_persistent_history(memory: Path) -> None:
    old = """(= (appendToHistory $addition)
   (append-file-raw (library OmegaClaw-Core ./memory/history.metta) (swrite $addition)))
"""
    new = """(= (appendToHistory $addition)
   ; Benchmark profile: persistent history writes disabled.
   True)
"""
    replace_once(memory, old, new, "history writer")


def restrict_prompt(prompt: Path) -> None:
    text = prompt.read_text(encoding="utf-8")
    for phrase in (
        "choose your own goals",
        "Keep memories and useful created skills",
        "ALWAYS query before responding anything",
        "Take at least 5 agent cycles",
    ):
        if phrase not in text:
            raise RuntimeError("OmegaClaw base prompt changed; refusing prompt reduction")
    prompt.write_text(RESIDENT_PROMPT, encoding="utf-8")


def sanitize_logging(loop: Path, provider: Path) -> None:
    loop_text = loop.read_text(encoding="utf-8")
    replacements = {
        '(log INFO "loop" $lastmessage)': '(log INFO "loop" (HUMAN-MSG-CHARS: (string_length $msg)))',
        '(CHARS_SENT: (string_length $send) $send)': '(CHARS_SENT: (string_length $send))',
        '(log INFO "loop" (RESPONSE: $sexpr))': '(log INFO "loop" RESPONSE-PARSED)',
        '(log INFO "loop" (RESPONSE: $results))': '(log INFO "loop" COMMAND-RESULTS-AVAILABLE)',
    }
    for old, new in replacements.items():
        if loop_text.count(old) != 1:
            raise RuntimeError(f"OmegaClaw log statement changed: {old}")
        loop_text = loop_text.replace(old, new, 1)
    loop.write_text(loop_text, encoding="utf-8")

    provider_text = provider.read_text(encoding="utf-8")
    old = (
        'logger.debug(f"[LLM_RAW] provider={provider} model={model} '
        'chars={len(raw or \'\')} raw={raw!r}")'
    )
    new = (
        'logger.debug(f"[LLM_RAW] provider={provider} model={model} '
        'chars={len(raw or \'\')}")'
    )
    if provider_text.count(old) != 1:
        raise RuntimeError("OmegaClaw raw-response logger changed")
    provider.write_text(provider_text.replace(old, new, 1), encoding="utf-8")


def install_benchmark_meter(destination: Path) -> None:
    """Instrument provider responses with the pinned external ThreadKeeper recorder."""
    meter_source = Path(__file__).with_name("threadkeeper_meter.py")
    if not meter_source.is_file():
        raise RuntimeError(f"benchmark meter source is missing: {meter_source}")
    shutil.copy2(meter_source, destination / "providers" / "alphaclaw_benchmark_meter.py")

    provider = destination / "providers" / "lib_llm_ext.py"
    text = provider.read_text(encoding="utf-8")
    import_anchor = "from config import config_get_by_key\n"
    if text.count(import_anchor) != 1:
        raise RuntimeError("OmegaClaw provider imports changed; refusing meter transform")
    text = text.replace(
        import_anchor,
        import_anchor + "from alphaclaw_benchmark_meter import record_openai_response\n",
        1,
    )
    response_anchor = '            raw = response.choices[0].message.content or ""\n'
    if text.count(response_anchor) != 1:
        raise RuntimeError("OmegaClaw base provider response path changed")
    text = text.replace(
        response_anchor,
        '            record_openai_response(self._model_name, response)\n' + response_anchor,
        1,
    )
    provider.write_text(text, encoding="utf-8")

    asione = destination / "providers" / "asione.py"
    text = asione.read_text(encoding="utf-8")
    import_anchor = "import lib_llm_ext as llm\n"
    if text.count(import_anchor) != 1:
        raise RuntimeError("OmegaClaw ASI:One imports changed")
    text = text.replace(
        import_anchor,
        import_anchor + "from alphaclaw_benchmark_meter import record_openai_response\n",
        1,
    )
    response_anchor = "            raw = response.choices[0].message.content\n"
    if text.count(response_anchor) != 1:
        raise RuntimeError("OmegaClaw ASI:One response path changed")
    text = text.replace(
        response_anchor,
        '            record_openai_response(self._model_name, response)\n' + response_anchor,
        1,
    )
    asione.write_text(text, encoding="utf-8")


def apply_profile(
    source: Path,
    destination: Path,
    *,
    channel: str,
    provider: str,
    max_new_input_loops: int = MAX_NEW_INPUT_LOOPS,
    meter: bool = False,
) -> None:
    validate_source(source)
    if destination.exists():
        raise RuntimeError(f"destination already exists: {destination}")
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns(".git"))

    loop = destination / "src" / "loop.metta"
    restrict_loop(loop)
    restrict_config(
        destination / "config" / "config.yaml",
        max_new_input_loops=max_new_input_loops,
    )
    restrict_send_termination(destination / "src" / "channels.metta")
    restrict_plugins(destination / "config" / "plugins.yaml", channel, provider)
    restrict_model_actions(destination / "src" / "helper.py", destination / "src" / "skills.metta")
    disable_persistent_history(destination / "src" / "memory.metta")
    restrict_prompt(destination / "memory" / "prompt.txt")
    sanitize_logging(loop, destination / "providers" / "lib_llm_ext.py")
    if meter:
        install_benchmark_meter(destination)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("OmegaClaw-Core"))
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--channel", choices=tuple(CHANNELS), default="mockchannel")
    parser.add_argument("--provider", choices=tuple(PROVIDERS), default="mockprovider")
    parser.add_argument("--max-loops", type=int, default=MAX_NEW_INPUT_LOOPS)
    parser.add_argument("--meter", action="store_true")
    args = parser.parse_args()
    apply_profile(
        args.source,
        args.destination,
        channel=args.channel,
        provider=args.provider,
        max_new_input_loops=args.max_loops,
        meter=args.meter,
    )
    print(f"profiled {OMEGA_SHA} -> {args.destination}")
    print(f"channel={args.channel} provider={args.provider}")
    print(
        f"maxNewInputLoops={args.max_loops} "
        f"maxWakeLoops={MAX_WAKE_LOOPS} maxHistory={MAX_HISTORY}"
    )
    print("after_response=wait_for_new_user_input_or_terminate")
    print("model_actions=send")
    print(f"threadkeeper_meter={'enabled' if args.meter else 'disabled'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())