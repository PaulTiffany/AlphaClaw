"""Research checkpoint index -- an index of frozen evidence, not a new result.

This module builds ``benchmark/research-checkpoint.json``. That file records **where the
evidence lives and what its bytes are**; it deliberately does NOT restate benchmark
results that can be recomputed from the artifacts it points at. Anything derivable stays
derivable, so there is exactly one source of truth for every number.

Pure, offline and read-only apart from the explicit CLI write of the manifest itself.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmark"
SCRIPTS = ROOT / "scripts"

MANIFEST = BENCHMARK / "research-checkpoint.json"

CHECKPOINT_VERSION = "research-checkpoint-1"

#: Frozen evidence, indexed by repository-relative path.
EVIDENCE = (
    "benchmark/protocol-v2.json",
    "benchmark/screening-v2-B1.json",
    "benchmark/benchmark-v2-A.json",
    "benchmark/benchmark-v2-B2.json",
    "benchmark/benchmark-v2-C.json",
    "benchmark/protocol-v3.json",
    "benchmark/benchmark-v3-A.json",
    "benchmark/benchmark-v3-B.json",
    "benchmark/v3b-ground-truth.json",
    "benchmark/v3b-stimuli/chain_a.png",
    "benchmark/v3b-stimuli/chain_b.png",
    "scripts/score_handoff.py",
    "scripts/synthesis_v2.py",
    "scripts/synthesis_v3.py",
)

#: Preregistration amendments, recorded as process evidence rather than hidden.
AMENDMENTS = (
    {
        "id": "v2.1",
        "module": "scripts/amendment_v2_1.py",
        "subject": "B2 replay-source selection",
        "discovered": "after condition B1 completed",
        "relative_to_inference": "BEFORE any B2 provider call",
        "changed": ("froze the rule that B2 replays B1 repeat_index = 0 only, with no "
                    "fall-through to repeat 1 and no quality-based selection"),
        "unchanged": ["stimuli", "sensory model", "resident model", "B2 item list",
                      "scorer", "sensory boundary", "B1 results", "replay bytes",
                      "ASICloud caps"],
    },
    {
        "id": "v2.2",
        "module": "scripts/amendment_v2_2.py",
        "subject": "B2 composition replay semantics",
        "discovered": "during the B2 preflight",
        "relative_to_inference": "BEFORE any B2 provider call",
        "changed": ("defined the composed replay payload as the frozen instruction plus "
                    "the frozen B1 handoff, byte-identical to what the live image+text "
                    "route would build; clarified that the replay input does NOT equal "
                    "the raw handoff"),
        "unchanged": ["B2 items", "the repeat-0 rule", "B1 handoff bytes", "task text",
                      "sensory model", "resident model", "scorer", "caps",
                      "live ingress behaviour"],
    },
    {
        "id": "v3.1",
        "module": "scripts/representation_v3.py",
        "subject": "answer-leakage check",
        "discovered": "during the V3-A preflight",
        "relative_to_inference": "BEFORE any V3-A provider call",
        "changed": ("a bare substring test falsely flagged the frozen number_arithmetic "
                    "payload, whose image digest contains \"19\"; leakage now means the "
                    "answer appears as a standalone token"),
        "unchanged": ["representations", "transforms", "models", "budgets",
                      "conditions", "the check still applies to every variant incl. R1"],
    },
    {
        "id": "v3.2",
        "module": "scripts/economics_v3.py",
        "subject": "reasoning-step parity and the AlphaClaw cost equation",
        "discovered": "after V3-A, during the V3-B fixture freeze",
        "relative_to_inference": ("BEFORE any V3-B provider call and before the V3-B "
                                  "population was frozen"),
        "changed": ("Protocol v3 defined E2 twice and inconsistently; the ruling is "
                    "reasoning-step parity, so C_Alpha(N) = C_multimodal + N * C_text "
                    "and E2 issues N + 1 provider calls per episode"),
        "unchanged": ["architectures", "models", "task family", "depths", "repeats",
                      "providers", "expected_call_structure", "all caps"],
    },
)

#: Merge commits that froze each synthesis.
SYNTHESIS_MERGES = {
    "v2": "364dac574464b1b39be9718a38a144a648b02976",
    "v3": "5bb771df44809c731f1386a678c2cfe22f1e9d89",
}

CHECKPOINT_BASE_COMMIT = "5bb771df44809c731f1386a678c2cfe22f1e9d89"


def digest(relative: str) -> str:
    return hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()


def substrate() -> dict[str, Any]:
    """OmegaClaw / ThreadKeeper / image identifiers, read from committed evidence.

    These are not re-declared by hand: they are lifted from the run manifests recorded
    inside the frozen result artifacts, and asserted to be single-valued.
    """
    manifests = []
    for name in ("benchmark-v2-A.json", "benchmark-v2-B2.json", "benchmark-v2-C.json",
                 "benchmark-v3-A.json"):
        data = json.loads((BENCHMARK / name).read_text(encoding="utf-8"))
        records = data.get("runs") or data.get("episodes") or []
        manifests += [r["manifest"] for r in records if r.get("manifest")]

    def single(key: str) -> str:
        values = sorted({m[key] for m in manifests if key in m})
        if len(values) != 1:
            raise ValueError(f"{key} is not single-valued across the evidence: {values}")
        return values[0]

    return {
        "omega_sha": single("omega_sha"),
        "threadkeeper_sha": single("threadkeeper_sha"),
        "stock_omega_image_id": single("omega_image_id"),
        "pins_all_true": all(
            m.get("omega_commit_matches_pin") and m.get("omega_worktree_bytes_match_pin")
            and m.get("threadkeeper_commit_matches_pin")
            and m.get("threadkeeper_worktree_bytes_match_pin") for m in manifests),
        "source": "read from run manifests inside the frozen result artifacts",
    }


def build() -> dict[str, Any]:
    return {
        "checkpoint_version": CHECKPOINT_VERSION,
        "purpose": ("an index of frozen evidence; results are NOT restated here and "
                    "must be derived from the artifacts this file points at"),
        "restates_results": False,
        "base_commit": CHECKPOINT_BASE_COMMIT,
        "synthesis_merge_commits": dict(SYNTHESIS_MERGES),
        "evidence": {path: digest(path) for path in EVIDENCE},
        "substrate": substrate(),
        "amendments": [dict(a) for a in AMENDMENTS],
        "derivation": {
            "v2": "scripts/synthesis_v2.py",
            "v3": "scripts/synthesis_v3.py",
            "verifier": "scripts/verify_research_checkpoint.py",
        },
        "protocols_complete": ["v2", "v3"],
        "protocol_v4_started": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    document = build()
    text = json.dumps(document, indent=2, sort_keys=True) + "\n"
    if args.write:
        MANIFEST.write_bytes(text.encode("utf-8"))
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
