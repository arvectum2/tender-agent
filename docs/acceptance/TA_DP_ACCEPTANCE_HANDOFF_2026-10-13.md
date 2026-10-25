# Tender Agent ← Data Platform: separate R2/R4/R5 acceptance

**Recorded:** 2026-10-13. **Task:** `TA-DP-ACCEPTANCE-20261013` (blocked on owner/human gates, not on Data Platform refactor). The active Tender Agent `.agent/current-task.yaml` and its ongoing APR-06/APR-07 branches remain authoritative and are not replaced by this handoff.

## Technical boundary already complete

- Data Platform core modularization and service boundaries landed in [DP PR #121](https://github.com/arvectum2/data-platform/pull/121), with checkpoint [#122](https://github.com/arvectum2/data-platform/pull/122), on Data Platform main `daa0719` at handoff. API v1, Python consumer SDK 0.3.0, Data Platform package 0.6.0 and isolated tenant/auth contracts are retained.
- On a **disposable, nonproduction** authenticated PostgreSQL+pgvector Data Platform stage, 5/5 real EIS binary source hashes, five resource/document identities and 127/127 normalized provenance chunks were verified.
- Separate authenticated, loopback-only end-to-end Tender Agent report flow passed: manual-source DOCX/PDF HTTP 200 with valid document bytes; official archived-version report exports correctly refused HTTP 409/409; neither path granted a business GO.
- The bounded archived EIS source corpus contains 72/72 attachment SHA/size rechecks and 96/96 archived XML byte matches. This does **not** prove the present notice version, source completeness or actual bidder eligibility.
- Prior CI and full local regressions passed. The production Data Platform on Mac mini was not written to, restarted or redeployed in this handoff.

## Open gates now owned by Tender Agent

| Gate | Current state | Exit evidence / decision |
| --- | --- | --- |
| **R2 — approved persistence and provenance** | **Awaiting scope/permission and current-revision check.** Disposable stage technically proved; no approved current-revision production or enduring staging acceptance. | Explicit owner-approved staging target and permitted source dataset; same current authenticated EIS revision, original SHA-256 → DP resource/document/chunk persisted hashes/coordinates → Tender Agent API/report/PDF/DOCX with exact provenance; stale/unknown versions fail closed. |
| **R4 — independent benchmark gold** | **Not accepted.** Machine-checked local Gemma XML score 67/68 fields across 17 cases is not independent legal/commercial/citation gold. | Real independent human reviewer labels original cited facts, legal/eligibility/economics claims, false positives/negatives, conflicting versions and unknowns; frozen rubric and dated reviewer identity. |
| **R5 — source/currentness + human decisions** | **0/20 owner signoffs at handoff.** 17 official archives, three SOAP `no_data`; historically verified bytes alone do not confirm current auction state. | Twenty dated, source-cited independently checked assessments and explicit owner decisions, including UNKNOWN/DEFER where originals/current revision or rights are missing. No inferred GO. |
| **Final product acceptance** | **Waiting for R2–R5.** | Repeat one physically traceable approved current-source flow, exact-head CI, human legal/business approval and protected exports; record result in APR-06/07 acceptance. |

**Cohort note:** these R5 twenty cases are the specific original-EIS review queue, **not** the separate APR-06 broader 28-case commercial KPI denominator. Do not blend them or promote machine labels to human reviews.

## Links to existing evidence and execution

- [R2 fresh EIS source-to-report and single-service persisted proof](TDP_R2_TA_DP_FRESH_REAL_SOURCE_E2E_2026-10-12.md)
- [R4/R5 human gold protocol and 20-case review template](TDP_R4_R5_HUMAN_GOLD_PROTOCOL_2026-10-12.md)
- [20-case owner review queue](TDP_R5_20_CASE_HUMAN_REVIEW_QUEUE_2026-10-11.csv)
- [Technical audit and original-source limitations](TDP_REFACTOR_INDEPENDENT_TECHNICAL_VERIFICATION_2026-10-12.md)
- [APR-06 / APR-07 execution roadmap](../roadmap/MASTER_ROADMAP.md)
- Mac mini private EIS proof folder: `/Volumes/ArvectumSSD/Arvectum/evidence/tdp-r2/0372200172326000015-20261011/`. Raw evidence stays private.

**Explicit stop rules:** no live Data Platform port 8094 writes, production deployment, binding bid, customer outreach, legal or commercial GO, external paid API call, or disabled watchdog reactivation without separate authorization. The completed Data Platform code refactor must not be reopened to resolve these human/source approvals.
