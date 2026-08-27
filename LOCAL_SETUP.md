# Local AlphaClaw setup on Windows

This guide assumes very little. It is for getting a Windows machine ready to run AlphaClaw's bounded local benchmark fixture with Docker Desktop.

Nothing in the setup steps below spends provider tokens. The first real provider call is a separate, explicit canary step and should only be run after the human approves the exact command.

## 1. Open the repository in PowerShell

Open PowerShell in the AlphaClaw repository folder. If you are not sure where you are, run:

```powershell
Get-Location
```

The folder should contain files such as `README.md`, `AGENTS.md`, `controller`, and `OmegaClaw-Core` after submodules are initialized.

To see the current Git state:

```powershell
git status
```

Do not continue from a mysterious dirty working tree. Ask for help first if Git reports changes you do not recognize.

## 2. Verify Git and Python

Run:

```powershell
git --version
python --version
```

The project CI uses Python 3.11. A newer compatible local Python may work, but when troubleshooting, matching CI is simplest.

## 3. Find and verify Docker

You do not need to know Docker Desktop's install directory if the Docker CLI is on `PATH`.

Run:

```powershell
Get-Command docker
docker --version
docker version
```

`Get-Command docker` shows which executable PowerShell will use.

`docker version` talks to both the Docker CLI and the Docker engine. If it prints client information but says it cannot connect to the daemon/engine, open **Docker Desktop** from the Windows Start menu and wait until it reports that Docker is running. Then retry:

```powershell
docker version
```

A useful second check is:

```powershell
docker info
```

Do not reinstall, reset, prune, or change Docker Desktop settings just because one command fails. Read the error first.

## 4. Initialize the pinned upstream submodules

From the AlphaClaw repository root, run:

```powershell
git submodule update --init --recursive
```

Then verify the exact pins:

```powershell
git -C OmegaClaw-Core rev-parse HEAD
git -C external/ThreadKeeper rev-parse HEAD
```

Expected OmegaClaw SHA:

```text
3d711e4b9f5254ae94f31123ca242f60cfd97d29
```

Expected ThreadKeeper SHA:

```text
a64de99e10f9f8078d25bff511b44fd71819e931
```

Also verify neither upstream checkout is dirty:

```powershell
git -C OmegaClaw-Core status --short
git -C external/ThreadKeeper status --short
```

Both commands should print nothing.

## 5. Install the same local test tools CI uses

This installs test/lint tooling only. It does not call a model provider.

```powershell
python -m pip install pytest==9.1.1 ruff==0.16.4
```

Then run the same deterministic checks used by CI:

```powershell
ruff check ingress controller tests
pytest -q
```

## 6. Create the local `.env`

The repository tracks `.env.example` but intentionally ignores `.env`.

Create your local file:

```powershell
Copy-Item .env.example .env
```

Open `.env` in a text editor and fill only the keys you actually plan to use. For example, a bounded ASI:One canary needs `ASIONE_API_KEY`. Image ingress through OpenRouter needs `OPENROUTER_API_KEY` as well.

Never commit `.env`. Never paste its values into a PR, issue, log, screenshot, or chat.

Before doing anything else, confirm Git ignores it:

```powershell
git status --short
```

`.env` should not appear.

## 7. Load `.env` into the current PowerShell session

Run this exact command from the repository root:

```powershell
. .\scripts\load-env.ps1
```

The first dot and following space are intentional. They make the variables available in the current PowerShell process.

The loader prints variable **names only**, never values.

To check one key without printing it:

```powershell
if ($env:ASIONE_API_KEY) { "ASIONE_API_KEY is loaded" } else { "ASIONE_API_KEY is missing" }
```

Replace the name if using another provider.

## 8. Build the pinned stock Omega Docker image without inference

This step may download/build Docker dependencies, but it does not call an LLM provider.

Run:

```powershell
docker build -t alphaclaw-omega-stock:3d711e4b9f52 .\OmegaClaw-Core
```

Then verify the image exists:

```powershell
docker image inspect alphaclaw-omega-stock:3d711e4b9f52 --format '{{.Id}}'
```

Do not manually modify the Omega source to make the build pass. If the pinned upstream build fails, preserve the error and diagnose the fixture instead.

## 9. Stop before the first real provider call

At this point the local machine should have:

- Docker running;
- the pinned OmegaClaw and ThreadKeeper submodules initialized and clean;
- deterministic tests passing;
- a local, ignored `.env` with the needed key(s);
- those keys loaded into the current PowerShell session;
- the stock Omega Docker image built.

**Stop here before spending tokens.**

The first canary should be deliberately narrow. An agent helping with setup must show the human the exact provider, model, prompt, and `--max-loops` value and receive explicit approval before running it.

A typical one-call text canary, after approval, will look like:

```powershell
python controller/omegaboi.py `
  --text "hello" `
  --provider asione `
  --model asi1-ultra `
  --max-loops 1
```

Do not copy this command as implicit authorization to run it.

## 10. After an approved canary

Inspect the new ignored directory under `benchmark-runs/`. A valid run should provide evidence such as:

```text
manifest.json
alpha-envelope.json
ingress-trace.json
provider_usage.jsonl
usage.jsonl
container.log
response.txt
```

Check that boot and episode provider usage were recorded separately, the ThreadKeeper accounting witness wrote its normalized record, and the fresh Omega container was torn down.

A simple container check is:

```powershell
docker ps -a
```

There should not be a forgotten AlphaClaw benchmark container left running from a completed one-shot episode.

## If Claude or another coding agent is helping

Tell it to read `AGENTS.md` first. Local setup assistance is welcome; changing the experiment's constitution is not part of setup.
