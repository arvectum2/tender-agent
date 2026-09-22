# ARV-004 revalidation — 2026-09-22

## Canonical target

ARV-004 requires the existing Hermes feedback/memory loop to become customer-scoped through canonical Customer / Project / ProcurementCase identities and immutable review, without changing frozen R9 contracts.

## Current repository evidence

The current repository already contains both sides of the intended integration boundary:

- src/modules/hermes_agent/models.py and service.py implement tender-scoped feedback, feedback-to-memory, eval-case creation, evidence/quality records and fail-closed tender memory isolation.
- src/modules/customer_pilot/models.py already defines canonical customer_id, project_id, procurement_case_id and run_id bindings.
- PilotReview stores review hashes plus immutable_at.
- src/modules/customer_pilot/expert_review_models.py binds expert-review/escalation records to the same Customer / Project / ProcurementCase / run scope and provides append-only hash-chained event identity.
- src/modules/customer_pilot/expert_review_service.py resolves cases/runs through scoped Customer / Project / ProcurementCase queries.

Therefore the earlier uncertainty about a missing canonical scope/review model is no longer valid. The remaining ARV-004 gap is narrower: Hermes feedback/memory rows still carry only tender_id / analysis_id, and the service does not bind or validate them against the existing customer-pilot scope/review primitives.

## Bounded successor candidate

ARV-004-CUSTOMER-SCOPED-FEEDBACK-001 remains candidate_not_admitted.

The repository now provides an existing integration target, so implementation no longer requires inventing a parallel Customer/Project/Case or immutable-review architecture.

No production/provider/customer/external mutation is performed by this revalidation.
