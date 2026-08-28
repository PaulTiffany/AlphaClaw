"""Route input deterministically, perceive media only when required, then always prepend Alpha."""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import openrouter_image
import prepend as alpha_prepend

TEXT_SUFFIXES = frozenset(
    {
        ".csv",
        ".htm",
        ".html",
        ".json",
        ".jsonl",
        ".md",
        ".metta",
        ".py",
        ".sh",
        ".toml",
        ".tsv",
        ".txt",
        ".xml",
        ".yaml",
        ".yml",
    }
)

TEXT_PASSTHROUGH = "text_passthrough"
MULTIMODAL_INFERENCE = "multimodal_inference"
# Image and human text arriving as components of ONE human-mediated input. The route
# name states the transformation: the reasoning agent receives a symbolic handoff
# produced by the sensory boundary, never the image bytes.
MULTIMODAL_INFERENCE_WITH_TEXT = "multimodal_inference_with_text"

ImageRunner = Callable[[Path, str, str], tuple[dict[str, Any], dict[str, Any]]]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def classify_file(path: Path) -> str:
    """Classify supported file input without model inference."""
    if not path.is_file():
        raise ValueError(f"input file not found: {path}")

    mime_type = mimetypes.guess_type(path.name)[0]
    if mime_type is not None and mime_type.startswith("image/"):
        return "image"
    if (mime_type is not None and mime_type.startswith("text/")) or path.suffix.lower() in TEXT_SUFFIXES:
        return "text"
    raise ValueError(f"unsupported ingress type: {mime_type or path.suffix or 'unknown'}")


def route_text(text: str, *, source: str = "inline") -> tuple[str, dict[str, Any]]:
    """Pass text directly to the fixed Alpha envelope without sensory inference."""
    encoded = text.encode("utf-8")
    return text, {
        "route": TEXT_PASSTHROUGH,
        "source": source,
        "source_sha256": sha256_bytes(encoded),
        "sensory_inference": False,
    }


def route_file(
    path: Path,
    *,
    model: str,
    api_key: str,
    image_runner: ImageRunner = openrouter_image.run,
) -> tuple[str, dict[str, Any]]:
    """Route a supported file to passthrough or the image perception boundary."""
    kind = classify_file(path)
    raw = path.read_bytes()

    if kind == "text":
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"text ingress is not valid UTF-8: {path}") from exc
        return route_text(text, source=path.name)

    if not api_key.strip():
        raise ValueError("OPENROUTER_API_KEY is required for image ingress")

    handoff, sensory_trace = image_runner(path, model, api_key)
    payload = json.dumps(handoff, ensure_ascii=False, sort_keys=True)
    return payload, {
        "route": MULTIMODAL_INFERENCE,
        "source": path.name,
        "source_sha256": sha256_bytes(raw),
        "sensory_inference": True,
        "sensory_trace": sensory_trace,
    }


def route_image_with_text(
    path: Path,
    text: str,
    *,
    model: str,
    api_key: str,
    image_runner: ImageRunner = openrouter_image.run,
) -> tuple[str, dict[str, Any]]:
    """Compose one payload from an image and its accompanying human text.

    Both are components of a single human-mediated input, so perception runs exactly
    once and the two components are labelled inside one payload. This is deliberately
    not two turns: the episode still delivers one Alpha envelope and one channel
    message, and the post-handoff reasoning budget is unchanged.

    Provenance is recorded separately for each component -- the image's exact bytes
    and the text's bytes are digested independently -- so neither can be silently
    substituted for the other.
    """
    kind = classify_file(path)
    if kind != "image":
        raise ValueError(
            f"combined text+file ingress requires an image, got {kind!r}: {path}"
        )
    if not text.strip():
        raise ValueError("combined ingress requires non-empty text")
    if not api_key.strip():
        raise ValueError("OPENROUTER_API_KEY is required for image ingress")

    raw = path.read_bytes()
    handoff, sensory_trace = image_runner(path, model, api_key)
    payload = json.dumps(
        {"human_text": text, "sensory_handoff": handoff},
        ensure_ascii=False,
        sort_keys=True,
    )
    return payload, {
        "route": MULTIMODAL_INFERENCE_WITH_TEXT,
        "source": path.name,
        "source_sha256": sha256_bytes(raw),
        "text_sha256": sha256_bytes(text.encode("utf-8")),
        "sensory_inference": True,
        "sensory_trace": sensory_trace,
    }


def prepare(
    *,
    text: str | None = None,
    input_file: Path | None = None,
    model: str = openrouter_image.DEFAULT_MODEL,
    api_key: str = "",
    image_runner: ImageRunner = openrouter_image.run,
    episode_contract: dict[str, object] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Produce the exact text-only Alpha envelope to deliver to OmegaClaw."""
    if text is None and input_file is None:
        raise ValueError("provide text, input_file, or both")

    if text is not None and input_file is not None:
        payload, trace = route_image_with_text(
            input_file,
            text,
            model=model,
            api_key=api_key,
            image_runner=image_runner,
        )
    elif text is not None:
        payload, trace = route_text(text)
    else:
        assert input_file is not None
        payload, trace = route_file(
            input_file,
            model=model,
            api_key=api_key,
            image_runner=image_runner,
        )

    # Mandatory convergence point: passthrough and perception both receive Alpha's fixed prepend.
    return alpha_prepend.prepend(payload, episode_contract=episode_contract), trace


def append_trace(path: Path, trace: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(trace, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    # Not mutually exclusive: supplying both composes ONE human-mediated input whose
    # image and text components travel in a single Alpha envelope. prepare() rejects
    # the empty case.
    parser.add_argument("--text")
    parser.add_argument("--input-file", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--trace", type=Path)
    parser.add_argument("--model", default=openrouter_image.DEFAULT_MODEL)
    args = parser.parse_args()

    try:
        rendered, trace = prepare(
            text=args.text,
            input_file=args.input_file,
            model=args.model,
            api_key=os.environ.get("OPENROUTER_API_KEY", ""),
        )
    except (OSError, RuntimeError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"AlphaClaw ingress failed: {exc}", file=sys.stderr)
        return 1

    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")

    if args.trace is not None:
        append_trace(args.trace, trace)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())