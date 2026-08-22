# Open Source & Licensing Basics

This page is for contributors to **AlphaClaw**.

AlphaClaw original code is published under the **MIT License**. The pinned `OmegaClaw-Core` submodule is upstream work and keeps its own upstream license, authorship, documentation, and notices.

## What MIT means in ordinary language

People may use, copy, modify, combine, publish, distribute, sublicense, or sell copies of MIT-licensed AlphaClaw code. They do not need to ask first.

The main condition is simple: copies or substantial portions of the software must keep the copyright notice and MIT permission notice.

The license also says the software is provided **as is**. The authors are not promising that it is perfect, safe for every purpose, or free of defects, and the license limits liability for problems that arise from using it.

## What it means when you contribute

You do not need to become a Git expert first. The contributor Wiki lets you work in ordinary Markdown using small templates. Your job is to describe what you observed, what you expected, what concerns you, or what provenance you checked. An assistant may help with wording or formatting, but the contribution should say what **you** mean.

Please contribute only material you are allowed to share. Do not put passwords, API keys, private messages, private personal information, or confidential third-party material into a public Wiki page.

If a contribution is accepted into AlphaClaw, the accepted material will be published as part of this public repository. If you do not want your contribution distributed that way, do not mark it ready for review.

## Your authorship does not disappear

The Wiki keeps its own edit history. The intake pipeline also records the source Wiki page, Wiki commit, Git-recorded author, and a SHA-256 hash of the exact Markdown that was compiled.

Automation creates a **review branch / pull request**, not a silent direct write to `main`. A human still decides whether the generated proposal should merge.

The generated intake commit is made by GitHub Actions. We do **not** call that commit cryptographically signed unless a dedicated signing mechanism is actually configured. The provenance claim comes from the recorded Wiki history and content hashes.

## The low-friction workflow

1. Open the project Wiki page prepared for your contribution type.
2. Choose **Edit**.
3. Type or dictate your observations.
4. Leave **Ready for review** as `no` while you are still working.
5. Change it to `yes` when the page says what you mean.
6. Choose **Save Page**.
7. GitHub automation validates the page and prepares a structured pull request for human review.

You are contributing judgment and evidence. The machinery carries the syntax and provenance burden.

This contributor path is pedagogical development infrastructure. It is not AlphaClaw sensory ingress and it does not grant runtime authority over OmegaClaw.

> This is a practical project guide, not individualized legal advice. Repository and upstream `LICENSE` files are the authoritative license texts.
