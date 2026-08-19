# AlphaClaw runtime composition

AlphaClaw is an overlay on a complete pinned OmegaClaw substrate. Hugging Face is only the current embodiment.

```text
AlphaClaw repository
├── OmegaClaw-Core @ pinned SHA   complete upstream substrate
├── alphaclaw.metta               Alpha directions / prompt extension
├── run.metta                     composition point
└── runtime/huggingface/
    ├── alphaclaw-runtime.yaml     Alpha-selected Omega dials
    ├── hf_entrypoint.sh           secret/runtime binding
    └── stage.py                   deterministic HF embodiment
```

## 1. Substrate: pinned OmegaClaw

`OmegaClaw-Core` is authoritative upstream code. The HF staging path copies the complete pinned source tree except Git metadata. AlphaClaw does not decide that an upstream directory is runtime-irrelevant merely because its name looks like tests, examples, or development support. If upstream startup imports it, it is part of the substrate.

The submodule SHA is the source identity. Staging may make narrowly documented embodiment adaptations, but the submodule itself remains pristine.

## 2. Directions: append through Omega's prompt-extension surface

AlphaClaw does not replace Omega's loop or base prompt. `run.metta` registers and imports the pinned Omega library, then imports `AlphaClaw/alphaclaw.metta`.

`alphaclaw.metta` defines:

```metta
(= (prompt-extension alphaclaw-inference-contract)
   (alpha-inference-contract))
```

Omega's own `getContext` evaluates `(prompt-extension $_)` and appends the resulting text to the context. That is the Alpha instruction seam: stock Omega prompt + stock skills + Alpha contract.

## 3. Dials: use Omega's configuration surface

AlphaClaw changes Omega behavior through Omega's existing configuration mechanism rather than a second control loop.

Omega resolves a configuration key in this order:

1. command-line `key=value`
2. `OMEGACLAW_<key>` environment variable
3. the selected YAML config file
4. Omega default

For the HF resident, `OMEGACLAW_config` points to `runtime/huggingface/alphaclaw-runtime.yaml`. Mechanically important Alpha-selected values belong there when possible so they remain typed, reviewable, and witnessed. The current finite-life dials are:

```yaml
maxNewInputLoops: 8
maxWakeLoops: 0
```

The HF entrypoint currently binds deployment-specific selections such as resident provider/model/channel and translates secret names at the process boundary. Because command-line values outrank YAML, any value supplied there is the effective Omega value and must be treated as part of the embodiment contract.

AlphaClaw must not maintain a second shadow copy of an Omega dial. Its prompt contract reads the same Omega configuration values that govern the loop.

## 4. Embodiment: Hugging Face

The HF Space is a deployment artifact, not the source of agent semantics. Staging performs four jobs:

1. verify the exact pinned Omega SHA and a pristine submodule;
2. copy the complete upstream substrate into the image;
3. add the Alpha overlay and Alpha-selected config without editing the submodule;
4. make only narrowly required HF compatibility adaptations and expose health/provenance witnesses.

Runtime credentials are injected separately and are revoked before a failed resident is paused.

## Composition invariant

```text
complete pinned Omega
        +
Alpha prompt extension
        +
Omega-native configuration dials
        +
embodiment bindings / secrets
        =
AlphaClaw resident
```

If a proposed change edits Omega cognition to express Alpha policy, creates a second lifecycle counter, or deletes pieces of the pinned substrate based on an Alpha-side guess, it is probably crossing the wrong seam.
