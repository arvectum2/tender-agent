# Mac mini — APR-03 local runtime / APR-04 onboarding

**LOCAL-ONLY:** real Russian VPS and public DNS are deferred until development
is complete. This overrides the vetted APR-03 Compose stack without touching
the existing Mac mini PostgreSQL or other containers.

Topology: PostgreSQL+pgvector, Redis with AOF, Alembic migration, FastAPI and
separate Redis worker, all in private Docker Compose network. The only published
host socket is \`127.0.0.1:18082\` to FastAPI. The existing pilot Basic auth
applies to \`/pilot\`, \`/api\`, \`/customers\`. No public Caddy profile, no
public 80/443. Storage uses isolated named Docker volumes and worker/container
restart policies. Backup/restore restrictions from deploy/production stay in
force. Frontend: \`http://127.0.0.1:18082/pilot/onboarding\`;
product wizard: \`http://127.0.0.1:18082/pilot/tender-agent\`.

Operator environment is at \`~/.config/arvectum/apr04-local.env\`, mode 0600,
outside Git. Do not copy credentials into repository/logs. External trust policy
uses the existing local ETP trust directory; no changes to system cert store.

## Start (after review)

Canonical Mac mini launcher (preflight, bounded build and health wait):

    bash deploy/local/start_local.sh

Operational read-only/EIS card probe:

    uv run python deploy/local/readiness_probe.py --env-file ~/.config/arvectum/apr04-local.env --customer CUS-2026-000002

The named app data volume is the local capacity-gate mount `/app/data`.
It is **not** an independent physical/offsite backup.


Set local shell \`PROD_SECRET_ENV\` and \`PROD_ETP_TRUST_DIR\` to absolute paths.
Export all names in that secret environment using \`set -a; source
"$PROD_SECRET_ENV"; set +a\` **without echoing them**.
Set \`ARVECTUM_IMAGE_REVISION\` to the exact committed branch SHA and
\`ARVECTUM_IMAGE_VERSION\` to the bounded local release identifier.

Run from repository root:

    docker compose -p arvectum-local-e2e --env-file "$PROD_SECRET_ENV" \
      -f deploy/production/compose.yaml -f deploy/local/compose.macmini.yaml \
      up -d --build api worker

Check API \`GET http://127.0.0.1:18082/health\` and Basic-authenticated
onboarding. Use \`docker compose ... ps\` for health. To stop only this local
stack, use the same files and project: \`stop\` (not \`down -v\`).

### End-to-end acceptance

The operator can create a company, save versioned supplier criteria and
commercial/risk settings, upload a real local PDF with SHA-256, reopen/download
a customer-scoped document, run source-cited pre-analysis, and separately create
and analyze an uploaded tender package through the existing pilot wizard. No
bid/application can be submitted automatically. Missing citations, mismatch,
absence of qualification evidence → \`HUMAN_REVIEW_REQUIRED\`.

Do NOT confuse a seeded/synthetic local test with verified live EIS documents.
If EIS access is tested, use the approved existing SOAP token and trust policy,
and preserve source error/unknown states without substituting demo data.
No customer personal data must be inserted into the synthetic acceptance database.

## Access from MacBook

Use existing authorized SSH/Tailscale access to the Mac mini and forward a
local port to 127.0.0.1:18082 rather than publishing the API publicly. Use
the established SSH identity; no new public ingress is required.

## Operational caveats

This is a development staging instance, NOT a hardened public multi-tenant
release. Backup storage and automated off-host transfer need their separate
operator decisions. Redis AOF is persisted but APR-03's coordinated full-node
recovery for in-flight jobs is still gated. APR-05 must implement per-tenant
auth before anyone other than an authorized internal pilot operator is granted
access. Local Docker images build from reviewed Git SHA, but external image
digest/signature supply-chain release gate remains pending.
