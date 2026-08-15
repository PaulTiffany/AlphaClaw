# AlphaClaw

**Multimodal at the boundary. Symbolic in the loop.**

AlphaClaw is an inference-aware composition of **OmegaClaw**, not a reimplementation of it.
The upstream `asi-alliance/OmegaClaw-Core` repository is pinned intact as a Git submodule.
AlphaClaw contributes one architectural mutation: it tells OmegaClaw what inference is currently
resident, then treats richer multimodal inference as tooling to invoke only at the boundary of
need.

```text
multimodal input
      |
      | one translation / handoff call
      v
symbolic + textual state
      |
      v
+------------------+
| stock OmegaClaw  |  <-- resident text inference knows what it is
+------------------+
      |
      +-----------> existing multimodal tooling
                     only when symbolic state is insufficient
```

## The move

OmegaClaw already separates its symbolic loop from LLM providers and supports prompt extensions
and dynamic skills. AlphaClaw uses those extension surfaces instead of forking the cognitive
core.

The central primitive is the **Inference Contract**. Every OmegaClaw context is told:

- which provider is resident;
- which model is resident;
- which modalities the resident inference actually has;
- that multimodal capability is tool-only;
- which multimodal tool/capability is available;
- which symbolic representation the perception boundary should target;
- when the agent may call multimodal inference again.

The agent therefore does not have to infer its own capabilities from a model name. A text-only
reasoner can know that it cannot directly see an image while also knowing that it can call a
vision-capable tool when perception is required.

## Policy

The default AlphaClaw policy is deliberately simple:

1. On first encounter with a new non-text source, make one multimodal translation/handoff call.
2. Preserve literal observations, interpretations, uncertainty, unresolved details, and a handle
   to the original evidence.
3. Continue the trajectory using resident text/symbolic inference.
4. Re-query multimodal tooling only when the symbolic state is insufficient, and make that query
   narrow and evidence-directed.
5. Treat tool output as an observation, not infallible ground truth.

AlphaClaw does **not** implement a competing multimodal stack. Configure it to name and use the
multimodal capability already available in the OmegaClaw deployment.

## Repository layout

```text
AlphaClaw/
├── OmegaClaw-Core/            # pristine pinned upstream submodule
├── alphaclaw.metta            # Inference Contract overlay
├── run.metta                  # stock OmegaClaw + Alpha overlay
├── scripts/
│   └── install-into-petta.sh  # deterministic PeTTa composition
├── tests/                     # architectural invariants
├── .gitmodules
└── LICENSE
```

There is intentionally no AlphaClaw agent framework and no copied OmegaClaw source.

## Install into PeTTa

Clone AlphaClaw where PeTTa expects repository libraries:

```bash
cd /path/to/PeTTa/repos
git clone --recurse-submodules https://github.com/PaulTiffany/AlphaClaw.git
cd AlphaClaw
./scripts/install-into-petta.sh /path/to/PeTTa
```

The installer leaves the pinned submodule inside AlphaClaw and creates the library alias
`PeTTa/repos/OmegaClaw-Core -> AlphaClaw/OmegaClaw-Core`. It refuses to overwrite an unrelated
OmegaClaw checkout. It also installs `run-alphaclaw.metta` at the PeTTa root.

Then run AlphaClaw using the normal OmegaClaw configuration path, for example:

```bash
cd /path/to/PeTTa
OMEGACLAW_AUTH_SECRET=<channel-secret> \
  sh run.sh run-alphaclaw.metta \
  provider=OpenAI \
  model=<text-model> \
  alphaResidentModalities=text-only \
  alphaMultimodalTool="<existing OmegaClaw multimodal capability>"
```

The model field is optional when the selected OmegaClaw provider already has a default. The
Inference Contract resolves OmegaClaw's configured provider and provider-specific default model
when possible.

## Alpha configuration

AlphaClaw reads configuration through OmegaClaw's existing configuration mechanism, so values can
come from command-line arguments, `OMEGACLAW_<key>` environment variables, or a config file.

| Key | Default | Meaning |
| --- | --- | --- |
| `alphaResidentModalities` | `text-only` | Capabilities resident in the reasoning model |
| `alphaMultimodalTool` | `OmegaClaw multimodal tooling` | Human-readable name of the perception capability |
| `alphaSymbolicTarget` | `MeTTa-compatible symbolic/text state` | Target representation for ingress translation |

`provider` and `model` remain ordinary OmegaClaw configuration. AlphaClaw reports them to the
reasoning model instead of silently leaving them in runtime plumbing.

## Hypersprint benchmark

The initial comparison is intentionally narrow:

```text
baseline:    multimodal inference resident throughout trajectory
AlphaClaw:   1 ingress multimodal call + k targeted re-queries + text/symbolic trajectory
```

Measure task success, multimodal calls/tokens, total inference cost, latency, and the number of
perceptual re-queries required.

The interesting question is not whether AlphaClaw has better vision. It is how much vision the
reasoning trajectory actually needs.

## Upstream integrity

CI verifies that `OmegaClaw-Core` is a real Git submodule, that the checked-out SHA matches the
gitlink pinned by AlphaClaw, and that the submodule worktree remains clean. The Alpha overlay is
tested separately.

## License

AlphaClaw original code: MIT © 2026 Paul Carver Tiffany III.

`OmegaClaw-Core` remains an upstream dependency and retains its own upstream license and notices.
