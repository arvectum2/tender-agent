# APR-03 — isolated runtime rehearsal, 2026-10-08

## Scope, provenance and limitations

Source: feature/apr03-production-runtime based on main ced71977.
Mac mini Docker Desktop with synthetic credentials, dummy ETP trust policy and
no real customers, commercial procurement workflows, public ports or real VPS.
Local Compose projects were prefixed arvectum-restore-* and kept isolated from
existing production/pilot services. Public Caddy profile was NOT started.

This is a repository/local rehearsal only. It does not establish a Russian VPS
deployment, ACME/domain, external EIS connectivity, real DDoS controls, SLA,
offsite backup or acceptance of personal-data hosting jurisdiction.

## Executed evidence

| Control | Result | Evidence |
| --- | --- | --- |
| Production Compose config (including public profile) | PASS | docker compose config --quiet, synthetic environment |
| Fail-closed preflight (SHA, env mode, auth, trust) | PASS | python3 runtime_ops.py preflight; new dedicated unit tests |
| PostgreSQL/Redis and migration | PASS | PG16 pgvector healthy; Redis PONG; Alembic migrate exit 0 |
| Private API and separate Redis worker | PASS | API GET /health = 200, worker process running, backend=redis |
| Restart and Redis delivery | PASS bounded | Stop worker, enqueue synthetic missing-job envelope; stream length 1; restart worker; stream length 0 after acknowledged absent job |
| Backup and integrity verification | PASS synthetic | Fresh private PostgreSQL -Fc dump and artifacts archive; manifest hashes verified |
| Safe isolated restore | PASS | Recovered to new arvectum-restore-apr03recovery2 namespace; restored migration exit 0, API GET /health = 200, worker running, no public ingress |
| Container health inventory | PASS | doctor JSON healthy true for API, DB, Redis, worker running |
| Code quality | PASS | make check; Ruff and focused tests |
| Existing R9 restore acceptance | PASS with PG16 tools | Initially failed with host PostgreSQL 18 client against PostgreSQL 16 test server; PATH to PostgreSQL 16 binaries yielded PASS; no unrelated code change |

The first isolated restore attempt hit an API readiness race: container was
running but Uvicorn had not started listening. Corrective action: Compose
--wait on API health before smoke; second isolated restore PASS.

The initial worker inherited the image's API HTTP healthcheck, incorrectly
reporting unhealthy. Corrective action: disable that inherited worker HTTP
healthcheck; monitor worker process and queue lag separately. No claim of
semantic job progress solely from an alive process.

An additional recovery gate checks the persisted Tender Research table for
queued/running work and refuses backup/restore rather than claim lossless Redis
recovery; on the isolated restored database, the 0-active-job check passed.
Future backups require ingress/job-submission quiescence to avoid concurrent races.

Restart drill used deliberately **nonexistent synthetic job identity** so no
source documents were downloaded or external effects made; the drill proves
delivery after worker restart, NOT mid-execution resume of a real document job.

## Residuals: do not call APR-03 complete

- Real, authorized Russia-based server, DNS, TLS, firewall, anti-DDoS,
  outbound EIS/ETP policies, operator access and deployment evidence absent.
- Independently encrypted offsite backup/restore, measured RPO/RTO, on-call
  alerts, real certificate lifetime and traffic/load gates not verified.
- Current backup includes PostgreSQL and application files, **not a coordinated
  Redis AOF snapshot**. Full-node disaster recovery of queued/in-flight work
  from a restore therefore remains UNPROVEN; do not claim lossless resume.
- Restarts after actual worker termination with real long-running analysis,
  lease reclaim and bounded retries require a separate controlled production
  acceptance drill.
- Dockerfile dependency resolution is not independently reproducible from an
  immutable production registry digest; image release supply-chain lock is
  pending production release review.
- APR-03 remains gated until Owner authorizes and the external provider/device
  requirements are satisfied with measured evidence.
