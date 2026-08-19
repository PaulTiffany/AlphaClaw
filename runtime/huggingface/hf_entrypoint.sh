#!/usr/bin/env bash
set -euo pipefail

: "${ASI_ONE_API_KEY:?ASI_ONE_API_KEY is required}"

# Keep the project-facing secret canonical. Pinned Omega expects ASIONE_API_KEY,
# so translate only at the stock-Omega process boundary.
export ASIONE_API_KEY="${ASI_ONE_API_KEY}"
export ALPHACLAW_SOURCE_SHA="${ALPHACLAW_SOURCE_SHA:-unknown}"

# AlphaClaw embodiment: one human input grants exactly eight resident inference
# cycles and scheduled wake-ups grant none. These are intentionally hard-coded
# deployment facts, not user-tunable runtime knobs.
readonly ALPHACLAW_MAX_NEW_INPUT_LOOPS=8
readonly ALPHACLAW_MAX_WAKE_LOOPS=0
export ALPHACLAW_MAX_NEW_INPUT_LOOPS ALPHACLAW_MAX_WAKE_LOOPS

python3 /opt/alphaclaw-hf/health.py &

args=(
  "commchannel=websocket"
  "provider=ASIOne"
  "embeddingprovider=Local"
  "securityPolicyPath=/PeTTa/repos/OmegaClaw-Core/profile/policy.yaml"
  'memoryDirectory=$MEMORY_DIR'
  "model=asi1-mini"
  "maxNewInputLoops=${ALPHACLAW_MAX_NEW_INPUT_LOOPS}"
  "maxWakeLoops=${ALPHACLAW_MAX_WAKE_LOOPS}"
)

if [[ -n "${OMEGA_WS_URL:-}" ]]; then
  args+=("WS_URL=${OMEGA_WS_URL}")
  args+=("WS_TOKEN=${OMEGA_WS_TOKEN:-}")
fi

exec /PeTTa/repos/OmegaClaw-Core/entrypoint.sh "${args[@]}"
