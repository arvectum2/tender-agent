# ARV-028 repository revalidation — 2026-09-27

## Scope

This is the standard repository-only REVALIDATION slice authorized by the active Owner continuation directive. It reconciles historical ARV-028 against current `main` without deploying n8n or changing any runtime, provider, network, credential, webhook, notification, procurement or external state.

Historical ARV-028 asks for a self-hosted n8n external orchestrator plus internal API contracts for schedules, waits, webhooks and notifications. The roadmap also fixes the boundary: business logic remains in FastAPI/Python.

## Current evidence

- `pyproject.toml` contains the current FastAPI, Redis, persistence and reporting dependencies; it contains no n8n package or repository adapter dependency.
- Root `docker-compose.yml` defines PostgreSQL only and contains no n8n service.
- `Makefile` exposes application, Redis, quality and acceptance commands and contains no n8n lifecycle command.
- GitHub default-branch searches for `n8n` and `workflow orchestration` returned no indexed repository file hit.
- Canonical queue evidence records the reusable foundations:
  - ARV-008 worker transport is complete with Redis Streams and PostgreSQL as source of truth.
  - ARV-012 production-runtime evidence has been revalidated.
  - INTEGRATION-OUTBOX-V1-001 is complete, while real delivery adapters remain disabled and separately gated.

These checks prove repository state only. They do not prove that no private or external n8n instance exists, and they do not authorize probing or deploying one.

## Reconciliation

ARV-028 is **not implemented in the canonical repository**. Current foundations can support a future external orchestrator boundary, but no repository-owned n8n dependency, service definition, lifecycle command, workflow artifact or explicit n8n-to-internal-API contract is evidenced on current `main`.

The residual is narrower than choosing a new orchestration architecture: prepare the already-roadmapped n8n boundary so that n8n invokes versioned internal APIs while FastAPI/Python retains business logic and PostgreSQL remains the source of truth.

## Bounded successor candidate

`ARV-028-N8N-CONTRACT-PREP-001` — **candidate_not_admitted**.

Permitted candidate scope:

- document the existing internal API/outbox seams that an external n8n workflow may call;
- define disabled-by-default request/idempotency/audit contracts and fixture-only examples;
- prepare a local-only compose/runbook example without starting services;
- preserve explicit HUMAN/REVIEW gates for secrets, provider/network configuration, production deployment and all external delivery.

Out of scope:

- selecting or purchasing hosting;
- starting n8n on any Mac, VPS or production contour;
- configuring credentials, OAuth, SMTP, webhooks or external notification transports;
- supplier/customer communication;
- procurement actions or commercial commitments;
- moving business decisions from FastAPI/Python into workflow definitions.

This candidate is not queue admission and does not authorize implementation or deployment.
