#!/usr/bin/env bash
set -euo pipefail

ALPHA_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PETTA_ROOT="${1:-}"

if [[ -z "$PETTA_ROOT" ]]; then
  echo "usage: scripts/install-into-petta.sh /path/to/PeTTa" >&2
  exit 2
fi

PETTA_ROOT="$(cd "$PETTA_ROOT" && pwd)"
EXPECTED_ALPHA="$PETTA_ROOT/repos/AlphaClaw"

if [[ ! -f "$PETTA_ROOT/run.sh" || ! -d "$PETTA_ROOT/repos" ]]; then
  echo "error: $PETTA_ROOT does not look like a PeTTa checkout" >&2
  exit 1
fi

if [[ "$ALPHA_ROOT" != "$EXPECTED_ALPHA" ]]; then
  echo "error: clone AlphaClaw at $EXPECTED_ALPHA so PeTTa library aliases remain deterministic" >&2
  exit 1
fi

git -C "$ALPHA_ROOT" submodule update --init --recursive

OMEGA_ALIAS="$PETTA_ROOT/repos/OmegaClaw-Core"
if [[ -e "$OMEGA_ALIAS" || -L "$OMEGA_ALIAS" ]]; then
  if [[ "$(readlink "$OMEGA_ALIAS" 2>/dev/null || true)" != "AlphaClaw/OmegaClaw-Core" ]]; then
    echo "error: $OMEGA_ALIAS already exists and is not AlphaClaw's pinned submodule" >&2
    exit 1
  fi
else
  ln -s "AlphaClaw/OmegaClaw-Core" "$OMEGA_ALIAS"
fi

cp "$ALPHA_ROOT/run.metta" "$PETTA_ROOT/run-alphaclaw.metta"

echo "AlphaClaw composed into PeTTa."
echo "Runner: $PETTA_ROOT/run-alphaclaw.metta"
echo "OmegaClaw alias: $OMEGA_ALIAS -> AlphaClaw/OmegaClaw-Core"
