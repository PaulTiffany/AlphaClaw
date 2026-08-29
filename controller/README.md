# Bounded benchmark controller

This directory is **not AlphaClaw** and not OmegaClaw.

AlphaClaw is the sensory/prepend boundary in `ingress/`. OmegaClaw is the pinned upstream `OmegaClaw-Core/` submodule. `controller/` is the small host-side fixture used to run finite experiments against **stock OmegaClaw**.

```text
human / world
    |
    v
AlphaClaw boundary
    |
    v
fixed text-only envelope + EpisodeContract
    |
    v
fresh stock Omega container
    |
    v
first user response / finite failure

SEPARATE MEASUREMENT PATH:
provider -> raw provider receipt -> isolated ThreadKeeper witness
```

The separation is deliberate:

```text
perception != authority != inference
control != measurement != judgment
```

## Stock Omega stays stock

The controller does not create a profiled Omega tree. `omega_profile.py` is intentionally absent.

One Docker image is built from the exact pinned, pristine `OmegaClaw-Core/` tree using OmegaClaw's own Dockerfile. The image is reused; each episode receives a fresh disposable container. The fixture uses OmegaClaw's native runtime configuration rather than rewriting Omega source.

The runner verifies the Omega and ThreadKeeper gitlinks are exact and clean before making a benchmark claim.

## Episode contract

`episode_contract.py` is the source of truth for the finite human-input grant.

```text
post-handoff reasoning loops:  50 default / 50 hard ceiling
maxWakeLoops:                  0
maxHistory:                    0
after response:                stop this one-shot episode
boot behavior:                 stock Omega; meter separately
```

Fifty is a ceiling, not a target. The container is destroyed after the first user response. Smaller deliberate experiments such as `--max-loops 1` or `--max-loops 7` use the same machinery.

The contract has three witnesses:

1. Alpha includes the bounded episode clause in its inert JSON handoff.
2. Stock Omega receives `maxNewInputLoops=N`, `maxWakeLoops=0`, `maxHistory=0` and `wakeupInterval` through its native configuration path, as a minimal YAML file mounted read-only and selected with Omega's own `config=` argument.
3. The host provider gateway refuses to forward post-handoff provider call `N + 1`.

The model is told the bound. The model does not enforce the bound.

## Stock boot behavior

Omega normally begins with a startup inference before any human message. The benchmark does not race, delete, or patch that behavior.

The gateway meters the first stock boot response. Alpha is then queued through Omega's native test channel. A host-side release gate holds any very fast episode provider request until boot-time public messages have been separated, so the measurement boundary does not depend on winning a timing race.

Boot usage and post-handoff usage remain separate in the raw receipts.

## Wake behavior

Pinned Omega currently grants `1 + maxWakeLoops` when a scheduled wake fires, so `maxWakeLoops=0` is not by itself a proof of zero future wake inference.

The fixture therefore sets:

```text
wakeupInterval > whole episode timeout
```

and destroys the fresh container on response, budget exhaustion, accounting failure, provider failure, or timeout. The scheduled wake is outside the reachable lifetime of a valid one-shot episode.

## Provider receipt first; ThreadKeeper second

Omega uses its stock generic `OpenAIAPI` provider seam, pointed at the small host-side gateway.

```text
stock Omega request
    |
    +-- fixed model check
    +-- post-handoff call ceiling
    +-- boot/episode release gate
    |
    v
real upstream provider
    |
    v
provider response
    |
    +--> controller writes provider_usage.jsonl FIRST
    |
    +--> token counts only
            |
            v
       python -I
       threadkeeper_worker.py
            |
            v
       pinned ThreadKeeper
       Record / Account only
            |
            v
       usage.jsonl
```

`provider_usage.jsonl` is the primary provider receipt. It is written by AlphaClaw's gateway before any ThreadKeeper code executes. If the accounting witness fails, the raw provider receipt remains and the benchmark is marked invalid.

ThreadKeeper is retained as a pinned submodule for provenance and community reuse, but its code is **not imported into the controller interpreter**. `threadkeeper_meter.py` launches a short-lived isolated Python process with `python -I`. The worker receives only:

```text
run id
phase / node role
model name
input token count
output token count
paths for its accounting files
```

It does not receive provider credentials, prompt text, model response text, Docker authority, or Alpha envelopes. The worker environment is allowlisted rather than inherited wholesale. ThreadKeeper's routing, escalation, subagents, MeTTa policy decisions, and model-selection logic are not used.

This is a process boundary, not a claim of hostile-code sandboxing. If later evidence shows a stronger boundary is necessary, the same one-shot worker can be moved into a read-only networkless container without changing the benchmark ontology.

The generic OpenAI-compatible benchmark profile also does not claim to reproduce provider-specific Omega plugins such as ASI:One thinking options or OpenRouter cache policy. Benchmark claims must name the profile actually used.

## Run one real bounded episode

```bash
export ASIONE_API_KEY=...
python controller/omegaboi.py \
  --text "hello" \
  --provider asione \
  --model asi1-ultra
```

A narrow one-call experiment is explicit:

```bash
python controller/omegaboi.py \
  --text "answer once" \
  --provider asione \
  --max-loops 1
```

For image evidence, Alpha perception occurs first and its sensory trace is recorded separately.

## Fresh state

The first run builds:

```text
alphaclaw-omega-stock:<pinned-sha-prefix>
```

from OmegaClaw's own Dockerfile. Later runs reuse that exact local image unless `--rebuild-image` is explicitly requested.

There is no benchmark memory volume. Each fresh container gets its own disposable writable layer, and `maxHistory=0` removes persistent-history recall from the prompt while leaving the current `HUMAN-MSG` input intact -- that input reaches the model outside the `HISTORY` field.

## Why the bounds are a config file, not command-line arguments

Omega's `src/config.py` applies no type coercion to command-line or environment
overrides (`dict[kv[0]] = kv[1]`), while its config file is parsed with
`yaml.safe_load`. `src/config.metta` passes the resolved value straight to
`src/loop.metta`, which uses these parameters arithmetically. A numeric bound passed
on argv therefore arrives as a string and kills the agent's main thread with
`Arithmetic: `'0'/0' is not a function`. Environment overrides cannot work either:
`entrypoint.sh` scrubs everything outside its `SAFE_VARS` allowlist.

The controller therefore writes a minimal YAML file per episode into the run
directory, mounts it read-only at `/etc/alphaclaw-bounds.yaml` (outside the tmpfs
mounts, which would shadow it), and selects it with `config=`. Selecting a config
file replaces Omega's own `config.yaml` wholesale, so the file is kept minimal:
every omitted key resolves from the in-source default at its `(configure key default)`
site.

Those in-source defaults were compared against all 42 keys in the pinned
`config.yaml` and match it with one exception: `openClawURL` defaults to `""` in
`plugins/openclaw/openclaw.metta` while the pinned `config.yaml` sets
`http://172.17.0.1:18789`. That difference is inert while `openClawEnabled` is
`disabled`, which is both the pinned default and the in-source default, so the
plugin never reads the URL.

What the bounds do and do not claim:

- `maxNewInputLoops` bounds prompted reasoning turns per new-input activation, not raw loop ticks.
- `maxHistory=0` suppresses prior recalled history; the current input is preserved.
- `maxWakeLoops=0` suppresses wake-driven prompted work.
- Provider calls are bounded separately by the external metering gateway.
- Skill executions are not provider calls: one prompted turn may request up to five
  skills, so no one-tool ceiling is claimed.

Outputs include:

```text
manifest.json
alpha-envelope.json
ingress-trace.json
provider_usage.jsonl     # primary provider receipt
usage.jsonl              # isolated ThreadKeeper-normalized witness
container.log
response.txt
```

The manifest records the exact Omega SHA, ThreadKeeper SHA, Alpha commit, Docker image ID, episode contract, provider/model, gateway state, usage by phase, and termination reason.

## First live bounded canary — 2026-08-28

The first real-provider episode. Facts below are taken from that run's receipts; the
run directory itself is evidence, not source, and is not committed.

| | |
|---|---|
| Run ID | `20260828T163256Z-4082212669` |
| Alpha commit | `f68ddab6ed6b350ed388b2a6a1cbee2b2beb21f7` |
| Pinned Omega | `3d711e4b9f5254ae94f31123ca242f60cfd97d29` — commit and raw bytes both verified |
| Pinned ThreadKeeper | `a64de99e10f9f8078d25bff511b44fd71819e931` — commit and raw bytes both verified |
| Stock image | `sha256:69ff11bf227b197f697aab4488e879258560730565838b19db25e3dd580af90a`, unchanged |
| Provider / model | ASICloud / `minimax/minimax-m3` |
| Typed bounds | `maxNewInputLoops: 1`, `maxWakeLoops: 0`, `maxHistory: 0`, `wakeupInterval: 960` |
| Status | `completed`, `termination_reason: responded` |
| Response | `ORANGE` |

Exactly two provider calls, split by phase:

```text
boot     1 call    1432 input / 134 output
episode  1 call    1915 input /  82 output
```

Stock Omega emitted two startup channel messages before the handoff:

```text
OmegaClaw version=unknown
No new input received. Standing by.
```

### Live validation of the boot-turn-completion barrier

Measured byte offsets in that run's `container.log`:

```text
188654  first numeric CHARS_SENT
194057  boot-originated send: No new input received. Standing by.
194272  next numeric loop boundary
195719  alphaclaw_human_ingress
```

That is `readiness < unique boot send < boot-turn barrier < Alpha handoff`.

The first real-provider run directly confirmed the race discovered during PR #33
review: a unique boot-originated `send` can occur after provider transport completion
but before the boot turn finishes. The relative boot-turn-completion barrier captured
that message as startup traffic before Alpha handoff, preventing false episode
completion.

### Evidence boundary: POLLRDHUP

`POLLRDHUP` is **not persisted in this run's receipts** — it appears zero times across
every artifact, because it is emitted host-side by the pinned `Autotests/mock` RPC
logger and the controller persists only the container's output.

The receipts therefore establish only that it did not prevent successful response
capture: `status=completed`, `termination_reason=responded`, `response.txt=ORANGE`,
`fatal_error=null`. They do not establish when it occurred, so it is not characterised
here as teardown-only. Whether to persist controller stderr alongside `container.log`
is left as a separate future decision.

## Multimodal benchmark tranche — 2026-08-28

Three usable receipts across the three ingress modes. Run directories are evidence,
not source, and stay uncommitted.

Every image-bearing run tests

```text
original image bytes -> OpenRouter sensory boundary -> symbolic handoff -> bounded stock Omega
```

Omega did not see image bytes in any run. Its channel carries strings and
`providers/lib_llm_ext.py` builds message content as a plain string, so the
transformation is mechanically required and is recorded as sensory inference.

Shared across all three: pinned Omega `3d711e4b…` and ThreadKeeper `a64de99e…` with
commit and raw bytes verified, stock image `sha256:69ff11bf227b197f…`, bounds
`maxNewInputLoops: 1` / `maxWakeLoops: 0` / `maxHistory: 0` / `wakeupInterval: 960`,
ASICloud with `minimax/minimax-m3`, one post-handoff reasoning call, no budget
exhaustion, no gateway fatal error, container torn down.

| Mode | Run | Sensory model | sensory / boot / episode | Expected | Actual | Grade |
|---|---|---|---|---|---|---|
| Text only | `20260828T163256Z-4082212669` | none | 0 / 1 / 1 | `ORANGE` | `ORANGE` | exact-match **PASS** |
| Image only | `20260828T173331Z-59957e98c2` | `dots-studio/dots-3-note-preview:free`, resolved from `openrouter/free` | 1 / 1 / 1 | faithful transformation | handoff with `K7` and three blue squares, delivered unchanged | transformation **PASS** |
| Image + text | `20260828T174544Z-568748ab99` | `dots-studio/dots-3-note-preview:free`, pinned | 1 / 1 / 1 | `K73` | `K7 3` | exact-match **FAIL** |

Stimulus for both image runs, generated by `scripts/make_benchmark_stimuli.py`:

```text
image sha256       3775285f05aeded8deaadfa57d1570861a16d417f0c6462f3c4847cbae861334
instruction sha256 82bac632f15b7df0607987dfdd1e4870ab308f5326bdd6fb62a26793a0e66fdc
                   "Reply only with the token shown in the image followed by the
                    number of shapes shown."
```

### Image only

The grading target was the transformation, not an exact utterance: the image-only
contract instructs the sensory boundary not to solve downstream tasks and gives Omega
no instruction, so requiring a specific final string would invent a contract. The
handoff carried the literal `K7` and represented the three blue squares faithfully,
and it reached the post-injection Omega prompt unchanged. Omega's final utterance was
recorded but was not an exact-match criterion.

### Image + text — output-contract failure

`response.txt` verbatim:

```text
b'K7 3\n'
```

The failure is narrow and must not be rounded up. The sensory handoff contained both
required facts: the literal `K7` (seven occurrences) and an unambiguous count of three,
present independently as prose (`"Three small blue square shapes aligned horizontally
on the left side of the image."`) and as a labelled entity (`"three blue squares"`).
Both the handoff and the human instruction reached the post-injection prompt. Omega
returned the correct token, the correct count, and the correct order.

The exact-match failure is the inserted separator, so it is classified as an
**output-contract failure**, not a perception failure and not a reasoning or
composition failure.

One qualifier the receipts require: the instruction said "followed by" and did not
prohibit whitespace or require concatenation. Omega therefore violated no stated
constraint; the exact-match criterion presumed a convention the stimulus never
expressed. This is an output-contract and stimulus-specification issue.

### Failed pre-run, preserved

Run `20260828T173545Z-579a71fd62` requested sensory model `openrouter/free`, made one
OpenRouter call, and received content that was not a JSON object. The failure occurred
in ingress before gateway start and before any container launch, so it cost zero
ASICloud calls and produced no usable receipt: the directory holds only `run_id` and
two zero-byte usage files, with no manifest.

### Benchmark sensory-model policy

`openrouter/free` is a nondeterministic router, not a model, and is not a stable
benchmark condition. Two byte-identical perception requests reached two different
models with different contract compliance. Benchmark sensory runs should pin an
explicit free or cheap model identifier. The exact sensory model is part of the
experimental condition and belongs in the receipt.

This is a policy note only. No automatic model selector is built.

### Usage across the three usable receipts

```text
OpenRouter sensory   2 calls     292 input /  2618 output
ASICloud boot        3 calls    4296 input /   366 output
ASICloud episode     3 calls    7636 input /   773 output
ASICloud total       6 calls   11932 input /  1139 output
total upstream       8 calls across two providers
```

Separately, the failed pre-run cost one OpenRouter sensory call and zero ASICloud
calls, and is excluded from the totals above.

### What this tranche does and does not claim

- Text-only bounded reasoning works.
- The image sensory transformation works.
- Image and text information composed correctly and reached bounded Omega.
- Exact output formatting failed under an under-specified concatenation contract.

Nothing here claims Omega perceived image bytes, and image-bearing runs are not
one-call benchmarks: each costs one sensory, one boot and one episode call across two
providers. The bounded claim remains one post-handoff reasoning call.

## Controlled benchmark suite protocol

Six matched families, each yielding three conditions from one underlying task: a text
control, an image-only condition, and an image+text condition sharing the exact same
image bytes. Eighteen end-to-end cases while holding task content constant.

Stimuli and ground truth come from `scripts/make_benchmark_suite.py` (stdlib only,
zlib level 0 for byte determinism). Digests are pinned in `benchmark/items.json` and
in the test suite.

| Item | Family | Probe | Answer |
|---|---|---|---|
| `ocr_count` | OCR + count | perception | `M45` |
| `colour_count` | colour + count | perception | `32` |
| `spatial_relation` | spatial relation | perception | `RED` |
| `number_arithmetic` | visible-number arithmetic | **resident reasoning** | `19` |
| `distractor_selection` | distractor / visual selection | perception | `RED` |
| `multi_fact_composition` | multi-fact relation + composition | perception | `Q932` |

`number_arithmetic` is deliberately a resident-reasoning probe rather than pure
perception; its matched text control separates arithmetic failure from sensory failure.

Every exact-answer rule states its formatting contract explicitly -- uppercase, digits
only, no spaces, no other text. An under-specified contract previously produced
`K7 3` against an expected `K73`, which was a stimulus defect rather than a model
failure.

### Frozen sensory boundary and its scoring limitation

`ingress/openrouter_image.py` is **not modified** for this benchmark. Its handoff has
no dedicated count field, so counts arrive as free-form prose or as an entity label.
That is a property of the system under test, recorded rather than repaired mid
experiment.

`scripts/score_handoff.py` is therefore pre-registered and deterministic. No
LLM-as-judge, no post-hoc human correction. Rules:

- **token** -- correct iff the exact case-sensitive token occurs in a literal
  observation or an entity label.
- **shape presence** -- correct iff colour and shape occur in the *same* assertion
  string.
- **count** -- correct iff the expected digit or number-word occurs in the *same*
  assertion string as the colour and shape mention.
- **relation** -- scored only through a fixed map of pre-declared predicate forms over
  the structured relation fields, with right-hand forms inverted. Anything unmapped is
  `unknown`.
- Facts the scorer cannot decide deterministically are `unknown` and never inferred.

Only literal observations and entity labels are read. Interpretations and uncertainty
are the model's commentary, not asserted observations.

Two figures are always reported together:

- **atomic-fact accuracy** = correct / scoreable facts
- **scoring coverage** = scoreable / all expected facts

### Sensory-model screening and the pre-registered selection rule

Screening uses explicit model identifiers only. `openrouter/free` is rejected as a
benchmark condition: it is a nondeterministic router, and two byte-identical
perception requests were observed reaching two different models with different
contract compliance. The exact sensory model is part of the experimental condition and
belongs in the receipt.

Three free candidates, six images, two repeats: 36 OpenRouter calls, no ASICloud, no
Omega, no containers. Selection happens **before** any downstream result is observed:

1. highest schema-compliant atomic-fact yield -- correct / all expected facts, where a
   request failure or non-schema response contributes zero correct facts
2. tie -> highest schema-compliance rate
3. tie -> highest repeat stability
4. tie -> lowest mean output tokens
5. residual tie -> lexicographically lowest exact model id

A model is **not** excluded for failing schema on some images. That failure is
benchmark evidence and is already penalised by rule 1.

### Fixed resident reasoning condition

The end-to-end tranche fixes provider `asicloud`, model `minimax/minimax-m3`,
`maxNewInputLoops: 1`, `maxWakeLoops: 0`, `maxHistory: 0`, and one externally metered
post-handoff reasoning call. Readiness, the boot-turn barrier, drain ordering, the
gateway and Docker hardening are unchanged.

This is a held-constant condition, not a benchmark-tuning target. No stimulus, rule or
scoring function references it; tests assert that. Resident-model comparison would be a
separate experiment and would confound this architecture benchmark.

### Experimental caps

Eighteen bounded runs, at most 36 ASICloud calls (18 boot, 18 episode), 106,776 input
and 18,612 output tokens. These are hard caps, not targets. No confidence reruns, no
retry-until-pass, no post-failure prompt tuning. Failures stay in the denominator.

## Screening v1 result and Protocol Amendment v1.1

### Screening v1 -- what it establishes, narrowly

Run against protocol commit `c78c08fce81c5b96d21bb19d3b693d4c4c15feac`. The artifact
`benchmark/screening.json` is preserved unmodified.

- 36 calls were attempted, exactly as preregistered.
- `dots-studio/dots-3-note-preview:free` produced **11 schema-conformant and correct
  runs out of 12**, with one genuine schema-contract failure on `spatial_relation`
  (`handoff field 'literal_observations' must be an array of strings`).
- Both Gemma candidates produced **0 usable observations**: all 24 requests failed
  with upstream HTTP 429.
- The preregistered selector mechanically returns `dots-studio/dots-3-note-preview:free`
  at criterion 1 (atomic-fact yield 0.9286 against 0.0000 and 0.0000).

That selector result is **formally correct under Protocol v1**, but the comparative
evidence is incomplete because the competing arms were unavailable. **No claim is made
that dots outperformed either Gemma model.** They were not measured.

`repeat_stability = 1.0` for both Gemma models is **not interpretable as performance**:
both repeats are identical failure vectors.

### Amendment v1.1 -- provider-availability handling only

Changes only how provider-availability failures are handled. Stimuli, ground truth,
sensory prompt and boundary, scorer, candidate model identifiers, the
two-successful-observations target, the model-selection hierarchy, the reasoning
condition and all downstream design are unchanged, and tests assert this.

Predeclared rules:

1. A failed call is preserved as an availability event and never disappears.
2. Availability failures are distinguished from model, schema and task failures.
3. A model x item x repeat cell that failed on availability may receive a replacement
   measurement after an availability wait.
4. **At most one** replacement attempt per availability-failed cell under v1.1.
5. Cells that produced any usable experimental outcome -- a model response, a schema
   failure, a wrong answer -- are **not** eligible and are never retried.
6. No substitution of another model or provider identity.
7. Replacements use the exact same image bytes, model id, sensory boundary and
   scoring protocol.
8. Screening v1 is immutable; recovery data goes to `benchmark/screening-v1.1.json`
   with explicit linkage to the protocol commit, the amendment commit, the original
   artifact and its digest, and the exact cells recovered.

A replacement supersedes its cell for comparative scoring **only** if it reached model
inference and produced an experimental outcome. A replacement that itself hits an
availability error supersedes nothing.

The original 24 HTTP-429 attempts remain reported separately as availability failures.
**HTTP-429 failures are not evidence of visual or model incapability.**

The dots `spatial_relation` schema failure is **not** eligible for recovery: that
request reached inference and produced a genuine contract failure, which stands as the
experimental outcome for that cell.

Availability is reported separately from performance: attempted calls, provider
availability failures, usable model observations, and availability rate. For
Screening v1 that is 36 attempted, 24 availability failures, 12 usable observations,
availability rate 0.667.

## Protocol v2 -- preregistered model-variety tranche

### Chronology

- **v1** established the controlled six-item benchmark, the frozen sensory boundary,
  the deterministic scorer, and a three-candidate sensory screen with a selection rule.
- **v1.1** added provider-availability recovery only.
- **v2** adds explicit model-variety experimental conditions and replay provenance.

v2 is preregistered **before any Qwen sensory, paid-Gemma resident, or new ASICloud
benchmark result exists**.

### The question

Does AlphaClaw's bounded architecture continue to behave sensibly when reasonable
explicit sensory and resident models are substituted while the tasks and architecture
are held fixed? This decomposes the architecture rather than re-running the whole
system and wondering why a result moved. It is not a leaderboard.

### Named conditions

Sensory primary `dots-studio/dots-3-note-preview:free`; sensory alternate
`qwen/qwen3.7-flash`; resident primary ASICloud `minimax/minimax-m3`; resident
alternate OpenRouter `google/gemma-4-26b-a4b-it`.

These are **experimental conditions, not tournament candidates**. The v1/v1.1
selection rules remain historically intact but do not select among v2 conditions.
Barred: `openrouter/free` and both exhausted free Gemma endpoints. There is no
automatic fallback and no substitute model: an unavailable named condition is
recorded as evidence.

| ID | Sensory | Resident | Items | Sensory | Boot | Episode | Grading | Question |
|---|---|---|---|---|---|---|---|---|
| A | dots (free) | ASICloud MiniMax M3 | all six, matched conditions | 12 | 18 | 18 | exact-match; transformation for image-only | Does the bounded architecture work end to end under the sponsored condition? |
| B1 | qwen3.7-flash | none | six images x2 repeats | 12 | 0 | 0 | frozen 21-fact scorer + coverage | Is the frozen sensory boundary portable across a distinct sensory-model family? |
| B2 | replayed B1 handoffs | ASICloud MiniMax M3 | `ocr_count`, `distractor_selection`, `multi_fact_composition` | 0 | 3 | 3 | exact-match | Does an alternate sensory model produce a symbolic handoff **sufficient for the same fixed MiniMax resident reasoner**? |
| C | replayed dots handoffs | OpenRouter gemma-4-26b-a4b-it | `number_arithmetic` text control; `ocr_count` image+text; `number_arithmetic` image+text | 0 | 3 | 3 | exact-match | Same symbolic evidence -> different resident model |

Item lists for B2 and C are fixed above, before any v2 result exists.

### Replay semantics

**A replay is not a native text benchmark condition.** Mechanically it routes through
`.json` text passthrough, so the ingress receipt correctly records
`route: text_passthrough`, `sensory_inference: false`, and the digest of the replay
JSON. That receipt is accurate for the replay event and is **never rewritten** to
pretend perception occurred.

Every replay record additionally carries `replayed_from`, `origin_run_id`,
`original_image_sha256`, `sensory_model` and `handoff_payload_sha256`.

Byte identity is required between the original symbolic payload, the replay input
payload, and the payload embedded in the resulting Alpha envelope. **If byte identity
fails the condition is invalid and must stop before provider inference.**

### Caps

ASICloud rises from the v1 cap of 36 to **42 calls** -- condition A 36, condition B2 6
-- with at most 124,572 input and 21,714 output tokens, derived from the v1 receipt
maxima. Condition C bills OpenRouter, not the sponsored allocation.

OpenRouter: 18 paid calls (B1 sensory 12, C resident 6) and 12 free (condition A).
Projected worst case about **$0.0054** from current catalog pricing -- a projection,
not a guaranteed invoice.

No retry-until-pass. Availability failures remain evidence.

### Unchanged by v2

The six items and their image, rule and answer digests; the ground truth; the sensory
`SYSTEM_PROMPT` and normalisation; the scorer and its scoring-coverage semantics; the
Alpha envelope; stock pinned Omega; the bounds; boot readiness; the boot-turn barrier;
drain ordering; gateway accounting; and the v1/v1.1 failure classification. The v1 and
v1.1 artifacts are not modified.

## Protocol v2 condition B1 -- result, and Amendment v2.1

### B1 result (frozen)

Condition B1 ran against merged main `2995003c649ee0dde8da08237cdabd2a189a4eb2`,
sensory model `qwen/qwen3.7-flash`, six deterministic images, two repeats, 12
OpenRouter calls. No resident model, no ASICloud calls, no Omega containers. The
artifact `benchmark/screening-v2-B1.json` is preserved unmodified.

| Metric | Value |
|---|---|
| Attempted / succeeded | 12 / 12 |
| Schema-compliance rate | 1.0000 |
| Atomic-fact yield | 0.9524 (40/42) |
| Atomic-fact accuracy over scoreable | 1.0000 (40/40) |
| Scoring coverage | 0.9524 |
| Repeat stability | 1.000 |
| Tokens in / out | 2,640 / 11,486 |
| Cost at catalog pricing | ~$0.0016 |

By fact type: token 4/4, shape_presence 18/18, shape_count 14/14, number 4/4,
relation **0 correct of 0 scoreable, 2 expected**.

Hallucinated-fact count is **not reported**: it is not implemented in the frozen
scorer, and adding it after results existed would be a post-hoc rule.

**The frozen sensory boundary is portable to a distinct model family.** Requested and
resolved model were both `qwen/qwen3.7-flash` on every call; there were no request
failures and no schema failures.

### Semantic plausibility is not mechanically scoreable evidence

Both `spatial_relation` calls asserted the correct spatial fact, in the correct
direction, in both directions:

```text
subject='Red Square'   predicate='is located to the left of'   object='Blue Square'
subject='Blue Square'  predicate='is located to the right of'  object='Red Square'
```

Neither predicate string appears in the preregistered deterministic mapping, which
matches predicates exactly. The scorer therefore returned **`unknown`**, and coverage
fell to 40/42.

That verdict stands. A human reading the wording understands it; the frozen scorer
does not, and it is not manually upgraded to correct. This is the declared
distinction between semantic plausibility and mechanically scoreable evidence, and it
is a property of the scorer's vocabulary rather than of the model's perception. The
relation lexicon was **not** broadened after seeing Qwen's wording; any richer
relation normalisation belongs to a future protocol version, not to B1.

### Amendment v2.1 -- B2 replay-source selection

Protocol v2 fixed the B2 item list but never specified which of the two B1 repeats
supplies the replay handoff. B1 had already been run, so the rule is deliberately
blind to every result:

> For every B2 item, replay B1 `repeat_index = 0` only.

- If repeat 0 produced a usable schema-conformant handoff, that exact payload is the
  B2 replay source.
- If repeat 0 did not, that B2 item is **unavailable** under v2.1.
- There is **no fall-through to repeat 1**. Repeat 1 is B1 replication evidence only
  and can never replace repeat 0 for B2.

Selection is independent of score, atomic-fact accuracy, apparent quality and the
downstream expected answer. Tests assert that repeat 0 is chosen even when repeat 1
scored better, and that a scoring field never gates selection.

Scope is replay-source selection only. Stimuli, the Qwen and MiniMax conditions, the
B2 item list, the scorer, the sensory boundary, the B1 results, the replay bytes and
the ASICloud caps are unchanged.

## Protocol v2 Condition A -- result (frozen)

The primary Alpha tranche: sensory `dots-studio/dots-3-note-preview:free`, resident
ASICloud `minimax/minimax-m3`, six deterministic items across three matched conditions,
`--max-loops 1`. **18 bounded runs, 18 executed, zero reruns.** Frozen at
`benchmark/benchmark-v2-A.json`.

| item | text control | image only (sensory) | image + text |
|---|---|---|---|
| `ocr_count` | PASS `M45` | 3/3 facts | PASS `M45` |
| `colour_count` | PASS `32` | 4/4 facts | PASS `32` |
| `spatial_relation` | PASS `RED` | 2/3 facts (1 unknown) | PASS `RED` |
| `number_arithmetic` | PASS `19` | 2/2 facts | PASS `19` |
| `distractor_selection` | PASS `RED` | 4/4 facts | **FAIL** -- no response |
| `multi_fact_composition` | PASS `Q932` | 5/5 facts | PASS `Q932` |

Text-control exact match **6/6**. Image+text exact match **5/6**. Image-only schema
compliance **6/6**, atomic-fact yield **20/21**, accuracy over scoreable facts
**20/20**, scoring coverage **20/21**. Every one of the 18 runs obeyed **1 boot + 1
episode**: 36 ASICloud calls (cap 42), 72,804 in / 7,092 out; 12 sensory calls, 1,800
in / 18,974 out, requested and resolved as the preregistered model on every call.

### The one failure, not rounded up

`distractor_selection` image+text is a **benchmark failure**, class **output-contract**:

- sensory handoff correct, 4/4 -- sensing was not the broken link
- expected final answer `RED`
- Omega's episode content contained `RED`
- it was emitted as an unknown skill call, not via `send`:
  `(RESPONSE: ((Error UNKNOWN_SKILL_CALL "RED")))`
- no valid channel message was produced, no response artifact exists
- the run timed out; exact match FAIL

The intended answer is recoverable from the container log. That does **not** make it a
pass, and it was not upgraded.

### Lifecycle observation, not a bound violation

That run logged 896 raw idle loop ticks (iterations 4-896, 21:12:26Z-21:27:26Z) while
the controller waited out its 900 s response window. The chronology matters and the
first reading of it was wrong: **the ticks did not follow a successful response.** The
two runs that did respond ended at 5 ticks each and were torn down immediately. Long
ticking occurred only in the run that never emitted a response.

During that interval prompted reasoning turns stayed bounded, boot calls stayed 1,
episode calls stayed 1, and **provider calls after the episode were 0**. Raw loop ticks
are not prompted reasoning turns; `maxNewInputLoops: 1` bounds the latter and did.
So this is an orchestration/lifecycle observation -- not a recursive-bound violation,
not additional model reasoning, not a provider-budget violation. Timeout, teardown and
controller behaviour are deliberately **unchanged** in this results tranche.

### Cross-model scorer-vocabulary limitation

`spatial_relation` scored `unknown` on its relation fact in both image conditions,
because dots produced `is located to the left of` -- the **same form Qwen produced in
B1**, and still absent from the frozen deterministic relation lexicon. Two unrelated
sensory-model families independently landed on a phrasing the scorer cannot decide.

That is recorded as **cross-model evidence of a scorer-vocabulary coverage limitation**,
not as a corrected sensory result. The lexicon was **not** broadened in v2; the verdicts
remain `unknown` and coverage remains 20/21. Any normalisation belongs to a future
scorer/protocol version.

### Derived analysis, and two classifier bugs found after the runs

`scripts/analyze_condition_a.py` derives the decomposition from the frozen artifact. It
is pure, offline and read-only: tests assert it has no network, container or write path,
and that it never mutates a run mapping. Two bugs in that derived layer were found and
corrected **after** the experimental runs:

1. `unknown` scorer verdicts were misclassified as sensory failures (sensory 2 -> 0).
2. A run that met its exact-match criterion was still assigned a failure class.

An `unknown` verdict is undecidable, not wrong -- excluded from accuracy, reported as
reduced coverage, exactly as ruled for B1. Only the derived classification changed to
match its already-declared semantics. **Raw provider receipts, exact-match verdicts and
frozen sensory-scorer verdicts are byte-identical, no run was re-executed, and no
additional provider call was made.** `--verify` recomputes every class and fails if the
committed decomposition and the committed evidence disagree.

### Failure decomposition

| class | count |
|---|---|
| sensory | 0 |
| reasoning/composition | 0 |
| output-contract | **1** |
| infrastructure | 0 |
| provider availability | 0 |
| passed | 17 |

## Protocol Amendment v2.2 -- B2 composition replay

Protocol v2 preregistered B2 as an image+text condition with **zero sensory calls**, but
the replay tooling could only re-deliver a *raw* handoff. A preflight before any B2
inference found the condition was not executable as written:

- `.json` without `--text` routes to `text_passthrough`, so the envelope carries the
  handoff **and no human instruction** -- exact-match grading is then unsatisfiable,
  because the resident is never told what to answer;
- `.json` with `--text` reaches `route_image_with_text`, which requires an image, would
  demand an OpenRouter key, and would run perception -- all forbidden at
  `sensory_calls: 0`.

Empirically this is not a theoretical gap: Condition A's `image_only` runs used the same
bare-handoff envelope shape and produced prose acknowledgements, **0/6** exact tokens.

No inference call was made to discover this, and none was made for the amendment.

### The clarified byte-identity invariant

It is **wrong** to claim the whole B2 replay input equals the raw B1 handoff. For an
image+text replay the invariant is:

- sensory constituent == the exact frozen B1 repeat-0 handoff;
- text constituent == the exact frozen benchmark instruction;
- combined payload == a deterministic composition of those two constituents;
- composed payload == byte-identical to what the **live** image+text route would produce
  if handed that same handoff.

This clarifies the intervention boundary. It is not permission to alter either
constituent: both are digest-checked, and a single changed byte in either one raises
before any provider call.

### Mechanical equivalence proof

`scripts/amendment_v2_2.py` composes `{"human_text": text, "sensory_handoff": handoff}`
with the same `json.dumps(..., ensure_ascii=False, sort_keys=True)` rules the live route
uses. Tests prove, offline with an injected fake runner that returns the frozen handoff:

| item | handoff sha256 | text sha256 | composed sha256 | payload == live | envelope == live |
|---|---|---|---|---|---|
| `ocr_count` | `d55183d4…` | `2111a904…` | `57a3a785…` | yes | yes |
| `distractor_selection` | `b6d1cd82…` | `d6bc2d90…` | `dae9694c…` | yes | yes |
| `multi_fact_composition` | `e41d1d2e…` | `c4736682…` | `ea819081…` | yes | yes |

Same text + same symbolic handoff produces the same combined payload and the same Alpha
envelope, without a sensory call. The stimuli are regenerated deterministically inside
the test, so the proof never silently skips.

`d6bc2d90…` is independently corroborated: it is the `text_sha256` Condition A recorded
on its `distractor_selection` image+text run, so the replayed instruction is provably
the same bytes that condition delivered.

### Scope and provenance

Composition lives in replay tooling. **Normal live ingress is unchanged** -- a test
asserts `route_image_with_text` still refuses a non-image input, so arbitrary JSON is
never silently treated as a multimodal replay.

Every B2 record carries `replayed_from`, `origin_run_id`, `original_image_sha256`,
`sensory_model`, `handoff_payload_sha256`, `human_text_sha256`,
`composed_payload_sha256`, `is_native_text_condition: false` and
`sensory_inference: false`. Recording a replay as native text, or as having perceived,
raises.

B2 items, the v2.1 repeat-0 rule, the B1 artifact and its handoff bytes, the task text,
the sensory and resident models, the scorer, the expected answers, the bounds, the
ASICloud caps and B2 grading are unchanged.

## Protocol v2 Condition B2 -- result (frozen)

Replay of the frozen B1 `repeat_index = 0` handoffs, composed under Amendment v2.2 with
the frozen benchmark instruction, into the same resident (ASICloud `minimax/minimax-m3`).
**3 runs, 0 new sensory calls, 3 boot + 3 episode = 6 ASICloud calls.** Frozen at
`benchmark/benchmark-v2-B2.json`.

All nine mechanical checks passed for every item **before** its provider call: repeat-0
selection through the v2.1 selector, both constituent digests, v2.2 composition, the
composed digest, equality with the live image+text payload under the frozen handoff,
Alpha prepend, envelope equality, and provenance validation. The delivered envelope was
also checked *after* each run: `envelope_payload_sha256` equals `composed_payload_sha256`
on all three.

| item | expected | response | verdict |
|---|---|---|---|
| `ocr_count` | `M45` | `M45` | PASS |
| `distractor_selection` | `RED` | *(none)* | **FAIL** -- output-contract |
| `multi_fact_composition` | `Q932` | `Q932` | PASS |

Exact-match **2/3**. Every run recorded `route: text_passthrough`,
`sensory_inference: false` and no `sensory_trace` -- receipts were not rewritten to
pretend perception occurred; provenance carries the origin instead.

### Paired contrast against Condition A image+text

Same task instruction (identical `text_sha256`), same resident, different
sensory-model handoff.

| item | dots handoff | qwen handoff | facts needed | dots | qwen | A | B2 | transition |
|---|---|---|---|---|---|---|---|---|
| `ocr_count` | `453cae8d…` | `d55183d4…` | 3 | 3/3 | 3/3 | `M45` PASS | `M45` PASS | none |
| `distractor_selection` | `b8d4741e…` | `b6d1cd82…` | 4 | 4/4 | 4/4 | FAIL | FAIL | none |
| `multi_fact_composition` | `b394302a…` | `e41d1d2e…` | 5 | 5/5 | 5/5 | `Q932` PASS | `Q932` PASS | none |

Fact verdicts come from the frozen scorer; no new judge was introduced. Both sensory
models supplied every mechanically identifiable fact each task needs.

**No pass/fail transition on any of the three paired items.**

The preregistered case of interest was `distractor_selection`. In Condition A the dots
handoff was correct 4/4, the resident internally derived `RED`, and emitted it as an
invalid skill call. B2 reproduces that exactly with different symbolic evidence:

```
A  (dots): (RESPONSE: ((Error UNKNOWN_SKILL_CALL "RED")))
B2 (qwen): (RESPONSE: ((Error UNKNOWN_SKILL_CALL "RED")))
```

Zero `send` emissions in either run; both timed out with no channel message. On this one
item, **changing only the symbolic sensory evidence did not change the resident's
emission behaviour.** `RED` again appears in the log inside an error, and the run again
scores FAIL / output-contract -- it is not rounded up.

This is three preregistered paired cases with one failure in common. It is not evidence
about emission behaviour in general, and no causal claim beyond these three is made.

### Cap status after A + B2

| | used | cap | headroom |
|---|---|---|---|
| ASICloud calls | **42** | 42 | **0** |
| input tokens | 86,057 | 124,572 | 38,515 |
| output tokens | 7,771 | 21,714 | 13,943 |

**Protocol v2's ASICloud allocation is now exhausted exactly at 42 calls.** That means
no further *ASICloud* condition may run without an amendment.

It does **not** block Condition C. C's preregistered resident is OpenRouter
`google/gemma-4-26b-a4b-it` with `resident_billing: openrouter` and `sensory_calls: 0`,
so **Condition C remains executable and does not consume ASICloud call headroom.** Tests
assert both halves: the allocation is exhausted at exactly 42, and C's frozen billing
path is OpenRouter rather than ASICloud. The ASICloud cap is not raised.

## Unbounded Omega is a different population

A developer who wants standing/autonomous/unbounded OmegaClaw runs upstream OmegaClaw directly instead of `controller/omegaboi.py`. That is a legitimate choice, but it is outside the bounded benchmark population and must not inherit its measurements or claims.

There is no standing cloud lifecycle controller, upstream watcher, automatic promotion path, or repository workflow that spends provider tokens.

The default development question remains:

> **WHY DO WE NEED THAT?**

For this controller the answer is narrow: configure a stock pinned subject, construct a finite episode, independently cap provider calls, preserve the provider's receipt, ask a borrowed accounting witness to check it, and stop.
