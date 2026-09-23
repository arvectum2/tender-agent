# ARV-004 revalidation — 2026-09-24

ARV-004 historically requires the Hermes feedback/memory loop to be bound to Customer / Project / Case with immutable review provenance. This revalidation does not change that legacy scope and does not claim customer acceptance.

## Current evidence

- `src/modules/hermes_agent/service.py` implements runtime analysis, relevant-memory loading, quality-triggered self-improvement and `run_feedback_reflection()`.
- Hermes feedback reflection currently loads `TenderAnalysisFeedback` and sends tender/field/feedback/correction data to `HermesClient.reflect_on_feedback()`.
- `src/modules/customer_pilot/models.py` independently defines `PilotFeedback` with `customer_id`, `project_id`, `procurement_case_id` and `run_id`.
- `src/modules/customer_pilot/router.py` enforces customer/case/run ownership when writing and listing pilot feedback.
- Focused deterministic tests passed: `26 passed` for `tests/tender_research/test_hermes_runtime_analyzer.py` plus `tests/test_r8_customer_pilot.py`.

## Proven residual

The two existing feedback paths are not connected: customer-pilot feedback is persisted as `PilotFeedback`, while Hermes `run_feedback_reflection()` reads `TenderAnalysisFeedback`. Repository search found no bridge that carries the customer/project/case/run-scoped pilot feedback into Hermes reflection/memory. This is the concrete remaining gap already described by the historical ARV-004 `next_result`; it is not evidence that a new architecture should be invented.

## Bounded successor candidate

`ARV-004-CUSTOMER-FEEDBACK-BRIDGE-001`: bind existing `PilotFeedback` customer/project/case/run identity into the existing Hermes feedback-reflection/memory path with immutable review provenance. Keep it repository-only, preserve customer isolation, and infer no HUMAN/customer acceptance. This is a candidate only; this revalidation does not admit implementation.
