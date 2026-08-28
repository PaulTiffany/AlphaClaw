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

## Unbounded Omega is a different population

A developer who wants standing/autonomous/unbounded OmegaClaw runs upstream OmegaClaw directly instead of `controller/omegaboi.py`. That is a legitimate choice, but it is outside the bounded benchmark population and must not inherit its measurements or claims.

There is no standing cloud lifecycle controller, upstream watcher, automatic promotion path, or repository workflow that spends provider tokens.

The default development question remains:

> **WHY DO WE NEED THAT?**

For this controller the answer is narrow: configure a stock pinned subject, construct a finite episode, independently cap provider calls, preserve the provider's receipt, ask a borrowed accounting witness to check it, and stop.
