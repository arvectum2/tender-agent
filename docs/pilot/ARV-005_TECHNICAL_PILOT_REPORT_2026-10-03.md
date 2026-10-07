# ARV-005 — aggregate technical pilot report

Date: 2026-10-03
Canonical task: ARV-005-CONTROLLED-PILOT-EVIDENCE-001
Repository: arvectum2/tender-agent
Pilot scope: read-only public procurement intake, local parsing/embeddings/inference, deterministic Decision Core, report generation. No authenticated EIS/ETP actions, submissions, EDS, outreach, payments, or commitments.

## 1. Technical outcome

The planned procurement denominator was exercised:

- 12 unique 44-FZ procurements in frozen waves 3 + 5 + 4;
- 3 unique 223-FZ exploratory procurements, scored separately;
- 15 unique public procurement numbers total.

For the 44-FZ core, all 12 procurement numbers have a completed local technical report. The original Wave 3 confirmation result for W3-C was intentionally preserved as a source-bound blocker; after the confirmation set was closed and its filename-classification defect received a regression fix, the same procurement was reacquired in a separate supplemental run and completed deterministically without re-invoking the counted LLM.

Human usefulness and commercial acceptance were not evaluated by the executor. All such conclusions remain HUMAN/REVIEW evidence.

## 2. Frozen runtime

Counted local inference used:

- provider: openai_compatible;
- model: arvectum-gemma4-12b-it-qat-q4_0;
- llama.cpp loopback endpoint: 127.0.0.1:8081;
- provider timeout: 120 seconds;
- embeddings: local Qwen3-Embedding-4B endpoint on 127.0.0.1:8090;
- PostgreSQL/pgvector: isolated runtime on 127.0.0.1:55432.

The model/provider/timeout configuration was not changed inside a frozen wave.

Final post-confirmation code verification:

- canonical code head before report/checkpoint commits: 7653c0700f02a3886655950c4aa0431823c558c0;
- focused/relevant exact-head tests: 105 passed, one Starlette/httpx deprecation warning;
- GitHub Actions CI run 37132350065: success.

## 3. 44-FZ core results

| Wave | Case | Registry number | Final technical state | Local LLM provenance | Decision Core |
|---|---|---:|---|---|---|
| W1 | A | 0342200026726000083 | completed with warnings | invoked; provider/model explicit; no fallback | NEEDS_REVIEW |
| W1 | B | 0333300006126000121 | completed with warnings | invoked; provider/model explicit; no fallback | NEEDS_REVIEW |
| W1 | C | 0301200067526000236 | needs review | invoked; provider/model explicit; no fallback | NEEDS_REVIEW |
| W2 | A | 0351100020326000084 | needs review | invoked; 4/4 controlled sections failed validation; explicit deterministic fallback | NO_GO |
| W2 | B | 0338300012526000076 | completed with warnings | invoked; 4/4 sections failed validation; explicit deterministic fallback | NEEDS_REVIEW |
| W2 | C | 0822500000926000094 | needs review | invoked; 4/4 sections failed validation; explicit deterministic fallback | NEEDS_REVIEW |
| W2 | D | 0348200027326000071 | needs review | invoked; 4/4 sections failed validation; explicit deterministic fallback | NEEDS_REVIEW |
| W2 | E | 0119200000126016261 | completed with warnings | invoked; 4/4 sections failed validation; explicit deterministic fallback | NEEDS_REVIEW |
| W3 | A | 0853500000326006680 | completed with warnings | invoked; 4/4 sections failed validation; explicit deterministic fallback | NEEDS_REVIEW |
| W3 | B | 0348200027026000447 | needs review | invoked; 4/4 sections failed validation; explicit deterministic fallback | NEEDS_REVIEW |
| W3 | C | 0373200074826000979 | original confirmation run source-bound blocked; supplemental post-fix run completed with warnings | supplemental run intentionally did not re-invoke counted LLM | NEEDS_REVIEW on supplemental report |
| W3 | D | 0329100002526000044 | completed with warnings | invoked; 4/4 sections failed validation; explicit deterministic fallback | NEEDS_REVIEW |

### 44-FZ aggregate

- Completed reports: 12/12 unique procurement numbers.
- Counted/supplemental cases with local LLM invoked: 11/12.
- Clean controlled-LLM path without fallback: 3/11 LLM-invoked cases (Wave 1).
- Explicit fail-closed deterministic fallback after controlled-section validation failure: 8/11 LLM-invoked cases (all five Wave 2 cases plus W3-A/B/D).
- Decision Core distribution across final reports: 1 NO_GO, 11 NEEDS_REVIEW.
- Silent LLM fallback after the provenance remediation: 0 observed.
- Cross-procurement source ownership violation in the frozen Wave 3 confirmation set: 0 observed.

The low clean-LLM completion rate is a technical reliability finding, not a human usefulness or commercial-acceptance result.

## 4. Wave 3 confirmation and post-confirmation remediation

Wave 3 was frozen before model-output inspection. No tuning was performed until all four confirmation cases were closed.

Confirmed defects and post-confirmation treatment:

1. W3-A — application/instruction boilerplate leaked into goods-oriented analysis.
   - Regression added to prevent product-scoped facts from application/instruction boilerplate.
   - After deterministic rerender, drug/ЖНВЛП/therapeutic boilerplate is absent from accepted goods requirements and customer decision material.
   - Diagnostic scope-classification evidence may still retain source excerpts; those excerpts are not accepted procurement facts.

2. W3-B — generic contract appendix table rows were promoted to goods line items.
   - PIK/ЕАСУЗ SLA rows and unrelated contract-table rows are no longer accepted as procurement goods.
   - Canonical line-item count dropped from 17 to 9 after remediation.
   - Eight false canonical items were removed.

3. W3-C — underscore-separated Russian filenames were not classified as required document kinds.
   - Проект_контракта_* and Техническое_задание_* are now recognized consistently.
   - Original confirmation run remains preserved as docs_required.
   - Supplemental reacquisition produced a complete 8-document set and a completed deterministic report.

4. W3-D — delivery-address row from the contract was promoted to a goods line item.
   - The address row is no longer accepted as a product.
   - Canonical line-item count dropped from 2 to 1 after remediation.

Primary remediation commits include e0dce95 and compatibility follow-up 1c90fcd. Exact-head local regression tests and CI are green.

## 5. Other material defects/regressions captured during the pilot

The pilot produced regression evidence for the following classes of defects:

- unsafe 44-FZ search-card URL selection and printForm/report-link confusion;
- public EIS procedure-specific document URL resolution;
- revision selection where an auxiliary clarification was incorrectly treated as a competing active notice revision;
- document-kind aliases such as Проект ГК, Техническая часть, ООЗ, mixed-script variants, and underscore-separated filenames;
- exact EIS deadline timezone preservation;
- top-level LLM provenance incorrectly reporting clean completion when controlled sections failed validation;
- canonical report/customer-decision disagreement with Decision Core;
- present-but-unparsed contract semantics;
- generic scope/template contamination and false goods extraction from contract/application tables.

These defects have regression tests or explicit bounded follow-ups in the task checkpoint/history.

## 6. 223-FZ exploratory wave

The three 223-FZ cases were frozen before detail/model inspection and were not mixed into the 44-FZ score.

| Case | Registry number | Search subject | Result | LLM |
|---|---:|---|---|---|
| E223-A | 32616432990 | cable | source-bound blocked; 0 documents | not invoked |
| E223-B | 32616423713 | lighting | source-bound blocked; 0 documents | not invoked |
| E223-C | 32616427405 | electrical supply | source-bound blocked; 0 documents | not invoked |

Observed 223-FZ limitations:

- the current public 223-FZ detail parser returns parse_error / unsupported_layout for all three frozen cases;
- detail parsing returned no confirmed customer and no document links;
- the 223-FZ search-card parser populated customer with publication-date-looking text in all three frozen cases;
- the generic public handoff attachment supplement currently calls the 44-FZ detail helper, so 223-FZ attachment dispatch is not law-aware end-to-end.

These are source-bound technical blockers. No 44-FZ legal/readiness semantics were inferred onto the 223-FZ cases, and no LLM was invoked after source completeness failed.

### Bounded 223-FZ follow-ups

1. Implement and fixture-test the current notice223 detail layout, including customer/source ownership and document-link extraction.
2. Make public attachment dispatch law-aware (44fz vs 223fz) instead of using the 44-FZ detail helper unconditionally.
3. Fix 223-FZ search-card field attribution so publication date cannot populate customer identity.
4. Add live-read-only regressions for the three frozen registry numbers or sanitized fixtures derived from their layouts.
5. Only after source completeness is reliable, run a separate 223-FZ semantic/readiness pilot; do not inherit 44-FZ hard-blocker semantics implicitly.

## 7. Runtime incident and evidence limitation

During Wave 2, Docker Desktop state loss removed the prior runtime PostgreSQL volume. The isolated database was restored from the available PostgreSQL dump and migrated to the current schema. Run-directory evidence and canonical checkpoints preserved the pilot history, but post-July historical database runtime-control traces that were not present in the restored dump cannot be reconstructed from the database.

This limitation is explicit in the checkpoint and does not change the preserved filesystem/run evidence.

## 8. Safety / external-action declaration

Throughout the pilot:

- procurement discovery and document acquisition were public and read-only;
- no authenticated EIS/ETP workflow was used;
- no application, bid, clarification, RFQ, email, or other external communication was submitted;
- no digital signature operation was performed;
- no payment, purchase, contractual commitment, or other consequential external action was performed;
- external_action_allowed remained false where Decision Core exposed that field.

## 9. Completion assessment

The technical pilot evidence package satisfies the planned execution denominator:

- 12/12 unique core 44-FZ procurements have completed reports;
- 3/3 exploratory 223-FZ procurements are explicitly source-bound blocked and scored separately;
- aggregate technical findings are recorded here;
- confirmed 44-FZ defects have regression coverage;
- 223-FZ gaps have explicit bounded follow-ups;
- human usefulness/commercial acceptance remains unclaimed and requires separate human review.

The strongest remaining engineering finding is not source isolation but local controlled-LLM reliability: after Wave 1, eight subsequent LLM-invoked 44-FZ cases failed all four controlled sections at validation/timeout and correctly fell back after the provenance fix. Future model/prompt/performance tuning should therefore be treated as a new frozen evaluation phase rather than retroactively changing this pilot.
