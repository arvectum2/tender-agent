# APR-06: AI-only provisional assessment of all 28 candidates (13 October 2026)

**Reviewer:** GPT-6, retrospective technical/procurement risk screening. **Evidence time:** 13 October 2026, 12:33 MSK. **Decision class:** INTERNAL ADVISORY ONLY. Not independent human expert opinion, a verified legal conclusion, owner-approved risk acceptance, fresh EIS notice audit, or bid authorization.

This report is based on the repository's [28 unverified intake candidates](apr06_candidate_pool_2026-10-09.json), [nine-case independent primary-source AI audit completed 9 October](APR06_GPT6_INDEPENDENT_REVIEW_2026-10-09.md), [archived source-hash audit JSON](apr06_independent_gpt6_audit_2026-10-09.json), and [machine outputs](apr06_machine_prefill_2026-10-09.json). The case-by-case machine-readable re-screen is [apr06_ai_provisional_asof_2026-10-13.json](apr06_ai_provisional_asof_2026-10-13.json). Original notice and attachment files were **not** retrieved or rehashed during the present run: Mac mini, where private originals are stored, was offline in Desktop Commander. Public EIS search yielded no independent 13 October source confirmation. Previous recorded SHA-256 strings are references, not fresh integrity validation.

## AI screening outcome and denominator

| Metric | Observed | Interpretation |
|---|---:|---|
| Candidate procurement IDs in intake | **28** | 20 under 44-ФЗ; 8 under 223-ФЗ; unverified candidate register only |
| Previously examined against saved primary-source EIS material | **9** | All are 44-ФЗ, using 9 October AI audit; source read was not repeated today |
| Candidate IDs without a completed original-source AI case audit | **19** | **DEFER / NOT ASSESSED** for case-level technical/legal fit; cannot be truth labels |
| Previously audited cases with an **archived** submission deadline already past by 13 October 12:33 MSK | **7** | Historical deadline only, not an independent live status or an owner participation decision |
| Previously audited cases with a future **archived** deadline | **2** | Museum of Bread and Moscow Region Employment Centre; require current EIS edition/status and documents |
| Previously audited cases with incomplete text extraction | **1** | Employment Centre: 10 of 19 files marked readable, no inference about absent nine files |
| New original EIS document reads / verified live case status this run | **0 / 0** | **No fresh procurement source truth** |
| Human expert reviews, verified legal GO/NO_GO labels, approved acceptance KPI | **0 / 0 / 0** | Commercial acceptance: **NOT MEASURED / NOT ACCEPTED** |

### Nine previously source-reviewed cases: my updated screening

| Notice | Machine at original run | Earlier independent AI review, 9 Oct | 13 Oct **retrospective** judgment | Source-grounded issue |
|---|---|---|---|---|
| **0158300034526000388**, Аксай | NO_GO | DEFER | **No action on archived expired deadline; recheck original EIS before any new conclusion** | **HIGH:** machine used edition 1 with 9 Oct deadline despite stored edition 5 extending to **12 Oct 08:00**. An error in the earlier hard NO_GO, although edition 5's deadline itself has now passed. Tilda versus Russian-software-register CMS, 12-month license/hosting and 14-day delivery remain unresolved attachment/version and cost questions. |
| **0372200172326000015**, Музей хлеба | NEEDS_REVIEW | DEFER | **DEFER** | Stored EIS deadline **16 Oct 10:00**, НМЦК ₽1m. Technical terms include three visual concepts, collateral designs, separated public server and isolated CMS backend, mandatory external penetration test and delivery by 7 Dec. Unknown infrastructure ownership, testing fee, contract liability and copyright assignment. |
| **0348100024426000039**, ЦЗН МО | NEEDS_REVIEW | DEFER | **DEFER** | Stored EIS notice edition 3 extended to **19 Oct 10:00**, whereas machine used edition 1 (**16 Oct**). Large legacy platform modernization; NDA, domestic test hosting, integration access and load tests for 6000 visitors/300 staff; only **10/19** attachments text-readable. НМЦК ₽1.245m is not enough to infer profit without source/technical access. |
| **0377100005726000128**, «Чемал» | NO_GO | NO_GO | **Archived deadline expired** | Stored 13 Aug 08:00 +07; Bitrix site; technical cost not independently priced. |
| **0376300000126000193**, Майкоп | NO_GO | NO_GO | **Archived deadline expired** | Stored 2 Jun 07:00 +03; site plus support, not an impossibility verdict. |
| **0169300008226000225**, Троицк AR | NO_GO | NO_GO | **Archived deadline expired** | Stored 14 Sep 09:00 +05; AR media, integration. A notice of cancellation of an *application* must not be confused with cancellation of the procurement. |
| **0169300008226000223**, Троицк multimedia | NO_GO | NO_GO | **Archived deadline expired** | Stored 14 Sep 09:00 +05; historical application deadline only. |
| **0169300003326000181**, Златоуст | NO_GO | NO_GO | **Archived deadline expired** | Stored 27 Jul 07:00 +05; website maintenance. |
| **0162300005826000156**, Верхняя Пышма | NO_GO | NO_GO | **Archived deadline expired** | Stored 17 Jun 07:00 +05; personal cabinet/ЕСИА. |

**Important date distinction:** the original October 9 model DEFER for Aksay was reasonable *at that historical snapshot* because a later archived notice extension was missed. On **13 October**, even that later stored deadline is in the past. The above is a retrospective time comparison, not a claim that no further EIS revision exists. For the Museum and CZN, having a future **saved** deadline does not prove a live, unchanged application window.

## Nineteen candidates that cannot be responsibly scored

The remaining candidate IDs have no prior full archived source-read model record in this evidence set: eleven under 44-ФЗ and eight under 223-ФЗ. The intake listing category/subject can identify a possible topic, **not** legal procedure, original deadline, participant requirements, technical deliverables, risks or true unit costs. The JSON names every one of these nineteen IDs and marks `DEFER_INSUFFICIENT_PRIMARY_EIS_EVIDENCE`, `NOT_PERFORMED` rather than inventing a favorable/negative grade.

Prioritize authentic EIS original notice and revision receipt, at least one source-bound attachment digest, status and lot deduplication *before* reviewing applicability of company competencies, economic exposure and procurement constraints. In particular, do not route the eight 223-ФЗ candidates through a 44-ФЗ source adapter or presume that a single-supplier procedure invites open competition.

## Product-quality findings and remediation status

1. **HIGH, previously reproduced:** Aksay hard NO_GO was generated using outdated notice revision 1. The parser's latest-valid `epNotification` selection and negative regressions were already fixed on APR-06 branch before this task. This run preserves that result rather than claiming a new discovery.
2. **HIGH, previously reproduced:** CZN analysis displayed the earlier application deadline instead of stored edition 3. This is a customer-visible fact error even though NEEDS_REVIEW remained cautious. Existing tests cover it; proof of live current revision is still missing.
3. **HIGH, unresolved integrity gate:** an archived SHA string cannot prove the current EIS notice or attachment revision. The commercial scorer's format checks cannot replace independently read bytes, hashes, current status and evidence binding.
4. **HIGH, unresolved human-gold gate:** our AI opinion is part of the SUT-adjacent model family, not an independent professional label. Counting these nine, or the nineteen missing-source cases, as human expert truth would contaminate the 20–30-case commercial benchmark. Keep frozen comparator and threshold approval separate.
5. **MEDIUM, source completeness:** CZN's 10/19 text extraction limits completeness claims; no unparsed file may be treated as carrying no obligations.

## Next acceptance actions (no unsolicited external effect)

First, from a machine with authorized original-source access, re-fetch the currently published EIS revision and immutable attachment receipts for Museum and CZN, plus Aksay for a retrospective stale-date regression. Then verify the actual contract/TЗ requirements, citations, delivery constraints and Arvectum's supplier eligibility. For the other nineteen, run primary-source read-only collection and deduplication before any source-bound expert assessment. Measure corrections and false decisions against **genuinely independent reviewer** decisions; obtain owner approval of seven proposed KPI thresholds. Only then may the APR-06 acceptance gate be evaluated. No applications, customer questions, signings, credentials, payments, production changes or model downloads were made.

**Reproduction (offline, creates a new output file only):**

```sh
python -m scripts.acceptance.apr06_ai_provisional_review \
  --as-of 2026-10-13T12:33:00+03:00 \
  --output /tmp/apr06-ai-provisional-NEW.json
```
