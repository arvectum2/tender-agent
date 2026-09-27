# BASE-014 customer workspace revalidation

Date: 2026-09-27
Task: `BASE-014-REVALIDATION-001`
Base: `189799ce4cc44a4e83e75169d689613bd14b55bf`

## Result

The historical “basic contour ready” statement is supported and substantially extended by current repository-owned foundations. Main contains canonical customer profiles, customer-bound projects and procurement cases, analysis-run/review/checklist lifecycle, cross-customer isolation controls, and an internal commercial kanban that delegates human-initiated transitions to the canonical status engine.

The item is not declared fully complete. Repository evidence does not establish a single unified end-user clients/projects/cases/kanban experience with production authentication and role enforcement. The commercial console is explicitly internal, and existing product documents preserve production auth as outside the current phase.

## Evidence matrix

| Capability | Current evidence | Reconciliation |
|---|---|---|
| Customer registry | `src/modules/customer_registry/` owns customer profile, external-reference and contour primitives. | Implemented foundation. |
| Projects and procurement cases | `src/modules/customer_pilot/models.py` and `router.py` create customer-bound projects/cases and scoped analysis runs. | Implemented foundation. |
| Review checklist and lifecycle | `PilotReview.checklist` plus client-ready, delivered, archive and feedback routes preserve explicit human review. | Implemented foundation. |
| Customer isolation | Customer/project/case bindings, scoped queries, artifact namespaces and R8 acceptance evidence reject cross-customer access. | Implemented and regression-tested. |
| Procurement search entry | Tender Operator UI and tests preserve the “Найти закупку” exact-number entry. | Implemented as a separate operator surface. |
| Kanban | `commercial_operator_console` renders an internal board over canonical `DealStatus`. | Implemented internal operator surface. |
| State transitions | Kanban changes are human-initiated, audited and delegated to the canonical status engine. | Implemented; no autonomous transition. |
| Production auth and roles | Current console documentation explicitly says no production auth was added in this phase. | Residual security/product boundary. |
| Unified customer-facing workspace | No single repository artifact was established that unifies customer/project/case, search, checklist and kanban under production role enforcement. | Residual gap; not inferred. |

## Validation

```text
uv run pytest -q   tests/test_r8_customer_pilot.py   tests/test_r8_acceptance_tenant_stage.py   tests/test_commercial_operator_console_c4.py

18 passed, 9 warnings
```

Warnings were existing Starlette/httpx deprecation and SQLite teardown ordering warnings; no focused test failed.

## Bounded successor candidate

Candidate only; **not admitted**:

`BASE-014-UNIFIED-WORKSPACE-UI-001 — Unified authenticated customer/project/case workspace`

Traceable boundary:

1. reuse the existing customer registry, pilot workspace and canonical commercial status engine;
2. define no new workflow states or procurement decision authority;
3. require separate canonical admission and security review before production authentication, authorization or role changes;
4. preserve tenant isolation, human-only status transitions and explicit checklist/review gates;
5. do not expose private/customer data or create external/procurement effects.

## Boundaries

No production authentication or authorization was changed; no private/customer data was read; no deployment, production mutation, procurement participation, application submission, external message or commercial effect occurred.
