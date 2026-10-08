# APR-03 — Production Runtime (candidate; NOT DEPLOYED)

Architecture: Docker Compose with pgvector/PostgreSQL (durable state), Redis Streams
with AOF, one-shot Alembic migration, a separate existing Tender Research worker,
read-only non-root API and opt-in Caddy TLS ingress. Only ingress publishes TCP
80/443; API, PostgreSQL and Redis remain private. Caddy permits the bounded
pilot/customer routes and health only. No autonomous bidding or signing.

## External production gates

Real Russian-region VPS, provider contract/access, DNS ownership, hardened host,
approved SSH restrictions, firewall and platform allowlists, Anti-DDoS policy,
off-host encrypted storage, monitoring alert routing and release approval must be
confirmed separately. The public Compose profile is never started automatically.
No production or customer state is changed by repository CI or local tests.

## Deployment instructions for approved operators

Prepare an external environment file based on env.production.example (mode 0600).
Use independent random URL-safe values, at least 32 characters each, for database,
Redis and operator passwords. Do not commit secrets or log rendered Compose config.
Set PROD_SECRET_ENV, PROD_ETP_TRUST_DIR, ARVECTUM_IMAGE_REVISION (full commit SHA),
and ARVECTUM_IMAGE_VERSION in the operator shell. ETP trust directory must include
a reviewed policy.yaml.

Run a non-mutating preflight:

    python3 deploy/production/runtime_ops.py preflight --project arvectum-production --env-file "$PROD_SECRET_ENV" --trust-dir "$PROD_ETP_TRUST_DIR" --revision "$ARVECTUM_IMAGE_REVISION" --version "$ARVECTUM_IMAGE_VERSION"

After separate production authorization ONLY:

    docker compose -p arvectum-production --env-file "$PROD_SECRET_ENV" -f deploy/production/compose.yaml --profile public up -d --build

Check exact image commit, migration, Redis/worker, authentication, HTTPS, 404
deny-list, port visibility, authorized EIS/ETP egress and DNS rollback readiness.

## Backup, restore and failure drills

For an approved encrypted independent destination only, run:

    python3 deploy/production/runtime_ops.py backup --project arvectum-production --env-file "$PROD_SECRET_ENV" --trust-dir "$PROD_ETP_TRUST_DIR" --revision "$ARVECTUM_IMAGE_REVISION" --version "$ARVECTUM_IMAGE_VERSION" --output /approved-encrypted-store/apr03-YYYYMMDD --encrypted-destination-confirmed

Verify an off-host retrieved copy:

    python3 deploy/production/runtime_ops.py verify --backup /approved-encrypted-store/apr03-YYYYMMDD

Restore to a NEVER-BEFORE-USED arvectum-restore-* project only (no public ingress):

    python3 deploy/production/runtime_ops.py restore --project arvectum-restore-20261008 --env-file "$PROD_SECRET_ENV" --trust-dir "$PROD_ETP_TRUST_DIR" --revision "$ARVECTUM_IMAGE_REVISION" --version "$ARVECTUM_IMAGE_VERSION" --backup /approved-encrypted-store/apr03-YYYYMMDD

Measure recovery, test PostgreSQL integrity, verify API smoke, and run controlled
synthetic worker crash/restart and stale-message reclaim. Targets (NOT achieved
SLOs): RPO 24 hours, DB RTO 4 hours, app RTO 8 hours. Retention target: 7 daily,
4 weekly, 6 monthly plus an independent encrypted copy. Monitor backup age,
pending queue, health, disk, 5xx, certificate expiry and alerts.

Do not close APR-03 until actual approved VPS deployment, off-host restore,
restart/resume and operational monitoring drills pass with evidence.
