# APR-04 — Mac mini local deployment / onboarding E2E (2026-10-08)

## Owner deployment decision

The APR-03 **real Russian VPS provision/cutover is explicitly paused until
development is complete**. Keep the historical APR-03 checkpoint
`.agent/checkpoints/APR-03-PRODUCTION-RUNTIME-001.yaml` open. No DNS,
provider, payment, public ingress or production certificate actions are approved.

Mac mini is the interim internal runtime. It has isolated Docker Compose
project `arvectum-local-e2e` with PostgreSQL 16 / pgvector, Redis AOF,
one-shot Alembic, FastAPI and a separate Redis Streams worker. Only
`127.0.0.1:18082` is published, with existing Basic auth. It does not
replace the previously running Mac mini PostgreSQL or other services.

## Measured synthetic end-to-end (real containerized HTTP)

- Anonymous `/pilot/onboarding` blocked (401), authorized UI succeeds.
- Health `/health` responds HTTP 200.
- Company `CUS-2026-000002` created, profile read back, margin/NMCK criteria
  persisted, and version incremented to v2.
- A synthetic PDF was physically stored and bound to the company through
  existing artifact/company-document tables; SHA256 and download round-trip pass.
- Separate synthetic notice/TZ/contract text files were uploaded through
  existing Tender Agent pilot API and analyzed. Result: `needs_review`.
- Existing analyzed run `toa-run-20261008204756-47da13` yielded a report,
  then APR-04 projection linked it to profile v2, preserving
  `HUMAN_REVIEW_REQUIRED` and `external_action_allowed=false`.

An initial real Docker test failed because pilot Dockerfile omitted the
required `demo_data/tender_operator_agent` fixtures. Fixed the image packaging
and validation script; the repeated containerized E2E passed.

## Read-only real EIS card

Using exact notice 0372200172326000015, existing approved local network
configuration returned `success_with_results`, cited subject `KNOWN`,
and bounded company NMCK check `OUTSIDE_BOUNDS` with mandatory human review.
This is a live **public card** check, not proof that the original complete
procurement document set was extracted/analyzed.

## Remaining gates and scope boundaries

- Mac mini mount-gate readiness: initial `/health/ready` was `degraded`
  because `ARVECTUM_STORAGE_ROOT` was absent inside Docker despite
  `/app/data` being a verified separate named volume. Local Compose override
  now configures that root; recheck after rollout.
- Real SOAP getDocsIP document ingestion/analysis is a separate bounded
  read-only check and is NOT to be inferred from successful public-card lookup.
- Local LLM is configured as a `stub` for this bounded acceptance;
  deterministic fallback must not be marketed as production-quality LLM/VLM.
- APR-05 tenant authentication/isolation, paid pilots, and public service
  authorization remain out of APR-04 scope.
- VPS, DNS/ACME, external offsite backups, full-node Redis recovery, measured
  production RPO/RTO and customer operational SLA remain deferred APR-03 gates.
- Never infer supplier license/SRO validity, profitability or procurement GO
  from a manually uploaded file or a source-card price match.
