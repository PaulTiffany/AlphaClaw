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
    -> one stock Omega Docker image
    -> fresh container per episode
    -> native Omega runtime bounds
    -> host-side lifecycle + provider-call bound

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

For an image:

```bash
export OPENROUTER_API_KEY=...
python ingress/pipe.py --input-file image.png
```

Unsupported media fails closed rather than being guessed at.

The fixed prepend tells OmegaClaw that its handoff is text-only evidence. OmegaClaw must not pretend that the handoff itself provides direct image, audio, video, or other multimedia perception; further multimedia perception requires an explicitly authorized external perception tool.

The controller may fill one explicit `episode_contract` slot in that envelope during bounded experiments. It cannot replace or mutate Alpha's fixed sensory contract.

AlphaClaw does not own the reasoning loop, lifecycle, memory, permissions, deployment, model selection, or recursive authorization.

## 2. OmegaClaw: pinned upstream dependency

This repository does **not** implement OmegaClaw.

`OmegaClaw-Core/` is a pristine Git submodule pinned to one exact revision of the upstream `asi-alliance/OmegaClaw-Core` project. AlphaClaw does not silently fork it, rebrand its internals, or treat its implementation as AlphaClaw code.

The benchmark runner likewise does **not** rewrite a disposable Omega tree. It builds and reuses OmegaClaw's own Dockerfile from the exact pinned source, then starts a fresh container for each measured episode. The image is the experimental subject; runtime configuration is the treatment fixture.

For OmegaClaw installation, operation, internal architecture, channels, providers, tools, and normal behavior, refer to the upstream OmegaClaw documentation and source. Questions or defects intrinsic to OmegaClaw belong upstream.

```text
perception != authority != inference
```

## 3. Bounded OmegaBoi experiments

`controller/` is benchmark apparatus. It is deliberately **not AlphaClaw** and is not an alternate OmegaClaw implementation.

The controller uses OmegaClaw's own runtime configuration seam:

```text
maxNewInputLoops = N
maxWakeLoops = 0
maxHistory = 0
wakeupInterval > episode timeout
commchannel = test
provider = OpenAIAPI
```

The default post-handoff grant is **1 reasoning loop**. Deliberate iterative experiments may request more, up to a hard controller ceiling of 50.

OmegaClaw's normal startup reasoning is not raced away or patched out. It runs as stock Omega and is metered separately as `boot` usage. After the Alpha handoff, provider calls are recorded as `episode` usage. The host-side provider gateway refuses to forward episode call `N + 1`, so the model is told the bound, stock Omega is configured with the same bound, and a separate external witness caps paid calls.

The controller also sets the first scheduled wake later than the entire allowed episode lifetime. The fresh container is stopped after the first post-handoff user response, provider-budget exhaustion, provider/accounting failure, or timeout. This makes the upstream `1 + maxWakeLoops` wake behavior unreachable during a valid one-shot benchmark without modifying Omega.

A real run is human-initiated and requires an explicit provider credential. Example with ASI:One:

```bash
export ASIONE_API_KEY=...
python controller/omegaboi.py \
  --text "hello" \
  --provider asione \
  --model asi1-ultra
```

ASI Cloud, OpenRouter, OpenAI, and a custom OpenAI-compatible endpoint are also available through the same stock Omega `OpenAIAPI` provider seam. For a custom endpoint:

```bash
export OPENAIAPI_API_KEY=...
python controller/omegaboi.py \
  --text "hello" \
  --provider openaiapi \
  --openaiapi-url http://host-or-service.example/v1 \
  --model your-model
```

For image evidence, Alpha perception happens first and its sensory trace is recorded separately:

```bash
export OPENROUTER_API_KEY=...
export ASIONE_API_KEY=...
python controller/omegaboi.py \
  --input-file image.png \
  --provider asione
```

### One image, fresh containers

The first local run builds a Docker image tagged from the pinned Omega SHA. Later runs reuse that exact local image unless `--rebuild-image` is explicitly requested.

Each episode gets a fresh container from that image and no persistent Omega memory volume. Omega's own memory writes can occur inside the container, but `maxHistory=0` prevents persistent-history recall and the writable layer is destroyed with the container.

The run manifest records the pinned Omega SHA and the concrete Docker image ID so a benchmark population can be tied to one actual execution substrate.

The controller is intentionally the default supported way to produce benchmark claims. A developer who wants standing, autonomous, or otherwise unbounded OmegaClaw must deliberately bypass this apparatus and run upstream OmegaClaw directly. That is allowed, but it is a different population and must not be presented as an AlphaClaw bounded benchmark result.

## 4. ThreadKeeper: benchmark accounting only

`external/ThreadKeeper/` is a second pinned Git submodule. It exists here because Larry Greenblatt's ThreadKeeper already provides the token-accounting seam needed for the experiments.

ThreadKeeper now stays on the **host side**. The provider gateway uses only `BudgetTracker.record_from_openai_response(...)` after a real upstream response. Nothing from ThreadKeeper is copied into or mounted inside Omega.

ThreadKeeper does not choose providers, route work, set loop bounds, alter the Alpha prepend, select actions, or decide whether an answer is good.

Benchmark accounting is stricter than ThreadKeeper's normal runtime semantics: if a real provider response does not expose usage, or if the usage record cannot be persisted, the benchmark is invalid rather than silently counting zero tokens.

Outputs include:

```text
manifest.json
alpha-envelope.json
ingress-trace.json
usage.jsonl              # ThreadKeeper-normalized counts
provider_usage.jsonl     # raw provider usage + boot/episode phase
container.log
response.txt             # when a post-handoff response was emitted
```

## 5. Contributor Wiki

The [AlphaClaw Wiki](https://github.com/PaulTiffany/AlphaClaw/wiki) is the public project notebook.

Its Home page is a small AlphaClaw landing page that humans can improve over time. The beginner open-source lesson lives on the Wiki's **Contributing** page.

A Wiki save changes the Wiki only. It does not run OmegaClaw, become AlphaClaw sensory input, change `main`, or trigger an automatic path into the codebase.

`contributor/README.md` is the short source text mirrored to Wiki `Contributing.md`.

## Local-first controller experiments

The controller keeps the experimental fixture outside the subject:

```text
HOST
  Alpha ingress
  episode contract
  provider meter / ThreadKeeper
  communication endpoint
  start -> observe -> stop lifecycle
          |
          v
FRESH CONTAINER
  stock pinned OmegaClaw
  stock prompt and skills
  stock security profile
  stock OpenAIAPI provider
  runtime configuration only
```

This is not a claim that stock OmegaClaw is intrinsically safe. It is a claim that the benchmark does not hide a fork of the thing it says it is studying. Omega's own container isolation and security profile remain in force, while the outer controller supplies the finite experimental boundary.

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
