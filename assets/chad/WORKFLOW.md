# SOP: Publishing AlphaClaw Philosophy Images via `letGPTsustakethewheel`

## Purpose

This document codifies the **working, demonstrated procedure** for generating illustrations through `PaulTiffany/letGPTsustakethewheel` and publishing selected images into:

- `PaulTiffany/AlphaClaw/assets/chad/`
- `PaulTiffany/AlphaClaw/assets/chad/PROVENANCE.md`
- `PaulTiffany/AlphaClaw/PHILOSOPHY.md`

This is a production procedure, not a boundary-exploration exercise.

The goal is:

> **Generate boundedly, select deliberately, preserve the original bytes, keep the receipts, and publish only the intended keepers.**

Boundary exploration, adversarial testing of the user or systems, recursive-agent experiments, speculative workflow redesign, and attempts to widen the authority of the process are out of scope.

---

# 1. Repository roles

## `letGPTsustakethewheel`

This is the **generation and experiment repository**.

It is responsible for:

- identifying candidate philosophy lines;
- discovering eligible image models;
- estimating cost;
- generating candidate images;
- recording the model and routed provider;
- recording the exact prompt;
- recording reported generation cost;
- hashing generated raster bytes;
- packaging images and receipts into a GitHub Actions artifact.

The canonical generation workflow is:

```text
.github/workflows/chad-raster.yml
```

The canonical generator is:

```text
chad_raster.py
```

The target-line manifest is:

```text
chad_lines.json
```

Generation output is written beneath:

```text
results/chad-raster/
```

with at least:

```text
results/chad-raster/
├── images/
├── provenance.jsonl
├── gallery.md
└── summary.json
```

## `AlphaClaw`

This is the **curated publication repository**.

It is responsible for:

- accepting only selected keeper images;
- preserving keeper raster bytes;
- maintaining publication receipts;
- placing each image beside the intended philosophy line;
- keeping generation provenance separate from the philosophy prose.

Published assets live at:

```text
assets/chad/
```

Publication receipts live at:

```text
assets/chad/PROVENANCE.md
```

The reader-facing document is:

```text
PHILOSOPHY.md
```

---

# 2. Start from the publication state

Before planning another generation round, inspect:

```text
AlphaClaw/assets/chad/PROVENANCE.md
AlphaClaw/PHILOSOPHY.md
```

`PROVENANCE.md` is the ledger of what has already been published.

Use it to determine:

- which philosophy lines already have illustrations;
- which model generated each published image;
- which routed provider was used;
- which generation runs have already contributed art;
- which models have already been published;
- which models were deliberately excluded from publication;
- any provider-specific publication conditions already established.

Then inspect `PHILOSOPHY.md` itself.

The target is **not simply “more images.”**

The target is:

> philosophy lines for which another illustration materially helps the document and which do not already have an adequate published illustration.

---

# 3. Define the next target set

Represent each desired generation target in:

```text
letGPTsustakethewheel/chad_lines.json
```

Each target has this basic form:

```json
{
  "id": "short-stable-slug",
  "section": "PHILOSOPHY.md section",
  "line": "Exact philosophy line.",
  "brief": "Concrete physical scene that visually expresses the line."
}
```

The `id` becomes the stable receipt anchor.

The `line` should correspond to real prose in `PHILOSOPHY.md`.

The `brief` should describe a **scene**, not simply rephrase the sentence.

Prefer:

- concrete physical action;
- one understandable visual metaphor;
- an image that can work without written labels;
- a composition whose meaning survives at README width.

Avoid making the generator depend on textual signage inside the image.

---

# 4. Update the model census from what has already happened

The generator maintains explicit knowledge of prior model use.

Conceptually, models fall into three sets:

```text
published
reroll-allowed
hard-blocked
```

The normal preference order is:

1. a suitable model not yet published;
2. a suitable fresh model from another author/provider family;
3. another unused suitable model;
4. an explicitly allowed reroll.

Previously published models are not silently treated as fresh candidates.

Known failed or intentionally excluded models stay excluded unless the publication procedure is deliberately revised in a separate action.

The objective is useful diversity, not novelty for its own sake.

---

# 5. Run the census first

Dispatch:

```text
Raster Chad
```

with:

```text
dry_run = true
```

Choose explicit values for:

```text
max_artists
max_spend_usd
max_per_image_usd
```

The census performs model discovery and prints the proposed assignment without generating anything.

Review the resulting plan.

For every proposed slot, check:

```text
target philosophy line
model
routed provider
selection kind
planned resolution
estimated one-image cost
estimated total cost
```

This is the point at which the generation round becomes concrete.

A satisfactory census should produce a legible mapping such as:

```text
target A -> model A -> provider A -> estimated cost
target B -> model B -> provider B -> estimated cost
...
```

Do not substitute a different model set between census and generation without treating that as a new plan.

---

# 6. Run the bounded generation

Dispatch the same workflow with:

```text
dry_run = false
```

using the selected bounds.

The workflow:

1. checks out `letGPTsustakethewheel`;
2. verifies that the inference credential exists;
3. compiles `chad_raster.py`;
4. invokes the bounded generator;
5. writes its output beneath `results/chad-raster`;
6. uploads that directory as:

```text
chad-raster-art
```

The generator pins the selected routed provider and disables provider fallbacks.

Each request asks for exactly one image.

The provider response is decoded from its raster payload into **binary bytes**.

Those bytes are written directly to disk.

For every successful image the generator records, among other fields:

```text
philosophy target
model
model author
routed provider
provider pricing information
estimated cost
actual reported cost
prompt
prompt SHA-256
media type
output filename
image byte count
image SHA-256
generation error, if any
```

`provenance.jsonl` is therefore part of the generated object, not an afterthought.

---

# 7. Preserve the generation artifact

The GitHub Actions artifact is the handoff object between generation and publication.

Record:

```text
generation repository
workflow run ID
artifact name
artifact ID
artifact ZIP SHA-256
```

The historical successful form is:

```text
Repository: PaulTiffany/letGPTsustakethewheel
Run: <RUN_ID>
Artifact: chad-raster-art
Artifact ID: <ARTIFACT_ID>
ZIP SHA-256: <ZIP_SHA256>
```

Do not treat individually downloaded preview images as the authoritative source when the verified generation artifact exists.

The artifact contains the relationship among:

```text
image bytes
provenance.jsonl
gallery
summary
```

That relationship is what is being published.

---

# 8. Select keepers

Inspect the generated images.

Keeper selection is a human publication decision.

For each candidate ask only the ordinary publication questions:

- Does it actually illustrate the intended philosophy line?
- Is the composition intelligible?
- Is the raster visually usable?
- Did the model accidentally generate visible words, labels, numbers, logos, or other unwanted text?
- Is this better than leaving the line unillustrated?

A failed candidate is simply not published.

Do not repair a rejected image by silently changing its bytes and then describing it as the original generation.

A new generation is a new generation.

The source artifact remains the receipt for the entire round, including rejected candidates.

---

# 9. Establish the publication manifest

For every selected keeper, establish one explicit publication record containing:

```text
id
philosophy line
model
routed provider
reported cost
source artifact filename
source SHA-256
destination filename
alt text
rights/source basis
publication note
```

Example shape:

```python
dict(
    id="test-not-assurance",
    line="A test is better than an assurance.",
    model="openai/gpt-5-image-mini",
    provider="openai",
    cost="0.013162",
    source="02-test-not-assurance--openai-gpt-5-image-mini.png",
    sha256="<SOURCE_SHA256>",
    dest="test-not-assurance.png",
    alt="A presenter gestures while a real component is quietly placed into a physical load-testing press",
    rights="<publication basis>",
    note="<publication note>",
)
```

This manifest defines what is allowed to cross from the generation artifact into AlphaClaw.

---

# 10. Treat a blob as a blob

This is the central binary-handling rule.

> **An image is binary data. Preserve it as binary data.**

The successful publication procedure does not reconstruct a PNG, JPEG, or WebP through Markdown, JSON text handling, lossy re-encoding, screenshots, or image conversion.

The established path is:

```text
provider raster payload
        ↓
decode once to raw bytes
        ↓
write source raster
        ↓
SHA-256 source raster
        ↓
GitHub Actions artifact ZIP
        ↓
verify ZIP SHA-256
        ↓
extract source raster
        ↓
verify raster SHA-256 against provenance.jsonl
        ↓
copy source bytes directly
        ↓
assets/chad/<published filename>
        ↓
SHA-256 destination raster
        ↓
assert destination bytes == source bytes
        ↓
Git blob
```

For exact-byte publication:

```python
shutil.copyfile(src, dst)
```

Then:

```python
assert sha256(dst) == expected_sha256
assert src.read_bytes() == dst.read_bytes()
```

The Git blob identity can additionally be computed from the bytes:

```python
data = path.read_bytes()

git_blob_sha = sha1(
    f"blob {len(data)}\0".encode() + data
).hexdigest()
```

This is useful as a second identifier of the object Git is actually storing.

### Important consequence

For an exact-byte publication:

```text
original generation SHA-256
    ==
artifact raster SHA-256
    ==
published raster SHA-256
```

There is no publication transform.

Record exactly:

```text
Publication transform: none; exact-byte copy from the verified artifact
```

If a deliberate resize or re-encode is performed, that is a different publication mode and both source and published hashes must be retained.

For the current working process, prefer the exact-byte form.

---

# 11. Verify the artifact before copying anything

Before publication:

```text
SHA256(downloaded artifact ZIP) == recorded artifact ZIP SHA256
```

After extraction, parse:

```text
provenance.jsonl
```

For every keeper, locate the row whose:

```text
image_file == selected source filename
```

Require:

```text
row exists
row.error is empty
row.model == expected model
row.provider_tag == expected routed provider
row.image_sha256 == expected SHA-256
SHA256(extracted raster) == expected SHA-256
```

Only after those checks pass is the file copied into `assets/chad/`.

Then require:

```text
SHA256(published raster) == expected SHA-256
source bytes == published bytes
```

The raster therefore has two independent relationships checked:

```text
receipt → source bytes
source bytes → published bytes
```

---

# 12. Update `PHILOSOPHY.md`

Insert each selected image beside the exact philosophy line it illustrates.

The established image block is:

```html
<p align="center">
  <img src="assets/chad/<FILE>" alt="<ALT TEXT>" width="620">
</p>

<p align="center"><em>annoned by <code><MODEL></code> · <a href="assets/chad/PROVENANCE.md#<ID>">receipt</a></em></p>
```

The model attribution stays immediately with the image.

The receipt links to the stable `PROVENANCE.md` anchor.

When inserting programmatically, use an **exact unique textual anchor**.

Before insertion:

```text
anchor count == 1
```

If the intended anchor is absent or appears more than once, stop the textual edit rather than guessing where the illustration belongs.

The philosophy prose itself does not need to be rewritten merely to accommodate an image.

---

# 13. Update `assets/chad/PROVENANCE.md`

For the generation round, record:

```text
source generation run
artifact name
artifact ID
artifact ZIP SHA-256
keeper count
rejected count where useful
publication mode
```

For each keeper, record:

```markdown
### <id>

- Philosophy line: **<line>**
- Model: `<model>`
- Routed provider: `<provider>`
- Generation cost reported by OpenRouter: `$<cost>`
- Reference image supplied: **no**
- Original run: `PaulTiffany/letGPTsustakethewheel` Actions run `<run>`
- Artifact: `chad-raster-art` (`<artifact id>`)
- Original run file: `<source filename>`
- Original generation SHA-256: `<sha256>`
- Published file: `<destination filename>`
- Published SHA-256: `<sha256>`
- Publication transform: **none; exact-byte copy from the verified artifact**
- Rights/source review: <source>
- Publication note: <note>
```

The provenance file is the publication ledger.

`PHILOSOPHY.md` should remain readable without reproducing all of this machinery.

---

# 14. Publication workflow

The successful publication form used a **temporary owner-dispatched workflow in AlphaClaw**.

Its job was narrowly defined:

```text
workflow_dispatch
contents: write
owner only
```

The workflow:

1. checked out `AlphaClaw/main` with full history;
2. downloaded the already-selected source artifact ZIP;
3. printed and verified the artifact ZIP SHA-256;
4. ran a purpose-built publication script;
5. removed temporary extracted files;
6. removed the temporary publication machinery;
7. staged the exact intended publication delta;
8. printed the staged delta;
9. committed;
10. pushed to `main`.

The important point is not the temporary filename.

The important point is the topology:

```text
generation is completed first
        ↓
artifact is fixed
        ↓
keepers are fixed
        ↓
publication receives a fixed artifact
        ↓
publisher verifies and copies
        ↓
one explicit AlphaClaw commit
```

Generation and publication are separate phases.

---

# 15. Stage only the intended publication delta

Before committing, explicitly stage:

```text
PHILOSOPHY.md
assets/chad/PROVENANCE.md
assets/chad/<keeper 1>
assets/chad/<keeper 2>
...
```

If a temporary publication script/workflow was introduced solely for the handoff, remove it before the final publication state unless there is an affirmative reason for it to remain.

Print:

```bash
git diff --cached --name-status
```

The staged delta should be explainable file by file.

A normal final commit should read conceptually like:

```text
Publish N Chad keepers
```

rather than bundling unrelated repository changes into the art publication.

---

# 16. Verify the committed result

After publication, check the repository state rather than merely trusting the workflow exit code.

For every published keeper confirm:

```text
assets/chad/<file> exists
PHILOSOPHY.md references that exact path
PHILOSOPHY.md names the correct model
PHILOSOPHY.md links to the correct receipt anchor
PROVENANCE.md contains that anchor
PROVENANCE.md names the correct source run
PROVENANCE.md names the correct artifact
PROVENANCE.md records source and published SHA-256
source SHA-256 == published SHA-256 for exact-byte copies
```

Also inspect the rendered `PHILOSOPHY.md`.

A technically valid image reference that appears in the wrong rhetorical location is not a completed publication.

---

# 17. Round completion condition

A picture is considered successfully added only when all four objects agree:

```text
generation receipt
        ↕
published raster
        ↕
PROVENANCE.md receipt
        ↕
PHILOSOPHY.md placement
```

More formally:

```text
generated bytes == published bytes
```

and:

```text
generation identity
== provenance identity
== attribution identity
```

and:

```text
philosophy target
== publication placement
```

The Actions run alone is not completion.

The image file alone is not completion.

The Markdown edit alone is not completion.

**The unit of publication is the image plus its receipt plus its placement.**

---

# 18. Minimal repeatable cycle

The full procedure can therefore be compressed to:

```text
1. Read AlphaClaw PHILOSOPHY.md and PROVENANCE.md.
2. Identify worthwhile unillustrated philosophy lines.
3. Encode those targets in chad_lines.json.
4. Update published/excluded/reroll model knowledge.
5. Run Raster Chad in dry-run mode.
6. Review model assignment and bounded spend.
7. Run the same bounded generation for real.
8. Preserve the chad-raster-art artifact.
9. Record run ID, artifact ID, and ZIP SHA-256.
10. Visually select keepers.
11. Establish the keeper publication manifest.
12. Verify publication basis for each routed provider.
13. Download the fixed artifact into the AlphaClaw publication step.
14. Verify artifact ZIP SHA-256.
15. Parse provenance.jsonl.
16. Verify each keeper's model, provider, filename, and source SHA-256.
17. Copy keeper raster bytes exactly into assets/chad/.
18. Re-hash every destination.
19. Assert source bytes == destination bytes.
20. Insert each image beside one exact unique PHILOSOPHY.md anchor.
21. Add the matching PROVENANCE.md receipt.
22. Stage only the intended publication delta.
23. Inspect the staged file list.
24. Commit and push the publication.
25. Verify the repository and rendered Markdown.
```

---

# 19. Historical mechanical exemplar

The full-population round demonstrates the complete procedure.

Generation:

```text
PaulTiffany/letGPTsustakethewheel
Actions run: 32431592545
Artifact: chad-raster-art
Artifact ID: 9429338299
Artifact ZIP SHA-256:
683b0b091184311ddf466f0db5e308763fd76bebe59313de3699695fc3625c01
```

The artifact contained twelve generated rasters.

Eleven were selected for publication.

One was rejected because it contained visible generated lettering/numbers.

The selected images were independently re-hashed against `provenance.jsonl`, copied byte-for-byte into `AlphaClaw/assets/chad/`, re-hashed after publication, attached to exact philosophy anchors, and entered into `PROVENANCE.md`.

The resulting publication commit was:

```text
d9f98d7168fd8fad453d652ceb73f261eee507a0
Publish eleven Chad round 15 keepers
```

That round is the mechanical reference implementation for this SOP.

---

# 20. Governing rule

When repeating this workflow, optimize for boring reproducibility.

Do not ask:

> What elaborate new machinery could we build for this?

Ask:

> What did the functioning pipeline do last time, and what are the new target lines?

The established pipeline is:

```text
bounded generation
→ artifact
→ receipts
→ human keeper selection
→ byte verification
→ exact-byte publication
→ provenance
→ philosophy placement
→ commit verification
```

**Keep the images binary, keep the receipts textual, and keep the two connected by hashes.**
