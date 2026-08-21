#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path

RUN_ID = "32431592545"
ARTIFACT_ID = "9429338299"
ZIP_SHA256 = "683b0b091184311ddf466f0db5e308763fd76bebe59313de3699695fc3625c01"
ZIP_PATH = Path("chad-raster-art.zip")
EXTRACT = Path(".chad-round15-artifact")

KEEPERS = [
    dict(id="capability-not-permission", line="Capability is not permission.", model="krea/krea-2-medium-turbo", provider="krea", cost="0.015", source="01-capability-not-permission--krea-krea-2-medium-turbo.png", sha256="1ac4174889e5a5c590c85dff198955c7d92824a3d7c5a2d50d7d3830f4c55d70", dest="capability-not-permission.png", alt="Chad holding the external key while a powerful robot remains physically separated behind a barrier", rights="Krea 2 Community License Agreement — https://www.krea.ai/krea-2-licensing", note="Krea states that users own Outputs and Krea claims no ownership of them. Commercial use under the community license is conditioned on company-wide trailing-twelve-month annual revenue below $1,000,000; otherwise an enterprise license is required."),
    dict(id="test-not-assurance", line="A test is better than an assurance.", model="openai/gpt-5-image-mini", provider="openai", cost="0.013162", source="02-test-not-assurance--openai-gpt-5-image-mini.png", sha256="8eae698b891fd2aead2b7bfbc5befa7f04c4767ec0f4af719fa65794a7847173", dest="test-not-assurance.png", alt="A presenter gestures while a real component is quietly placed into a physical load-testing press", rights="OpenAI Services Agreement — https://openai.com/policies/services-agreement/", note="OpenAI states that, as between Customer and OpenAI and to the extent permitted by law, Customer owns Output and OpenAI assigns any right, title, and interest it may have in Output."),
    dict(id="change-mind", line="If the world proves you wrong, change your mind.", model="google/gemini-3.1-flash-image-preview", provider="google-ai-studio", cost="0.068515", source="03-change-mind--google-gemini-3-1-flash-image-preview.jpg", sha256="815a2967d32f9d9d7a3b621a1eef142352c65e79c2de1c2b43302072e9bd1366", dest="change-mind.jpg", alt="Chad sets aside a failed gear design and works from the visibly successful replacement", rights="Gemini API Additional Terms of Service — https://ai.google.dev/gemini-api/terms", note="Google states that some Gemini API and Google AI Studio services generate original content and that Google will not claim ownership over that generated content; output may not be unique."),
    dict(id="mechanical-checks", line="Mechanical checks should become cheap wherever we can make them cheap.", model="microsoft/mai-image-2.5", provider="azure", cost="0.037036", source="04-mechanical-checks--microsoft-mai-image-2-5.png", sha256="a5532f2a7e1d7d5579d8cbf6189b002085ee3ad09bbcc05eba0e5efafc25a2e0", dest="mechanical-checks.png", alt="A long row of simple identical mechanical fixtures checks parts before human attention is needed", rights="Microsoft Product Terms, Microsoft Generative AI Services — https://www.microsoft.com/licensing/terms/product/foronlineServices/all", note="Microsoft's Product Terms state that Output Content is Customer Data and Microsoft does not own Customer's Output Content."),
    dict(id="rest-delegation", line="Rest, delegation, and asking for help are not failures of seriousness.", model="krea/krea-2-medium", provider="krea", cost="0.03", source="05-rest-delegation--krea-krea-2-medium.png", sha256="236d7870d5e9f6f3557ba1582acd3d071a8778c6fd2041038fc063a0cbfed16b", dest="rest-delegation.png", alt="Chad drinks water while handing a wrench to a teammate and shared work continues around him", rights="Krea 2 Community License Agreement — https://www.krea.ai/krea-2-licensing", note="Krea states that users own Outputs and Krea claims no ownership of them. Commercial use under the community license is conditioned on company-wide trailing-twelve-month annual revenue below $1,000,000; otherwise an enterprise license is required."),
    dict(id="truth-not-winning", line="The point is not to win arguments. The point is to find out what is actually true.", model="krea/krea-2-large", provider="krea", cost="0.06", source="06-truth-not-winning--krea-krea-2-large.png", sha256="4da0f1c3bf5ba359b9a785aa3aa8ed21ee8c37956cdb8067c9a6ed2c817d464b", dest="truth-not-winning.png", alt="Chad and another person inspect an experiment while a debate podium and trophy sit ignored behind them", rights="Krea 2 Community License Agreement — https://www.krea.ai/krea-2-licensing", note="Krea states that users own Outputs and Krea claims no ownership of them. Commercial use under the community license is conditioned on company-wide trailing-twelve-month annual revenue below $1,000,000; otherwise an enterprise license is required."),
    dict(id="ideas-meet-reality", line="Chad philosophy does not protect ideas from reality.", model="microsoft/mai-image-2.5-pro", provider="azure", cost="0.083854", source="07-ideas-meet-reality--microsoft-mai-image-2-5-pro.png", sha256="0ea50a1f345bf73107c9f3bc4e1e001ca665aaa81c18d1888494329ea5f5591c", dest="ideas-meet-reality.png", alt="Chad removes protective padding from his own prototype over a real industrial testing machine", rights="Microsoft Product Terms, Microsoft Generative AI Services — https://www.microsoft.com/licensing/terms/product/foronlineServices/all", note="Microsoft's Product Terms state that Output Content is Customer Data and Microsoft does not own Customer's Output Content."),
    dict(id="recoverable-progress", line="Chad philosophy therefore prefers recoverable progress over heroic overextension.", model="google/gemini-3-pro-image-preview", provider="google-ai-studio/global", cost="0.137336", source="08-recoverable-progress--google-gemini-3-pro-image-preview.jpg", sha256="252d0340039a867622e20f185b949806dad0e7af308c434f28c5d6a9839b2326", dest="recoverable-progress.jpg", alt="Chad calmly rebuilds in stable supported stages while an overloaded shortcut collapses nearby", rights="Gemini API Additional Terms of Service — https://ai.google.dev/gemini-api/terms", note="Google states that some Gemini API and Google AI Studio services generate original content and that Google will not claim ownership over that generated content; output may not be unique."),
    dict(id="authorized-gate", line="No high-consequence actuator without an independently authorized gate in its causal past that can still say no.", model="openai/gpt-5.4-image-2", provider="openai", cost="0.05047", source="09-authorized-gate--openai-gpt-5-4-image-2.png", sha256="9f08f5ac73550628a128440323a892b871bb97ac48e1772dc7a302c82c815823", dest="authorized-gate.png", alt="A powerful industrial press remains downstream of a heavy barred gate with a separate mechanical control", rights="OpenAI Services Agreement — https://openai.com/policies/services-agreement/", note="OpenAI states that, as between Customer and OpenAI and to the extent permitted by law, Customer owns Output and OpenAI assigns any right, title, and interest it may have in Output."),
    dict(id="brake-engine-path", line="Do not put the brake on the same failure path as the engine.", model="openai/gpt-5-image", provider="openai", cost="0.06529", source="10-brake-engine-path--openai-gpt-5-image.png", sha256="4ce2e07ff23867f42126c09f9647dd55aea6eb80daf76a82b03ac6667854aa34", dest="brake-engine-path.png", alt="An engine cable bundle sparks and fails while Chad retains a separate simple mechanical brake linkage", rights="OpenAI Services Agreement — https://openai.com/policies/services-agreement/", note="OpenAI states that, as between Customer and OpenAI and to the extent permitted by law, Customer owns Output and OpenAI assigns any right, title, and interest it may have in Output."),
    dict(id="strongest-criticism", line="When testing an idea, use the strongest reasonable criticism you can find.", model="black-forest-labs/flux.2-klein-4b", provider="black-forest-labs", cost="0.015", source="11-strongest-criticism--black-forest-labs-flux-2-klein-4b.png", sha256="c001859049098b233b05b73ca2e945fc00f7d1992d1bb2e94c42a0d59e3ff966", dest="strongest-criticism.png", alt="Chad deliberately stress-tests his own bridge-like structure instead of giving it an easy harmless test", rights="Black Forest Labs Developer Terms of Service — https://bfl.ai/legal/developer-terms-of-service", note="Black Forest Labs states that, as between developer and BFL, the developer owns Output; outputs may carry Content Credentials or provenance data, which this exact-byte publication does not remove or alter."),
]

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
    n = text.count(anchor)
    if n != 1:
        raise SystemExit(f"anchor count {n} != 1: {anchor[:90]!r}")
    return text.replace(anchor, anchor + block, 1)

def image_block(k: dict) -> str:
    return (
        '<p align="center">\n'
        f'  <img src="assets/chad/{k["dest"]}" alt="{k["alt"]}" width="620">\n'
        '</p>\n\n'
        f'<p align="center"><em>annoned by <code>{k["model"]}</code> · '
        f'<a href="assets/chad/PROVENANCE.md#{k["id"]}">receipt</a></em></p>\n\n'
    )

if sha256(ZIP_PATH) != ZIP_SHA256:
    raise SystemExit("artifact ZIP SHA-256 mismatch")
if EXTRACT.exists():
    shutil.rmtree(EXTRACT)
EXTRACT.mkdir()
with zipfile.ZipFile(ZIP_PATH) as z:
    z.extractall(EXTRACT)

rows = [json.loads(line) for line in (EXTRACT / "provenance.jsonl").read_text().splitlines() if line.strip()]
by_file = {r.get("image_file"): r for r in rows}
asset_dir = Path("assets/chad")
asset_dir.mkdir(parents=True, exist_ok=True)
for k in KEEPERS:
    row = by_file.get(k["source"])
    if not row or row.get("error"):
        raise SystemExit(f"missing/error provenance row: {k['source']}")
    if row.get("model") != k["model"] or row.get("provider_tag") != k["provider"]:
        raise SystemExit(f"model/provider mismatch: {k['source']}")
    if row.get("image_sha256") != k["sha256"]:
        raise SystemExit(f"receipt SHA mismatch: {k['source']}")
    src = EXTRACT / "images" / k["source"]
    if sha256(src) != k["sha256"]:
        raise SystemExit(f"source byte SHA mismatch: {k['source']}")
    dst = asset_dir / k["dest"]
    shutil.copyfile(src, dst)
    if sha256(dst) != k["sha256"]:
        raise SystemExit(f"published byte SHA mismatch: {k['dest']}")
    print(f"keeper {k['id']}: sha256={k['sha256']} git_blob={git_blob_sha(dst)}")

ph_path = Path("PHILOSOPHY.md")
ph = ph_path.read_text()
K = {k["id"]: k for k in KEEPERS}
ph = insert_after_once(ph, "The point is to find out what is actually true.\n\n", image_block(K["truth-not-winning"]))
ph = insert_after_once(ph, "A test is better than an assurance.\n\n", image_block(K["test-not-assurance"]))
ph = insert_after_once(ph, "If the world proves you wrong, change your mind.\n\n", image_block(K["change-mind"]))
ph = insert_after_once(ph, "Chad philosophy does not protect ideas from reality.\n\n", image_block(K["ideas-meet-reality"]))
ph = insert_after_once(ph, "Chad philosophy therefore prefers **recoverable progress** over heroic overextension.\n\n", image_block(K["recoverable-progress"]))
ph = insert_after_once(ph, "## Capability is not permission\n\n", image_block(K["capability-not-permission"]))
ph = insert_after_once(ph, "> **No high-consequence actuator without an independently authorized gate in its causal past that can still say no.**\n\n", image_block(K["authorized-gate"]))
ph = insert_after_once(ph, "> **Do not put the brake on the same failure path as the engine.**\n\n", image_block(K["brake-engine-path"]))
ph = insert_after_once(ph, "Mechanical checks should become cheap wherever we can make them cheap. Provenance should become cheap. Reproducibility should become cheap. Tests should become cheap.\n\n", image_block(K["mechanical-checks"]))
ph = insert_after_once(ph, "So when testing an idea, use the strongest reasonable criticism you can find.\n\n", image_block(K["strongest-criticism"]))
ph = insert_after_once(ph, "Rest, delegation, and asking for help are not failures of seriousness. They are ways of preserving judgment for the next branch point.\n\n", image_block(K["rest-delegation"]))
ph_path.write_text(ph)

prov_path = asset_dir / "PROVENANCE.md"
prov = prov_path.read_text()
prov = prov.replace(
    "run `32399313906`, and frontier-model run `32424076108`.",
    "run `32399313906`, frontier-model run `32424076108`, and full-population run `32431592545`.", 1)
prov = prov.replace(
    "Accepted keepers from runs `32388944793`, `32399313906`, and `32424076108` are published as exact-byte copies of the original artifact files.",
    "Accepted keepers from runs `32388944793`, `32399313906`, `32424076108`, and `32431592545` are published as exact-byte copies of the original artifact files.", 1)
artifact_anchor = "For run `32424076108`, publication started from GitHub Actions artifact `9426834676`, whose ZIP SHA-256 is `a0210aee107921ed678b473f7a71b26a77e0301f69820a8de5f123491ac1e6f5`. Each selected raster was independently re-hashed against `provenance.jsonl` before its bytes were copied into this repository.\n\n"
artifact_block = (
    "For run `32431592545`, publication started from GitHub Actions artifact `9429338299`, whose ZIP SHA-256 is "
    "`683b0b091184311ddf466f0db5e308763fd76bebe59313de3699695fc3625c01`. All twelve source rasters were independently "
    "re-hashed against `provenance.jsonl`; eleven passed the visual/no-text publication gate and were copied into this repository byte-for-byte. "
    "The rejected `comfortable-way-wrong` raster was not published because it contained visible generated lettering and numbers.\n\n"
)
prov = insert_after_once(prov, artifact_anchor, artifact_block)
rights_anchor = "- Frontier-provider publication bases re-checked on **2026-08-20** include the OpenAI Services Agreement, Gemini API Additional Terms of Service, and Google Cloud Service Specific Terms; routed-provider terms remain the controlling boundary rather than OpenRouter's routing layer alone.\n"
rights_block = (
    "- Round `32431592545` additionally re-checked the Krea 2 Community License Agreement, Microsoft Product Terms for Microsoft Generative AI Services, and Black Forest Labs Developer Terms of Service.\n"
    "- Krea states that users own Outputs, but commercial use under its community license is subject to a company-wide trailing-twelve-month revenue threshold of less than $1,000,000; otherwise an enterprise license is required.\n"
    "- Microsoft states that generative Output Content is Customer Data and Microsoft does not own Customer's Output Content.\n"
    "- Black Forest Labs may embed Content Credentials or other provenance data in Output; exact-byte publication preserves rather than strips such metadata.\n"
)
prov = insert_after_once(prov, rights_anchor, rights_block)
receipts = []
for k in KEEPERS:
    receipts.append(
        f"### {k['id']}\n\n"
        f"- Philosophy line: **{k['line']}**\n"
        f"- Model: `{k['model']}`\n"
        f"- Routed provider: `{k['provider']}`\n"
        f"- Generation cost reported by OpenRouter: `${k['cost']}`\n"
        f"- Reference image supplied: **no**\n"
        f"- Original run: `PaulTiffany/letGPTsustakethewheel` Actions run `{RUN_ID}`\n"
        f"- Artifact: `chad-raster-art` (`{ARTIFACT_ID}`)\n"
        f"- Original run file: `{k['source']}`\n"
        f"- Original generation SHA-256: `{k['sha256']}`\n"
        f"- Published file: `{k['dest']}`\n"
        f"- Published SHA-256: `{k['sha256']}`\n"
        "- Publication transform: **none; exact-byte copy from the verified artifact**\n"
        f"- Rights/source review: {k['rights']}\n"
        f"- Publication note: {k['note']}\n\n")
prov = prov.replace("## Why “annoned by”?\n", "".join(receipts) + "## Why “annoned by”?\n", 1)
prov_path.write_text(prov)

for k in KEEPERS:
    src = EXTRACT / "images" / k["source"]
    dst = asset_dir / k["dest"]
    if src.read_bytes() != dst.read_bytes():
        raise SystemExit(f"exact-byte invariant failed: {k['dest']}")
print(f"published_keep_count={len(KEEPERS)} rejected_count=1 run={RUN_ID} artifact={ARTIFACT_ID}")
