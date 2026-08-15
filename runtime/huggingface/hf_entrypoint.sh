#!/usr/bin/env bash
set -euo pipefail

: "${ASI_ONE_API_KEY:?ASI_ONE_API_KEY is required}"

# Keep the project-facing secret canonical. Pinned Omega expects ASIONE_API_KEY,
# so translate only at the stock-Omega process boundary.
export ASIONE_API_KEY="${ASI_ONE_API_KEY}"
export ALPHACLAW_SOURCE_SHA="${ALPHACLAW_SOURCE_SHA:-unknown}"

python3 /opt/alphaclaw-hf/health.py &

args=(
  "commchannel=websocket"
  "provider=ASIOne"
  "embeddingprovider=Local"
  "securityPolicyPath=/PeTTa/repos/OmegaClaw-Core/profile/policy.yaml"
  'memoryDirectory=$MEMORY_DIR'
  "model=asi1-mini"
)

if [[ -n "${OMEGA_WS_URL:-}" ]]; then
  args+=("WS_URL=${OMEGA_WS_URL}")
  args+=("WS_TOKEN=${OMEGA_WS_TOKEN:-}")
fi

exec /PeTTa/repos/OmegaClaw-Core/entrypoint.sh "${args[@]}"
