# Bounded benchmark controller

This directory is **not AlphaClaw** and not OmegaClaw.

AlphaClaw is the sensory/prepend boundary in `ingress/`. OmegaClaw itself is the pinned upstream `OmegaClaw-Core/` submodule. `controller/` is the host-side experimental apparatus used to run finite benchmark episodes against **stock OmegaClaw**.

```text
world / human
    |
    v
AlphaClaw sensory boundary
    |
    v
fixed text-only envelope
    |
    +-- controller-issued EpisodeContract
    |
    v
fresh stock Omega container
    |
    v
user response / failed finite episode

SEPARATE OBSERVATION SEAM:
provider gateway -> external/ThreadKeeper accounting
```

The separation remains:

```text
perception != authority != inference
measurement != control
```

## No Omega source transform

The controller does not create a profiled Omega tree. `omega_profile.py` is intentionally gone.

One Docker image is built from the exact pinned `OmegaClaw-Core/` tree using OmegaClaw's own Dockerfile. That image is reused across runs. Every episode starts a fresh container from it and uses OmegaClaw's documented runtime configuration path.

The runner verifies the Omega and ThreadKeeper gitlinks are exact and clean before making a benchmark claim.

## Episode contract

`episode_contract.py` is the source of truth for the finite human-input grant.

Defaults:

```text
post-handoff reasoning loops:  50
hard controller ceiling:       50
maxWakeLoops:                  0
maxHistory:                    0
after response:                stop this one-shot episode
boot behavior:                 stock Omega; meter separately
```

Fifty is not a requirement to spend fifty calls. It preserves the pinned OmegaClaw iterative default as the ceiling; the controller tears the container down after the first user response. Smaller deliberate bounds such as `--max-loops 1` or `--max-loops 7` remain available for targeted experiments.

The same contract is represented three ways:

1. Alpha includes a plain-language/structured episode clause in its fixed JSON envelope.
2. The fresh stock Omega container receives `maxNewInputLoops=N`, `maxWakeLoops=0`, and `maxHistory=0` as native runtime configuration.
3. The host-side provider gateway refuses to forward post-handoff provider call `N + 1`.

The model is told the bound. The model does not enforce the bound.

## Stock boot behavior

OmegaClaw normally starts with `&loops = maxNewInputLoops` before any human message. The benchmark does not race, delete, or patch that behavior.

The provider gateway begins in `boot` phase and meters the first stock startup inference. As soon as that upstream boot response reaches the host gateway, the controller queues the prepared Alpha envelope into Omega's native test channel. The current boot response is still being processed, so the next stock `receive()` sees genuinely new human input without a source patch or boot-sequence race.

The controller waits for Omega's second-iteration log marker only to separate any public messages emitted while processing the boot response. Alpha has already been queued at that point; the marker is not used to time injection.

Boot usage remains visible and separate from the human-input grant.

## Wake behavior

Pinned Omega currently grants `1 + maxWakeLoops` when its scheduled wake fires, so `maxWakeLoops=0` is not itself a proof of zero future wake inference.

The one-shot fixture therefore also sets:

```text
wakeupInterval > whole episode timeout
```

and destroys the fresh container on response, budget exhaustion, failure, or timeout. The scheduled wake is outside the reachable lifetime of a valid benchmark episode.

## Provider and ThreadKeeper seam

Omega stays stock and uses its built-in `OpenAIAPI` provider. That documented generic provider seam points to a tiny host-side OpenAI-compatible gateway over `host.docker.internal`.

The gateway:

```text
stock Omega OpenAIAPI request
        |
        +--> checks fixed benchmark model
        +--> applies external post-handoff call ceiling
        |
        v
real selected upstream provider
        |
        v
actual provider response + usage
        |
        +--> ThreadKeeper Record / Account
        +--> raw provider_usage.jsonl
        |
        v
unchanged response back to stock Omega
```

This intentionally studies stock Omega through its generic OpenAI-compatible provider seam; it does not claim to reproduce provider-specific Omega plugins such as ASI:One thinking options or OpenRouter cache policy. Keeping that distinction explicit avoids another runtime overlay solely for metering.

For OpenRouter the gateway asks the upstream response to include usage accounting. For all providers, missing usage invalidates the benchmark instead of being treated as zero.

ThreadKeeper stays on the host. Nothing from ThreadKeeper is copied into or mounted inside Omega. Its routing, escalation, subagents, and policy decisions are not used.

## Run one real bounded episode

Example with ASI:One:

```bash
export ASIONE_API_KEY=...
python controller/omegaboi.py \
  --text "hello" \
  --provider asione \
  --model asi1-ultra
```

Example with ASI Cloud:

```bash
export ASI_API_KEY=...
python controller/omegaboi.py \
  --text "hello" \
  --provider asicloud
```

Example with a one-call human-input grant:

```bash
python controller/omegaboi.py \
  --text "answer once" \
  --provider asione \
  --max-loops 1
```

Example with image evidence:

```bash
export OPENROUTER_API_KEY=...
export ASIONE_API_KEY=...
python controller/omegaboi.py \
  --input-file image.png \
  --provider asione
```

The hard controller ceiling is 50.

## One image, fresh state

The first run builds:

```text
alphaclaw-omega-stock:<pinned-sha-prefix>
```

from OmegaClaw's own Dockerfile. Later runs reuse that exact local image unless `--rebuild-image` is explicitly requested.

There is no benchmark memory volume. Each fresh container gets its own disposable writable layer, so stock Omega may use its normal working memory during the episode without state leaking into the next episode. `maxHistory=0` also removes persistent history from the prompt.

Outputs include:

```text
manifest.json
alpha-envelope.json
ingress-trace.json
usage.jsonl              # ThreadKeeper-normalized counts
provider_usage.jsonl     # raw usage with boot/episode phase
container.log
response.txt             # when a response was emitted after handoff
```

The manifest records the exact Omega SHA, ThreadKeeper SHA, Alpha commit, local Docker image ID, runtime episode contract, provider/model, gateway state, usage by phase, and termination reason.

## Inspect upstream state

`inspect_omega.py` reports source-state facts without changing Omega:

```bash
python controller/inspect_omega.py --source OmegaClaw-Core
```

Its output is **not a safety certificate and not authorization to run or deploy anything**.

## The unbounded population is explicit

This controller does not silently turn itself off.

A developer who wants standing/autonomous/unbounded OmegaClaw runs upstream OmegaClaw directly instead of `controller/omegaboi.py`. That is a legitimate experiment or deployment choice, but it is outside the bounded benchmark population and must not inherit its measurements or claims.

There is no standing cloud lifecycle controller, upstream watcher, automatic promotion path, or repository workflow that spends provider tokens.

The default development question remains:

> **WHY DO WE NEED THAT?**

For this controller the answer is narrow: configure a stock pinned subject, construct a fresh finite episode, tell Omega the true boundary, independently cap paid post-handoff calls, measure what happened with borrowed accounting, and stop.
