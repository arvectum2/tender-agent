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

The isolated actual Gemma4 12B original-source run is staged privately at
`ta-apr067-r4-seventh-eok-revisions-20261015`, run
`toa-run-20261015185058-9a58e4`. It may run only once; report/API/source
citations and the successful exact-head CI must be observed rather than
presumed. **At protocol creation the real local model analysis is still
IN_PROGRESS; do not yet count this as seventh accepted E2E.**

**Authority boundary:** Owner-approved ChatGPT source review is accepted as
expert judgement for DEVELOPMENT E2E. No human legal-gold is needed as a
development prerequisite. This does not establish commercial/legal GO,
current EIS state, detached signing certificate verification, automatic bid
submission, payment, production readiness or rolling SLO. Original files and
LLM outputs remain private and are not included in the repository.
