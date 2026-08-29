# AlphaClaw — research checkpoint

A bounded-benchmark controller that runs **stock, unmodified OmegaClaw** in Docker while
externally metering and bounding it, to test one architectural question:

> Can multimodal perception be externalised once, at ingress, so that downstream
> reasoning runs text-only — and does that decomposition hold up, and buy anything?

Protocols **v2** and **v3** are complete, frozen, and mechanically verifiable. This
document is the entry point; you should not need to read PRs #30–#50 in order.

Verify everything offline, with no API key and no cost:

```
python scripts/verify_research_checkpoint.py
```

---

## Architecture

AlphaClaw separates perception from reasoning around a pinned substrate:

```
multimodal perception  ->  symbolic handoff  ->  text-only resident reasoning
```

The multimodal model is used at ingress. Downstream reasoning operates on the symbolic
handoff alone. **Stock OmegaClaw stays pinned and unmodified**; all bounding, metering
and receipt-keeping is host-side machinery outside it.

The economic shape this buys, at reasoning depth *N*:

```
AlphaClaw (perceive once)                 multimodal-resident baseline

image + task                              image + task   -> multimodal turn 1
     |                                    image + state  -> multimodal turn 2
     v                                    image + state  -> multimodal turn 3
multimodal sensory inference  (once)      ...
     |                                    image + state  -> multimodal turn N
     v
symbolic handoff                          => N multimodal calls
     |
     +--> text resident turn 1
     +--> text resident turn 2
     +--> ...
     +--> text resident turn N

=> 1 multimodal call + N text calls
```

The perception call is an architectural setup cost, not one of the *N* reasoning steps,
so AlphaClaw issues `N + 1` provider calls per episode against the baseline's `N`.

---

## V2 — is the decomposition operationally stable?

**Question.** Does the decomposition survive explicit sensory- and resident-model
substitution, holding tasks and architecture fixed?

| condition | result |
|---|---|
| **B1** alternate Qwen sensory boundary | **40/40** correct over scoreable facts, coverage **40/42** |
| **A** primary (dots + MiniMax) | text control **6/6**, image+text **5/6** |
| **B2** sensory substitution | **0/3** paired outcome transitions |
| **C** resident substitution | **3/3** PASS → FAIL |

> **Under the tested bounded conditions, outcomes were more robust to sensory-model
> substitution than to resident-model substitution.**

That is a statement about these conditions, not a universal ranking of models.

The single Condition A failure is instructive: `distractor_selection` had mechanically
correct sensory evidence (4/4) and the correct token `RED` present internally, but the
resident emitted it as an invalid skill call rather than through the channel. The same
failure survived swapping the sensory model, and a sibling failure appeared under a
different resident — so **output-channel behaviour is observable independently of sensory
correctness**.

## V3-A — why do downstream failures occur?

18 runs, zero new sensory calls, four representation variants crossed with one- and
two-turn budgets, replaying frozen v2 evidence.

**The cause was not isolated.** Representation and turn-budget manipulations produced
transitions in *both* directions, and with one run per cell those effects are not
separable from run-to-run variability. The correct-token/no-valid-emission signature
reproduced **twice**.

> **V3-A did not isolate a unique cause for the downstream failures, but it reproduced
> the correct-token-without-valid-emission signature under multiple diagnostic
> conditions.**

This is a limitation of the tranche — it lacked repeats — and **not** evidence of
architecture instability. The failure surface spans the whole seam:
`Alpha representation/instruction -> resident model -> stock OmegaClaw skill/action
contract`, and no single link was isolated.

## V3-B — does perceive-once buy anything?

One model (`qwen/qwen3.7-flash`) serves all three arms, so capability and price schedule
are identical and only input modality per call varies.

**Multimodal inference avoided** (architectural, price-independent):

| N | E1 multimodal | E2 multimodal | avoided | avoidance |
|---|---:|---:|---:|---:|
| 1 | 1 | 1 | 0 | 0% |
| 2 | 2 | 1 | 1 | 50% |
| 4 | 4 | 1 | 3 | 75% |
| 8 | 8 | 1 | 7 | 87.5% |

**Measured savings** from OpenRouter receipts:

| N | E1 | E2 | measured |
|---|---:|---:|---:|
| 1 | $0.000284 | $0.000292 | **-2.7%** |
| 2 | $0.000174 | $0.000136 | **+22.0%** |
| 4 | $0.000789 | $0.000489 | **+38.0%** |
| 8 | $0.001500 | $0.000943 | **+37.1%** |

At **N=4 and N=8** both arms had equal success counts (2/2), and AlphaClaw achieved them
at lower measured cost per successful episode ($0.000245 vs $0.000394; $0.000472 vs
$0.000750).

Run outcomes: **20 completed successes · 4 upstream availability failures · 0 wrong
answers.**

> **Perceive once, reason many: AlphaClaw held multimodal inference to one perception
> call per episode while the multimodal-resident baseline scaled with reasoning depth.**

The loss at N=1 is the hypothesis working as stated, not evidence against it: one fixed
perception cost is amortised over subsequent cheaper text-only calls. The measured sign
changed between N=1 and N=2; no break-even point is interpolated.

---

## Claims and non-claims

| supported by the frozen evidence | not established |
|---|---|
| the symbolic boundary operated across the tested sensory substitutions | any universal model ranking |
| sensory substitution caused **0/3** paired transitions (v2 B2) | a universal break-even at N=2 |
| resident substitution caused **3/3** transitions (v2 C) | that AlphaClaw is always cheaper |
| the downstream emission failure surface is observable independently of sensory correctness | that AlphaClaw is always more accurate |
| V3-A did not isolate a unique cause | that symbolic representation *causes* the emission failures |
| perceive-once reduced multimodal calls according to depth | that stock Omega alone *causes* the emission failures |
| measured cost was lower at N=2/4/8 in this Qwen/OpenRouter experiment | that Qwen pricing generalises to other providers |
| equal-success E1/E2 cells at N=4/8 favoured AlphaClaw on measured cost per success | that all perceive-once architectures show the same economics |

---

## Reproducing this research

### Reproduce the published analysis — no API key, no cost

```
python -m pip install pytest==9.1.1 ruff==0.16.4    # the exact versions CI uses
python scripts/verify_research_checkpoint.py
python -m pytest -q
```

This verifies the committed receipts and artifacts and re-derives every headline number
from them. It makes **no** provider call, launches **no** container, and needs **no**
credentials.

The raw evidence — provider receipts, run manifests, container-side observations, the
stimulus bytes and the ground truth — is deliberately committed. Scientific claims can
therefore be audited **without trusting current provider availability or current model
behaviour**, both of which drift.

### Re-run the experiments — requires credentials and costs money

Separate, and deliberately not the default path. Re-running requires ASICloud and/or
OpenRouter credentials in `.env`, launches Docker containers, and spends real money
against live endpoints. Model behaviour and provider availability will have changed, so a
re-run is a *new* experiment, not a reproduction of this one. See `LOCAL_SETUP.md` and
`controller/README.md` for the protocol, caps and stop conditions that governed each
tranche.

---

## Preregistration amendments

Four amendments were made. Each is recorded as process evidence, not hidden.

| id | subject | discovered | relative to inference | changed | unchanged |
|---|---|---|---|---|---|
| **v2.1** | B2 replay-source selection | after B1 completed | **before** any B2 call | froze "replay repeat 0 only", no fall-through, no quality-based selection | stimuli, models, B2 items, scorer, boundary, B1 results, caps |
| **v2.2** | B2 composition replay | during B2 preflight | **before** any B2 call | defined the composed payload as frozen instruction + frozen handoff, byte-identical to the live route | B2 items, repeat-0 rule, handoff bytes, task text, models, scorer, caps, live ingress |
| **v3.1** | answer-leak check | during V3-A preflight | **before** any V3-A call | word-anchored the check; a bare substring wrongly flagged `19` inside an image digest | representations, transforms, models, budgets, conditions |
| **v3.2** | reasoning-step parity | after V3-A, during V3-B freeze | **before** any V3-B call and before the population was frozen | Protocol v3 defined E2 twice; ruled reasoning-step parity, `C_Alpha(N) = C_multimodal + N·C_text` | architectures, models, task family, depths, repeats, providers, call structure, caps |

Two of the four were contradictions inside the frozen protocol itself, found by preflight
before any money was spent. Preregistration is what made them findable.

---

## Evidence index

`benchmark/research-checkpoint.json` indexes every frozen artifact by SHA256, plus the
substrate identifiers, the amendment locations and the synthesis merge commits. It is an
**index, not a second source of results** — anything derivable is derived from the
artifacts it points at, so there is exactly one source of truth per number.

Substrate, read back from the committed run manifests and asserted single-valued across
every tranche:

| | |
|---|---|
| OmegaClaw | `3d711e4b9f5254ae94f31123ca242f60cfd97d29` |
| ThreadKeeper | `a64de99e10f9f8078d25bff511b44fd71819e931` |
| stock image | `sha256:69ff11bf227b197f697aab4488e879258560730565838b19db25e3dd580af90a` |

Derivation modules: `scripts/synthesis_v2.py`, `scripts/synthesis_v3.py`.
Detailed per-tranche results live in `controller/README.md`.
