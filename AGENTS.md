# AlphaClaw agent instructions

This file is for coding agents and local operator assistants working in this repository.

## Stay inside the established architecture

- **Alpha senses. Omega reasons. The benchmark controller bounds. ThreadKeeper measures. Humans authorize and judge.**
- Do not modify, vendor, or silently fork `OmegaClaw-Core/` or `external/ThreadKeeper/`.
- Do not change their pinned revisions unless the human explicitly asks for an upstream-pin change.
- Do not add recursive authority, autonomous deployment, standing background inference, or a new control layer without explicit human approval.
- Do not bypass `controller/omegaboi.py` when producing AlphaClaw bounded-benchmark claims.
- Treat `Autotests.mock.comm` from the pinned Omega checkout as the one explicit host-side trusted transport exception already documented by the project.

## Local setup assistance is allowed

An agent may help the human:

- find and verify Docker Desktop / the Docker CLI;
- inspect local Docker state and explain errors;
- initialize and verify Git submodules;
- create `.env` from `.env.example`;
- load local environment variables with `scripts/load-env.ps1`;
- run lint, deterministic tests, read-only pin checks, and other non-spending diagnostics;
- prepare a bounded canary command for the human to approve.

Prefer literal, step-by-step operator guidance. Do not assume Docker, Git, Python, PowerShell, paths, or environment-variable behavior are familiar.

## Secrets and paid inference

- Never put real credentials in tracked files, commits, issues, pull requests, logs, screenshots, or chat output.
- `.env` is local-only and Git-ignored. `.env.example` contains names and comments only.
- Never print secret values. When verifying setup, report only whether a variable is present.
- Do not run a real provider call, image perception call, or other token-spending inference without the human explicitly approving that specific run.
- Before a first paid canary, show the exact command, provider, model, and `--max-loops` value and wait for approval.

## Git and collaboration

- Work on a branch and propose changes through a pull request. `main` is protected.
- Do not weaken repository rules, CI, pin checks, or provenance checks.
- Do not merge your own work unless the human explicitly asks and repository rules permit it.
- Local benchmark outputs under `benchmark-runs/` are evidence, not source; do not commit them by default.

## Default local workflow

1. Read `README.md`, `LOCAL_SETUP.md`, and this file.
2. Verify the working tree and submodule pins before changing anything.
3. Verify Docker without changing Docker configuration unnecessarily.
4. Help create/load `.env` without exposing values.
5. Run non-spending checks first.
6. Stop before the first real provider call and ask the human for explicit approval.
7. After any approved canary, inspect receipts and teardown before proposing further changes.

When uncertain, prefer stopping and asking over silently broadening authority.
