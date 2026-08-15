"""Mechanically inventory OpenRouter models addressable by stock OmegaClaw."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
SIGNAL_NAMES = (
    "tools",
    "tool_choice",
    "reasoning",
    "structured_outputs",
    "response_format",
    "max_tokens",
)

OMEGA_WITNESSES: dict[str, tuple[str, ...]] = {
    "providers/openrouter.py": (
        'config_get_by_key("model", openrouter_model)',
        '"https://openrouter.ai/api/v1"',
    ),
    "providers/lib_llm_ext.py": (
        "self._client.chat.completions.create(",
        "max_tokens=max_tokens",
        'raw = response.choices[0].message.content or ""',
    ),
}


class CensusError(RuntimeError):
    """Raised when provider discovery or Omega transport witnessing fails."""


def _read(root: Path, relative: str) -> str:
    path = root / relative
    if not path.is_file():
        raise CensusError(f"missing OmegaClaw source file: {relative}")
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
        raise CensusError(f"cannot resolve git SHA for {root}") from exc
    return result.stdout.strip()


def witness_omega_openrouter(root: Path) -> dict[str, Any]:
    witnesses: list[dict[str, Any]] = []
    missing: list[str] = []

    for relative, tokens in OMEGA_WITNESSES.items():
        text = _read(root, relative)
        for token in tokens:
            line = _line_for(text, token)
            if line == 0:
                missing.append(f"{relative}: {token}")
            else:
                witnesses.append({"path": relative, "line": line, "token": token})

    if missing:
        joined = "\n  - ".join(missing)
        raise CensusError(
            "OmegaClaw OpenRouter transport changed; model census cannot preserve old "
            f"selection assumptions:\n  - {joined}"
        )

    return {
        "repository": "asi-alliance/OmegaClaw-Core",
        "sha": _git_sha(root),
        "provider": "OpenRouter",
        "model_override": "OMEGACLAW_model",
        "transport": "openai-compatible-chat-completions",
        "resident_io": "text-in/text-out",
        "witnesses": witnesses,
    }


def _price_is_zero(value: Any) -> bool:
    if value is None:
        return True
    try:
        return Decimal(str(value)) == 0
    except (InvalidOperation, ValueError):
        return False


def _zero_text_price(pricing: Any) -> bool:
    if not isinstance(pricing, dict):
        return False
    if "prompt" not in pricing or "completion" not in pricing:
        return False
    keys = ("prompt", "completion", "request", "internal_reasoning")
    return all(_price_is_zero(pricing.get(key)) for key in keys)


def _list_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted({item for item in value if isinstance(item, str)})


def normalize_model(model: dict[str, Any]) -> dict[str, Any]:
    architecture = model.get("architecture")
    if not isinstance(architecture, dict):
        architecture = {}

    model_id = model.get("id")
    if not isinstance(model_id, str):
        model_id = ""

    input_modalities = _list_strings(architecture.get("input_modalities"))
    output_modalities = _list_strings(architecture.get("output_modalities"))
    supported_parameters = _list_strings(model.get("supported_parameters"))
    pricing = model.get("pricing")
    if not isinstance(pricing, (dict, list)):
        pricing = {}

    addressable = bool(model_id) and "text" in input_modalities and "text" in output_modalities
    signals = {name: name in supported_parameters for name in SIGNAL_NAMES}

    return {
        "id": model_id,
        "canonical_slug": model.get("canonical_slug"),
        "name": model.get("name"),
        "context_length": model.get("context_length"),
        "architecture": {
            "input_modalities": input_modalities,
            "output_modalities": output_modalities,
            "tokenizer": architecture.get("tokenizer"),
            "instruct_type": architecture.get("instruct_type"),
        },
        "supported_parameters": supported_parameters,
        "signals": signals,
        "pricing": pricing,
        "explicit_free_variant": model_id.endswith(":free"),
        "zero_text_price": _zero_text_price(pricing),
        "top_provider": model.get("top_provider"),
        "per_request_limits": model.get("per_request_limits"),
        "reasoning": model.get("reasoning"),
        "expiration_date": model.get("expiration_date"),
        "stock_omega_openrouter_addressable": addressable,
        "qualification": {
            "status": "unqualified",
            "reason": (
                "Provider metadata does not demonstrate the behavioral powers in the "
                "OmegaClaw Residency Certificate."
            ),
        },
    }


def normalize_catalog(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data")
    if not isinstance(data, list):
        raise CensusError("OpenRouter response does not contain a data list")

    models = [normalize_model(item) for item in data if isinstance(item, dict)]
    return sorted(models, key=lambda item: item["id"])


def _fetch_payload(api_key: str) -> tuple[dict[str, Any], str]:
    query = urllib.parse.urlencode({"output_modalities": "text"})
    url = f"{OPENROUTER_MODELS_URL}?{query}"
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": "AlphaClaw-OpenRouter-Census/1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        raise CensusError(f"OpenRouter model pull failed: {exc}") from exc

    if not isinstance(payload, dict):
        raise CensusError("OpenRouter model pull returned a non-object JSON payload")
    return payload, url


def _load_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CensusError("input model catalog must be a JSON object")
    return payload


def _apply_filters(
    models: list[dict[str, Any]],
    *,
    free_only: bool,
    min_context: int | None,
    require_signals: list[str],
) -> list[dict[str, Any]]:
    selected = models
    if free_only:
        selected = [
            model
            for model in selected
            if model["explicit_free_variant"] or model["zero_text_price"]
        ]

    if min_context is not None:
        selected = [
            model
            for model in selected
            if isinstance(model["context_length"], int)
            and model["context_length"] >= min_context
        ]

    for signal in require_signals:
        selected = [model for model in selected if model["signals"].get(signal, False)]

    return selected


def _counts(models: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "models": len(models),
        "stock_omega_openrouter_addressable": sum(
            bool(model["stock_omega_openrouter_addressable"]) for model in models
        ),
        "explicit_free_variants": sum(bool(model["explicit_free_variant"]) for model in models),
        "zero_text_price": sum(bool(model["zero_text_price"]) for model in models),
        "advertises_tools": sum(bool(model["signals"]["tools"]) for model in models),
        "advertises_reasoning": sum(bool(model["signals"]["reasoning"]) for model in models),
        "advertises_structured_outputs": sum(
            bool(model["signals"]["structured_outputs"]) for model in models
        ),
    }


def build_census(
    payload: dict[str, Any],
    *,
    omega_source: Path,
    source_url: str,
    free_only: bool = False,
    min_context: int | None = None,
    require_signals: list[str] | None = None,
) -> dict[str, Any]:
    require_signals = require_signals or []
    models = normalize_catalog(payload)
    selected = _apply_filters(
        models,
        free_only=free_only,
        min_context=min_context,
        require_signals=require_signals,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "provider": "OpenRouter",
            "endpoint": source_url,
            "filters": {
                "free_only": free_only,
                "min_context": min_context,
                "require_signals": require_signals,
            },
        },
        "omega": witness_omega_openrouter(omega_source),
        "claim": (
            "This is a provider-metadata census for model selection. It does not certify that "
            "any listed model satisfies OmegaClaw's resident-model powers."
        ),
        "counts": _counts(selected),
        "models": selected,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--omega-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--input",
        type=Path,
        help="Replay a saved OpenRouter /models JSON response instead of making a live request.",
    )
    parser.add_argument("--free-only", action="store_true")
    parser.add_argument("--min-context", type=int)
    parser.add_argument(
        "--require-signal",
        action="append",
        choices=SIGNAL_NAMES,
        default=[],
        help="Metadata signal to require; may be repeated. This is not qualification.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.input is not None:
            payload = _load_payload(args.input)
            source_url = f"file:{args.input}"
        else:
            api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
            if not api_key:
                raise CensusError(
                    "OPENROUTER_API_KEY is required for a live census; use --input for replay mode"
                )
            payload, source_url = _fetch_payload(api_key)

        census = build_census(
            payload,
            omega_source=args.omega_source,
            source_url=source_url,
            free_only=args.free_only,
            min_context=args.min_context,
            require_signals=args.require_signal,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(census, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        counts = census["counts"]
        print(f"omega_sha={census['omega']['sha']}")
        print(f"models={counts['models']}")
        print(f"addressable={counts['stock_omega_openrouter_addressable']}")
        print(f"explicit_free_variants={counts['explicit_free_variants']}")
        print(f"output={args.output}")
        return 0
    except (
        CensusError,
        json.JSONDecodeError,
        OSError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        print(f"model census failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
