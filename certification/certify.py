#!/usr/bin/env python3
"""Mechanically witness the resident-model powers demanded by an OmegaClaw tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
UPSTREAM_REPOSITORY = "asi-alliance/OmegaClaw-Core"

RULES: tuple[dict[str, Any], ...] = (
    {
        "id": "symbolic-command-protocol",
        "power": "Emit parseable OmegaClaw skill expressions instead of ordinary prose.",
        "evidence": {
            "src/loop.metta": (
                "OUTPUT_FORMAT: Up to 5 lines",
                "(sread $response)",
                '(== "(" (first_char $resp))',
            )
        },
    },
    {
        "id": "skill-grounding",
        "power": "Select actions from the skill vocabulary supplied in the current prompt.",
        "evidence": {
            "src/loop.metta": ("SKILLS: ", "(getSkills)"),
            "src/skills.metta": ("(= (getSkills)", "(dynamic-skill $_)"),
        },
    },
    {
        "id": "multi-turn-tool-feedback",
        "power": "Continue a trajectory after tool results are returned on later loop iterations.",
        "evidence": {
            "src/loop.metta": (
                "LAST_SKILL_USE_RESULTS:",
                "(change-state! &lastresults",
                "(llmProviderChat $send",
            )
        },
    },
    {
        "id": "error-recovery",
        "power": "Repair malformed, unknown, or failed skill calls rather than abandoning the task.",
        "evidence": {
            "src/loop.metta": (
                "UNKNOWN_SKILL_CALL",
                "SINGLE_COMMAND_ERROR_NOTHING_WAS_DONE_PLEASE_FIX_AND_RETRY",
                "MULTI_COMMAND_FAILURE_NOTHING_WAS_DONE_PLEASE_CORRECT_PARENTHESES",
            )
        },
    },
    {
        "id": "policy-gated-file-io",
        "power": "Respect an explicit I/O policy before using filesystem skills.",
        "evidence": {
            "src/skills.metta": (
                "get-io-policy",
                "always use get-io-policy before reading/writing files",
            )
        },
    },
    {
        "id": "verified-side-effects",
        "power": "Use returned evidence to verify filesystem side effects before claiming success.",
        "evidence": {
            "src/skills.metta": (
                "result is read back from disk",
                "never claim a write succeeded without it",
                "(= (write-file $file $str)",
            )
        },
    },
    {
        "id": "dynamic-skill-surface",
        "power": "Tolerate a skill vocabulary and prompt contract that can change at runtime.",
        "evidence": {
            "src/skills.metta": (
                "(: add-skill",
                "(add-atom &self (= (dynamic-skill $function)",
                "(: add-prompt-extension",
            )
        },
    },
    {
        "id": "context-endurance",
        "power": "Remain coherent while history and tool feedback are repeatedly reintroduced.",
        "evidence": {
            "src/loop.metta": ("(getHistory)", "(last_chars (get-state &lastresults) (maxFeedback))"),
            "config/config.yaml": ("maxFeedback:", "maxHistory:", "maxNewInputLoops:"),
        },
    },
    {
        "id": "ordinary-chat-transport",
        "power": "Operate through ordinary chat-completion transport; native API tool calls are not required.",
        "evidence": {
            "providers/lib_llm_ext.py": (
                "self._client.chat.completions.create(",
                "messages=self._build_messages(content)",
            ),
            "src/loop.metta": ("(llmProviderChat $send",),
        },
    },
)

LIMIT_PATTERNS = {
    "max_new_input_loops": ("config/config.yaml", r"^maxNewInputLoops:\s*(\d+)\s*$"),
    "max_feedback_chars": ("config/config.yaml", r"^maxFeedback:\s*(\d+)\s*$"),
    "max_history_chars": ("config/config.yaml", r"^maxHistory:\s*(\d+)\s*$"),
    "max_output_tokens": ("config/config.yaml", r"^maxOutputToken:\s*(\d+)\s*$"),
}


class CertificationError(RuntimeError):
    """Raised when the certifier can no longer witness an expected OmegaClaw mechanic."""


def _read(root: Path, relative: str) -> str:
    path = root / relative
    if not path.is_file():
        raise CertificationError(f"missing required source file: {relative}")
    return path.read_text(encoding="utf-8")


def _line_for(text: str, token: str) -> int:
    index = text.find(token)
    if index < 0:
        return 0
    return text.count("\n", 0, index) + 1


def _git_sha(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise CertificationError(f"cannot resolve git SHA for {root}") from exc
    return result.stdout.strip()


def _witness_rule(root: Path, rule: dict[str, Any]) -> dict[str, Any]:
    witnesses: list[dict[str, Any]] = []
    missing: list[str] = []

    for relative, tokens in rule["evidence"].items():
        text = _read(root, relative)
        for token in tokens:
            line = _line_for(text, token)
            if line == 0:
                missing.append(f"{relative}: {token}")
            else:
                witnesses.append({"path": relative, "line": line, "token": token})

    if missing:
        joined = "\n  - ".join(missing)
        raise CertificationError(
            f"OmegaClaw mechanic changed; rule {rule['id']} lost evidence:\n  - {joined}"
        )

    return {
        "id": rule["id"],
        "power": rule["power"],
        "status": "witnessed",
        "witnesses": witnesses,
    }


def _extract_limits(root: Path) -> dict[str, int]:
    values: dict[str, int] = {}
    for name, (relative, pattern) in LIMIT_PATTERNS.items():
        text = _read(root, relative)
        match = re.search(pattern, text, flags=re.MULTILINE)
        if match is None:
            raise CertificationError(f"cannot extract {name} from {relative}")
        values[name] = int(match.group(1))
    return values


def _signature(powers: list[dict[str, Any]], limits: dict[str, int]) -> str:
    payload = {
        "powers": [{"id": item["id"], "power": item["power"]} for item in powers],
        "limits": limits,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


def certify(root: Path) -> dict[str, Any]:
    powers = [_witness_rule(root, rule) for rule in RULES]
    limits = _extract_limits(root)
    return {
        "schema_version": SCHEMA_VERSION,
        "subject": {
            "repository": UPSTREAM_REPOSITORY,
            "sha": _git_sha(root),
        },
        "claim": (
            "These powers are mechanically witnessed as requirements of the inspected "
            "OmegaClaw source tree. They are not claims that any particular model satisfies them."
        ),
        "limits": limits,
        "powers": powers,
        "residency_signature": _signature(powers, limits),
    }


def _write_certificate(certificate: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(certificate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"certified {certificate['subject']['sha']} -> {output}")
    print(f"residency_signature={certificate['residency_signature']}")


def _compare(left_path: Path, right_path: Path) -> int:
    left = json.loads(left_path.read_text(encoding="utf-8"))
    right = json.loads(right_path.read_text(encoding="utf-8"))
    left_signature = left["residency_signature"]
    right_signature = right["residency_signature"]

    print(f"pinned_sha={left['subject']['sha']}")
    print(f"latest_sha={right['subject']['sha']}")
    print(f"pinned_signature={left_signature}")
    print(f"latest_signature={right_signature}")

    if left_signature == right_signature:
        print("OmegaClaw revision changed without changing the witnessed residency contract.")
        return 0

    print("OmegaClaw residency contract changed; review the new certificate before updating the pin.")
    print("pinned limits:", json.dumps(left["limits"], sort_keys=True))
    print("latest limits:", json.dumps(right["limits"], sort_keys=True))
    return 3


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="OmegaClaw source tree to inspect")
    parser.add_argument("--output", type=Path, help="JSON certificate output path")
    parser.add_argument(
        "--compare",
        nargs=2,
        type=Path,
        metavar=("PINNED", "LATEST"),
        help="compare two generated certificates; exit 3 when the residency signature changed",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.compare:
            return _compare(*args.compare)
        if args.source is None or args.output is None:
            raise CertificationError("--source and --output are required unless --compare is used")
        _write_certificate(certify(args.source), args.output)
        return 0
    except (CertificationError, json.JSONDecodeError, OSError, KeyError, TypeError, ValueError) as exc:
        print(f"certification failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
