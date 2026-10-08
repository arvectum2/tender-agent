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

- Mount-gate issue corrected: `ARVECTUM_STORAGE_ROOT=/app/data` for API
  and worker in Docker. After rebuilt deployment, `GET /health/ready` returned
  `status=ok`, `ingestion_allowed=true`, Redis healthy, customer pilot ready.
- Real SOAP getDocsIP procurement `0372200172326000015`: download HTTP 200,
  six files (`.xml`, `.xls`, `.doc`, two `.docx`, `.pdf`).
  Analyzed run `toa-run-20261008205700-f21a7c` returned
  `completed_with_warnings` in fallback mode and source-bound
  `NEEDS_REVIEW`; initial inspection showed 7 warnings and extraction failed
  for legacy Office/XML files because the Docker service pointed to its own
  `127.0.0.1:8094` instead of the Mac mini Data Platform.
- Connected existing authenticated Mac mini Data Platform (v0.6.0) via
  `host.docker.internal:8094` for temporary `/v1/process/document` extraction.
  The internal key remains only in the external mode-0600 operator env;
  synthetic bridge test returned `extracted` with text. This reuses the
  existing host service, not a second extractor or new permanent data store.
- Repeated exact real SOAP getDocsIP intake and analysis, run
  `toa-run-20261008210259-ba5815`. All **six** files reported
  `extracted_text_available=true` and run metadata warnings fell to zero.
  Existing fast pre-analysis remained `NEEDS_REVIEW`,
  `HUMAN_REVIEW_REQUIRED`, no external action. The separate field
  `documents_extracted_count=1` refers to archive extraction, **not**
  the six document text-extraction statuses.
- A controlled local API/worker restart was executed with isolated Docker
  containers (no service on the main Mac mini stack touched). After restart,
  the same real EIS report `toa-run-20261008210259-ba5815` remained readable
  through the authenticated HTTP API with all six text-extraction flags true,
  and `/health/ready` again returned `ok`. Containerized PostgreSQL and
  Redis remained healthy throughout. No full-node-loss recovery is claimed.
- Local LLM is configured as a `stub` for this bounded acceptance;
  deterministic fallback must not be marketed as production-quality LLM/VLM.
- APR-05 tenant authentication/isolation, paid pilots, and public service
  authorization remain out of APR-04 scope.
- VPS, DNS/ACME, external offsite backups, full-node Redis recovery, measured
  production RPO/RTO and customer operational SLA remain deferred APR-03 gates.
- Never infer supplier license/SRO validity, profitability or procurement GO
  from a manually uploaded file or a source-card price match.


## Final bounded local acceptance

- Source code deployed: `00df43958674a9eebee2bbd54e7f4116bb87173f`.
  Only the separate development stack `arvectum-local-e2e` is under
  management; no public HTTP ingress or real VPS mutation.
- End-to-end synthetic onboarding (new company, versioned supplier profile,
  PDF evidence, three tender files, report, personalized HUMAN gate) passed
  twice: `CUS-2026-000002` and `CUS-2026-000003`.
- Live read-only EIS: exact 44-ФЗ notice 0372200172326000015, getDocsIP
  archive download, 6/6 office/XML/PDF text-extraction flags true via existing
  Data Platform, report retrieval, human-gated `NEEDS_REVIEW`.
- `completed_with_warnings` remains valid because analysis is a bounded
  deterministic fallback and other source/qualification uncertainties persist.
- APR-04 is accepted **only** as operator-scoped Mac mini onboarding v1.
  Future APR-05 must introduce true tenant isolation, role/account permissions,
  entitled SaaS, billing and legal HUMAN gates. Actual Russian VPS deployment
  stays paused inside APR-03 until after development.
