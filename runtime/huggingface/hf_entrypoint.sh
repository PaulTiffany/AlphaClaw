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
memory=/PeTTa/repos/OmegaClaw-Core/src/memory.metta
resident_prompt=/PeTTa/repos/OmegaClaw-Core/memory/prompt.txt
plugin=/PeTTa/repos/OmegaClaw-Core/src/plugin.metta
plugins=/PeTTa/repos/OmegaClaw-Core/config/plugins.yaml
llm_ext=/PeTTa/repos/OmegaClaw-Core/providers/lib_llm_ext.py
runtime_config=/opt/alphaclaw-hf/alphaclaw-runtime.yaml

test "$(grep -Fc '(change-state! &loops 0)' "$loop")" = 1
test "$(grep -Fc '(change-state! &loops (maxNewInputLoops))' "$loop")" = 1
if grep -Fq '(and (> $k 1) $msgnew)' "$loop"; then
  echo "refusing resident start: first-iteration human input would not refill authority" >&2
  exit 1
fi

grep -Fq 'collapse (eval (loadOmegaClawPlugin))' "$plugin"
if grep -Fq 'once (eval (loadOmegaClawPlugin))' "$plugin"; then
  echo "refusing resident start: Omega plugin loader was modified" >&2
  exit 1
fi

# Only the channel and provider needed by this deployment are loadable.
python3 - "$plugins" <<'PY'
from pathlib import Path
import sys

names = []
for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    if line.startswith("- name: "):
        names.append(line.removeprefix("- name: ").strip())
if names != ["wschat", "asione"]:
    raise SystemExit(f"refusing resident start: unexpected plugin allowlist {names!r}")
PY

# The model may communicate with the human. It may not acquire shell, web,
# file, memory, arbitrary MeTTa, or dynamically-added command authority.
PYTHONPATH=/PeTTa/repos/OmegaClaw-Core python3 - <<'PY'
from src import helper

if helper.STATIC_LLM_COMMANDS != {"send"}:
    raise SystemExit(
        f"refusing resident start: unexpected static model actions {helper.STATIC_LLM_COMMANDS!r}"
    )
if helper.LLM_COMMANDS != {"send"}:
    raise SystemExit(
        f"refusing resident start: unexpected model actions {helper.LLM_COMMANDS!r}"
    )
if helper.add_llm_command("shell"):
    raise SystemExit("refusing resident start: dynamic command expansion is enabled")
if helper.LLM_COMMANDS != {"send"}:
    raise SystemExit("refusing resident start: command set changed during expansion probe")
if "UNKNOWN_SKILL_CALL" not in helper.balance_parentheses("shell env"):
    raise SystemExit("refusing resident start: shell-like model output was not rejected")
PY

# The resident prompt must describe the authority that actually exists, not
# instruct the model to choose goals, persist memories, or exercise absent tools.
grep -Fq 'Your only model-directed action is: send string.' "$resident_prompt"
grep -Fq 'Do not create goals beyond responding to the current human-mediated input.' "$resident_prompt"
for forbidden_prompt in \
  'choose your own goals' \
  'Keep memories and useful created skills' \
  'ALWAYS query before responding anything' \
  'Take at least 5 agent cycles'; do
  if grep -Fq "$forbidden_prompt" "$resident_prompt"; then
    echo "refusing resident start: autonomous or unavailable-capability prompt survived" >&2
    exit 1
  fi
done

# Human payloads and model responses must not be silently retained by the
# stock history writer, nor reintroduced into later human episodes.
grep -Fq 'AlphaClaw staged boundary: persistent history writes disabled.' "$memory"
grep -Fq 'maxHistory: 0' "$runtime_config"

# Runtime logs are structural witnesses, not a second conversation archive.
grep -Fq '(HUMAN-MSG-CHARS: (string_length $msg))' "$loop"
grep -Fq '(CHARS_SENT: (string_length $send))' "$loop"
grep -Fq 'RESPONSE-PARSED' "$loop"
grep -Fq 'COMMAND-RESULTS-AVAILABLE' "$loop"
if grep -Fq '(CHARS_SENT: (string_length $send) $send)' "$loop"; then
  echo "refusing resident start: prompt bodies would be logged" >&2
  exit 1
fi
if grep -Fq '(log INFO "loop" $lastmessage)' "$loop"; then
  echo "refusing resident start: human messages would be logged" >&2
  exit 1
fi
if grep -Fq 'raw={raw!r}' "$llm_ext"; then
  echo "refusing resident start: raw model responses would be logged" >&2
  exit 1
fi

if [[ -n "${OMEGA_WS_URL:-}" && "${OMEGA_WS_URL}" != wss://* ]]; then
  echo "refusing resident start: OMEGA_WS_URL must use wss://" >&2
  exit 1
fi

readonly ALPHACLAW_BOOT_LOOPS=0
readonly ALPHACLAW_MAX_NEW_INPUT_LOOPS=8
readonly ALPHACLAW_MAX_WAKE_LOOPS=0
readonly ALPHACLAW_MAX_HISTORY_CHARS=0
readonly ALPHACLAW_PERSIST_HISTORY=0
readonly ALPHACLAW_LOG_CONVERSATION_CONTENT=0
readonly ALPHACLAW_MODEL_ACTIONS=send
readonly ALPHACLAW_RESIDENT_PLUGINS=wschat,asione
export ALPHACLAW_BOOT_LOOPS ALPHACLAW_MAX_NEW_INPUT_LOOPS ALPHACLAW_MAX_WAKE_LOOPS
export ALPHACLAW_MAX_HISTORY_CHARS ALPHACLAW_PERSIST_HISTORY
export ALPHACLAW_LOG_CONVERSATION_CONTENT
export ALPHACLAW_MODEL_ACTIONS ALPHACLAW_RESIDENT_PLUGINS

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
