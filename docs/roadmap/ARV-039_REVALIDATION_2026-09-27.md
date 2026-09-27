# ARV-039 revalidation — site and product outcome metrics

Date: 2026-09-27  
Task: `ARV-039-REVALIDATION-001`  
Authority: AUTO, repository-only evidence

## Canonical question

ARV-039 asks for outcome-oriented site and product metrics: activation, successful analysis, evidence coverage, funnel conversion, time-to-decision, automated outcome, win/loss, forecast accuracy, RFQ conversion and retention. This slice maps current repository evidence to that list. It does not deploy tracking or invent customer/commercial results.

## Existing foundations

- `docs/product/Pilot_Metrics_Definition.md` defines per-run identity, start/end timestamps, artifact references, operator actions, blocker/report counts, a 1–5 usefulness proxy, directional time saved and human-reviewed final outcome.
- `docs/product/Pilot_Success_Metrics.md` adds demo completion, time to first report, accepted usefulness, blockers caught, control/traceability confidence, feedback, would-pay and documented outcome.
- `docs/product/DP5_Feedback_and_Outcome_Loop.md` defines structured feedback/outcome records while explicitly excluding CRM, automated surveys, billing and sales outreach.
- `src/modules/outcome_intake/` persists deal/tracker-bound outcome codes, rationale, effective time, artifact bindings, revision status and event-log entries.
- Existing event, report and workflow records are potential repository-owned inputs, but current main does not evidence one consolidated ARV-039 aggregation contract.

## Coverage matrix

| Canonical signal | Current evidence | Classification | Residual |
|---|---|---|---|
| Activation | Reproducible demo completion is defined as a pilot success metric. | Definition only | No stable activation event/denominator or site-to-product cohort aggregation evidenced |
| Successful analysis | Demo completion, generated report count and blocking-issue rules exist. | Partially derivable | No canonical success predicate and denominator across runs |
| Evidence coverage | Artifact references and traceability confidence are required; benchmark/report layers also retain evidence. | Inputs exist | No unified evidence-coverage formula or aggregate |
| Funnel conversion | Would-pay and outcome decisions are recorded for pilots. | Proxy/partial | No product/site funnel stages, cohort denominator or conversion report |
| Time-to-decision | Run start/end and time to first report are defined. Outcome records have effective timestamps. | Partially derivable | No canonical start/end event pairing or cross-run aggregate |
| Automated outcome | Outcome intake stores explicit human-supplied outcome codes. | Human-recorded only | No valid automatic-outcome classification; it must not be inferred |
| Win/loss | Deal-bound outcome codes can record final outcomes when a human supplies them. | Foundation only | No normalized win/loss aggregate, missing-data semantics or revision policy for reporting |
| Forecast accuracy | No forecast/prediction record tied to later outcome is evidenced. | Absent | Requires a frozen prediction-to-outcome comparison contract before any accuracy claim |
| RFQ conversion | RFQ/TKP preparation and internal outbox foundations exist elsewhere. | Workflow foundation only | No sent-RFQ authority, response/conversion denominator or report; external send remains gated |
| Retention | No customer/product cohort retention model or repeated-use aggregate is evidenced. | Absent | Requires explicit cohort/event semantics and approved data boundary |

## Interpretation boundaries

- `customer_usefulness_score` is documented as an internal operator proxy unless real pilot feedback is explicitly collected.
- `estimated_time_saved_minutes` is directional and must not be presented as audited ROI.
- Outcome intake records are human-supplied evidence, not automatically inferred procurement or commercial truth.
- Missing signals stay `unknown` or absent; they are not converted to zero.
- No public site analytics repository, external tracker deployment, cookie consent change or production telemetry mutation was performed.

## Residual gap

The repository has useful metric vocabulary and persisted outcome/event foundations, but not a deterministic cross-run metric layer that states:

1. exact event and denominator definitions;
2. time windows and cohort boundaries;
3. unknown, missing and revised-outcome handling;
4. proxy versus externally evidenced fields;
5. prediction freeze time for forecast accuracy;
6. aggregation output with provenance back to repository-owned records.

## Bounded successor candidate

`ARV-039-OUTCOME-METRIC-CONTRACT-001` — `candidate_not_admitted`.

Allowed scope would define and deterministically aggregate the canonical ARV-039 metric contract over existing repository-owned events, reports and human-reviewed outcomes, preserving explicit denominator, unknown and proxy semantics.

It must stop before external analytics, cookies/tracking deployment, CRM/customer outreach, automated surveys, pricing or participation decisions, production mutation, private/customer data expansion, or fabricated outcome/ROI/conversion claims.

## Decision

ARV-039 is `revalidated_residual_gap`. Definitions and individual outcome persistence exist, but the full outcome-oriented metric set is not yet available as a governed deterministic aggregate.
