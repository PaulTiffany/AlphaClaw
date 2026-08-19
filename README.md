# AlphaClaw

**Multimodal at the boundary. Symbolic in the loop. Authority outside the loop.**

AlphaClaw is a small boundary around a pinned **OmegaClaw** resident. It is not a second agent,
not an Omega fork, and not an Alpha process living inside Omega's symbolic state.

```text
human / media
      |
      v
external Python ingress
  optional one multimodal translation
  + fixed Alpha directions
      |
      v
minimum-authority OmegaClaw resident
  ASI:One / asi1-mini
  boot: 0 inference cycles
  new human input: 8 cycles
  scheduled wake: 0 cycles
  model action: send only
  persistent history: off
```

## The rule

AlphaClaw does three things:

1. translate new non-text evidence once when needed;
2. prepend a fixed boundary contract once;
3. mechanically bound the resident Omega trajectory and authority surface.

Everything else belongs to OmegaClaw.

There is no `alphaclaw.metta`, no custom Alpha `run.metta`, no Alpha library inside PeTTa, and no
Alpha callback that Omega can invoke. If the resident needs more evidence, it waits for another
human-mediated ingress.

## Pinned Omega

`OmegaClaw-Core/` is a pristine Git submodule pinned to an exact upstream commit. Hugging Face
staging copies the complete pinned source tree except Git metadata. The upstream submodule itself
is never edited.

The deployed copy deliberately narrows authority. Source implementations may remain present in the
pinned tree without being model-callable.

The HF configuration is:

```yaml
maxNewInputLoops: 8
maxWakeLoops: 0
maxHistory: 0
```

Provider and model are bound at the process boundary as `ASIOne` / `asi1-mini`.

## Human-start gate

Pinned Omega normally begins with `maxNewInputLoops` available at process startup. AlphaClaw starts
with zero instead. Every genuinely new human message, including one received on the first loop
iteration, grants the configured finite trajectory.

```text
boot             -> 0 cycles
new human input  -> 8 cycles
scheduled wake   -> 0 useful inference cycles
```

No second counter is introduced.

## Minimum authority

The first resident experiment needs to reason over human-supplied evidence and communicate the
result. It does not need arbitrary shell, web search, file mutation, arbitrary MeTTa evaluation,
dynamic model commands, or long-term memory.

The staged resident therefore exposes exactly one model-directed action:

```text
send
```

Omega's command parser rejects other model output as an unknown skill. Dynamic command registration
cannot widen the set from inside mutable Omega state.

Only two Omega plugins are loaded:

```text
wschat   # the configured human communication channel
asione   # the configured resident inference provider
```

Workflow/OpenClaw plugins, alternate providers, and unused communication channels remain in the
pinned source tree but are not loaded into the resident.

Persistent history writes are disabled in the staged copy and `maxHistory: 0` prevents historical
recall. `remember`, `query`, `episodes`, and `pin` are not model-callable.

The ASI:One key is still necessarily present in the resident provider process. The security control
is therefore to remove model-directed code execution and alternate network/tool sinks rather than
pretend the credential is isolated from the process that must use it.

## External ingress

For text, `ingress/prepend.py` produces a data-only JSON envelope containing the fixed Alpha
boundary contract and the human-mediated payload:

```bash
python ingress/prepend.py --text "your message"
```

The whole output is JSON data, not a MeTTa form. Even a payload that looks like MeTTa remains a JSON
string; Alpha never imports or evaluates it.

For non-text evidence, use an external one-call translator first:

```bash
python ingress/openrouter_image.py \
  --image image.png \
  --output handoff.json

python ingress/prepend.py --input-file handoff.json
```

The multimodal credential belongs to that external ingress process, not to the Omega resident. The
handoff is fixed before Omega sees it.

## Hugging Face resident

`runtime/huggingface/stage.py` deterministically stages the pinned Omega source and the small HF
boundary files. The generated image contains no `/PeTTa/repos/AlphaClaw` library; the runtime
entrypoint fails closed if one appears.

Before Omega starts, the resident verifies the loop grant, plugin allowlist, model-action allowlist,
history non-persistence, stock plugin-loader semantics, WSS transport, and credential allowlist.
The controller independently scrubs forbidden alternate-provider/ingress credentials before
restart and revokes runtime credentials on OFF.

The public Space surface is health/status only. The Space remains a deployment target, not an Alpha
agent.

## Development invariant

Before adding or restoring a capability, ask:

```text
WHY DO WE NEED THAT?
```

If the minimum experiment works without it, leave it absent. If a change requires Alpha code inside
Omega's mutable state, expands model-directed authority, changes plugin semantics, or adds a second
lifecycle authority, reject it until a minimal control experiment proves the requirement.

**Alpha is a gate, not a god.**

## License

AlphaClaw original code: MIT © 2026 Paul Carver Tiffany III.

`OmegaClaw-Core` remains an upstream dependency and retains its own upstream license and notices.
