# Tender Agent — остаток E2E-приёмки, 15.10.2026

This file is an evidence register, not an assertion of production/commercial acceptance.
The Owner decision in `APR03B_DEVELOPMENT_AI_E2E_POLICY_2026-10-15.md`
is controlling for **DEVELOPMENT**: ChatGPT source-grounded reviews count as
expert acceptance on this stage. No newly hired human legal reviewer, twenty
independently signed gold labels or final Owner corrections are prerequisites
to the DEVELOPMENT E2E gate. An Owner approval for real ETP bids, live
production, money, signatures and contractual obligations has **not** been
granted by that rule.

## Accepted versus open gates

| Track | At 15 October 2026 | Remaining for that track |
|---|---|---|
| **APR-03B DEVELOPMENT technical E2E** | **ACCEPTED**, frozen original source, real local Gemma4, source facts and citations, authenticated workspace/reopen/history, protected archived export | None of the extra commercial corpus / independent human gold is a reason to revoke this development acceptance; separately, owner-facing browser ergonomics in Safari is still an open *product UX* check |
| APR-06 extended commercial acceptance | **7 distinct historical source-offline full model runs** with evidence admitted for development; minimum planned corpus **20** (upper end **30**) | **13–23 additional distinct full real-source E2E cases** to reach numeric target, not repeats of XML-only audits or the same case run again; sampling across procedures/formats/editions/business profiles |
| APR-06 claim-level decision metrics | Three key EIS XML facts source-backed on each of the seven sample runs; selected original-source citations and source SHA verified | Track time-to-decision (not merely LLM compute), claim-level citation coverage, corrections, missed blockers, false GO/NO-GO, unknown rate, application rework. Source-grounded ChatGPT expert classifications usable for development labels; genuinely independent commercial legal attestations are a separate release/participation gate |
| APR-07 model and document quality | ZIP/XML/DOCX/PDF/ODT examples and regression fixes; local wall times for seven different Gemma analyses | Frozen representative benchmark and auditable denominators for unsupported/fallback/OCR/document completeness, hallucinations, source versions, evidence coverage and model comparisons; don't modify benchmark truth after observing results |
| APR-07 reliable performance | Seven individual model timings; static local CI; no steady-state measurement | A **rolling** staging/production-like reliability window measuring full path latency percentiles, error, OCR/document, uptime/retries. Seven isolated model durations are **not** p95 SLO |
| Development PR/release boundary | Technical E2E changes stacked in Draft PRs #433–#443; Data Platform native ODT #125 code CI verified | Resolve review/dependency chain and integrate only under applicable change authority; separately stage and smoke-test assembled stack, not merely each isolated Draft branch |
| APR-03 / APR-04 / APR-05 commercial launch | Local runtime/onboarding/SaaS code exists separately | Russian VPS, public TLS, backup/restore, monitoring, tenant/customer onboarding accuracy, live paid pilot/legal/commercial authorization. **Not prerequisites to the already accepted DEVELOPMENT E2E**, but required before claiming a public commercial production launch |

### Historical E2E ledger — count distinct case IDs, not repeated calls

| Distinct archived EIS number | Verified originals | Actual local Gemma4 calls | Model analysis only (s) | Development E2E | Source caveat |
|---|---:|---:|---:|---|---|
| 0372200172326000015 | 6 | 4 | 138.79 | accepted | Original Museum case; no current EIS/ETP |
| 0376300000126000193 | 8 | 4 | 358.92 | accepted | Clarifications/protocols not duplicate notices |
| 0162200011826003089 | 17 | 4 | 150.08 | accepted after original ODT correction | Four authentic archived notice revisions; selected XML SHA pinned |
| 0151600003226000011 | 5 | 4 | 403.23 | accepted after source-bound docKind and report correction | Old report remains as audit artifact |
| 0152200004026000069 | 7 | 4 | 348.24 | accepted after generalized draft-contract report correction | Old report remains as audit artifact |
| 0348100024426000021 | 14 original (8 XML + 6 attachments, including 4 ZIP) | 4 | 368.53 | source + model + exact-head CI ACCEPTED | 10 flat texts + 4 archive-extracted ZIP containers + 5 nested substantive PDF/DOCX; original strict receipt failed pre-fix, preserved, corrected via deterministic replay without model |
| 0348100024426000039 | 11 original (3 notice revisions + clarification + 7 v3 UID-bound attachments) | 4 | 333.22 | source + model ACCEPTED, exact-head PR CI PENDING | One missing v3 ZIP independently restored, deadline v1/v2 16 Oct -> v3 19 Oct; 4 ZIP containers + 5 nested docs; 3 original v3 XML cites |

The seven case counts total **68** SHA-protected original source files,
but 68 is *not* the number of independent commercial decisions or examples
of full semantic correctness. Sixth child checkpoint and PR442 source
code CI are complete; seventh original EOK source + model proof passed, but
its exact-head PR443 CI is pending before marking seventh child `completed`.

## Recommended completion path

1. Finish exact-head CI for seventh original EOK revision/UID proof and
   close child checkpoint seven without repeating Gemma.
2. Use the same bounded SHA-pinned harness on the remainder of the frozen
   R4 original corpus; include at least a few real DOC/PDF/OCR/223-FZ
   procedures rather than manufacturing 15 variants of one XML.
3. Record each distinct case's **expert-observed** missed blockers, false
   claims, necessary edits, exact source citations, time-to-decision, model
   fallback/unsupported and operational errors in an append-only, versioned
   private acceptance ledger. Never retcon benchmark truth after LLM output.
4. Aggregate APR-06 real-case acceptance and APR-07 rolling staging SLO only
   after denominators and permitted environments exist.
5. Reconcile Draft PR stack and separately run an assembled-stack browser
   and staging walkthrough; production and any real procurement decision
   require their existing independent Owner gates.

This is a roadmap ledger, not a new requirement to obtain human sign-off
before the first development gate. It does **not** classify the seven historical
cases as five currently biddable commercial tenders.
