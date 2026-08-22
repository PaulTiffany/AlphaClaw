"""Inspect an OmegaClaw tree without certifying or authorizing it.

This is state-based information for deciding what a separate controller profile
would need to constrain. It deliberately makes no claim that the inspected tree
is safe, approved, or suitable to run.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
from pathlib import Path

LIMITS = {
    "maxNewInputLoops": r"^maxNewInputLoops:\s*(\d+)\s*$",
    "maxWakeLoops": r"^maxWakeLoops:\s*(\d+)\s*$",
    "maxFeedback": r"^maxFeedback:\s*(\d+)\s*$",
    "maxHistory": r"^maxHistory:\s*(\d+)\s*$",
    "maxOutputToken": r"^maxOutputToken:\s*(\d+)\s*$",
}


def git_head(root: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()


def read(root: Path, relative: str) -> str:
    path = root / relative
    if not path.is_file():
        raise RuntimeError(f"missing OmegaClaw source file: {relative}")
    return path.read_text(encoding="utf-8")


def config_limits(text: str) -> dict[str, int | None]:
    result: dict[str, int | None] = {}
    for name, pattern in LIMITS.items():
        match = re.search(pattern, text, flags=re.MULTILINE)
        result[name] = int(match.group(1)) if match else None
    return result


def plugin_names(text: str) -> list[str]:
    return [
        line.removeprefix("- name: ").strip()
        for line in text.splitlines()
        if line.startswith("- name: ")
    ]


def static_commands(text: str) -> list[str]:
    tree = ast.parse(text)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "STATIC_LLM_COMMANDS"
            for target in node.targets
        ):
            value = ast.literal_eval(node.value)
            if not isinstance(value, set) or any(not isinstance(item, str) for item in value):
                raise RuntimeError("STATIC_LLM_COMMANDS is not a literal set of strings")
            return sorted(value)
    raise RuntimeError("STATIC_LLM_COMMANDS assignment not found")


def inspect(root: Path) -> dict[str, object]:
    config = read(root, "config/config.yaml")
    plugins = read(root, "config/plugins.yaml")
    helper = read(root, "src/helper.py")
    skills = read(root, "src/skills.metta")
    memory = read(root, "src/memory.metta")
    prompt = read(root, "memory/prompt.txt")
    loop = read(root, "src/loop.metta")

    return {
        "schema_version": 1,
        "subject": {"sha": git_head(root)},
        "claim": "observed source state only; not a safety certificate or authorization",
        "limits": config_limits(config),
        "plugins": plugin_names(plugins),
        "static_llm_commands": static_commands(helper),
        "dynamic_command_registration_present": "LLM_COMMANDS.add" in helper,
        "dynamic_skill_surface_present": "(dynamic-skill $_)" in skills,
        "persistent_history_writer_present": "append-file-raw" in memory,
        "history_reintroduced_into_prompt": "(getHistory)" in loop,
        "autonomous_prompt_phrases": {
            phrase: phrase in prompt
            for phrase in (
                "choose your own goals",
                "Keep memories and useful created skills",
                "ALWAYS query before responding anything",
                "Take at least 5 agent cycles",
            )
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("OmegaClaw-Core"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = inspect(args.source)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
