#!/usr/bin/env bash
set -euo pipefail

# ASI:One documents ASI_ONE_API_KEY. The pinned OmegaClaw ASIOne provider
# currently expects ASIONE_API_KEY. Keep the repository/user-facing secret
# canonical and translate only at the stock-Omega process boundary.
: "${ASI_ONE_API_KEY:?ASI_ONE_API_KEY is required}"
export ASIONE_API_KEY="${ASI_ONE_API_KEY}"

exec "$@"
