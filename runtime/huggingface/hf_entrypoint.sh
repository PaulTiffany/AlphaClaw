#!/usr/bin/env bash
set -euo pipefail

: "${ASI_ONE_API_KEY:?ASI_ONE_API_KEY is required}"

# Alpha's multimodal/provider credentials must never be resident with Omega.
for forbidden in \
  OPENROUTER_API_KEY \
  ASI_API_KEY \
  OPENAI_API_KEY \
  ANTHROPIC_API_KEY \
  MINIMAX_API_KEY; do
  if [[ -n "${!forbidden:-}" ]]; then
    echo "refusing resident start: forbidden credential $forbidden is present" >&2
    exit 1
  fi
done

# Keep the project-facing secret canonical. Pinned Omega expects ASIONE_API_KEY,
# so translate only at the stock-Omega process boundary.
export ASIONE_API_KEY="${ASI_ONE_API_KEY}"
export ALPHACLAW_SOURCE_SHA="${ALPHACLAW_SOURCE_SHA:-unknown}"

# The image must contain the complete pinned Omega substrate and no in-process
# AlphaClaw library. Alpha is an external ingress boundary, not a resident agent.
test -f /PeTTa/repos/OmegaClaw-Core/lib_omegaclaw.metta
test -f /PeTTa/run.metta
test ! -e /PeTTa/repos/AlphaClaw

# Refuse to run if the bounded staged semantics drifted. These checks happen
# before health starts and before Omega receives provider authority.
loop=/PeTTa/repos/OmegaClaw-Core/src/loop.metta
plugin=/PeTTa/repos/OmegaClaw-Core/src/plugin.metta
test "$(grep -Fc '(change-state! &loops 0)' "$loop")" = 1
test "$(grep -Fc '(change-state! &loops (maxNewInputLoops))' "$loop")" = 1
grep -Fq '(collapse (eval (loadOmegaClawPlugin)))' "$plugin"
if grep -Fq '(once (eval (loadOmegaClawPlugin)))' "$plugin"; then
  echo "refusing resident start: Omega plugin loader was modified" >&2
  exit 1
fi

if [[ -n "${OMEGA_WS_URL:-}" && "${OMEGA_WS_URL}" != wss://* ]]; then
  echo "refusing resident start: OMEGA_WS_URL must use wss://" >&2
  exit 1
fi

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
