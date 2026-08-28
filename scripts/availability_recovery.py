"""Protocol Amendment v1.1 -- provider-availability recovery.

Scope is deliberately narrow. This amendment changes ONLY how provider-availability
failures are handled. It does not touch stimuli, ground truth, the sensory prompt or
boundary, the scorer, the candidate model identifiers, the two-successful-observations
target, the model-selection hierarchy, the reasoning condition, or any downstream
benchmark design.

Motivation
----------
Screening v1 attempted all 36 preregistered calls. Both Gemma arms returned zero
usable observations because all 24 of their requests failed with upstream HTTP 429
before reaching model inference. That is a provider-availability event, not evidence
about visual or model capability, and it must not be read as such.

Rules (predeclared)
-------------------
1. A failed call is preserved as an availability event; it never disappears.
2. Availability failures are distinguished from model, schema and task failures.
3. A model x item x repeat cell that failed on availability may receive a replacement
   measurement after an availability wait.
4. At most ONE replacement attempt per availability-failed cell under v1.1.
5. Cells that produced any usable experimental outcome -- a model response, a schema
   failure, a wrong answer -- are NOT eligible and are never retried.
6. No substitution of another model or provider identity.
7. Replacements use the exact same image bytes, model id, sensory boundary and
   scoring protocol.
8. The Screening v1 artifact is immutable. Recovery data goes to a new artifact with
   explicit linkage.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

AVAILABILITY = "availability"
EXPERIMENTAL = "experimental"
NONE = "none"

# Narrow, predeclared markers of a provider-availability failure occurring BEFORE
# model inference. Anything else is an experimental outcome and is never recovered.
AVAILABILITY_MARKERS = (
    "http 429",
    "rate-limited",
    "rate limited",
    "too many requests",
    "temporarily rate-limited upstream",
)


def classify_failure(error: str | None) -> str:
    """Classify a recorded call error.

    ``availability``  provider refused before inference (recoverable once)
    ``experimental``  the call reached inference and produced an outcome
    ``none``          no error recorded
    """
    if not error:
        return NONE
    low = error.lower()
    return AVAILABILITY if any(m in low for m in AVAILABILITY_MARKERS) else EXPERIMENTAL


def _cells(screening: dict[str, Any]):
    for candidate in screening.get("candidates", []):
        for call in candidate.get("calls_detail", []):
            yield candidate["model_id"], call


def eligible_cells(screening: dict[str, Any]) -> list[dict[str, Any]]:
    """Cells that failed on provider availability and may be measured once more.

    A cell that reached inference is excluded even when its outcome was a failure:
    a schema-contract failure is an experimental result, not an availability event.
    """
    out = []
    for model_id, call in _cells(screening):
        if call.get("request_success"):
            continue
        if classify_failure(call.get("error")) != AVAILABILITY:
            continue
        out.append(
            {
                "model_id": model_id,
                "item_id": call["item_id"],
                "repeat_index": call.get("repeat_index"),
                "original_error": call.get("error"),
            }
        )
    return out


def availability_report(screening: dict[str, Any]) -> dict[str, Any]:
    """Separate availability from experimental outcomes, per model and overall."""
    per_model: dict[str, dict[str, int]] = {}
    for model_id, call in _cells(screening):
        bucket = per_model.setdefault(
            model_id,
            {"attempted": 0, "availability_failures": 0, "experimental_failures": 0,
             "usable_observations": 0},
        )
        bucket["attempted"] += 1
        if call.get("request_success"):
            bucket["usable_observations"] += 1
            continue
        kind = classify_failure(call.get("error"))
        if kind == AVAILABILITY:
            bucket["availability_failures"] += 1
        else:
            # Reached inference and produced an outcome: usable experimental evidence.
            bucket["experimental_failures"] += 1
            bucket["usable_observations"] += 1

    for bucket in per_model.values():
        attempted = bucket["attempted"]
        bucket["availability_rate"] = (
            bucket["availability_failures"] / attempted if attempted else None
        )

    totals = {
        "attempted": sum(b["attempted"] for b in per_model.values()),
        "availability_failures": sum(b["availability_failures"] for b in per_model.values()),
        "experimental_failures": sum(b["experimental_failures"] for b in per_model.values()),
        "usable_observations": sum(b["usable_observations"] for b in per_model.values()),
    }
    totals["availability_rate"] = (
        totals["availability_failures"] / totals["attempted"] if totals["attempted"] else None
    )
    return {"per_model": per_model, "totals": totals}


def build_recovery_plan(
    screening: dict[str, Any],
    *,
    already_recovered: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Cells to measure once more, honouring the one-replacement-per-cell limit.

    ``screening`` is never mutated.
    """
    done = {
        (r["model_id"], r["item_id"], r.get("repeat_index"))
        for r in (already_recovered or [])
    }
    return [
        cell
        for cell in eligible_cells(copy.deepcopy(screening))
        if (cell["model_id"], cell["item_id"], cell["repeat_index"]) not in done
    ]


def artifact_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_recovery_artifact(
    *,
    original_path: Path,
    protocol_commit: str,
    amendment_commit: str,
    recovered_calls: list[dict[str, Any]],
    screening: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble the v1.1 artifact with explicit linkage to Screening v1.

    The original artifact is read for its digest only and is never rewritten.
    """
    original = screening or json.loads(original_path.read_text(encoding="utf-8"))
    return {
        "schema_version": 1,
        "amendment": "v1.1",
        "amendment_scope": "provider-availability recovery only",
        "linkage": {
            "protocol_commit": protocol_commit,
            "amendment_commit": amendment_commit,
            "original_artifact": original_path.name,
            "original_artifact_sha256": artifact_digest(original_path),
        },
        "recovered_cells": [
            {k: c[k] for k in ("model_id", "item_id", "repeat_index") if k in c}
            for c in recovered_calls
        ],
        "recovered_calls": recovered_calls,
        "original_availability_report": availability_report(original),
        "note": (
            "The original HTTP-429 attempts remain reported as availability failures in "
            "Screening v1. A replacement observation supersedes its cell for comparative "
            "scoring only when it reached model inference and produced an experimental "
            "outcome. HTTP-429 failures are not evidence of visual or model incapability."
        ),
    }


def supersedes(cell_result: dict[str, Any]) -> bool:
    """Whether a replacement observation may be used for comparative scoring.

    Only if it reached model inference and produced an experimental outcome. A
    replacement that itself hit an availability error does not supersede anything.
    """
    if cell_result.get("request_success"):
        return True
    return classify_failure(cell_result.get("error")) == EXPERIMENTAL
