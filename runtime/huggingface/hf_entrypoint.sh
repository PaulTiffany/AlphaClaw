#!/usr/bin/env bash
set -euo pipefail

: "${ASI_ONE_API_KEY:?ASI_ONE_API_KEY is required}"

# Keep the project-facing secret canonical. Pinned Omega expects ASIONE_API_KEY,
# so translate only at the stock-Omega process boundary.
export ASIONE_API_KEY="${ASI_ONE_API_KEY}"
export ALPHACLAW_SOURCE_SHA="${ALPHACLAW_SOURCE_SHA:-unknown}"

# The image must contain the complete pinned Omega substrate and no in-process
# AlphaClaw library. Alpha is an external ingress boundary, not a resident agent.
test -f /PeTTa/repos/OmegaClaw-Core/lib_omegaclaw.metta
test -f /PeTTa/run.metta
test ! -e /PeTTa/repos/AlphaClaw

readonly ALPHACLAW_BOOT_LOOPS=0
readonly ALPHACLAW_MAX_NEW_INPUT_LOOPS=8
readonly ALPHACLAW_MAX_WAKE_LOOPS=0
export ALPHACLAW_BOOT_LOOPS ALPHACLAW_MAX_NEW_INPUT_LOOPS ALPHACLAW_MAX_WAKE_LOOPS

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
