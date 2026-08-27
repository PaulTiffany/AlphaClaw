"""Translate an image into AlphaClaw's symbolic handoff through OpenRouter."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openrouter/free"
SCHEMA_VERSION = 1

SYSTEM_PROMPT = """You are AlphaClaw's perception boundary. Convert the supplied image into a compact symbolic handoff for a text-only reasoning agent. Do not solve downstream tasks. Return only one JSON object with exactly these keys: literal_observations, interpretations, uncertainty, unresolved, entities, relations. literal_observations, interpretations, uncertainty, and unresolved must be arrays of strings. entities must be an array of objects with string keys label and kind. relations must be an array of objects with string keys subject, predicate, and object. Preserve visible text literally when legible. Separate observation from interpretation and state uncertainty rather than guessing."""


def _json_from_text(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()

    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("multimodal response did not contain a JSON object") from None
        payload = json.loads(stripped[start : end + 1])

    if not isinstance(payload, dict):
        raise TypeError("multimodal handoff must be a JSON object")
    return payload


def _require_string_list(payload: dict[str, Any], key: str) -> list[str]:
    value = payload.get(key)
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise TypeError(f"handoff field {key!r} must be an array of strings")
    return value


def _require_object_list(
    payload: dict[str, Any], key: str, required: tuple[str, ...]
) -> list[dict[str, str]]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise TypeError(f"handoff field {key!r} must be an array")

    clean: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            raise TypeError(f"handoff field {key!r} must contain objects")
        normalized: dict[str, str] = {}
        for field in required:
            member = item.get(field)
            if not isinstance(member, str):
                raise TypeError(f"handoff {key!r}.{field!r} must be a string")
            normalized[field] = member
        clean.append(normalized)
    return clean


def normalize_handoff(
    payload: dict[str, Any],
    *,
    image: Path,
    mime_type: str,
    requested_model: str,
    resolved_model: str,
) -> dict[str, Any]:
    image_bytes = image.read_bytes()
    return {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "kind": "image",
            "filename": image.name,
            "mime_type": mime_type,
            "sha256": hashlib.sha256(image_bytes).hexdigest(),
        },
        "observation": {
            "literal": _require_string_list(payload, "literal_observations"),
            "interpretations": _require_string_list(payload, "interpretations"),
            "uncertainty": _require_string_list(payload, "uncertainty"),
            "unresolved": _require_string_list(payload, "unresolved"),
            "entities": _require_object_list(payload, "entities", ("label", "kind")),
            "relations": _require_object_list(
                payload, "relations", ("subject", "predicate", "object")
            ),
        },
        "provenance": {
            "provider": "OpenRouter",
            "requested_model": requested_model,
            "resolved_model": resolved_model,
            "observed_at": datetime.now(UTC).isoformat(),
        },
    }


def build_request(image: Path, model: str) -> tuple[dict[str, Any], str]:
    mime_type = mimetypes.guess_type(image.name)[0] or "application/octet-stream"
    if not mime_type.startswith("image/"):
        raise ValueError(f"unsupported ingress MIME type: {mime_type}")
    encoded = base64.b64encode(image.read_bytes()).decode("ascii")
    data_url = f"data:{mime_type};base64,{encoded}"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Translate this evidence into the handoff schema."},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0,
        "usage": {"include": True},
    }
    return payload, mime_type


def call_openrouter(payload: dict[str, Any], api_key: str) -> dict[str, Any]:
    request = urllib.request.Request(
        OPENROUTER_CHAT_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "AlphaClaw-Multimodal-Ingress/1",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenRouter ingress failed: HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"OpenRouter ingress failed: {exc}") from exc

    if not isinstance(result, dict):
        raise TypeError("OpenRouter response must be a JSON object")
    return result


def _required_usage_int(usage: dict[str, Any], key: str) -> int:
    if key not in usage or usage[key] is None:
        raise RuntimeError(f"OpenRouter image response is missing usage.{key}")
    value = int(usage[key])
    if value < 0:
        raise RuntimeError(f"OpenRouter image response has negative usage.{key}")
    return value


def response_content(response: dict[str, Any]) -> tuple[str, str, int, int]:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("OpenRouter response has no choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise TypeError("OpenRouter choice must be an object")
    message = first.get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise TypeError("OpenRouter response has no text content")

    resolved_model = response.get("model")
    if not isinstance(resolved_model, str) or not resolved_model:
        resolved_model = "unknown"
    usage = response.get("usage")
    if not isinstance(usage, dict):
        raise RuntimeError("OpenRouter image response did not include usage accounting")
    prompt_tokens = _required_usage_int(usage, "prompt_tokens")
    completion_tokens = _required_usage_int(usage, "completion_tokens")
    return message["content"], resolved_model, prompt_tokens, completion_tokens


def trace_record(
    *,
    requested_model: str,
    resolved_model: str,
    input_tokens: int,
    output_tokens: int,
    source_sha256: str,
) -> dict[str, Any]:
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "node_role": "multimodal_ingress",
        "provider": "OpenRouter",
        "requested_model": requested_model,
        "model": resolved_model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "source_sha256": source_sha256,
    }


def run(image: Path, model: str, api_key: str) -> tuple[dict[str, Any], dict[str, Any]]:
    request_payload, mime_type = build_request(image, model)
    response = call_openrouter(request_payload, api_key)
    content, resolved_model, input_tokens, output_tokens = response_content(response)
    model_payload = _json_from_text(content)
    handoff = normalize_handoff(
        model_payload,
        image=image,
        mime_type=mime_type,
        requested_model=model,
        resolved_model=resolved_model,
    )
    trace = trace_record(
        requested_model=model,
        resolved_model=resolved_model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        source_sha256=handoff["source"]["sha256"],
    )
    return handoff, trace


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trace", type=Path)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        print("OPENROUTER_API_KEY is required", file=sys.stderr)
        return 2
    if not args.image.is_file():
        print(f"image not found: {args.image}", file=sys.stderr)
        return 2

    try:
        handoff, trace = run(args.image, args.model, api_key)
    except (OSError, RuntimeError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"multimodal ingress failed: {exc}", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(handoff, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.trace is not None:
        args.trace.parent.mkdir(parents=True, exist_ok=True)
        with args.trace.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(trace, sort_keys=True) + "\n")

    print(f"resolved_model={handoff['provenance']['resolved_model']}")
    print(f"source_sha256={handoff['source']['sha256']}")
    print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())