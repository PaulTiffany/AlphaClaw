#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path

RUN_ID = "32424076108"
ARTIFACT_ID = "9426834676"
ZIP_SHA256 = "a0210aee107921ed678b473f7a71b26a77e0301f69820a8de5f123491ac1e6f5"
ZIP_PATH = Path("chad-raster-art.zip")
EXTRACT = Path(".chad-artifact")

KEEPERS = [
    {"id":"stop-path","source":"02-stop-path--openai-gpt-image-1-mini.png","published":"stop-path.png","sha256":"274d207fbac8fd3566723ac9e8ac5b30ca99e98e0039be22862e3689696f9aa0","model":"openai/gpt-image-1-mini","provider":"openai","cost":"0.01307","line":"The control loop must remain outside and operationally independent of the system it controls.","rights":"OpenAI Services Agreement — https://openai.com/policies/services-agreement/","note":"OpenAI states that, as between Customer and OpenAI and to the extent permitted by law, Customer owns Output and OpenAI assigns any right, title, and interest it may have in Output."},
    {"id":"telemetry-not-control","source":"03-telemetry-not-control--google-gemini-3-1-flash-lite-image.jpg","published":"telemetry-not-control.jpg","sha256":"5562a6b96ed0a32c8cc4086bc3a5d2dcacef953f045c1f70677a7a3c7927b286","model":"google/gemini-3.1-flash-lite-image","provider":"google-ai-studio","cost":"0.03436425","line":"More telemetry is not necessarily more control.","rights":"Gemini API Additional Terms of Service — https://ai.google.dev/gemini-api/terms","note":"Google states that some Gemini API and Google AI Studio services generate original content and that Google will not claim ownership over that generated content; output may not be unique."},
    {"id":"recursive-authority","source":"04-recursive-authority--google-gemini-3-1-flash-image.png","published":"recursive-authority.png","sha256":"e7dc3b0444d57f270acb788c261fe55faadc1c0ea6619a4b35d76e2e8e24e070","model":"google/gemini-3.1-flash-image","provider":"google-vertex/global","cost":"0.06729","line":"Recursive capability is not recursive authority.","rights":"Google Cloud Service Specific Terms — https://cloud.google.com/terms/service-terms","note":"Google Cloud states that Generated Output is Customer Data and that, as between Customer and Google, Google does not assert ownership rights in new intellectual property created in Generated Output."},
    {"id":"no-defensive-branch","source":"05-no-defensive-branch--openai-gpt-image-2.png","published":"no-defensive-branch.png","sha256":"b72274c486592f412a03c94d9344a3107f2fc6ac8af1e866cb1b162a692febb9","model":"openai/gpt-image-2","provider":"openai","cost":"0.04983","line":"There is no special step called: Become defensive.","rights":"OpenAI Services Agreement — https://openai.com/policies/services-agreement/","note":"OpenAI states that, as between Customer and OpenAI and to the extent permitted by law, Customer owns Output and OpenAI assigns any right, title, and interest it may have in Output."},
    {"id":"source-truth","source":"08-source-truth--bytedance-seed-seedream-5-0-lite.jpg","published":"source-truth.jpg","sha256":"f94497687cad14c3f85d3bbd94de59824b60121a1dae2904e0ea1bedd32cf031","model":"bytedance-seed/seedream-5-0-lite","provider":"seed","cost":"0.035","line":"The source and the truth are still different questions.","rights":"BytePlus Model Services terms — https://docs.byteplus.com/vi/docs/legal/docs-service-specific-terms","note":"BytePlus states that, to the extent permitted by law, output IP rights belong to the customer or other applicable rights holder and BytePlus does not claim ownership."},
    {"id":"operator-latency","source":"09-operator-latency--recraft-recraft-v4-1.webp","published":"operator-latency.webp","sha256":"2ce2916e07976acf5b48ab284aa2f18d8af49d022244737caf1b0c5c4a289f56","model":"recraft/recraft-v4.1","provider":"recraft","cost":"0.035","line":"Operator latency is part of the system.","rights":"Recraft API Terms — https://www.recraft.ai/legal/terms","note":"Recraft states that API users own assets created with the API and assigns any copyright it may have, subject to its restriction against using those assets to train AI models, systems, or networks."},
    {"id":"handholds","source":"11-handholds--recraft-recraft-v3.webp","published":"handholds.webp","sha256":"0a5c51f8377a26d9c46d64db95a12b8aedf643eb0b99096ebaab214c2fba0a5a","model":"recraft/recraft-v3","provider":"recraft","cost":"0.04","line":"A good team leaves handholds for other people.","rights":"Recraft API Terms — https://www.recraft.ai/legal/terms","note":"Recraft states that API users own assets created with the API and assigns any copyright it may have, subject to its restriction against using those assets to train AI models, systems, or networks."},
]

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

assert ZIP_PATH.is_file(), ZIP_PATH
assert sha256(ZIP_PATH) == ZIP_SHA256, "artifact ZIP SHA-256 mismatch"
if EXTRACT.exists(): shutil.rmtree(EXTRACT)
EXTRACT.mkdir()
with zipfile.ZipFile(ZIP_PATH) as zf: zf.extractall(EXTRACT)

rows = {}
for raw in (EXTRACT / "provenance.jsonl").read_text(encoding="utf-8").splitlines():
    row = json.loads(raw)
    rows[row["philosophy"]["id"]] = row

for k in KEEPERS:
    row = rows[k["id"]]
    assert row["error"] is None
    assert row["image_file"] == k["source"]
    assert row["image_sha256"] == k["sha256"]
    source = EXTRACT / "images" / k["source"]
    assert sha256(source) == k["sha256"]
    target = Path("assets/chad") / k["published"]
    assert not target.exists(), f"refusing overwrite: {target}"
    shutil.copyfile(source, target)
    assert sha256(target) == k["sha256"]

philosophy = Path("PHILOSOPHY.md")
text = philosophy.read_text(encoding="utf-8")
blocks = {
"handholds": '''\n<p align="center">\n  <img src="assets/chad/handholds.webp" alt="A scaffold with rails ladders and teammates showing work designed so others can follow safely" width="620">\n</p>\n\n<p align="center"><em>annoned by <code>recraft/recraft-v3</code> · <a href="assets/chad/PROVENANCE.md#handholds">receipt</a></em></p>\n''',
"stop-path": '''\n<p align="center">\n  <img src="assets/chad/stop-path.png" alt="Chad beside a simple independent analog control while the machine it governs overloads separately" width="620">\n</p>\n\n<p align="center"><em>annoned by <code>openai/gpt-image-1-mini</code> · <a href="assets/chad/PROVENANCE.md#stop-path">receipt</a></em></p>\n''',
"operator-latency": '''\n<p align="center">\n  <img src="assets/chad/operator-latency.webp" alt="Chad operating a direct control as a fast-moving hazard closes the available response window" width="620">\n</p>\n\n<p align="center"><em>annoned by <code>recraft/recraft-v4.1</code> · <a href="assets/chad/PROVENANCE.md#operator-latency">receipt</a></em></p>\n''',
"telemetry-not-control": '''\n<p align="center">\n  <img src="assets/chad/telemetry-not-control.jpg" alt="Chad using one simple gauge while a wall of noisy telemetry crowds the background" width="620">\n</p>\n\n<p align="center"><em>annoned by <code>google/gemini-3.1-flash-lite-image</code> · <a href="assets/chad/PROVENANCE.md#telemetry-not-control">receipt</a></em></p>\n''',
"recursive-authority": '''\n<p align="center">\n  <img src="assets/chad/recursive-authority.png" alt="A self-expanding machine remains behind a fixed external permission barrier controlled from outside" width="620">\n</p>\n\n<p align="center"><em>annoned by <code>google/gemini-3.1-flash-image</code> · <a href="assets/chad/PROVENANCE.md#recursive-authority">receipt</a></em></p>\n''',
"source-truth": '''\n<p align="center">\n  <img src="assets/chad/source-truth.jpg" alt="Chad testing similar mechanisms from ornate and plain containers on the same neutral fixture" width="620">\n</p>\n\n<p align="center"><em>annoned by <code>bytedance-seed/seedream-5-0-lite</code> · <a href="assets/chad/PROVENANCE.md#source-truth">receipt</a></em></p>\n''',
"no-defensive-branch": '''\n<p align="center">\n  <img src="assets/chad/no-defensive-branch.png" alt="Chad calmly replacing a cracked machine part after another person points out the failure" width="620">\n</p>\n\n<p align="center"><em>annoned by <code>openai/gpt-image-2</code> · <a href="assets/chad/PROVENANCE.md#no-defensive-branch">receipt</a></em></p>\n''',
}
anchors = [
("A good team leaves handholds for other people.\n", "handholds"),
("**The control loop must remain outside and operationally independent of the system it controls.**\n", "stop-path"),
("Operator latency is part of the system.\n", "operator-latency"),
("More telemetry is not necessarily more control if it arrives too quickly, too noisily, or through an interface too degraded to understand.\n", "telemetry-not-control"),
("\\[\n\\text{recursive capability} \\not\\Rightarrow \\text{recursive authority}\n\\]\n", "recursive-authority"),
("But the source and the truth are still different questions.\n", "source-truth"),
("> **Become defensive.**\n", "no-defensive-branch"),
]
for anchor, ident in anchors:
    assert text.count(anchor) == 1, (ident, text.count(anchor))
    text = text.replace(anchor, anchor + blocks[ident], 1)
philosophy.write_text(text, encoding="utf-8")

prov_path = Path("assets/chad/PROVENANCE.md")
prov = prov_path.read_text(encoding="utf-8")
old_intro = "These images are original raster generations selected from **Raster Chad** run #3 in `PaulTiffany/letGPTsustakethewheel` (GitHub Actions run `32037144396`) and the accepted-keeper run `32388944793`. Additional accepted selections come from run `32399313906`."
new_intro = "These images are original raster generations selected from **Raster Chad** run #3 in `PaulTiffany/letGPTsustakethewheel` (GitHub Actions run `32037144396`), accepted-keeper run `32388944793`, run `32399313906`, and frontier-model run `32424076108`."
assert prov.count(old_intro) == 1
prov = prov.replace(old_intro, new_intro, 1)
old_exact = "The earlier published JPEGs are web-optimized derivatives of the original generated raster files: resize/re-encode only, with no generative edit. Accepted keepers from runs `32388944793` and `32399313906` are published as exact-byte copies of the original artifact files. Original-generation and published-file SHA-256 values are recorded below."
new_exact = "The earlier published JPEGs are web-optimized derivatives of the original generated raster files: resize/re-encode only, with no generative edit. Accepted keepers from runs `32388944793`, `32399313906`, and `32424076108` are published as exact-byte copies of the original artifact files. Original-generation and published-file SHA-256 values are recorded below.\n\nFor run `32424076108`, publication started from GitHub Actions artifact `9426834676`, whose ZIP SHA-256 is `a0210aee107921ed678b473f7a71b26a77e0301f69820a8de5f123491ac1e6f5`. Each selected raster was independently re-hashed against `provenance.jsonl` before its bytes were copied into this repository."
assert prov.count(old_exact) == 1
prov = prov.replace(old_exact, new_exact, 1)
rights_anchor = "- Provider/model terms were reviewed on **2026-08-17** for the first publication and re-checked on **2026-08-20** for the accepted keepers.\n"
rights_extra = "- Frontier-provider publication bases re-checked on **2026-08-20** include the OpenAI Services Agreement, Gemini API Additional Terms of Service, and Google Cloud Service Specific Terms; routed-provider terms remain the controlling boundary rather than OpenRouter's routing layer alone.\n"
assert prov.count(rights_anchor) == 1
prov = prov.replace(rights_anchor, rights_anchor + rights_extra, 1)
receipts=[]
for k in KEEPERS:
    receipts.append(f'''### {k["id"]}\n\n- Philosophy line: **{k["line"]}**\n- Model: `{k["model"]}`\n- Routed provider: `{k["provider"]}`\n- Generation cost reported by OpenRouter: `${k["cost"]}`\n- Reference image supplied: **no**\n- Original run: `PaulTiffany/letGPTsustakethewheel` Actions run `{RUN_ID}`\n- Artifact: `chad-raster-art` (`{ARTIFACT_ID}`)\n- Original run file: `{k["source"]}`\n- Original generation SHA-256: `{k["sha256"]}`\n- Published file: `{k["published"]}`\n- Published SHA-256: `{k["sha256"]}`\n- Publication transform: **none; exact-byte copy from the verified artifact**\n- Rights/source review: {k["rights"]}\n- Publication note: {k["note"]}\n''')
receipt_text="\n".join(receipts).rstrip()
marker="\n## Why “annoned by”?"
assert prov.count(marker)==1
prov=prov.replace(marker,"\n"+receipt_text+"\n\n## Why “annoned by”?",1)
prov_path.write_text(prov,encoding="utf-8")

for k in KEEPERS:
    target=Path("assets/chad")/k["published"]
    assert sha256(target)==k["sha256"]
    assert f'assets/chad/{k["published"]}' in philosophy.read_text(encoding="utf-8")
    assert f"### {k['id']}" in prov_path.read_text(encoding="utf-8")
