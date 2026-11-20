# Targeted daily recovery: operator preflight

The existing daily CLI resumes runs and starts a new discovery; it is not a
selective historical repair command. The new read-only planner accepts exact
run ID, registry number, existing deal ID and full source fingerprint. It
rejects ambiguous identities, changed sibling revisions/deals, human decisions,
active runs, prior/orphan analysis history and missing or archived deals.
It excludes already completed identical deal/fingerprint siblings.

Run the read-only planner from the approved pinned environment:
`python -m scripts.ops.plan_daily_tender_recovery --run RUN --registry NUMBER --deal DEAL --fingerprint FULL_SHA256`.
The command explicitly sets PostgreSQL transaction READ ONLY. It never writes
or creates an intake, runs analysis, downloads documents or sends notifications.

Acceptance on the existing November 19/20 failed-item inventory: 9 candidates,
2 already completed. No live data changes.

Before adding the apply path: require exact source revision and collection
identity, verify individual existing chunk evidence against Data Platform,
retain current deal and failed-run provenance, verified production backup +
mandatory MI/PITR prewrite acceptance and shared fresh lease, no broad discovery,
post-decision automation or external submission. Reconcile any interrupted
analysis history rather than starting a duplicate. Do not use this planner as
a write authorization. Actual repair remains a separate reviewed operation.
