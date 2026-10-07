# ARV-019 canonical procurement workflow projection

The Commercial Workflow admission extends the existing operator kanban without creating another procurement state model. The read-only workflow projection maps the canonical `DealStatus` lifecycle into operator-facing funnel stages and joins the existing Procurement Portfolio and Submission Readiness evidence.

Each projected item exposes its canonical status, human/agent decision, submission-readiness status, readiness flags, factual submission state and recorded outcome. Preparation or submission stages without canonical readiness evidence receive an explicit `READINESS_EVIDENCE_MISSING` blocker instead of inferred readiness.

The kanban cards now display decision, readiness, blocker count and outcome. The `/commercial-console/workflow` endpoint exposes the same stages together with the existing portfolio KPI calculations. Status changes remain human-initiated through the canonical status engine; this slice adds no autonomous participation, submission, signing, external communication or commercial effect.

Focused verification covers the operator console, portfolio and canonical status engine. Exact-head CI remains required before completion or merge.
