#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

RUN_ID = "32797015558"
ARTIFACT_ID = "9545294372"
ARTIFACT_NAME = "chad-raster-art"
ZIP_NAME = "chad-raster-art-32797015558.zip"
ZIP_SHA256 = "283f30685d81d37be598f9411b3a84d0c4fc1933505fbeb9796cf59256365261"

ROOT = Path.cwd()
PHILOSOPHY = ROOT / "PHILOSOPHY.md"
PROVENANCE = ROOT / "assets/chad/PROVENANCE.md"
ASSET_DIR = ROOT / "assets/chad"
ZIP_PATH = ROOT / ZIP_NAME

KEEPERS = [
    {
        "id": "plan-survives-failure",
        "line": "A good plan can survive one person getting tired, one tool failing, one assumption being wrong, or one experiment going badly.",
        "anchor": "A good plan can survive one person getting tired, one tool failing, one assumption being wrong, or one experiment going badly.",
        "model": "bytedance-seed/seedream-5-0-lite",
        "provider": "seed",
        "cost": 0.035,
        "source": "01-plan-survives-failure--bytedance-seed-seedream-5-0-lite.jpg",
        "sha256": "9cc0befb2ab7a464fbdf69d35a4b2d2ca7dee62cdfb11e2bf478c5e186ace8a7",
        "git_blob": "60aab9d0bed8f838e207fb654007fc85c7b96590",
        "dest": "plan-survives-failure.jpg",
        "alt": "Chad works beside a stable scaffold while a tired teammate rests and the project remains supported",
        "rights": "BytePlus Model Services terms — https://docs.byteplus.com/vi/docs/legal/docs-service-specific-terms",
        "note": "BytePlus states that, to the extent permitted by law, output IP rights belong to the customer or other applicable rights holder and BytePlus does not claim ownership.",
    },
    {
        "id": "better-method-not-authority",
        "line": "A system may discover a better method. That does not mean it has earned the right to deploy that method, widen its own permissions, or remove the gate that judged it.",
        "anchor": "A system may discover a better method. That does not mean it has earned the right to deploy that method, widen its own permissions, or remove the gate that judged it.",
        "model": "recraft/recraft-v4.1",
        "provider": "recraft",
        "cost": 0.035,
        "source": "02-better-method-not-authority--recraft-recraft-v4-1.webp",
        "sha256": "d878ea8ebc02133a8e5ffe66151dbae969639fab880112f64d1c1c02c5b45f41",
        "git_blob": "faeb758870a83f81c0a2d0bf5e834177a535c201",
        "dest": "better-method-not-authority.webp",
        "alt": "Chad holds a useful component beside a separate locked authorization gate while the machine remains behind the boundary",
        "rights": "Recraft API Terms — https://www.recraft.ai/legal/terms",
        "note": "Recraft states that API users own assets created with the API and assigns any copyright it may have, subject to a restriction against using the assets to train AI models, systems, or networks.",
    },
]

NONPUBLICATION = [
    {
        "id": "ridiculous-experiment",
        "model": "black-forest-labs/flux.2-klein-4b",
        "provider": "black-forest-labs",
        "source": "03-ridiculous-experiment--black-forest-labs-flux-2-klein-4b.png",
        "sha256": "d06eb3eb73ebd781a48ee1d7062fc7aa431c4c65513896790cdde53b4417b2f2",
        "kind": "visual rejection",
        "reason": "visible hallucinated lettering violated the explicit no-visible-text generation constraint",
    },
    {
        "id": "indispensable-single-point",
        "model": "recraft/recraft-v3",
        "provider": "recraft",
        "source": "04-indispensable-single-point--recraft-recraft-v3.webp",
        "sha256": "dd9e651ff76371b905b81369054fceec48f0099b6fd854d68868081dcf5730e4",
        "kind": "visual rejection",
        "reason": "the composition rhetorically celebrated the indispensable central operator rather than showing the single-point-of-failure warning",
    },
    {
        "id": "embarrassing-truth-standing",
        "model": "black-forest-labs/flux.2-max",
        "provider": "black-forest-labs/us-3",
        "source": None,
        "sha256": None,
        "kind": "generation failure",
        "reason": "provider response read timed out; no raster was produced and no generation cost was reported",
    },
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def fail(msg: str) -> None:
    raise RuntimeError(msg)


def load_rows(path: Path) -> dict[str, dict]:
    rows = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        pid = row["philosophy"]["id"]
        if pid in rows:
            fail(f"duplicate provenance id: {pid}")
        rows[pid] = row
    return rows


def verify_keeper(row: dict, k: dict, source: Path) -> None:
    if row["model"] != k["model"]:
        fail(f"{k['id']}: model mismatch")
    if row["provider_tag"] != k["provider"]:
        fail(f"{k['id']}: provider mismatch")
    if row.get("actual_cost_usd") != k["cost"]:
        fail(f"{k['id']}: cost mismatch {row.get('actual_cost_usd')!r}")
    if row.get("error") is not None:
        fail(f"{k['id']}: generation error unexpectedly present")
    if row.get("image_file") != k["source"]:
        fail(f"{k['id']}: source filename mismatch")
    if row.get("image_sha256") != k["sha256"]:
        fail(f"{k['id']}: provenance SHA mismatch")
    data = source.read_bytes()
    if sha256(data) != k["sha256"]:
        fail(f"{k['id']}: source bytes SHA mismatch")
    if git_blob_sha(data) != k["git_blob"]:
        fail(f"{k['id']}: source Git blob mismatch")


def verify_nonpublication(rows: dict[str, dict], item: dict, image_dir: Path) -> None:
    row = rows[item["id"]]
    if row["model"] != item["model"] or row["provider_tag"] != item["provider"]:
        fail(f"{item['id']}: nonpublication identity mismatch")
    if item["kind"] == "visual rejection":
        if row.get("error") is not None:
            fail(f"{item['id']}: expected successful generation before visual rejection")
        if row.get("image_file") != item["source"] or row.get("image_sha256") != item["sha256"]:
            fail(f"{item['id']}: rejected raster receipt mismatch")
        source = image_dir / item["source"]
        if not source.exists() or sha256(source.read_bytes()) != item["sha256"]:
            fail(f"{item['id']}: rejected raster bytes mismatch")
    else:
        if row.get("image_file") is not None or row.get("image_sha256") is not None:
            fail(f"{item['id']}: generation failure unexpectedly has raster")
        err = row.get("error") or {}
        if err.get("exception") != "TimeoutError":
            fail(f"{item['id']}: expected TimeoutError, got {err!r}")
        if row.get("actual_cost_usd") is not None:
            fail(f"{item['id']}: expected no reported generation cost")


def image_block(k: dict) -> str:
    return (
        f'\n\n<p align="center">\n'
        f'  <img src="assets/chad/{k["dest"]}" alt="{k["alt"]}" width="620">\n'
        f'</p>\n\n'
        f'<p align="center"><em>annoned by <code>{k["model"]}</code> · '
        f'<a href="assets/chad/PROVENANCE.md#{k["id"]}">receipt</a></em></p>'
    )


def receipt(k: dict) -> str:
    return f"""### {k["id"]}

- Philosophy line: **{k["line"]}**
- Model: `{k["model"]}`
- Routed provider: `{k["provider"]}`
- Generation cost reported by OpenRouter: `${k["cost"]}`
- Reference image supplied: **no**
- Original run: `PaulTiffany/letGPTsustakethewheel` Actions run `{RUN_ID}`
- Artifact: `{ARTIFACT_NAME}` (`{ARTIFACT_ID}`)
- Original run file: `{k["source"]}`
- Original generation SHA-256: `{k["sha256"]}`
- Published file: `{k["dest"]}`
- Published SHA-256: `{k["sha256"]}`
- Publication transform: **none; exact-byte copy from the verified artifact**
- Rights/source review: {k["rights"]}
- Publication note: {k["note"]}
"""


def main() -> int:
    if not ZIP_PATH.exists():
        fail(f"missing artifact ZIP: {ZIP_PATH}")
    actual_zip_sha = sha256(ZIP_PATH.read_bytes())
    if actual_zip_sha != ZIP_SHA256:
        fail(f"artifact ZIP SHA mismatch: {actual_zip_sha}")

    if not PHILOSOPHY.exists() or not PROVENANCE.exists():
        fail("expected AlphaClaw PHILOSOPHY.md and PROVENANCE.md")

    philosophy_text = PHILOSOPHY.read_text(encoding="utf-8")
    provenance_text = PROVENANCE.read_text(encoding="utf-8")

    if f"## Publication round `{RUN_ID}`" in provenance_text:
        fail(f"publication round {RUN_ID} already present")

    for k in KEEPERS:
        if philosophy_text.count(k["anchor"]) != 1:
            fail(f"{k['id']}: anchor count != 1")
        if f"assets/chad/{k['dest']}" in philosophy_text:
            fail(f"{k['id']}: destination already referenced")
        if f"### {k['id']}" in provenance_text:
            fail(f"{k['id']}: receipt anchor already present")
        if (ASSET_DIR / k["dest"]).exists():
            fail(f"{k['id']}: destination file already exists")

    with tempfile.TemporaryDirectory(prefix="chad-publish-") as td:
        extract = Path(td)
        with zipfile.ZipFile(ZIP_PATH) as z:
            z.extractall(extract)
        rows = load_rows(extract / "provenance.jsonl")
        image_dir = extract / "images"

        for k in KEEPERS:
            row = rows[k["id"]]
            source = image_dir / k["source"]
            verify_keeper(row, k, source)
            dest = ASSET_DIR / k["dest"]
            shutil.copyfile(source, dest)
            source_bytes = source.read_bytes()
            dest_bytes = dest.read_bytes()
            if source_bytes != dest_bytes:
                fail(f"{k['id']}: exact-byte copy failed")
            if sha256(dest_bytes) != k["sha256"]:
                fail(f"{k['id']}: destination SHA mismatch")
            if git_blob_sha(dest_bytes) != k["git_blob"]:
                fail(f"{k['id']}: destination Git blob mismatch")
            print(f"keeper {k['id']}: sha256={k['sha256']} git_blob={k['git_blob']} bytes={len(dest_bytes)}")

        for item in NONPUBLICATION:
            verify_nonpublication(rows, item, image_dir)
            print(f"{item['kind']} {item['id']}: {item['reason']}")

    new_philosophy = philosophy_text
    for k in KEEPERS:
        new_philosophy = new_philosophy.replace(k["anchor"], k["anchor"] + image_block(k), 1)
    PHILOSOPHY.write_text(new_philosophy, encoding="utf-8")

    nonpub_lines = "\n".join(
        f"- `{x['id']}` — **{x['kind']}**: {x['reason']}."
        + (f" Source file `{x['source']}`, SHA-256 `{x['sha256']}`." if x["source"] else "")
        for x in NONPUBLICATION
    )
    section = f"""

## Publication round `{RUN_ID}`

This publication started from `PaulTiffany/letGPTsustakethewheel` Actions run `{RUN_ID}`, artifact `{ARTIFACT_NAME}` (`{ARTIFACT_ID}`), ZIP SHA-256 `{ZIP_SHA256}`.

Five model calls were attempted. Four produced valid raster bytes. Two passed human visual review and are published below as exact-byte copies. Two successful generations were rejected at the visual publication gate, and one model call produced no raster because the provider response timed out.

Non-publication outcomes:

{nonpub_lines}

""" + "\n".join(receipt(k) for k in KEEPERS)

    PROVENANCE.write_text(provenance_text.rstrip() + section + "\n", encoding="utf-8")

    for k in KEEPERS:
        data = (ASSET_DIR / k["dest"]).read_bytes()
        if sha256(data) != k["sha256"] or git_blob_sha(data) != k["git_blob"]:
            fail(f"{k['id']}: final byte identity check failed")
        if PHILOSOPHY.read_text(encoding="utf-8").count(f"assets/chad/{k['dest']}") != 1:
            fail(f"{k['id']}: philosophy reference count mismatch")
        if PROVENANCE.read_text(encoding="utf-8").count(f"### {k['id']}") != 1:
            fail(f"{k['id']}: provenance anchor count mismatch")

    print("publication manifest verified: 2 keepers, 2 visual rejections, 1 generation failure")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
