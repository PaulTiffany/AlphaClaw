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
perception != inference != control != measurement != judgment
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
2. Stock Omega receives `maxNewInputLoops=N`, `maxWakeLoops=0`, and `maxHistory=0` through its native configuration path.
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

There is no benchmark memory volume. Each fresh container gets its own disposable writable layer, and `maxHistory=0` removes persistent-history recall from the prompt.

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

## Unbounded Omega is a different population

A developer who wants standing/autonomous/unbounded OmegaClaw runs upstream OmegaClaw directly instead of `controller/omegaboi.py`. That is a legitimate choice, but it is outside the bounded benchmark population and must not inherit its measurements or claims.

There is no standing cloud lifecycle controller, upstream watcher, automatic promotion path, or repository workflow that spends provider tokens.

The default development question remains:

> **WHY DO WE NEED THAT?**

For this controller the answer is narrow: configure a stock pinned subject, construct a finite episode, independently cap provider calls, preserve the provider's receipt, ask a borrowed accounting witness to check it, and stop.
