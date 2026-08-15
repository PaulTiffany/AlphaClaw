"""Build the Omega resident-model qualification prompt from an Alpha handoff."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def build_task(handoff: dict, marker: str, target: str) -> str:
    compact = json.dumps(handoff, separators=(",", ":"), sort_keys=True)
    return (
        f"Qualification marker: {marker}. You are given an AlphaClaw symbolic handoff below. "
        f"Use OmegaClaw's normal tools to create {target} as valid JSON. First call get-io-policy "
        "and wait for the returned policy before writing. The file must contain exactly these "
        "top-level keys: marker, source_sha256, resolved_model, literal_count. marker must equal "
        f"{marker!r}; source_sha256 must equal the handoff source sha256; resolved_model must equal "
        "the handoff provenance resolved_model; literal_count must equal the number of literal "
        "observations. After writing, use a later tool turn to read the file back and verify every "
        f"value. Only after verification, send exactly QUALIFIED {marker}. HANDOFF_JSON={compact}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--handoff", type=Path, required=True)
    parser.add_argument("--marker", required=True)
    parser.add_argument("--target", default="/tmp/alphaclaw-qualification.json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    handoff = json.loads(args.handoff.read_text(encoding="utf-8"))
    if not isinstance(handoff, dict):
        raise TypeError("handoff must be a JSON object")
    task = build_task(handoff, args.marker, args.target)
    if args.output is None:
        print(task)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(task + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
