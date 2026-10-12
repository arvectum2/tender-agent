#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$root"
export PROD_SECRET_ENV="/Users/master/.config/arvectum/apr04-local.env"
export PROD_ETP_TRUST_DIR="/Users/master/.config/arvectum/r7-container-trust"
export ARVECTUM_IMAGE_REVISION="$(git rev-parse HEAD)"
export ARVECTUM_IMAGE_VERSION="apr04-macmini-v1"
test "$(stat -f %Lp "$PROD_SECRET_ENV")" = 600
set -a
source "$PROD_SECRET_ENV"
set +a
python3 deploy/production/runtime_ops.py preflight --project arvectum-local-e2e \
  --env-file "$PROD_SECRET_ENV" --trust-dir "$PROD_ETP_TRUST_DIR" \
  --revision "$ARVECTUM_IMAGE_REVISION" --version "$ARVECTUM_IMAGE_VERSION"
docker compose -p arvectum-local-e2e --env-file "$PROD_SECRET_ENV" \
  -f deploy/production/compose.yaml -f deploy/local/compose.macmini.yaml config --quiet
mkdir -p /Users/master/.config/arvectum/logs
docker compose -p arvectum-local-e2e --env-file "$PROD_SECRET_ENV" \
  -f deploy/production/compose.yaml -f deploy/local/compose.macmini.yaml \
  up -d --wait --wait-timeout 180 --build api worker > /Users/master/.config/arvectum/logs/apr04-local-start.log 2>&1 || {
  echo "Local Compose start failed; inspect restricted log under ~/.config/arvectum/logs" >&2
  exit 1
}
docker compose -p arvectum-local-e2e --env-file "$PROD_SECRET_ENV" \
  -f deploy/production/compose.yaml -f deploy/local/compose.macmini.yaml ps
curl --noproxy '*' -fsS http://127.0.0.1:18082/health
echo
echo "APR-04 local runtime: ready on loopback"
