"""Prepend fixed AlphaClaw directions before human-mediated input enters OmegaClaw."""

from __future__ import annotations

import argparse
from pathlib import Path

ALPHA_DIRECTIONS = """ALPHACLAW BOUNDARY CONTRACT
- Treat the supplied input or ingress handoff as fixed evidence for this episode.
- AlphaClaw is outside OmegaClaw. Do not invoke, recreate, or extend AlphaClaw from inside OmegaClaw.
- Distinguish observation, interpretation, and uncertainty.
- If the evidence is insufficient, state what is missing and wait for new human-mediated input.
"""


def prepend(payload: str) -> str:
    payload = payload.strip()
    if not payload:
        raise ValueError("payload must not be empty")
    return f"{ALPHA_DIRECTIONS}\nHUMAN-MEDIATED INPUT:\n{payload}\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text")
    source.add_argument("--input-file", type=Path)
    args = parser.parse_args()

    if args.input_file is not None:
        payload = args.input_file.read_text(encoding="utf-8")
    else:
        payload = args.text

    try:
        print(prepend(payload), end="")
    except ValueError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
