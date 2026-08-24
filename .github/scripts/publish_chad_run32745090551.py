#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path

RUN_ID = "32745090551"
ARTIFACT_ID = "9526742320"
ZIP_SHA256 = "9d4dedbdad5f6cb0b4e93973b0d46f134f2f85b8b5f3caddb4d1e63427d81049"
ZIP_PATH = Path("chad-raster-art.zip")
EXTRACT = Path(".chad-run32745090551-artifact")

KEEPERS = [
    dict(
        id="basic-idea",
        line="See what is true. Accept what is true. Fix what is false. Do not waste your life defending your pride.",
        anchor="**See what is true. Accept what is true. Fix what is false. Do not waste your life defending your pride.**",
        model="google/gemini-2.5-flash-image",
        provider="google-ai-studio",
        cost="0.0387914",
        source="01-basic-idea--google-gemini-2-5-flash-image.png",
        sha256="3d456301bf6777f0b94ae8662aa4555f4d1fc262521861555819f29f5b901c91",
        dest="basic-idea.png",
        alt="Chad calmly replacing a failed mechanical part while status objects sit ignored in the background",
        rights="Gemini API Additional Terms of Service — https://ai.google.dev/gemini-api/terms",
        note="Google states that some Gemini API and Google AI Studio services generate original content and that Google will not claim ownership over that generated content; output may not be unique.",
    ),
    dict(
        id="judgment-scarcity",
        line="So making intelligence abundant can create a second scarcity: attention and judgment about what all that intelligence produces.",
        anchor="So making intelligence abundant can create a second scarcity: **attention and judgment about what all that intelligence produces.**",
        model="openai/gpt-image-1",
        provider="openai",
        cost="0.064315",
        source="02-judgment-scarcity--openai-gpt-image-1.png",
        sha256="cb02439f99a68034e44f9afa66612041127aa0b6aceb5a99459c338c484912a9",
        dest="judgment-scarcity.png",
        alt="Automated machinery produces many parts while Chad carefully inspects one item at a narrow decision station",
        rights="OpenAI Services Agreement — https://openai.com/policies/services-agreement/",
        note="OpenAI states that, as between Customer and OpenAI and to the extent permitted by law, Customer owns Output and OpenAI assigns any right, title, and interest it may have in Output.",
    ),
]

REJECTED = dict(
    id="room-to-think",
    model="google/gemini-3-pro-image",
    provider="google-vertex/global",
    source="03-room-to-think--google-gemini-3-pro-image.png",
    sha256="acd3bfe542d926db53c3e829eb9d73ff3724d2fa69a0bc0745d180dcda6fc0c5",
    reason="not published: visible alphanumeric labels and a question-mark symbol violated the no-visible-text/symbol generation constraint",
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def insert_after_once(text: str, anchor: str, block: str) -> str:
    count = text.count(anchor)
    if count != 1:
        raise SystemExit(f"anchor count {count} != 1: {anchor[:100]!r}")
    return text.replace(anchor, anchor + block, 1)


def image_block(k: dict) -> str:
    return (
        "\n\n"
        '<p align="center">\n'
        f'  <img src="assets/chad/{k["dest"]}" alt="{k["alt"]}" width="620">\n'
        "</p>\n\n"
        f'<p align="center"><em>annoned by <code>{k["model"]}</code> · '
        f'<a href="assets/chad/PROVENANCE.md#{k["id"]}">receipt</a></em></p>'
    )


if sha256(ZIP_PATH) != ZIP_SHA256:
    raise SystemExit("artifact ZIP SHA-256 mismatch")

if EXTRACT.exists():
    shutil.rmtree(EXTRACT)
EXTRACT.mkdir()
with zipfile.ZipFile(ZIP_PATH) as z:
    z.extractall(EXTRACT)

rows = [
    json.loads(line)
    for line in (EXTRACT / "provenance.jsonl").read_text(encoding="utf-8").splitlines()
    if line.strip()
]
by_file = {r.get("image_file"): r for r in rows}
asset_dir = Path("assets/chad")
asset_dir.mkdir(parents=True, exist_ok=True)

for k in KEEPERS:
    row = by_file.get(k["source"])
    if not row:
        raise SystemExit(f"missing provenance row: {k['source']}")
    if row.get("error"):
        raise SystemExit(f"source generation has error: {k['source']}")
    if row.get("model") != k["model"] or row.get("provider_tag") != k["provider"]:
        raise SystemExit(f"model/provider mismatch: {k['source']}")
    if row.get("image_sha256") != k["sha256"]:
        raise SystemExit(f"receipt SHA mismatch: {k['source']}")
    if str(row.get("actual_cost_usd")) != k["cost"]:
        raise SystemExit(f"reported cost mismatch: {k['source']}")

    src = EXTRACT / "images" / k["source"]
    if sha256(src) != k["sha256"]:
        raise SystemExit(f"source byte SHA mismatch: {k['source']}")

    dst = asset_dir / k["dest"]
    if dst.exists():
        raise SystemExit(f"destination already exists: {dst}")
    shutil.copyfile(src, dst)
    if sha256(dst) != k["sha256"] or src.read_bytes() != dst.read_bytes():
        raise SystemExit(f"published byte mismatch: {k['dest']}")
    print(f"keeper {k['id']} sha256={k['sha256']} git_blob={git_blob_sha(dst)}")

rej_row = by_file.get(REJECTED["source"])
if not rej_row or rej_row.get("image_sha256") != REJECTED["sha256"]:
    raise SystemExit("rejected-candidate receipt mismatch")

philosophy_path = Path("PHILOSOPHY.md")
philosophy = philosophy_path.read_text(encoding="utf-8")
for k in KEEPERS:
    if f"PROVENANCE.md#{k['id']}" in philosophy:
        raise SystemExit(f"philosophy already contains receipt: {k['id']}")
    philosophy = insert_after_once(philosophy, k["anchor"], image_block(k))
philosophy_path.write_text(philosophy, encoding="utf-8")

provenance_path = Path("assets/chad/PROVENANCE.md")
provenance = provenance_path.read_text(encoding="utf-8")
for k in KEEPERS:
    if f"### {k['id']}" in provenance:
        raise SystemExit(f"provenance already contains receipt: {k['id']}")

round_block = f"""

## Publication round `{RUN_ID}`

This publication started from `PaulTiffany/letGPTsustakethewheel` Actions run `{RUN_ID}`, artifact `chad-raster-art` (`{ARTIFACT_ID}`), ZIP SHA-256 `{ZIP_SHA256}`.

Three rasters were generated. Two passed human visual review and are published below as exact-byte copies. `{REJECTED['id']}` (`{REJECTED['source']}`, SHA-256 `{REJECTED['sha256']}`) was {REJECTED['reason']}.

"""
receipt_blocks = []
for k in KEEPERS:
    receipt_blocks.append(
        f"""### {k['id']}

- Philosophy line: **{k['line']}**
- Model: `{k['model']}`
- Routed provider: `{k['provider']}`
- Generation cost reported by OpenRouter: `${k['cost']}`
- Reference image supplied: **no**
- Original run: `PaulTiffany/letGPTsustakethewheel` Actions run `{RUN_ID}`
- Artifact: `chad-raster-art` (`{ARTIFACT_ID}`)
- Original run file: `{k['source']}`
- Original generation SHA-256: `{k['sha256']}`
- Published file: `{k['dest']}`
- Published SHA-256: `{k['sha256']}`
- Publication transform: **none; exact-byte copy from the verified artifact**
- Rights/source review: {k['rights']}
- Publication note: {k['note']}
"""
    )

provenance_path.write_text(
    provenance.rstrip() + round_block + "\n".join(receipt_blocks).rstrip() + "\n",
    encoding="utf-8",
)

for k in KEEPERS:
    src = EXTRACT / "images" / k["source"]
    dst = asset_dir / k["dest"]
    if src.read_bytes() != dst.read_bytes():
        raise SystemExit(f"final byte identity failed: {k['id']}")

print(f"published_keep={len(KEEPERS)} rejected=1 run={RUN_ID} artifact={ARTIFACT_ID}")
