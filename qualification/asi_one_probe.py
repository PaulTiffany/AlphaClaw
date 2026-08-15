"""Spend one ASI:One request to verify the free API path without touching Omega."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

API_URL = "https://api.asi1.ai/v1/chat/completions"
MODEL = "asi1-mini"
MARKER = "ALPHACLAW_ASI1_OK"


def _request(api_key: str, timeout: float) -> dict[str, Any]:
    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": f"Reply with exactly {MARKER} and nothing else.",
            }
        ],
        "max_tokens": 24,
        "temperature": 0,
    }
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"ASI:One HTTP {exc.code}: {body}") from exc

    parsed = json.loads(body)
    if not isinstance(parsed, dict):
        raise TypeError("ASI:One response must be a JSON object")
    return parsed


def _probe_record(response: dict[str, Any]) -> dict[str, Any]:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("ASI:One response contains no choices")

    first = choices[0]
    if not isinstance(first, dict):
        raise TypeError("ASI:One first choice must be a JSON object")
    message = first.get("message")
    if not isinstance(message, dict):
        raise TypeError("ASI:One first choice has no message object")
    reply = message.get("content")
    if not isinstance(reply, str) or not reply.strip():
        raise RuntimeError("ASI:One returned an empty reply")

    usage = response.get("usage")
    if not isinstance(usage, dict):
        usage = {}

    resolved_model = response.get("model")
    if not isinstance(resolved_model, str) or not resolved_model:
        resolved_model = MODEL

    return {
        "schema_version": 1,
        "provider": "ASI:One",
        "requested_model": MODEL,
        "resolved_model": resolved_model,
        "observed_at": datetime.now(UTC).isoformat(),
        "reply": reply.strip(),
        "marker_exact": reply.strip() == MARKER,
        "usage": {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()

    api_key = os.environ.get("ASI_ONE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ASI_ONE_API_KEY is required")

    record = _probe_record(_request(api_key, args.timeout))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "provider": record["provider"],
                "requested_model": record["requested_model"],
                "resolved_model": record["resolved_model"],
                "marker_exact": record["marker_exact"],
                "usage": record["usage"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
