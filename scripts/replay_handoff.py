"""Byte-identical symbolic-handoff replay for Protocol v2 resident/sensory substitution.

A replay re-delivers a payload that a previous sensory call already produced, so a
substitution experiment varies exactly one thing:

    same symbolic evidence -> different resident model
    different sensory model -> same resident model, same task

Mechanically this uses existing ingress routing with no code change to the pipeline:
a ``.json`` file is classified as text, so ``route_file`` takes the text-passthrough
branch and no sensory call is made. The ingress receipt therefore records
``route=text_passthrough``, ``sensory_inference=false`` and the digest of the replay
JSON. That is accurate for the replay event and is deliberately not rewritten; the
provenance block below supplies the missing context instead.

A replay is NOT a native text benchmark condition, and must never be reported as one.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

REQUIRED_PROVENANCE_FIELDS = (
    "replayed_from",
    "origin_run_id",
    "original_image_sha256",
    "sensory_model",
    "handoff_payload_sha256",
)


def payload_digest(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_replay_payload(payload: str, path: Path) -> Path:
    """Write a previously produced symbolic payload verbatim for replay.

    No normalisation, re-serialisation or key reordering: the bytes must survive
    unchanged, because byte identity is the whole point of the condition.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
    written = path.read_text(encoding="utf-8")
    if written != payload:
        raise ValueError(f"replay payload did not round-trip to {path}")
    return path


def build_provenance(
    *,
    replayed_from: str,
    origin_run_id: str,
    original_image_sha256: str,
    sensory_model: str,
    payload: str,
) -> dict[str, Any]:
    """Provenance a replay benchmark record must carry alongside its ingress receipt."""
    return {
        "replayed_from": replayed_from,
        "origin_run_id": origin_run_id,
        "original_image_sha256": original_image_sha256,
        "sensory_model": sensory_model,
        "handoff_payload_sha256": payload_digest(payload),
        "is_native_text_condition": False,
        "receipt_note": (
            "Ingress correctly records route=text_passthrough and "
            "sensory_inference=false for this replay event. No perception occurred "
            "during this run; the evidence originated from the sensory model named above."
        ),
    }


def verify_replay_identity(
    *, original_payload: str, replay_path: Path, envelope: str
) -> dict[str, Any]:
    """Check byte identity across all three required points.

    Returns a report; the caller must stop before provider inference when
    ``identical`` is False.
    """
    replay_input = replay_path.read_text(encoding="utf-8")
    embedded = json.loads(envelope)["payload"]["content"]

    input_matches = replay_input == original_payload
    embedded_matches = embedded == original_payload
    return {
        "identical": input_matches and embedded_matches,
        "replay_input_matches_original": input_matches,
        "envelope_payload_matches_original": embedded_matches,
        "original_sha256": payload_digest(original_payload),
        "replay_input_sha256": payload_digest(replay_input),
        "envelope_payload_sha256": payload_digest(embedded),
    }


def assert_replay_valid(report: dict[str, Any]) -> None:
    """Hard stop before any provider inference if byte identity failed."""
    if not report.get("identical"):
        raise ValueError(
            "replay byte identity failed; the replay condition is invalid and must not "
            f"proceed to provider inference: {report}"
        )


def validate_provenance(provenance: dict[str, Any]) -> None:
    missing = [f for f in REQUIRED_PROVENANCE_FIELDS if not provenance.get(f)]
    if missing:
        raise ValueError(f"replay record is missing provenance fields: {missing}")
    if provenance.get("is_native_text_condition"):
        raise ValueError("a replay must never be recorded as a native text condition")
