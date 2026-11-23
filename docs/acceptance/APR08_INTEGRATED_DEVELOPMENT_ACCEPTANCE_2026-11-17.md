# APR08 / ARV-065 — integrated development acceptance

Canonical roadmap requires procurement-scoped Q&A, legal/commercial calculations and explanations with citations, exposed unsupported questions, and no authoritative legal or participation approval. Bounded development gate PASS on archived replays, not generic semantic reasoning or production acceptance. Main remains a1686d85baf139b7a01b0f29ae8283a266938482. PR625 a763aaf8cf78b9c4b7f0ba16a23c77eba15caf7a and PR626 5c606bcae85d0e5822d803e07a5f287b97509f02 exact CI 19/19 each CLEAN, full make test and mirror. Integrated harness commit 427a548cffc5d61aa062826ea82fe43a54d542e5 pending successor CI and explicit integration decision.

## Reproduction

`python -m scripts.acceptance.run_apr08_integrated_acceptance` with prior private corpus dir `AI_CORP_TENDER_LEGAL_SNAPSHOTS_DIR`, empty private `APR08_SCREENSHOT_DIR`, `APR08_NODE`, `APR08_PLAYWRIGHT_MODULE`, `APR08_CHROME`, local venv including PyMuPDF. Exact DP revision 38322fd5f1cbec2d377c478d9980cae2382366a0 and clean tracked files required. Four isolated scenarios PASS: 19 legal excerpts and two comparisons; pinned XML desktop and narrow 390px Chromium; actual isolated DP original-document Chromium. Nine legal source files SHA unchanged; archived ZIP/XML/run originals unchanged. Private logs/screenshots `ArvectumSafe/apr08-integrated.nJJ8Bu/` on Mac mini. 223 focused tests, Ruff, Node simulation and full-stack diff PASS. One trailing whitespace removed. No model, live procurement, working DB changes, production or external actions.

| Criterion | Result/boundary |
|---|---|
| Procurement scope | Existing private workspace, supported run-bound templates, unsupported UNKNOWN. |
| Citations | Pinned XML facts, original DP quotes with SHA/chunk, typed terms/security, historical law. |
| Partial answers | 7/9 pinned brief, 3/3 legal comparison, 2/8 DP brief are coverage observations, not accuracy/completeness. |
| Legal | Customer references, historical sources, secondary calendar only; no current law or applicability. |
| Commercial | Explicit scenario price/cost/tax/fees and liquidity stress; no actual cash flow or obligation. |
| Auth | Anonymous 401, individually exempted POST 503 in regression tests, replay analyse denied, no bid/pay/sign. |
| UX | Actual Chromium desktop/narrow, before-analysis and archived report, reset, zero page errors. |

## Open gates

Current authoritative consolidated law and effective intervals unverified, official portal unavailable in earlier attempts. Broader semantic Q&A, 223-FZ procurement-document structured coverage, nested retrieval and goods-specific payment not validated. No representative frozen accuracy score or customer acceptance. Private operator auth is not production multitenant acceptance. APR03–07 external/business/evaluation gates unchanged. Integration of stacked PR610–617,619–623,625–626 and final acceptance successor requires separate explicit Owner decision. APR09/10 triggers not established. Verify final CI, then integrate only if authorized; no scope expansion merely to keep working.
