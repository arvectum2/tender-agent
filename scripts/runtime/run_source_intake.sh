#!/usr/bin/env bash
# Prepared release-only Mac mini runner. Never auto-apply without explicit env.
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)
env_file=${ARVECTUM_ENV_FILE:-"$root/.env.local"}
[[ -f "$env_file" ]] || { echo "source intake: canonical runtime env missing" >&2; exit 2; }
set -a; source "$env_file"; set +a
python_bin=${ARVECTUM_PYTHON:-"$root/.venv/bin/python"}
[[ -x "$python_bin" ]] || { echo "source intake: Python not configured" >&2; exit 2; }
declare -a args=()
case "${TENDER_SOURCE_INTAKE_APPLY:-0}" in
  0) ;;
  1) args=(--apply --confirm-database arvectum) ;;
  *) echo "source intake: apply flag must be 0 or 1" >&2; exit 2 ;;
esac
cd "$root"
export PYTHONPATH="$root"
exec "$python_bin" -m scripts.procurement_llm.unified_source_pipeline "${args[@]}"
