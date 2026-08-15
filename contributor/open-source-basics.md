# Open Source & Licensing Basics

This page is for contributors to **AlphaClaw** and **Docent**. Both public repositories use the **MIT License**.

## What that means in ordinary language

People may use, copy, modify, combine, publish, distribute, sublicense, or sell copies of the software. They do not need to ask us first.

The main condition is simple: copies or substantial portions of the software must keep the copyright notice and MIT permission notice.

The license also says the software is provided **as is**. The authors are not promising that it is perfect, safe for every purpose, or free of defects, and the license limits liability for problems that arise from using it.

## What it means when you contribute

You do not need to become a Git expert. For the sensitive contributor path, you can work in the GitHub Wiki using ordinary Markdown and the provided templates. Your job is to describe what you observed, what you expected, what concerns you, or what provenance you checked. Automation can turn a ready Wiki page into a structured review proposal.

Please contribute only material you are allowed to share. Do not put passwords, API keys, private messages, private personal information, or confidential third-party material into a public Wiki page.

If the team accepts your contribution into AlphaClaw or Docent, the accepted material will be published as part of an MIT-licensed repository. If you do not want your contribution distributed that way, say so before submitting it for review.

## Your authorship does not disappear

The Wiki keeps its own edit history. The intake pipeline also records the source Wiki page, the Wiki commit, the Wiki author recorded by Git, and a SHA-256 hash of the exact Markdown that was compiled.

The automation creates a **review branch / pull request**, not a silent direct write to `main`. A human still decides whether the generated proposal should merge.

The generated intake commit is made by GitHub Actions. We do **not** call that commit cryptographically signed unless a dedicated signing key is actually configured. The provenance claim comes from the recorded Wiki history and content hashes.

## The low-friction workflow

1. Open the project Wiki page prepared for your contribution type.
2. Choose **Edit**.
3. Type or dictate your observations. Gemini can help with wording and formatting.
4. Leave **Ready for review** as `no` while you are still working.
5. Change it to `yes` when the page says what you mean.
6. Choose **Save Page**.
7. GitHub automation validates the page and prepares a structured pull request for human review.

You are contributing judgment and evidence. The machinery should carry the syntax burden.

> This is a practical project guide, not individualized legal advice. The repository `LICENSE` files are the authoritative license text.
