# Bounded benchmark controller

This directory is **not AlphaClaw** and not OmegaClaw.

AlphaClaw is the sensory/prepend boundary in `ingress/`. OmegaClaw itself is the pinned upstream `OmegaClaw-Core/` submodule. `controller/` is the experimental apparatus used to construct and run bounded OmegaClaw benchmark episodes.

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
fresh bounded OmegaBoi
    |
    v
user response / failed finite episode

SEPARATE OBSERVATION SEAM:
external/ThreadKeeper -> provider usage accounting
```

The separation remains:

```text
perception != authority != inference
```

and, for benchmarks:

```text
measurement != control
```

## One contract, three witnesses

`episode_contract.py` is the source of truth for the bounded experiment. The default is 50 reasoning loops, zero wake loops, zero persistent-history recall, and `wait_for_new_user_input_or_terminate` after a response.

The same contract is represented three ways:

1. Alpha includes a plain-language/structured episode clause in its fixed JSON envelope.
2. `omega_profile.py` writes the same `max_reasoning_loops` into the disposable Omega loop grant.
3. `omegaboi.py` counts actual metered provider calls and refuses a run that exceeds the declared grant.

The model is told the bound. The model does not enforce the bound.

A successful `send` inside the profiled Omega copy mechanically sets the current loop grant to zero. With no autonomous wake loops, the process must then wait for genuinely new user input; the one-shot benchmark runner tears the container down after collecting that response.

## Inspect upstream state

`inspect_omega.py` reports source-state facts that help determine what interference a controller would need:

```bash
python controller/inspect_omega.py --source OmegaClaw-Core
```

Its output is **not a safety certificate and not authorization to run or deploy anything**.

## Create a disposable bounded profile

Credential-free mechanical inspection still works without running a provider:

```bash
python controller/omega_profile.py \
  --source OmegaClaw-Core \
  --destination /tmp/omegaclaw-profiled \
  --max-loops 50
```

The profile applies these benchmark constraints:

```text
boot inference grant:          0
new-human-input grant:         chosen finite loop budget
scheduled-wake grant:          0
history recall:                0
persistent history writes:    disabled
model-directed actions:        send only
successful send:               current grant -> 0
dynamic command expansion:    disabled
autonomous goal prompt:        removed
conversation bodies in logs:   removed
```

The controller refuses to transform an unexpected or dirty Omega source tree. It uses exact-source substitutions so upstream mechanical drift becomes a visible failure.

## Run one real bounded OmegaBoi episode

`omegaboi.py` is the default supported benchmark runner. A provider must be selected explicitly; there is no default API spend.

Example with ASI:One:

```bash
export ASIONE_API_KEY=...
python controller/omegaboi.py \
  --text "hello" \
  --provider asione \
  --model asi1-ultra
```

Example with image evidence:

```bash
export OPENROUTER_API_KEY=...
export ASIONE_API_KEY=...
python controller/omegaboi.py \
  --input-file image.png \
  --provider asione
```

For each run the controller:

```text
verify pinned pristine Omega + ThreadKeeper
        |
        v
create one EpisodeContract
        |
        +--> prepare Alpha envelope
        |
        +--> create fresh bounded Omega tree
        |
        v
build Omega's native Dockerfile
        |
        v
start native mock communication channel + real chosen provider
        |
        v
send exactly one Alpha envelope
        |
        v
first response OR finite-budget failure
        |
        v
stop container and write manifest/accounting
```

The native Omega mock communication seam keeps benchmark traffic deterministic and programmatic. The provider call itself is real.

## ThreadKeeper accounting

`external/ThreadKeeper/` is mounted read-only into the benchmark container. `omega_profile.py --meter` inserts a tiny provider-boundary adapter into the disposable copy. The adapter calls ThreadKeeper's `BudgetTracker.record_from_openai_response(...)` after each real provider response.

It does not use ThreadKeeper's routing or escalation policy.

Benchmark semantics are deliberately stricter than ThreadKeeper runtime semantics: missing provider usage or a failed accounting write invalidates the run.

Outputs include:

```text
manifest.json
alpha-envelope.json
ingress-trace.json
usage.jsonl              # ThreadKeeper-normalized input/output counts
provider_usage.jsonl     # raw provider usage details
container.log
response.txt             # when a response was emitted
```

## The unbounded population is explicit

This controller does not silently turn itself off.

A developer who wants standing/autonomous/unbounded OmegaClaw runs upstream OmegaClaw directly instead of `controller/omegaboi.py`. That is a legitimate experiment or deployment choice, but it is outside the bounded benchmark population and must not inherit its measurements or claims.

There is no standing cloud lifecycle controller, upstream watcher, automatic promotion path, or repository workflow that spends provider tokens.

The default development question remains:

> **WHY DO WE NEED THAT?**

For this controller the answer is narrow: construct a fresh finite experiment, tell Omega the true experimental boundary, mechanically enforce the same boundary, measure what happened, and stop.