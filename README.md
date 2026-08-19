# AlphaClaw

**Multimodal at the boundary. Symbolic in the loop. Tool-mediated at the boundary of action.**

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
pinned stock OmegaClaw
  ASI:One / asi1-mini
  boot: 0 inference cycles
  new human input: 8 cycles
  scheduled wake: 0 cycles
```

## The rule

AlphaClaw does three things:

1. translate new non-text evidence once when needed;
2. prepend a fixed boundary contract once;
3. mechanically bound the resident Omega trajectory.

Everything else belongs to OmegaClaw.

There is no `alphaclaw.metta`, no custom Alpha `run.metta`, no Alpha library inside PeTTa, and no
Alpha callback that Omega can invoke. If the resident needs more evidence, it waits for another
human-mediated ingress.

## Pinned Omega

`OmegaClaw-Core/` is a pristine Git submodule pinned to an exact upstream commit. Hugging Face
staging copies the complete pinned source tree except Git metadata. AlphaClaw does not decide that
upstream tests, plugins, channels, or support directories are disposable.

The resident uses Omega's native configuration surface. The bounded HF configuration is:

```yaml
maxNewInputLoops: 8
maxWakeLoops: 0
```

Provider and model are bound at the process boundary as `ASIOne` / `asi1-mini`.

## Human-start gate

Pinned Omega normally begins with `maxNewInputLoops` already available at process startup. That is
broader authority than AlphaClaw intends.

The deployed copy therefore has one narrow semantic adaptation: startup initializes Omega's loop
budget to `0`; stock Omega's existing new-human-message path still refills the budget to
`maxNewInputLoops`. The staged copy also initializes the wake timestamp so the zero-cycle boot path
is defined.

The pinned submodule itself remains unchanged.

```text
boot             -> 0 cycles
new human input  -> 8 cycles
scheduled wake   -> 0 useful inference cycles
```

Inference bounds and capability bounds are separate. The loop budget limits model calls; Omega's
own security/tool policy governs what a model call may touch.

## External ingress

For text, `ingress/prepend.py` produces a data-only JSON envelope containing the fixed Alpha
boundary contract and the human-mediated payload:

```bash
python ingress/prepend.py --text "your message"
```

The whole output is JSON data, not a MeTTa form. Even a payload that looks like MeTTa remains a JSON
string; Alpha never imports or evaluates it.

For non-text evidence, use an external one-call translator first. The existing image path is:

```bash
python ingress/openrouter_image.py \
  --image image.png \
  --output handoff.json

python ingress/prepend.py --input-file handoff.json
```

The multimodal credential belongs to that external ingress process, not to the Omega resident.
The handoff is fixed before Omega sees it.

## Hugging Face resident

`runtime/huggingface/stage.py` deterministically stages the pinned Omega source and the small HF
boundary files. The generated image contains no `/PeTTa/repos/AlphaClaw` library; the runtime
entrypoint fails closed if one appears.

Before Omega starts, the resident also verifies the boot/refill loop cardinalities, verifies that
the stock plugin loader has not acquired the abandoned `once(...)` modification, rejects plaintext
WebSocket endpoints, and refuses any known alternate-provider or multimodal credential in its
environment.

The controller independently scrubs those forbidden credentials from the dedicated Space before
restart and revokes them on OFF. CI verifies that the resident workflow exposes only the intended
ASI:One model credential plus the optional WebSocket token.

The public Space surface is health/status only. Runtime provider credentials are injected at enable
time and revoked before a failed or disabled Space is paused.

## Repository layout

```text
AlphaClaw/
├── OmegaClaw-Core/                 # pristine pinned upstream submodule
├── ingress/
│   ├── prepend.py                  # fixed data-only Alpha envelope
│   └── openrouter_image.py         # optional one-call image translation
├── runtime/huggingface/
│   ├── alphaclaw-runtime.yaml      # Omega-native 8 / 0 dials
│   ├── hf_entrypoint.sh            # runtime bindings + fail-closed guards
│   ├── health.py                   # deployment witness
│   └── stage.py                    # deterministic HF embodiment
├── qualification/                  # bounded resident qualification
├── certification/                  # pinned-source witnesses
├── tests/                          # architectural invariants
├── docs/runtime-composition.md
├── .gitmodules
└── LICENSE
```

## Development invariant

Before modifying an Omega subsystem to make AlphaClaw work, first reproduce the requirement on
vanilla pinned Omega.

```text
Does vanilla pinned Omega exhibit the problem?
        |
   +----+----+
   |         |
   no        yes
   |         |
remove      isolate the smallest
Alpha       compatibility change
complexity  and witness it
```

Alpha is a gate, not a god.

## License

AlphaClaw original code: MIT © 2026 Paul Carver Tiffany III.

`OmegaClaw-Core` remains an upstream dependency and retains its own upstream license and notices.
