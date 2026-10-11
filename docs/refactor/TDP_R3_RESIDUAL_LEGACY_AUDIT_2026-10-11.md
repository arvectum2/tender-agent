# Tender Agent R3: residual legacy boundary audit (2026-10-11)

Scope: src/**/*legacy*.py after source-preserving report item rows (#350)
and the report model builder extraction. Measured by Python AST
end_lineno - lineno + 1; threshold >= 60 source lines. A long function is
a review candidate, not automatically an architectural defect.

| Function | LOC | Responsibility | Next safe action |
| --- | ---: | --- | --- |
| operator_legacy_html_renderer.render_legacy_report_html | 401 | Presentation-only HTML | Extract HTML sections behind existing facade; preserve escaping and golden snapshots |
| upload_service_legacy.analyze_uploaded_demo_run | 365 | End-to-end processing orchestrator | High product risk: map state machine, transactions, failures and source metadata before extraction |
| legacy_binding_backfill.backfill_legacy_run_binding | 266 | Historic customer binding migration | Idempotence, rollback and tenant isolation tests before decomposition |
| upload_service_legacy.create_uploaded_demo_run | 109 | Upload creation and persistence | Preserve atomic transaction boundary; isolate independently testable pure logic only |
| upload_service_legacy.get_uploaded_demo_run | 94 | Read-only report retrieval | Consider read projection after source-preserving regression |
| upload_service_legacy.append_files_to_demo_run | 70 | Additional file write and preflight | Preserve all-or-nothing batch validation and rollback |

Compatibility facades remain until real runtime callers, monkeypatch tests
and E2E usage prove removal safe. Do not delete code based on LOC alone.

Remaining R3 exit gates:
1. AST architecture boundaries; zero illegal cross-repository implementation imports.
2. No duplicated business logic with Data Platform: product decisions stay in TA.
3. Exact original evidence and UNKNOWN semantics retained for real EIS.
4. Full local regression, Ruff/make check, required exact-head CI and tenant security.

This audit does not prove R2 live Data Platform original source parity,
R4 human-gold procurement model quality or R5 twenty owner approvals.
