# OmegaClaw residency certification

This directory answers a question that comes **before** model benchmarking:

> What powers does this exact OmegaClaw revision require from a resident model?

`certify.py` inspects an OmegaClaw source tree and emits a JSON certificate tied to the exact
Git SHA. Each derived resident power is backed by explicit source witnesses (file, line, and
source token). If an upstream edit removes one of those witnesses, certification fails rather
than silently preserving an obsolete assumption.

## What this certifies

The certificate separates two things:

1. **Observed OmegaClaw mechanics** — source facts such as S-expression parsing, repeated tool
   feedback, dynamic skills, I/O policy checks, verified file writes, and context limits.
2. **Derived resident powers** — the minimum behavioral capabilities implied by those mechanics,
   such as symbolic command fidelity, multi-turn tool-result continuation, error recovery, and
   context endurance.

It does **not** certify that any model possesses those powers. Model qualification belongs in the
benchmark/qualification layer.

It also deliberately does not declare workload-specific abilities such as "good at JSON" or
"can build a genealogy knowledge graph" to be OmegaClaw requirements unless OmegaClaw itself
mechanically requires them. Those are candidate-model/task requirements, not base runtime
requirements.

## Generate a certificate

```bash
python certification/certify.py \
  --source OmegaClaw-Core \
  --output /tmp/omegaclaw-residency.json
```

The output includes:

- exact upstream repository and SHA;
- mechanically witnessed resident powers;
- line-level source provenance for every witness;
- relevant loop/context limits;
- a deterministic `residency_signature` over the powers and limits.

Two revisions can therefore have different Git SHAs while retaining the same residency contract.

## Upstream watch

`.github/workflows/residency-watch.yml` runs on a cron schedule and can also be launched manually.
It:

1. certifies AlphaClaw's pinned `OmegaClaw-Core` submodule;
2. fetches current upstream `asi-alliance/OmegaClaw-Core`;
3. certifies that revision independently;
4. compares the residency signatures.

If upstream changed but the required resident powers did not, the watch stays green. If a source
witness disappears, a relevant limit changes, or the residency signature changes, the watch goes
red and preserves the candidate certificate as a short-lived Actions artifact for review.

That failure is intentional: an upstream change may invalidate AlphaClaw's inference contract and
must not be silently blessed.

## Design rule

**Re-certify automatically; update the AlphaClaw pin deliberately.**

The watcher observes upstream. It does not auto-merge a new OmegaClaw revision into AlphaClaw.
