# Human contributor on-ramp

This directory is a **pedagogical development surface** for people who may not yet use command-line Git.

It is intentionally independent of AlphaClaw's sensory runtime and OmegaClaw's inference loop.

The goal is not to hide development. The goal is to expose the important parts in a smaller order.

```text
ordinary language
    -> Wiki edit
    -> visible Git history
    -> mechanical validation
    -> structured review proposal
    -> human review
```

A new contributor can learn what a commit, provenance record, branch, diff, and pull request are by participating before they need to operate those mechanisms directly.

## What authority this gives you

The Wiki path gives a contributor bounded **developmental authority**:

- write and revise a public contribution in ordinary Markdown;
- decide when that contribution is ready for review;
- preserve authorship and exact source provenance;
- cause automation to prepare a review proposal.

It does **not** give a Wiki editor runtime authority over AlphaClaw or OmegaClaw. A Wiki save does not run OmegaClaw, change its tools, select a model, alter an inference budget, deploy an agent, or merge a change into `main`.

The distinction is intentional:

```text
developmental authority != agent authority
```

## Lowest-friction path

1. Open the repository Wiki and choose **Contributor Workspace**.
2. Pick a template:
   - **Domain Rule** — a principle or boundary you think the project should respect.
   - **Edge-Case Evaluation** — something surprising, confusing, fragile, or worth reproducing.
   - **Provenance Log** — a check of where a claim, result, or artifact came from.
3. Type or dictate into the existing sections. Plain language is fine.
4. Keep **Ready for review** as `no` while you are still thinking.
5. Change it to `yes` when the page says what you mean.
6. Choose **Save Page**.

The Wiki intake compiler validates only marked templates. If the page is ready, it creates an immutable JSON record addressed by the exact source Wiki commit and records the Git author, Wiki path, and SHA-256 of the exact Markdown.

Automation places those records on a review branch and opens a pull request. **A human still decides whether to merge it.**

## Why the machinery is here

The contributor supplies the judgment and evidence. The machinery carries syntax, provenance, and review plumbing.

A useful development system should not require someone to understand every layer before they are allowed to make a bounded, inspectable contribution. If getting started requires extensive private instruction, the interface is asking too much from the person.

This project therefore treats onboarding itself as an interpretability problem.

## Files

- `wiki-templates/` — the small structured pages seeded into the GitHub Wiki.
- `wiki_intake.py` — deterministic compiler from explicitly ready Wiki pages to review records.
- `open-source-basics.md` — plain-language licensing and contribution notes.
- `.github/workflows/bootstrap-contributor-wiki.yml` — seeds missing Wiki pages without overwriting contributor edits.
- `.github/workflows/wiki-intake.yml` — compiles ready pages into a review-only pull request.

## Public information only

Do not place passwords, API keys, private messages, private personal information, or confidential third-party material in the public Wiki.
