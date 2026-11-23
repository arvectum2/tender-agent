# Paired Data Platform + Tender Agent runtime candidate, 2026-11-23

**Status: source-level integration tested; production release HOLD pending
representative shared Qwen acceptance, exact CI and controlled rollback.**

## Immutable dependencies and boundaries

- Data Platform main: e4fdda34067dfd341e22a5ed53ea7d22f3d372f0,
  source-only merges #134, #135 and #136.
- New Python consumer wheel release: consumer-sdk-v0.4.1,
  SHA-256 5822888ab9be9081b74317953fb7a53197c3efaabe472277d1013558cd9956e3,
  GitHub release asset (0.4.0 was not overwritten).
- Tender Agent Python 3.15.2 with Redis 7 / pytest 9 compatible stack.
  Both hashed requirements.lock (dev) and requirements-runtime.lock (prod)
  bind the immutable SDK 0.4.1 release by exact URL and SHA-256.
- The opt-in RAG async ingest switch stays false by default. Neither a
  successful HTTP 202 nor a queued job is a searchable result.

## Independent acceptance before this PR

- Tender Agent combined code of modernization #734 + dual ingest #729:
  7055 PASS, 292 skipped, one local PG18-vs-PG16 R9 deselection.
- R9 separately repeated with the correct native PG16 client:
  6 PASS, disposable PG16 only; clean owned-container teardown.
- Actual two-DB disposable PostgreSQL17 and HTTP source-faithful interop:
  9/9 durable jobs completed and 9/9 RAG hits; pending search refused,
  database receipt reopened and destructive migration downgrade blocked.
- Installed published SDK 0.4.1 in the isolated Python3.15 TA venv,
  uv pip check PASS, all four consumer API entrypoints verified.
- Exact new branch targeted tests: 44 PASS; make check PASS.
- Existing Python3.15 non-root Docker design passed Linux ARM64 build
  and no-network read-only GET /health under UID10001.

## Explicit release gates not waived

1. New exact-commit GitHub CI must pass all quality, migrations,
   PG integrations, Redis integrations, security and Linux Docker jobs.
2. Data Platform's shared Qwen3-Embedding-4B production ingest p95
   remains RED in prior 256-sample observation (21,635ms vs 10,000ms).
   Previous isolated 20-sample Qwen run had 9,050ms p95 but did not
   represent 18/27 chunk production cohorts. Re-measure after controlled
   TA/DP pause without launching a second model or weakening ACL/provenance.
3. Keep async worker and TA receipt DB migration v128 disabled or gated
   until owned DB migrations, worker lifecycle, pending-job recovery,
   measurable queue-to-search completion and resource budgets are proved.
4. Preserve active Mac mini source trees and existing runtime.env files.
   Backup both live PostgreSQL databases, TA and DP release sources,
   model/embedding dimension and queue state before changing launchd.
5. Use one bounded downtime window for BOTH products with independent
   rollback on health, data contract, startup and source-faithful search.
   Do not blindly replay UNKNOWN or downgrade populated job tables.
6. Do not claim business readiness from CI PASS or source merge.
