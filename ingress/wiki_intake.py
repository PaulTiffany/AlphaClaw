from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

MARKER = "<!-- alphaclaw-wiki-intake:v1 -->"
MAX_PAGE_BYTES = 64_000
MAX_FIELD_CHARS = 10_000
MAX_READY_PAGES = 100

SCHEMAS: dict[str, tuple[str, ...]] = {
    "Domain Rule": (
        "Ready for review",
        "Title",
        "Rule or principle",
        "Why it matters",
        "Evidence or example",
        "Confidence",
        "Suggested next step",
    ),
    "Edge-Case Evaluation": (
        "Ready for review",
        "Title",
        "Question or edge case",
        "What happened",
        "What I expected",
        "Why it matters",
        "Confidence",
        "Suggested next step",
    ),
    "Provenance Log": (
        "Ready for review",
        "Title",
        "Thing being checked",
        "Source or witness",
        "What I observed",
        "What remains uncertain",
        "Confidence",
        "Suggested next step",
    ),
}

KIND_BY_TITLE = {
    "Domain Rule": "domain-rule",
    "Edge-Case Evaluation": "edge-case-evaluation",
    "Provenance Log": "provenance-log",
}


class WikiIntakeError(RuntimeError):
    pass


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip() + "\n"


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    if not slug:
        raise WikiIntakeError(f"cannot derive a safe slug from {value!r}")
    return slug


def parse_page(markdown: str, *, page_name: str) -> dict[str, str] | None:
    if len(markdown.encode("utf-8")) > MAX_PAGE_BYTES:
        raise WikiIntakeError(f"{page_name}: page exceeds {MAX_PAGE_BYTES} bytes")
    text = _normalize(markdown)
    if MARKER not in text:
        return None

    lines = text.splitlines()
    h1 = [line[2:].strip() for line in lines if line.startswith("# ")]
    if len(h1) != 1 or h1[0] not in SCHEMAS:
        raise WikiIntakeError(f"{page_name}: expected exactly one supported level-1 heading")
    contribution_type = h1[0]

    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines:
        if line.startswith("## "):
            heading = line[3:].strip()
            if heading in sections:
                raise WikiIntakeError(f"{page_name}: duplicate section {heading!r}")
            sections[heading] = []
            current = heading
            continue
        if current is not None:
            sections[current].append(line)

    required = SCHEMAS[contribution_type]
    if set(sections) != set(required):
        missing = [name for name in required if name not in sections]
        extra = [name for name in sections if name not in required]
        raise WikiIntakeError(f"{page_name}: section mismatch; missing={missing}, extra={extra}")

    fields = {name: "\n".join(sections[name]).strip() for name in required}
    ready = fields["Ready for review"].casefold()
    if ready in {"no", "draft", "not yet"}:
        return None
    if ready != "yes":
        raise WikiIntakeError(f"{page_name}: Ready for review must be yes or no")

    for name, value in fields.items():
        if not value:
            raise WikiIntakeError(f"{page_name}: section {name!r} is empty")
        if len(value) > MAX_FIELD_CHARS:
            raise WikiIntakeError(f"{page_name}: section {name!r} exceeds {MAX_FIELD_CHARS} chars")

    fields.pop("Ready for review")
    return {"contribution_type": contribution_type, **fields}


def _git_page_provenance(wiki_dir: Path, relative_path: Path) -> tuple[str, str, str]:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(wiki_dir),
            "log",
            "-1",
            "--format=%H%x00%an%x00%ae",
            "--",
            relative_path.as_posix(),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    parts = result.stdout.strip().split("\x00")
    if len(parts) != 3 or not parts[0]:
        raise WikiIntakeError(f"missing Git provenance for {relative_path.as_posix()}")
    return parts[0], parts[1], parts[2]


def compile_wiki(wiki_dir: Path, output_dir: Path, *, repository: str) -> list[Path]:
    if not (wiki_dir / ".git").exists():
        raise WikiIntakeError(f"{wiki_dir} is not a Git-backed Wiki checkout")

    ready: list[tuple[Path, dict[str, str], str]] = []
    errors: list[str] = []
    for path in sorted(wiki_dir.rglob("*.md")):
        relative = path.relative_to(wiki_dir)
        try:
            markdown = path.read_text(encoding="utf-8")
            parsed = parse_page(markdown, page_name=relative.as_posix())
            if parsed is not None:
                ready.append((relative, parsed, _normalize(markdown)))
        except (UnicodeDecodeError, WikiIntakeError) as exc:
            errors.append(str(exc))

    if errors:
        raise WikiIntakeError("\n".join(errors))
    if len(ready) > MAX_READY_PAGES:
        raise WikiIntakeError(f"too many ready Wiki pages: {len(ready)} > {MAX_READY_PAGES}")

    output_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    seen_slugs: set[str] = set()
    for relative, parsed, markdown in ready:
        slug = _slug(relative.stem)
        if slug in seen_slugs:
            raise WikiIntakeError(f"duplicate generated slug: {slug}")
        seen_slugs.add(slug)

        commit, author_name, author_email = _git_page_provenance(wiki_dir, relative)
        contribution_type = parsed["contribution_type"]
        fields = {key: value for key, value in parsed.items() if key != "contribution_type"}
        page_name = relative.stem
        record = {
            "schema_version": 1,
            "kind": KIND_BY_TITLE[contribution_type],
            "title": fields["Title"],
            "fields": fields,
            "source": {
                "repository": repository,
                "wiki_page": page_name,
                "wiki_path": relative.as_posix(),
                "wiki_commit": commit,
                "wiki_author_name": author_name,
                "wiki_author_email": author_email,
                "wiki_url": f"https://github.com/{repository}/wiki/{page_name}",
                "markdown_sha256": _sha256(markdown),
            },
        }
        serialized = json.dumps(record, indent=2, sort_keys=True) + "\n"
        destination = output_dir / f"{slug}--{commit}.json"
        if destination.exists():
            if destination.read_text(encoding="utf-8") != serialized:
                raise WikiIntakeError(
                    f"immutable generated record conflicts with {destination.name}"
                )
            continue
        destination.write_text(serialized, encoding="utf-8")
        written.append(destination)

    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile ready AlphaClaw Wiki pages into review records")
    parser.add_argument("--wiki-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--repository", required=True)
    args = parser.parse_args()
    written = compile_wiki(args.wiki_dir, args.output_dir, repository=args.repository)
    print(f"Compiled {len(written)} new ready Wiki contribution(s).")


if __name__ == "__main__":
    main()
