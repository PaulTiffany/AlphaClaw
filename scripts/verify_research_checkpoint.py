"""One-command offline verification of the AlphaClaw research checkpoint.

    python scripts/verify_research_checkpoint.py

Read-only and networkless. It launches no container, makes no provider call, needs no
API key, spends nothing, and writes nothing. Reproducing the published analysis must
never require re-running paid inference or trusting current provider availability.

It mechanically checks that:

* every pinned artifact digest matches its committed bytes;
* the substrate identifiers recorded in the committed evidence are single-valued;
* the v2 synthesis still derives from the frozen artifacts;
* the v3 synthesis still derives from the frozen artifacts;
* the checkpoint manifest indexes exactly the files it claims, at the right digests;
* the Git ancestry facts the checkpoint records hold in this checkout.

What it does NOT prove
----------------------
Git ancestry establishes the order of *commits*, not the order of *provider calls*. The
amendments' "BEFORE any ... provider call" statements remain **recorded process
evidence** from the repository history; no artifact ties an amendment to a wall-clock
moment relative to an inference request, and this verifier does not pretend otherwise.

Ancestry checks are skipped, not failed, when the tree is not a Git checkout or `git` is
unavailable -- a source tarball can still verify every artifact digest and both syntheses.

Exit status is 0 when every executed check passes, 1 otherwise.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import research_checkpoint
import synthesis_v2
import synthesis_v3

MANIFEST = ROOT / "benchmark" / "research-checkpoint.json"

SKIPPED = None

#: The only subprocesses this verifier may run: read-only local Git queries, no shell.
GIT_READ_ONLY_COMMANDS = (
    ("rev-parse", "--git-dir"),
    ("cat-file", "-e"),
    ("merge-base", "--is-ancestor"),
)


def _git(*args: str) -> tuple[bool, str]:
    """Run one read-only local Git query. Never a shell, never the network."""
    if not any(args[:len(prefix)] == prefix for prefix in GIT_READ_ONLY_COMMANDS):
        raise ValueError(f"refusing to run a non-allowlisted git command: {args}")
    try:
        completed = subprocess.run(
            ["git", "-C", str(ROOT), *args],
            capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return False, "git unavailable"
    return completed.returncode == 0, completed.stdout.strip()


def _check(results: list[tuple[str, bool | None, str]], name: str, ok: bool | None,
           detail: str = "") -> None:
    results.append((name, ok if ok is SKIPPED else bool(ok), detail))


def git_ancestry(manifest: dict[str, Any],
                 results: list[tuple[str, bool | None, str]]) -> None:
    """Validate the repository-history facts the checkpoint records.

    These are ancestry facts about commits available in this checkout. They say nothing
    about when provider calls were issued.
    """
    base = manifest["base_commit"]
    plan = (
        ("checkpoint base is an ancestor of HEAD", base, "HEAD"),
        ("v2 synthesis commit is an ancestor of the checkpoint base",
         manifest["synthesis_merge_commits"]["v2"], base),
        ("v3 synthesis commit is the checkpoint base or its ancestor",
         manifest["synthesis_merge_commits"]["v3"], base),
    )

    available, _ = _git("rev-parse", "--git-dir")
    if not available:
        for name, _commit, _target in plan:
            _check(results, name, SKIPPED, "not a git checkout")
        return

    # A commit missing from the working checkout is UNKNOWN, not false: CI and many
    # clones are shallow, so the history simply is not present to consult. Only a
    # commit that IS present and is NOT an ancestor is a real contradiction.
    for name, commit, target in plan:
        for ref in (commit, target):
            if ref == "HEAD":
                continue
            present, _ = _git("cat-file", "-e", f"{ref}^{{commit}}")
            if not present:
                _check(results, name, SKIPPED,
                       f"{ref[:12]} not in this checkout (shallow clone?)")
                break
        else:
            ok, _ = _git("merge-base", "--is-ancestor", commit, target)
            _check(results, name, ok, commit[:12])


def run() -> tuple[bool, list[tuple[str, bool | None, str]]]:
    results: list[tuple[str, bool | None, str]] = []

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    # 1. every pinned artifact digest
    mismatched = []
    for path, expected in manifest["evidence"].items():
        actual = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        if actual != expected:
            mismatched.append(path)
    _check(results, f"artifact digests ({len(manifest['evidence'])} files)",
           not mismatched, ", ".join(mismatched))

    # 2. the manifest indexes exactly the declared evidence set. The manifest is stored
    # with sorted keys, so membership is what matters, not declaration order.
    declared = research_checkpoint.EVIDENCE
    _check(results, "manifest indexes the declared evidence set",
           set(manifest["evidence"]) == set(declared)
           and len(declared) == len(set(declared)))

    # 3. substrate identifiers, read back from the committed evidence
    substrate = research_checkpoint.substrate()
    _check(results, "OmegaClaw / ThreadKeeper / image single-valued",
           substrate == manifest["substrate"],
           f"omega={substrate['omega_sha'][:12]} tk={substrate['threadkeeper_sha'][:12]}")
    _check(results, "commit and byte pins true in every run manifest",
           substrate["pins_all_true"] is True)

    # 4. the v2 synthesis still derives
    v2 = synthesis_v2.synthesis()
    _check(results, "v2 synthesis derives from frozen artifacts",
           all(synthesis_v2.artifact_digests_match().values()))
    _check(results, "v2 reports no single aggregate accuracy",
           v2["single_aggregate_accuracy_reported"] is False)

    # 5. the v3 synthesis still derives
    v3 = synthesis_v3.synthesis()
    _check(results, "v3 synthesis derives from frozen artifacts",
           all(synthesis_v3.artifact_digests_match().values()))
    _check(results, "v3 reports no single aggregate score",
           v3["single_aggregate_v3_score_reported"] is False)

    # 6. headline invariants that must survive any future edit
    _check(results, "v2: sensory substitution produced 0/3 transitions",
           v2["B2"]["transitions"] == 0)
    _check(results, "v2: resident substitution produced 3/3 transitions",
           v3 is not None and v2["C"]["transitions"] == v2["C"]["paired_cases"] == 3)
    _check(results, "v3-A: no unique cause isolated",
           v3["V3A"]["unique_cause_isolated"] is False)
    _check(results, "v3-B: max multimodal avoidance is 87.5%",
           abs(v3["V3B_architecture"]["max_avoidance_fraction"] - 0.875) < 1e-9)
    _check(results, "v3-B: all completed episodes produced correct answers",
           v3["V3B_availability"]["completed_episodes_all_correct"] is True)
    _check(results, "v3-B: 429 burst classified as availability, not wrong answers",
           v3["V3B_availability"]["incorrect_answers"] == 0
           and v3["V3B_availability"]["classified_as_incorrect_answers"] is False)

    # 7. the checkpoint is an index, not a second results source
    _check(results, "checkpoint restates no results",
           manifest["restates_results"] is False)
    _check(results, "protocol v4 not started",
           manifest["protocol_v4_started"] is False)

    # 8. repository-history facts (commit ancestry only, never call chronology)
    git_ancestry(manifest, results)

    return all(ok is not False for _, ok, _ in results), results


def main() -> int:
    passed, results = run()
    width = max(len(name) for name, _, _ in results)
    print("AlphaClaw research checkpoint -- offline verification")
    print("(read-only: no network, no container, no provider call, no API key)\n")
    for name, ok, detail in results:
        mark = "SKIP" if ok is SKIPPED else ("PASS" if ok else "FAIL")
        suffix = f"  {detail}" if detail else ""
        print(f"  [{mark}] {name:<{width}}{suffix}")

    executed = [ok for _, ok, _ in results if ok is not SKIPPED]
    skipped = len(results) - len(executed)
    print(f"\n{sum(1 for ok in executed if ok)}/{len(executed)} checks passed"
          + (f", {skipped} skipped" if skipped else ""))
    print("\nMechanically verified here: artifact identity, synthesis derivation,\n"
          "substrate pins and Git commit ancestry. Amendment timing relative to\n"
          "provider calls is recorded process evidence from the repository history,\n"
          "not reconstructed by this verifier.")
    print("\nRESULT: PASS" if passed else "\nRESULT: FAIL")
    return 0 if passed else 1


def summary() -> dict[str, Any]:
    """Machine-readable form of the same verification, for tests."""
    passed, results = run()
    return {"passed": passed,
            "checks": [{"name": n, "ok": ok, "skipped": ok is SKIPPED}
                       for n, ok, _ in results]}


if __name__ == "__main__":
    raise SystemExit(main())
