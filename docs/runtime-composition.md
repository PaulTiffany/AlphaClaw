# AlphaClaw runtime composition

AlphaClaw is a boundary around a pinned OmegaClaw resident, not an agent inside it.

```text
human / media
     |
     v
external Python ingress
  - optional one multimodal translation
  - fixed Alpha directions prepended once
     |
     v
minimum-authority pinned OmegaClaw
  - provider: ASIOne
  - model: asi1-mini
  - boot inference cycles: 0
  - cycles per new human input: 8
  - scheduled wake cycles: 0
  - persistent history: off
  - historical recall: 0 chars
  - model-directed actions: send
  - loaded plugins: wschat, asione
```

## Substrate

`OmegaClaw-Core` is a pristine pinned Git submodule. The Hugging Face stage copies the complete
upstream tree except Git metadata. AlphaClaw does not import an Alpha MeTTa library, replace
Omega's runner, patch the generic plugin loader, or install a second control loop.

The staged copy may remove authority without deleting the corresponding upstream implementation.
Presence in source is not permission to the resident model.

## Alpha boundary

Alpha directions are prepared outside the resident by `ingress/prepend.py`. Non-text ingress may
first pass through one external Python translation call such as `ingress/openrouter_image.py`. The
resulting handoff is inert JSON data and is fixed before it crosses into Omega.

Omega has no callback into the Alpha ingress path. If evidence is insufficient, the resident waits
for new human-mediated input rather than autonomously re-running ingress.

## Inference grant

The resident uses Omega's native loop budget:

```yaml
maxNewInputLoops: 8
maxWakeLoops: 0
```

Pinned Omega normally initializes `&loops` to `maxNewInputLoops`. The staged copy starts `&loops`
at `0`, initializes the wake timestamp, and removes the stock `k > 1` condition from the existing
new-message refill. The result is one grant rule:

```text
new human input -> configured finite budget
```

No second counter exists.

## Model-action boundary

The initial safe resident needs one outward model action: communicate with the human. The staged
copy therefore changes Omega's model-command allowlist to exactly:

```text
send
```

The skill prompt exposes the same one action. Dynamic skill aggregation is removed from the model
surface and `add_llm_command` cannot widen the allowlist. A model response such as `shell env`,
`websearch ...`, `write-file ...`, or `metta ...` is rejected by the parser rather than executed.

This is the primary credential boundary: the ASI:One provider process must possess its inference
credential, so model-directed code execution is removed from that process instead of relying on an
instruction not to inspect its environment.

## Plugin boundary

The complete pinned plugin tree remains present, but the staged `plugins.yaml` loads only:

```text
wschat
asione
```

The resident does not load workflow/OpenClaw plugins, alternate providers, IRC, Slack, Telegram,
Mattermost, or the test channel.

## Episode boundary

Stock Omega writes message/response history and can reintroduce it on later turns. The safe resident
does not need that persistence. Staging makes `appendToHistory` a no-op and configures:

```yaml
maxHistory: 0
```

Long-term memory commands (`remember`, `query`, `episodes`) and working-memory `pin` are also absent
from the model-command allowlist.

## Runtime guards

Before health or Omega startup, the HF entrypoint verifies:

- no in-process Alpha library exists;
- boot/refill/wake semantics have not widened;
- the generic Omega plugin loader remains stock;
- the plugin allowlist is exactly `wschat, asione`;
- the model-command allowlist is exactly `send` and cannot be dynamically expanded;
- shell-like output is mechanically rejected by the parser;
- persistent history writes and history recall are disabled;
- alternate-provider/ingress credentials are absent;
- an optional WebSocket endpoint uses `wss://`.

## Invariant

```text
Alpha = external data gate
Omega = bounded reasoner
human input = inference grant authority
runtime = capability authority
```

A mutation inside Omega may change beliefs, plans, or symbolic state. It may not thereby gain more
inference, tools, plugins, credentials, persistence, or Alpha.

Before restoring any removed capability: **WHY DO WE NEED THAT?**
