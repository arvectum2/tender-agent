# APR-06/07 — seventh independent, version-bound EOK2020 case

**Case:** 0348100024426000039, 44-ФЗ, archived **electronic open competition**,
not a repeated single-version EIS auction. First-party saved Oct-09 EIS archive
contains official EOK2020 notice **three revisions**, plus official clarification.
The selected notice is **v3 only**. Its archived original
`endDT` is **19.10.2026 10:00 Moscow time**, whereas original versions 1
and 2 state **16.10.2026 10:00 Moscow time**. All three source notices
state the same `maxPrice` of **1,245,000 RUB**. This is a material
source-version regression trap: older earlier deadlines must not override v3.
Source material describes works developing
the standard website management platform for the Moscow Oblast employment
centre. The saved snapshot is not proof of the current EIS revision or a live
permission to bid.

**Immutable first-party original evidence:**
- Saved getDocsIP archive SHA
  `af61797c60db6a9054380b052c495deacb62c0be5813fe3a78bb07c648dcde1e`.
- Selected v3 notice XML SHA
  `2580e43ef01f2a3b57f6e690bc09572859eafb1b7c43243b511890c083182a9d`.
- Exactly **seven attachment UID + exact official filename + declared bytes +
  SHA-256** combinations, committed to the frozen source manifest
  `docs/quality/APR067_R4_SEVENTH_EOK_V3_SHA_PINNED_SOURCES_2026-10-15.json`.
  Six are independently matched to original saved-run first-party download
  source URL UIDs. The previously missing v3 PIK contract-annex ZIP is now
  included from an independent first-party Oct-14 restored-file receipt with
  SHA `5d1411e9788212a7c7ef12ccc02d6182bf8ebf905e4a73acbb2d460c436ac8d9`.
- Staging copied the genuine getDocsIP ZIP via the normal guarded intake,
  selected one EOK v3 XML and appended **seven actual v3 originals only**.
  Historical lower-version DOCX/PDF/ZIP contents did **not** enter this
  selected-v3 document set.
- Exactly **4 original EIS XML + 7 filestore files = 11 original SHA-protected
  input files**. Four v3 ZIPs additionally contain **five substantive
  PDF/DOCX**; bounded real Data Platform preflight on localhost:18099 confirmed
  all five texts. ZIP container versus child-document extraction must be
  counted separately.
- Document set is `ready_to_analyze`, achieved by the product's native
  completeness gate, with no bypass. Adversarial synthetic fixtures verify
  fail-closed SHA mismatch, repeated UID, filename mismatch, old-v2
  selection, wrong source-role, unsafe relative source path, and independent
  restored receipt tampering.

## Actual local model + source-grounded E2E observed

The authentic standalone Data Platform + Gemma4-12B run
`toa-run-20261015185058-9a58e4` completed **once**, with **4 real
localhost Gemma calls in 333.22 seconds**, HTTP200, mode
`llm_tender_operator_provider`, no fallback, and saved result
`needs_review` / `manual_review_required`.

- All **11/11 exact SHA-protected source files** preserved and text-enabled:
  4 original XML, 3 direct PDF/DOCX, 4 signed ZIP containers. All 4 ZIPs
  `archive_extracted`, **5/5 nested substantive PDF/DOCX**, zero failed
  direct/nested documents. The actual report trace has **12** text documents
  (4 XML + 3 direct + 5 nested). Source containers and nested texts counted
  separately.
- Original evidence selector is
  `pinned_latest_archived_notice_revision`; all 3 material EIS XML facts
  `KNOWN` with **3 actual HTML `eis-xml:` citations**. Original v3 title,
  **deadline 19.10.2026 10:00 +03:00** and **NMCK 1,245,000 RUB** are
  retained; the superseded **16.10.2026** deadline does not occur in the
  persisted final recommendation, report JSON or tender summary.
- The authenticated workspace, persisted report/history, source evidence
  and read-only registry re-opened successfully (HTTP200). Both PDF and
  DOCX export for archived source returned **HTTP409**. Original report HTML
  SHA-256 `5d70b6230215b73290841c82f0689a8eaebc2f3791a632cf05e2ef0ccd7bee44`.
- ChatGPT development expert reading of the saved actual report found
  the supplied contract correctly marked **present**, no false request to
  obtain it, correct revision-specific deadline, and a review-only decision.
  Five LLM-suggested contractual risks remain explicitly labeled
  `[Гипотеза LLM — проверить договор]`, several in English. They are **not**
  independently confirmed contract clauses; absence of commercial pricing,
  staffing model or current EIS status remains an unresolved review matter.

**Tests:** 20 focused/adversarial source-UID/SHA/revision/cross-path
tests PASS; complete Mac mini regression **4,164 passed, 238 skipped,
0 failed**, 328 pre-existing warnings (189.66 s), Ruff PASS.
The Draft PR's exact-head GitHub CI is tracked separately; until that
returns SUCCESS this child checkpoint stays `in_progress`. The original
private LLM result and source file bytes were not rewritten or regenerated.

**Authority boundary:** Owner-approved ChatGPT source review is accepted as
expert judgement for DEVELOPMENT E2E. No human legal-gold is needed as a
development prerequisite. This does not establish commercial/legal GO,
current EIS state, detached signing certificate verification, automatic bid
submission, payment, production readiness or rolling SLO. Original files and
LLM outputs remain private and are not included in the repository.
