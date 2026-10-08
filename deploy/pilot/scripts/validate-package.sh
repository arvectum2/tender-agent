#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "$0")/../../.." && pwd)
compose="$root/deploy/pilot/compose.yaml"
dockerfile="$root/deploy/pilot/Dockerfile"

# Keep deployment-only prerequisites detectable before an expensive staging start.
rg -q 'image: pgvector/pgvector:pg16' "$compose"
rg -q 'pilot-artifacts:/app/company_agent_runs' "$compose"
rg -q 'networks: \[pilot-internal, pilot-egress\]' "$compose"
rg -q 'networks: \[pilot-internal, pilot-ingress\]' "$compose"
rg -q 'pilot-internal: \{ internal: true \}' "$compose"
rg -q 'pilot-ingress: \{\}' "$compose"
rg -q 'pilot-egress: \{\}' "$compose"
rg -q '127\.0\.0\.1:18081:8080' "$compose"
rg -q 'location = /health/tender-agent.*proxy_set_header Host \$host' "$root/deploy/pilot/nginx.conf"
rg -q '^COPY scripts ./scripts$' "$dockerfile"
rg -q '^COPY docs/agents/company ./docs/agents/company$' "$dockerfile"
rg -q '^COPY demo_data/tender_operator_agent ./demo_data/tender_operator_agent$' "$dockerfile"

echo "pilot package validation: passed"
