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
# Source intake must fully succeed before any analysis worker can execute.
"$python_bin" -m scripts.procurement_llm.unified_source_pipeline "${args[@]}"

# Source -> actual LLM worker is opt-in by a separately approved runtime flag.
# The worker always checks private original SHA, tender documents, Data Platform,
# exact archived-source binding and actual local model before generating outputs.
case "${TENDER_QUEUE_ANALYZE_APPLY:-0}" in
  0) exit 0 ;;
  1) ;;
  *) echo "analysis queue: apply flag must be 0 or 1" >&2; exit 2 ;;
esac
declare -a worker_args=(--apply --confirm-database arvectum --max-actual 1)
if [[ -n "${TENDER_QUEUE_LLM_BASE_URL:-}" || -n "${TENDER_QUEUE_LLM_MODEL:-}" ]]; then
  [[ -n "${TENDER_QUEUE_LLM_BASE_URL:-}" && -n "${TENDER_QUEUE_LLM_MODEL:-}" ]] || {
    echo "analysis queue: both local LLM endpoint and model must be configured" >&2
    exit 2
  }
  worker_args+=(--llm-base-url "$TENDER_QUEUE_LLM_BASE_URL" --llm-model "$TENDER_QUEUE_LLM_MODEL")
fi
exec "$python_bin" -m scripts.procurement_llm.analysis_queue_worker "${worker_args[@]}"
