from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

try:
    from .stage import MODEL, OMEGA_SHA, PROVIDER, stage
except ImportError:
    from stage import MODEL, OMEGA_SHA, PROVIDER, stage

SPACE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*$")
DEFAULT_SPACE_ID = "PaulTiffany/alphaclaw-omega"
ASI_SECRET = "ASI_ONE_API_KEY"
WS_SECRET = "OMEGA_WS_TOKEN"
WS_VARIABLE = "OMEGA_WS_URL"
ALPHA_VARIABLE = "ALPHACLAW_SOURCE_SHA"
FORBIDDEN_RESIDENT_SECRET_KEYS = frozenset(
    {
        "OPENROUTER_API_KEY",
        "ASI_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "MINIMAX_API_KEY",
    }
)


def as_bool(value: str | None, default: bool = True) -> bool:
    if value is None or not value.strip():
        return default
    normalized = value.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError("boolean value must be true/false, yes/no, on/off, or 1/0")


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def existing_secret_keys(api, repo_id: str) -> set[str]:
    return set(api.get_space_secrets(repo_id=repo_id))


def forbidden_resident_secrets(secret_keys: set[str]) -> set[str]:
    return secret_keys & FORBIDDEN_RESIDENT_SECRET_KEYS


def safe_runtime(runtime, secret_keys: set[str]) -> dict[str, object]:
    return {
        "stage": str(runtime.stage),
        "hardware": runtime.hardware,
        "requested_hardware": runtime.requested_hardware,
        "provider": PROVIDER,
        "model": MODEL,
        "omega_source_sha": OMEGA_SHA,
        "asi_secret_present": ASI_SECRET in secret_keys,
        "ws_secret_present": WS_SECRET in secret_keys,
        "forbidden_resident_secrets": sorted(forbidden_resident_secrets(secret_keys)),
    }


def status(api, repo_id: str) -> dict[str, object]:
    runtime = api.get_space_runtime(repo_id=repo_id)
    if str(runtime.stage) == "BUILD_ERROR":
        emit_build_logs(api, repo_id)
    return safe_runtime(runtime, existing_secret_keys(api, repo_id))


def delete_secret_if_present(api, repo_id: str, key: str) -> None:
    if key in existing_secret_keys(api, repo_id):
        api.delete_space_secret(repo_id=repo_id, key=key)


def scrub_forbidden_resident_secrets(api, repo_id: str) -> None:
    present = forbidden_resident_secrets(existing_secret_keys(api, repo_id))
    for key in sorted(present):
        api.delete_space_secret(repo_id=repo_id, key=key)
    remaining = forbidden_resident_secrets(existing_secret_keys(api, repo_id))
    if remaining:
        raise RuntimeError(
            "forbidden resident credentials remain after scrub: " + ", ".join(sorted(remaining))
        )


def revoke_runtime_authority(api, repo_id: str) -> None:
    # Revoke every resident credential before removing compute authority.
    for key in sorted({ASI_SECRET, WS_SECRET} | FORBIDDEN_RESIDENT_SECRET_KEYS):
        delete_secret_if_present(api, repo_id, key)
    api.pause_space(repo_id=repo_id)


def turn_off(api, repo_id: str) -> dict[str, object]:
    revoke_runtime_authority(api, repo_id)
    return status(api, repo_id)


def synchronize(api, repo_id: str, private: bool) -> None:
    api.create_repo(
        repo_id=repo_id,
        repo_type="space",
        space_sdk="docker",
        private=private,
        exist_ok=True,
    )
    with tempfile.TemporaryDirectory(prefix="alphaclaw-omega-space-") as temporary:
        staged = Path(temporary)
        stage(staged)
        api.upload_folder(
            repo_id=repo_id,
            repo_type="space",
            folder_path=staged,
            delete_patterns="*",
            commit_message=f"Synchronize AlphaClaw Omega resident at {OMEGA_SHA[:12]}",
        )


def emit_build_logs(api, repo_id: str) -> None:
    print("----- Hugging Face build log -----", file=sys.stderr)
    try:
        emitted = False
        for line in api.fetch_space_logs(repo_id=repo_id, build=True):
            emitted = True
            text = str(line)
            print(text, end="" if text.endswith("\n") else "\n", file=sys.stderr)
        if not emitted:
            print("(no build log lines returned)", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001 - diagnostics must not mask the build failure
        print(
            f"(unable to fetch build logs: {type(exc).__name__}: {exc})",
            file=sys.stderr,
        )


def redact(text: str, secrets: tuple[str, ...]) -> str:
    redacted = text
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "[REDACTED]")
    return redacted


def emit_runtime_logs(api, repo_id: str, secrets: tuple[str, ...]) -> None:
    print("----- Hugging Face runtime log -----", file=sys.stderr)
    try:
        emitted = False
        for line in api.fetch_space_logs(repo_id=repo_id, build=False):
            emitted = True
            text = redact(str(line), secrets)
            print(text, end="" if text.endswith("\n") else "\n", file=sys.stderr)
        if not emitted:
            print("(no runtime log lines returned)", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001 - diagnostics must not mask the runtime failure
        print(
            f"(unable to fetch runtime logs: {type(exc).__name__}: {exc})",
            file=sys.stderr,
        )


def turn_on(api, repo_id: str, private: bool) -> dict[str, object]:
    asi_key = require_env("ASI_ONE_API_KEY")
    alpha_sha = os.environ.get("ALPHACLAW_SOURCE_SHA", "").strip()
    ws_url = os.environ.get("OMEGA_WS_URL", "").strip()
    ws_token = os.environ.get("OMEGA_WS_TOKEN", "").strip()

    # Validate all caller-controlled configuration before mutating external state.
    if ws_url and not ws_url.startswith("wss://"):
        raise RuntimeError("OMEGA_WS_URL must start with wss://")

    synchronize(api, repo_id, private)

    try:
        # The dedicated Omega resident may hold its own model key and optional
        # channel token, but never Alpha ingress or alternate-provider keys.
        scrub_forbidden_resident_secrets(api, repo_id)

        api.add_space_secret(
            repo_id=repo_id,
            key=ASI_SECRET,
            value=asi_key,
            description=(
                "Canonical ASI:One credential; translated only at the Omega process boundary."
            ),
        )

        if alpha_sha:
            api.add_space_variable(
                repo_id=repo_id,
                key=ALPHA_VARIABLE,
                value=alpha_sha,
                description="AlphaClaw source commit that synchronized this runtime.",
            )

        if ws_url:
            api.add_space_variable(
                repo_id=repo_id,
                key=WS_VARIABLE,
                value=ws_url,
                description="Outbound bounded Omega WebSocket gateway.",
            )

        if ws_token:
            api.add_space_secret(
                repo_id=repo_id,
                key=WS_SECRET,
                value=ws_token,
                description="Bearer token for the outbound bounded Omega WebSocket gateway.",
            )

        secret_keys = existing_secret_keys(api, repo_id)
        forbidden = forbidden_resident_secrets(secret_keys)
        if forbidden:
            raise RuntimeError(
                "refusing activation with forbidden resident credentials: "
                + ", ".join(sorted(forbidden))
            )

        api.restart_space(repo_id=repo_id)
        runtime = api.wait_for_space(repo_id=repo_id, timeout=1800, poll_interval=5)
        runtime_stage = str(runtime.stage)
        if runtime_stage != "RUNNING":
            if runtime_stage == "BUILD_ERROR":
                emit_build_logs(api, repo_id)
            else:
                emit_runtime_logs(api, repo_id, (asi_key, ws_token))
            raise RuntimeError(
                f"Omega Space did not reach RUNNING; final stage={runtime.stage}"
            )
        return safe_runtime(runtime, existing_secret_keys(api, repo_id))
    except Exception as exc:  # activation must fail closed on ordinary errors
        try:
            revoke_runtime_authority(api, repo_id)
        except Exception as cleanup_exc:  # noqa: BLE001 - report cleanup failure explicitly
            raise RuntimeError(
                "Omega activation failed and fail-closed cleanup also failed: "
                f"activation={type(exc).__name__}: {exc}; "
                f"cleanup={type(cleanup_exc).__name__}: {cleanup_exc}"
            ) from exc
        raise


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manually control the dedicated AlphaClaw Omega Space"
    )
    parser.add_argument("state", choices=("status", "on", "off"))
    args = parser.parse_args()

    repo_id = os.environ.get("HF_OMEGA_SPACE_ID", "").strip() or DEFAULT_SPACE_ID
    token = require_env("HF_TOKEN")
    if not SPACE_ID.fullmatch(repo_id):
        raise RuntimeError("HF_OMEGA_SPACE_ID must have owner/name form")
    private = as_bool(os.environ.get("HF_OMEGA_SPACE_PRIVATE"), default=True)

    from huggingface_hub import HfApi

    api = HfApi(token=token)
    if args.state == "on":
        result = turn_on(api, repo_id, private)
    elif args.state == "off":
        result = turn_off(api, repo_id)
    else:
        result = status(api, repo_id)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
