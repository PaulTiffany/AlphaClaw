"""Raw-byte provenance checks for the pinned benchmark dependencies.

Git's line-ending filters can rewrite a checked-out working tree while `git status`
still reports it clean. That is not hypothetical: a Windows checkout with
core.autocrlf=true rewrote OmegaClaw's entrypoint.sh shebang, the container died with
exit 127, and every existing pin check still passed.

These tests build synthetic Git repositories rather than invoking PowerShell or
mutating the real submodules, so they behave identically on the Linux CI runner and
on Windows.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "controller"
if str(CONTROLLER) not in sys.path:
    sys.path.insert(0, str(CONTROLLER))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


runner = _load("omegaboi_provenance", CONTROLLER / "omegaboi.py")

SHEBANG_LF = b"#!/usr/bin/env bash\nset -euo pipefail\necho stock\n"
CRLF_SHEBANG = b"#!/usr/bin/env bash\r\n"
TRACKED = ("entrypoint.sh", "requirements.txt")


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def _make_repo(tmp_path: Path) -> Path:
    """A pinned repository whose blobs hold LF, as upstream committed them."""
    repo = tmp_path / "pinned"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Provenance Test")
    _git(repo, "config", "core.autocrlf", "false")

    (repo / "entrypoint.sh").write_bytes(SHEBANG_LF)
    (repo / "requirements.txt").write_bytes(b"torch==2.12.1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "pinned tree")
    return repo


def _simulate_windows_checkout(repo: Path) -> None:
    """Reproduce a Git-for-Windows checkout: Git itself rewrites LF to CRLF.

    The distinction matters. Hand-writing CRLF bytes leaves the tree visibly dirty;
    letting Git perform the smudge on checkout is what makes `git status` report clean
    while the bytes on disk differ from the pinned blob. That is the production
    failure mode, so the fixture must reproduce it rather than approximate it.
    """
    _git(repo, "config", "core.autocrlf", "true")
    for name in TRACKED:
        (repo / name).unlink()
    _git(repo, "checkout", "--", ".")


def test_clean_worktree_reports_no_mismatches(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    mismatched, unverifiable = runner.worktree_byte_mismatches(repo)
    assert mismatched == []
    assert unverifiable == []


def test_crlf_drift_is_invisible_to_git_status_but_caught_by_byte_check(
    tmp_path: Path,
) -> None:
    """The certificate: git status says clean, raw-byte comparison says corrupted."""
    repo = _make_repo(tmp_path)
    _simulate_windows_checkout(repo)

    # The pre-existing guard sees nothing: autocrlf normalizes CRLF away on compare.
    assert _git(repo, "status", "--porcelain") == ""
    # A filtered hash is fooled the same way, which is why --no-filters is required.
    assert _git(repo, "hash-object", "entrypoint.sh") == _git(
        repo, "rev-parse", "HEAD:entrypoint.sh"
    )

    mismatched, unverifiable = runner.worktree_byte_mismatches(repo)
    assert "entrypoint.sh" in mismatched
    assert "requirements.txt" in mismatched
    assert unverifiable == []


def test_executable_shebang_drift_is_detected(tmp_path: Path) -> None:
    """The exact corruption that produced exit 127: env looks for a program named bash\r."""
    repo = _make_repo(tmp_path)
    _simulate_windows_checkout(repo)

    assert (repo / "entrypoint.sh").read_bytes().startswith(CRLF_SHEBANG)
    assert _git(repo, "status", "--porcelain") == ""

    mismatched, _ = runner.worktree_byte_mismatches(repo)
    assert "entrypoint.sh" in mismatched


def test_commit_and_byte_facts_are_independent(tmp_path: Path) -> None:
    """A matching commit must never be allowed to imply matching bytes."""
    repo = _make_repo(tmp_path)
    head_before = _git(repo, "rev-parse", "HEAD")
    _simulate_windows_checkout(repo)

    assert _git(repo, "rev-parse", "HEAD") == head_before
    mismatched, _ = runner.worktree_byte_mismatches(repo)
    assert mismatched


def test_requirements_txt_drift_is_caught_before_any_docker_work(
    tmp_path: Path,
) -> None:
    """requirements.txt is the Dockerfile cache key that costs gigabytes when it misses."""
    repo = _make_repo(tmp_path)
    _simulate_windows_checkout(repo)

    mismatched, _ = runner.worktree_byte_mismatches(repo)
    assert "requirements.txt" in mismatched


def test_missing_tracked_file_is_reported_as_mismatch(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    (repo / "entrypoint.sh").unlink()
    mismatched, _ = runner.worktree_byte_mismatches(repo)
    assert "entrypoint.sh" in mismatched


def test_pin_verification_exposes_both_facts_separately() -> None:
    fields = runner.PinVerification.__dataclass_fields__
    assert "commit_matches_pin" in fields
    assert "worktree_bytes_match_pin" in fields


def test_remediation_hint_names_the_actual_repair_commands() -> None:
    hint = runner._RENORMALIZE_HINT.format(path="OmegaClaw-Core")
    assert "core.autocrlf false" in hint
    assert "core.eol lf" in hint
    assert "rm --cached -rq ." in hint
    assert "reset --hard HEAD" in hint


def test_rebuild_does_not_delete_the_existing_image_first() -> None:
    """A failed rebuild must leave the last-known-good stock image in place."""
    source = (CONTROLLER / "omegaboi.py").read_text(encoding="utf-8")
    assert '"image", "rm"' not in source
    assert "docker image rm" not in source


def test_pin_verification_precedes_the_docker_build() -> None:
    """Byte drift must fail before any heavyweight Docker layer work begins."""
    source = (CONTROLLER / "omegaboi.py").read_text(encoding="utf-8")
    body = source.split("def ensure_stock_image", 1)[1]
    assert body.index("verify_omega()") < body.index('"docker", "build"')


@pytest.mark.parametrize("dependency", ["OmegaClaw-Core", "external/ThreadKeeper"])
def test_real_pins_are_byte_faithful(dependency: str) -> None:
    """Both pinned dependencies must match their blobs byte for byte.

    This mirrors the controller's own precondition: verify_omega() and
    verify_threadkeeper() raise on drift, so a tree that fails here would fail the
    benchmark too.
    """
    mismatched, unverifiable = runner.worktree_byte_mismatches(ROOT / dependency)
    assert mismatched == [], f"{dependency} byte drift ({len(mismatched)}): {mismatched[:5]}"
    assert unverifiable == [], f"{dependency} unverifiable: {unverifiable[:5]}"
