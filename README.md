# AlphaClaw

**Multimodal at the boundary. Text inference in the loop. Human authority around both.**

AlphaClaw is a small sensory tool for a text-only reasoning process.

The repository also carries deliberately separate experimental and human-development surfaces. They should not be confused with AlphaClaw itself.

```text
1. PERCEPTION
human / world
    -> AlphaClaw sensory boundary
    -> fixed text-only evidence envelope

2. INFERENCE
text handoff
    -> pinned upstream OmegaClaw

3. BOUNDED BENCHMARK APPARATUS
controller/
    -> fresh disposable OmegaBoi
    -> finite episode contract
    -> mechanical loop/termination bounds

4. BENCHMARK ACCOUNTING
external/ThreadKeeper
    -> provider usage records only

5. HUMAN DEVELOPMENT
GitHub Wiki
    -> public authored pages
```

The first is AlphaClaw proper. OmegaClaw and ThreadKeeper are pinned upstream dependencies. The controller is experimental apparatus. The Wiki is a human contribution surface.

## 1. AlphaClaw: sensory boundary

`ingress/` contains the AlphaClaw runtime idea.

`ingress/pipe.py` is the deterministic front door. It mechanically chooses only between text passthrough and supported multimedia perception. Text never invokes a sensory model. Both paths always converge on the same fixed Alpha prepend before anything is handed to OmegaClaw.

```text
text -------------------------------> fixed Alpha prepend -> text-only handoff
image -> one external perception ---> fixed Alpha prepend -> text-only handoff
```

For already-textual input:

```bash
python ingress/pipe.py --text "your message"
```

For a text file, the file is read as UTF-8 and takes the same passthrough path:

```bash
python ingress/pipe.py --input-file notes.md
```

For an image, the pipe invokes the external sensory translator once and then prepends the resulting symbolic handoff:

```bash
export OPENROUTER_API_KEY=...
python ingress/pipe.py --input-file image.png
```

Unsupported media fails closed rather than being guessed at.

The fixed prepend tells OmegaClaw that its handoff is text-only evidence. OmegaClaw must not pretend that the handoff itself provides direct image, audio, video, or other multimedia perception; further multimedia perception requires an explicitly authorized external perception tool.

The controller may fill one explicit `episode_contract` slot in that envelope during bounded experiments. It cannot replace or mutate Alpha's fixed sensory contract.

The multimodal model is a perceptual translator, not an agent and not an authority source.

AlphaClaw does not own the reasoning loop, lifecycle, memory, permissions, deployment, model selection, or recursive authorization.

## 2. OmegaClaw: pinned upstream dependency

This repository does **not** implement OmegaClaw.

`OmegaClaw-Core/` is a pristine Git submodule pinned to one exact revision of the upstream `asi-alliance/OmegaClaw-Core` project. AlphaClaw does not silently fork it, rebrand its internals, or treat its implementation as AlphaClaw code.

For OmegaClaw installation, operation, internal architecture, channels, providers, tools, and normal behavior, refer to the upstream OmegaClaw documentation and source. Questions or defects intrinsic to OmegaClaw belong upstream.

What this repository owns is narrower:

- the exact upstream revision it chooses to test against;
- the sensory interface presented to a text-reasoning process;
- a deterministic benchmark transform over a disposable local Omega working copy.

```text
perception != authority != inference
```

## 3. Bounded OmegaBoi experiments

`controller/` is benchmark apparatus. It is deliberately **not AlphaClaw** and is not an alternate OmegaClaw implementation.

The supported experiment is one fresh, bounded episode:

```text
one EpisodeContract
       |
       +--> Alpha episode clause: "at most N reasoning loops"
       |
       +--> Omega maxNewInputLoops: N
       |
       +--> host-side provider-call witness: <= N

new user input -> finite grant
send response  -> grant becomes 0
no response by N calls -> terminate failed episode
wake loops -> 0
persistent history -> 0
```

The default contract is 50 reasoning loops. The model is told the bound, but the model does not enforce it: the disposable Omega profile and outer Python runner do.

A real bounded run uses OmegaClaw's native mock communication seam with a real explicitly selected provider:

```bash
export ASIONE_API_KEY=...
python controller/omegaboi.py \
  --text "hello" \
  --provider asione \
  --model asi1-ultra
```

The runner creates a fresh profiled Omega tree, builds Omega's own Docker image from it, delivers one Alpha envelope, records actual provider usage, captures the first user response, stops the container, and writes a run manifest under `benchmark-runs/` unless `--output-dir` is supplied.

For image evidence, Alpha perception happens first and its own OpenRouter token trace is recorded separately:

```bash
export OPENROUTER_API_KEY=...
export ASIONE_API_KEY=...
python controller/omegaboi.py \
  --input-file image.png \
  --provider asione
```

The controller is intentionally the default supported way to produce benchmark claims. A developer who wants standing, autonomous, or otherwise unbounded OmegaClaw must deliberately bypass this apparatus and run upstream OmegaClaw directly. That is allowed, but it is a different population and must not be presented as an AlphaClaw bounded benchmark result.

## 4. ThreadKeeper: benchmark accounting only

`external/ThreadKeeper/` is a second pinned Git submodule. It exists here because Larry Greenblatt's ThreadKeeper already provides the token-accounting seam needed for the experiments.

The benchmark controller mounts ThreadKeeper read-only and uses only its usage recorder/accounting path. ThreadKeeper does not choose providers, route work, set loop bounds, alter the Alpha prepend, select actions, or decide whether an answer is good.

Benchmark accounting is stricter than ThreadKeeper's normal runtime semantics: if a real provider response does not expose usage, or if the usage record cannot be persisted, the benchmark is invalid rather than silently counting zero tokens.

The run keeps both:

- ThreadKeeper-normalized `usage.jsonl` for comparable input/output token counts;
- raw provider `provider_usage.jsonl` so provider-specific cache/reasoning details are not discarded.

## 5. Contributor Wiki

The [AlphaClaw Wiki](https://github.com/PaulTiffany/AlphaClaw/wiki) is the public project notebook.

Its Home page is a small AlphaClaw landing page that humans can improve over time. The beginner open-source lesson lives on the Wiki's **Contributing** page.

A Wiki save changes the Wiki only. It does not run OmegaClaw, become AlphaClaw sensory input, change `main`, or trigger an automatic path into the codebase.

`contributor/README.md` is the short source text mirrored to Wiki `Contributing.md`.

## Local-first controller experiments

`controller/omega_profile.py` inspects the exact pinned Omega source shape and produces a disposable reduced-authority benchmark copy. It fails closed if expected upstream mechanics move.

The bounded profile currently enforces:

```text
boot inference grant:          0
new-human-input grant:         EpisodeContract.max_reasoning_loops
scheduled-wake grant:          0
history recall:                0
persistent history writes:    disabled
model-directed actions:        send only
successful send:               current grant -> 0
dynamic command expansion:    disabled
autonomous goal prompt:        removed
conversation bodies in logs:   removed
```

Live-provider experiments remain human-initiated edge operations. There is no standing repository workflow that spends inference tokens.

## Development invariant

Before adding a mechanism, capability, workflow, resident process, or controller layer, ask:

> **WHY DO WE NEED THAT?**

Documentation machinery has to answer the same question. A runtime capability must also justify the authority it adds.

**Alpha senses. Omega reasons. The benchmark controller bounds. ThreadKeeper measures. Humans authorize and judge.**

## Philosophy

`PHILOSOPHY.md` is the normative human-facing companion to these boundaries. It includes commitments around fallibility, recoverability, provenance, operator slack, capability versus permission, and bounded recursive improvement.

## License and attribution

AlphaClaw original code: MIT © 2026 Paul Carver Tiffany III.

`OmegaClaw-Core` and `external/ThreadKeeper` are upstream works and retain their own upstream licenses, authorship, documentation, and notices.