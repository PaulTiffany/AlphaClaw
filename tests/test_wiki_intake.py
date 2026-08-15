from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("wiki_intake", ROOT / "ingress" / "wiki_intake.py")
assert SPEC is not None and SPEC.loader is not None
wiki_intake = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = wiki_intake
SPEC.loader.exec_module(wiki_intake)

DOMAIN_PAGE = """<!-- alphaclaw-wiki-intake:v1 -->
# Domain Rule

## Ready for review
yes

## Title
Preserve the evidence boundary

## Rule or principle
A generated recommendation must retain the evidence that licensed it.

## Why it matters
Reviewers need to distinguish source material from later interpretation.

## Evidence or example
A provenance record names the source Wiki commit and exact Markdown hash.

## Confidence
High for this project boundary.

## Suggested next step
Keep generated contributions review-only until a human merges them.
"""


def _git(*args: str, cwd: Path) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def _init_wiki(path: Path) -> None:
    path.mkdir()
    _git("init", cwd=path)
    _git("config", "user.name", "Sheila Example", cwd=path)
    _git("config", "user.email", "sheila@example.invalid", cwd=path)


def test_parse_ready_domain_rule() -> None:
    parsed = wiki_intake.parse_page(DOMAIN_PAGE, page_name="Domain-Rule-Test.md")
    assert parsed is not None
    assert parsed["contribution_type"] == "Domain Rule"
    assert parsed["Title"] == "Preserve the evidence boundary"
    assert "source Wiki commit" in parsed["Evidence or example"]


def test_draft_page_is_not_compiled() -> None:
    draft = DOMAIN_PAGE.replace("## Ready for review\nyes", "## Ready for review\nno")
    assert wiki_intake.parse_page(draft, page_name="Draft.md") is None


def test_ready_page_rejects_missing_required_section() -> None:
    broken = DOMAIN_PAGE.replace(
        "## Confidence\nHigh for this project boundary.\n\n",
        "",
    )
    with pytest.raises(wiki_intake.WikiIntakeError, match="section mismatch"):
        wiki_intake.parse_page(broken, page_name="Broken.md")


def test_compile_wiki_records_git_and_content_provenance(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _init_wiki(wiki)
    page = wiki / "Evidence-Boundary.md"
    page.write_text(DOMAIN_PAGE, encoding="utf-8")
    _git("add", "Evidence-Boundary.md", cwd=wiki)
    _git("commit", "-m", "Add evidence boundary evaluation", cwd=wiki)
    expected_commit = _git("rev-parse", "HEAD", cwd=wiki)

    output = tmp_path / "generated"
    written = wiki_intake.compile_wiki(wiki, output, repository="PaulTiffany/AlphaClaw")

    expected = output / f"evidence-boundary--{expected_commit}.json"
    assert written == [expected]
    record = json.loads(expected.read_text(encoding="utf-8"))
    assert record["kind"] == "domain-rule"
    assert record["source"]["wiki_commit"] == expected_commit
    assert record["source"]["wiki_author_name"] == "Sheila Example"
    assert record["source"]["wiki_author_email"] == "sheila@example.invalid"
    assert len(record["source"]["markdown_sha256"]) == 64

    assert wiki_intake.compile_wiki(wiki, output, repository="PaulTiffany/AlphaClaw") == []


def test_compiled_history_is_append_only_across_reused_working_page(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _init_wiki(wiki)
    page = wiki / "Domain-Rule.md"
    page.write_text(DOMAIN_PAGE, encoding="utf-8")
    _git("add", "Domain-Rule.md", cwd=wiki)
    _git("commit", "-m", "Submit first domain rule", cwd=wiki)
    first_commit = _git("rev-parse", "HEAD", cwd=wiki)

    output = tmp_path / "generated"
    first_written = wiki_intake.compile_wiki(wiki, output, repository="PaulTiffany/AlphaClaw")
    first_record = output / f"domain-rule--{first_commit}.json"
    assert first_written == [first_record]

    draft = DOMAIN_PAGE.replace("## Ready for review\nyes", "## Ready for review\nno")
    page.write_text(draft, encoding="utf-8")
    _git("add", "Domain-Rule.md", cwd=wiki)
    _git("commit", "-m", "Start next draft", cwd=wiki)
    assert wiki_intake.compile_wiki(wiki, output, repository="PaulTiffany/AlphaClaw") == []
    assert first_record.exists()

    second = DOMAIN_PAGE.replace("Preserve the evidence boundary", "Preserve human review")
    page.write_text(second, encoding="utf-8")
    _git("add", "Domain-Rule.md", cwd=wiki)
    _git("commit", "-m", "Submit second domain rule", cwd=wiki)
    second_commit = _git("rev-parse", "HEAD", cwd=wiki)
    second_written = wiki_intake.compile_wiki(wiki, output, repository="PaulTiffany/AlphaClaw")
    second_record = output / f"domain-rule--{second_commit}.json"

    assert second_written == [second_record]
    assert first_record.exists()
    assert second_record.exists()
    assert len(list(output.glob("*.json"))) == 2


def test_unmarked_wiki_page_is_ignored(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _init_wiki(wiki)
    (wiki / "Home.md").write_text("# Ordinary Wiki Home\n", encoding="utf-8")
    output = tmp_path / "generated"
    assert wiki_intake.compile_wiki(wiki, output, repository="PaulTiffany/AlphaClaw") == []
    assert list(output.iterdir()) == []
