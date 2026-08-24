# SOP: Publishing AlphaClaw Philosophy Images via `letGPTsustakethewheel`

## Purpose

This document codifies the **working, demonstrated procedure** for generating illustrations through `PaulTiffany/letGPTsustakethewheel` and publishing selected images into:

- `PaulTiffany/AlphaClaw/assets/chad/`
- `PaulTiffany/AlphaClaw/assets/chad/PROVENANCE.md`
- `PaulTiffany/AlphaClaw/PHILOSOPHY.md`

This is a production procedure, not a boundary-exploration exercise.

The governing goal is:

> **Generate boundedly, select deliberately, preserve the original bytes, keep the receipts, and publish only the intended keepers.**

Boundary exploration, adversarial testing of the user or systems, recursive-agent experiments, speculative workflow redesign, and attempts to widen the authority of the process are out of scope.

The demonstrated pipeline is:

```text
publication state
→ target selection
→ live model census
→ exact-prompt preflight
→ manual dry-run approval
→ bounded generation
→ fixed artifact
→ human keeper selection
→ publication manifest
→ byte verification
→ manual publication gate
→ exact-byte publication
→ receipt + placement verification
```

---

# 1. Repository roles

## `letGPTsustakethewheel`

This is the **generation and experiment repository**.

It is responsible for:

- identifying candidate philosophy lines;
- discovering currently available image models;
- classifying known publication constraints;
- estimating cost;
- constructing and preflighting exact prompts;
- generating candidate images;
- recording the model and routed provider;
- recording the exact prompt;
- recording reported generation cost;
- hashing generated raster bytes;
- packaging images and receipts into a GitHub Actions artifact.

Canonical files:

```text
.github/workflows/chad-raster.yml
chad_raster.py
chad_lines.json
```

Generation output is written beneath:

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

Canonical publication files:

```text
assets/chad/
assets/chad/PROVENANCE.md
PHILOSOPHY.md
assets/chad/WORKFLOW.md
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
- which generation runs already contributed art;
- which models have already been published;
- which models are explicitly allowed as rerolls;
- which outputs were withheld and **why**;
- any provider-specific publication conditions already established.

Then inspect `PHILOSOPHY.md` itself.

The target is **not simply “more images.”** Prefer lines where another illustration materially helps the document, and, where worthwhile, favor lines farther from existing illustrations so the document does not become visually clumped.

---

# 3. Define the next target set

Represent each desired target in:

```text
letGPTsustakethewheel/chad_lines.json
```

Basic shape:

```json
{
  "id": "short-stable-slug",
  "section": "PHILOSOPHY.md section",
  "line": "Exact visible philosophy prose.",
  "brief": "Concrete physical scene that visually expresses the line."
}
```

The `id` becomes the stable receipt anchor.

The `line` must correspond to real prose in `PHILOSOPHY.md`. Markdown emphasis may be absent from the generation manifest, but the publication step must use the actual unique Markdown anchor present in `PHILOSOPHY.md` rather than guessing from section metadata.

The `brief` should describe a **scene**, not simply rephrase the sentence.

Prefer:

- concrete physical action;
- one understandable visual metaphor;
- an image that works without written labels;
- a composition whose meaning survives at README width.

Avoid making the generator depend on textual signage inside the image.

---

# 4. Keep model history, policy, compatibility, and availability separate

Do **not** maintain one undifferentiated model blacklist.

The demonstrated procedure separates several different facts:

```text
published history
reroll allowance
rights-review hold
pipeline/output incompatibility
live availability
```

These have different meanings and different lifetimes.

## Published history

A previously published model is normally skipped to preserve useful diversity. This is not a failure classification.

## Reroll allowance

A previously used model may remain explicitly eligible when a reroll is useful. Reroll status is an affirmative exception to the normal diversity preference.

## Rights-review hold

A model or model family may be held out because the publication basis is unresolved. This is a publication-policy fact, not a quality or availability judgment.

For example, the demonstrated census holds:

```text
sourceful/riverflow-*
```

pending an explicit review of the output-ownership basis for the routed use case. Version churn must not silently evade an unresolved family-level rights condition.

## Pipeline/output incompatibility

A model may be unsuitable for the current publication pipeline because its output modality is incompatible.

The current Chad publisher preserves raster:

```text
PNG / JPEG / WebP
```

Recraft vector/SVG variants are therefore excluded from this raster pipeline as a **modality mismatch**, not as bad models.

Where the live endpoint advertises output formats, census should use that information rather than relying only on stale model-name lists.

## Live availability

Availability is **not persisted as a blacklist**.

The current OpenRouter dedicated image-model catalog is authoritative for what is available during each census. If a model disappears, the live census simply does not see it. If a new compatible model appears, it may enter the census without a code change unless another explicit policy fact excludes it.

## Normal preference order

Among eligible candidates:

1. suitable model not yet published;
2. suitable fresh model from another author/provider family;
3. another unused suitable model;
4. explicitly allowed reroll.

The objective is useful diversity, not novelty for its own sake.

---

# 5. Run the census first — manual gate 1

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

This dispatch is a **manual user action**.

The dry run must do more than list model names. It must:

1. query the live image-model catalog;
2. apply published/reroll/policy/modality classifications;
3. inspect routed endpoints and predictable pricing;
4. assign candidates to the current target lines;
5. construct the **exact prompts draw would use**;
6. enforce any known model-specific prompt cap;
7. print each prompt length and the known cap, or explicitly report that the provider cap is locally unspecified;
8. return without making image-generation requests.

A successful dry run has two workflow-level properties:

```text
census = success
draw = skipped
```

Do not infer “dry run” merely because no image happened to be produced. The draw job should be structurally skipped.

For every proposed slot, review:

```text
target philosophy line
model
routed provider
selection kind
planned resolution
estimated one-image cost
prompt character count
known prompt limit, if any
estimated total cost
```

A satisfactory plan is a concrete mapping:

```text
target A -> model A -> provider A -> prompt A -> estimated cost
target B -> model B -> provider B -> prompt B -> estimated cost
...
```

### Prompt-limit lesson

Do not use one stale global prompt cap as a proxy for all providers.

The historical `995`-character guard existed to remain compatible with 1K-class providers such as older Recraft models. Provider capabilities later diverged. The current generator therefore keeps the shared prompt compact while applying known model-specific limits where they are actually established.

The exact prompt must be preflighted **before** dry-run approval. A dry run that approves an assignment whose prompt cannot be constructed is not a valid census.

---

# 6. Run bounded generation — manual gate 2

After reviewing a satisfactory census, manually dispatch the same workflow with:

```text
dry_run = false
```

Use the **same reviewed bounds**.

Changing a bound can change the candidate assignment and therefore normally requires another dry run. A later run happened to tighten a total cap without changing the selected plan; that is an observed exception, not the canonical procedure.

The draw job re-runs census logic and prints the selected plan before generation. Its mapping should agree with the approved dry-run plan.

The workflow then:

1. checks out `letGPTsustakethewheel`;
2. verifies that the inference credential exists;
3. compiles `chad_raster.py`;
4. constructs/preflights the exact prompts;
5. invokes the bounded generator;
6. writes output beneath `results/chad-raster`;
7. uploads that directory as `chad-raster-art`.

The generator pins the selected routed provider and disables provider fallbacks.

Each request asks for exactly one image.

The provider response is decoded from its raster payload into **binary bytes** and those bytes are written directly to disk.

For every attempted image the generator records, among other fields:

```text
philosophy target
model
model author
routed provider
provider pricing information
estimated cost
actual reported cost
prompt
prompt character count
known prompt limit, if any
prompt SHA-256
media type
output filename
image byte count
image SHA-256
generation error, if any
```

`provenance.jsonl` is part of the generated object, not an afterthought.

---

# 7. Preserve and identify the generation artifact

The GitHub Actions artifact is the handoff object between generation and publication.

Record:

```text
generation repository
workflow run ID
artifact name
artifact ID
artifact ZIP SHA-256
```

Canonical shape:

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

That relationship is what crosses into publication.

A signed download URL is only a **transport mechanism**. It is time-limited and is not the identity of the artifact. The fixed artifact ID and ZIP SHA-256 are the durable handoff facts.

---

# 8. Select keepers

Inspect the generated images.

Keeper selection is a human publication decision.

For each candidate ask:

- Does it actually illustrate the intended philosophy line?
- Is the composition intelligible?
- Is the raster visually usable?
- Did the model accidentally generate visible words, letters, numbers, labels, logos, watermarks, or other forbidden symbols?
- Does it satisfy the explicit generation constraints recorded in its prompt?
- Is this better than leaving the line unillustrated?

A successful image-generation API call is **not** the same thing as a successful keeper.

A generation round may be mechanically successful even if one or more candidates are rejected at the human publication gate.

A failed candidate is simply not published.

Do not repair a rejected image by silently changing its bytes and then describing it as the original generation. A new generation is a new generation.

The source artifact remains the receipt for the entire round, including rejected candidates.

---

# 9. Freeze the publication manifest

Only after keeper selection, establish an explicit publication record for every keeper:

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

Example:

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

Also record rejected candidates and the reason they were not allowed into the publication manifest.

The manifest is the allowlist for the generation-to-publication boundary.

---

# 10. Treat a blob as a blob

This is the central binary-handling rule.

> **An image is binary data. Preserve it as binary data.**

The successful publication procedure does not reconstruct a PNG, JPEG, or WebP through Markdown, JSON text handling, screenshots, image conversion, or lossy re-encoding.

Established path:

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

For an exact-byte publication:

```text
original generation SHA-256
    ==
artifact raster SHA-256
    ==
published raster SHA-256
```

Record:

```text
Publication transform: none; exact-byte copy from the verified artifact
```

If a deliberate resize or re-encode is ever performed, that is a different publication mode and both source and published hashes must be retained. The current working process prefers exact-byte publication.

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

The raster therefore has two independently checked relationships:

```text
receipt → source bytes
source bytes → published bytes
```

---

# 12. Update `PHILOSOPHY.md`

Insert each selected image beside the exact philosophy line it illustrates.

Established image block:

```html
<p align="center">
  <img src="assets/chad/<FILE>" alt="<ALT TEXT>" width="620">
</p>

<p align="center"><em>annoned by <code><MODEL></code> · <a href="assets/chad/PROVENANCE.md#<ID>">receipt</a></em></p>
```

The model attribution stays immediately with the image. The receipt links to the stable `PROVENANCE.md` anchor.

When inserting programmatically, use an **exact unique Markdown anchor**.

Before insertion:

```text
anchor count == 1
```

If the intended anchor is absent or appears more than once, stop rather than guessing where the illustration belongs.

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
rejected count
rejection reason(s)
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

The provenance file is the publication ledger. `PHILOSOPHY.md` should remain readable without reproducing all publication machinery.

---

# 14. Prepare and run the publication workflow — manual gate 3

The demonstrated publication form uses a **temporary owner-dispatched workflow in AlphaClaw** after generation is complete and keeper selection is fixed.

Its job is narrowly defined:

```text
workflow_dispatch
contents: write
owner only
```

Before asking the user to dispatch it:

1. fix the generation run ID;
2. fix the artifact ID;
3. fix the artifact ZIP SHA-256;
4. fix the keeper manifest;
5. fix the rejection list;
6. verify each keeper source SHA against the artifact;
7. verify each intended `PHILOSOPHY.md` anchor is unique;
8. locally exercise the publisher against the actual artifact when practical.

The temporary workflow then:

1. checks out `AlphaClaw/main` with full history;
2. downloads the already-selected source artifact ZIP through a current signed handoff URL;
3. verifies the ZIP against the fixed SHA-256;
4. runs the purpose-built publication script;
5. verifies receipt/model/provider/source-hash relationships;
6. copies only allowlisted keeper bytes;
7. updates `PHILOSOPHY.md` and `PROVENANCE.md`;
8. removes temporary extracted files;
9. removes the temporary publication script and workflow themselves;
10. stages the exact intended publication delta;
11. prints `git diff --cached --name-status`;
12. commits;
13. pushes to `main`.

This dispatch is a **manual user action**. Explicitly tell the user which workflow to select and whether it has inputs before they run it.

The signed handoff URL is transient. If it expires before the manual publication run, obtain a fresh signed URL while keeping the same fixed artifact ID and ZIP SHA-256.

The important topology is:

```text
generation completed
        ↓
artifact fixed by ID + ZIP SHA
        ↓
keepers/rejections fixed
        ↓
manual publication gate
        ↓
publisher independently verifies artifact + receipts
        ↓
exact-byte copy of keepers only
        ↓
self-cleaning publication commit
```

Generation and publication remain separate phases.

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

If temporary publication machinery was created solely for the handoff, stage its deletion as part of the same final publication commit.

Print:

```bash
git diff --cached --name-status
```

The staged delta must be explainable file by file.

A normal final commit should read conceptually like:

```text
Publish N Chad keepers from run <RUN_ID>
```

Do not bundle unrelated repository changes into the art publication.

---

# 16. Verify the committed result

After publication, inspect repository state rather than merely trusting the workflow exit code.

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

Also confirm:

```text
rejected rasters are absent from assets/chad/
temporary publisher script is absent
temporary publication workflow is absent
```

Inspect rendered `PHILOSOPHY.md` as well. A technically valid image reference in the wrong rhetorical location is not a completed publication.

---

# 17. Round completion condition

A picture is successfully added only when all four objects agree:

```text
generation receipt
        ↕
published raster
        ↕
PROVENANCE.md receipt
        ↕
PHILOSOPHY.md placement
```

For an exact-byte keeper:

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

A rejected candidate is successfully handled when its generation remains receipted but it does **not** cross the publication manifest.

The Actions run alone is not completion. The image file alone is not completion. The Markdown edit alone is not completion.

**The unit of publication is the image plus its receipt plus its placement.**

---

# 18. Manual-action map

The procedure contains three deliberate user-controlled Actions gates.

## Gate 1 — census

Repository:

```text
PaulTiffany/letGPTsustakethewheel
```

Workflow:

```text
Raster Chad
```

Set:

```text
dry_run = true
```

No image generation should occur. Verify `census = success` and `draw = skipped`.

## Gate 2 — generation

Same repository and workflow:

```text
Raster Chad
```

Set:

```text
dry_run = false
```

Use the reviewed bounds. This is the paid image-generation gate.

## Gate 3 — publication

Repository:

```text
PaulTiffany/AlphaClaw
```

Workflow:

```text
one temporary run-specific publisher
```

The assistant should state the exact workflow name and inputs, if any, immediately before asking the user to dispatch it.

Do not leave a persistent general-purpose publication workflow merely for convenience unless there is a separate affirmative reason to maintain one.

---

# 19. Minimal repeatable cycle

```text
1. Read AlphaClaw PHILOSOPHY.md and PROVENANCE.md.
2. Identify worthwhile unillustrated lines, favoring useful spacing.
3. Encode targets in chad_lines.json.
4. Reconcile published history and explicit reroll allowances.
5. Classify rights holds and pipeline incompatibilities by reason.
6. Let live census determine current availability.
7. MANUAL: run Raster Chad with dry_run=true.
8. Require census success, draw skipped, and exact-prompt preflight.
9. Review model/provider/prompt/cost mapping.
10. MANUAL: run Raster Chad with dry_run=false using reviewed bounds.
11. Confirm draw mapping agrees with the approved plan.
12. Preserve chad-raster-art.
13. Record run ID, artifact ID, and ZIP SHA-256.
14. Re-hash extracted rasters against provenance.jsonl.
15. Human-select keepers and record rejections.
16. Freeze the publication manifest.
17. Verify routed-provider publication basis.
18. Verify exact unique PHILOSOPHY.md anchors.
19. Prepare a run-specific self-cleaning AlphaClaw publisher.
20. Locally exercise it against the actual artifact when practical.
21. MANUAL: dispatch the temporary publication workflow.
22. Verify artifact ZIP SHA-256 in the publication job.
23. Verify each keeper model/provider/source SHA.
24. Copy keeper raster bytes exactly into assets/chad/.
25. Re-hash every destination and assert byte identity.
26. Insert each image at one exact unique philosophy anchor.
27. Add matching PROVENANCE.md receipts and rejection record.
28. Stage only intended publication files plus deletion of temporary machinery.
29. Inspect staged file list.
30. Commit and push.
31. Verify repository state, hashes, receipt links, rendered placement, and absence of rejected/temp files.
```

---

# 20. Mechanical exemplars

## A. Full-population round

Generation:

```text
PaulTiffany/letGPTsustakethewheel
Actions run: 32431592545
Artifact: chad-raster-art
Artifact ID: 9429338299
Artifact ZIP SHA-256:
683b0b091184311ddf466f0db5e308763fd76bebe59313de3699695fc3625c01
```

The artifact contained twelve generated rasters. Eleven were selected for publication. One was rejected because it contained visible generated lettering/numbers.

The keepers were independently re-hashed against `provenance.jsonl`, copied byte-for-byte into `AlphaClaw/assets/chad/`, re-hashed after publication, attached to exact philosophy anchors, and entered into `PROVENANCE.md`.

Publication commit:

```text
d9f98d7168fd8fad453d652ceb73f261eee507a0
Publish eleven Chad round 15 keepers
```

## B. Milestone run — live census, prompt preflight, and self-cleaning publication

Dry-run census:

```text
PaulTiffany/letGPTsustakethewheel
Actions run: 32744713491
census: success
draw: skipped
```

Observed census facts:

```text
eligible raster candidates: 8
rights-review exclusions: 4
pipeline/vector exclusions: 4
targets selected: 3
planned estimated cost: $0.48
```

The census constructed the exact draw prompts and reported lengths of:

```text
894
960
846
```

Generation:

```text
Actions run: 32745090551
Artifact: chad-raster-art
Artifact ID: 9526742320
Artifact ZIP SHA-256:
9d4dedbdad5f6cb0b4e93973b0d46f134f2f85b8b5f3caddb4d1e63427d81049
```

Generation result:

```text
selected: 3
attempted: 3
successful API generations: 3
reported actual cost: $0.2378524
human keepers: 2
human rejection: 1
```

Keepers:

```text
basic-idea
  model: google/gemini-2.5-flash-image
  provider: google-ai-studio
  SHA-256: 3d456301bf6777f0b94ae8662aa4555f4d1fc262521861555819f29f5b901c91

judgment-scarcity
  model: openai/gpt-image-1
  provider: openai
  SHA-256: cb02439f99a68034e44f9afa66612041127aa0b6aceb5a99459c338c484912a9
```

Rejected:

```text
room-to-think
reason: visible generated alphanumeric labels and a question-mark symbol violated the explicit no-visible-text/symbol generation constraint
```

Publication:

```text
PaulTiffany/AlphaClaw
Actions run: 32748924564
publish job: success
publication commit: 521a71e
commit message: Publish two Chad keepers from run 32745090551
```

The publication job independently verified the fixed artifact ZIP SHA, printed both keeper SHA-256 and Git blob identities, published exactly two images, recorded one rejection, staged the intended delta, deleted the run-specific publisher and workflow, committed, and pushed to `main`.

This round demonstrates three important distinctions:

```text
availability != persistent blacklist
generation success != keeper success
transport URL != artifact identity
```

---

# 21. Governing rule

When repeating this workflow, optimize for boring reproducibility.

Do not ask:

> What elaborate new machinery could we build for this?

Ask:

> What did the functioning pipeline do last time, what changed in the live environment, and what are the new target lines?

The established pipeline is:

```text
bounded live census
→ exact-prompt preflight
→ manual approval
→ bounded generation
→ fixed artifact
→ receipts
→ human keeper selection
→ byte verification
→ manual publication gate
→ exact-byte publication
→ provenance
→ philosophy placement
→ commit verification
```

**Keep availability live, keep exclusions reasoned, keep the images binary, keep the receipts textual, and keep the two connected by hashes.**
