# APR-06/07 — шестой независимый официальный 44-ФЗ E2E, подписанные ZIP (15.10.2026)

**Статус до окончания настоящего LLM/CI: IN PROGRESS.** Нельзя считать
отдельный успешный ZIP preflight завершённым полным E2E или приравнивать
архивные ZIP-контейнеры к успешно извлечённым PDF/DOCX.

Case: №0348100024426000021, saved first-party original from frozen development
corpus. Official getDocsIP archive contains **8 original XML** (one
`epNotificationEF2020`, three explanations, protocols and placement/proposals
results) and selected notice references **6 original official attachments**.
All 14 source input SHA-256 matched the pinned first-party receipts.

Of the six source attachments: **four are ZIP** archives of originally signed
documents, two are DOCX. The four ZIPs safely disclosed **five substantive**
text documents through the real local Data Platform at localhost:18098:
two PDF sources of NMCK justification (1,301 and 4,370 extracted chars),
one 50,968-character contract DOCX, a 33,998-character contract PIK annex,
and an 85,952-character technical specification DOCX. These are *nested*
documents, not five extra first-party downloads.

Original ZIPs additionally contain HTML `Лист подписания...` receipts and
detached `.sign` envelopes. These are not the contract terms, vendor quotes
or price justifications. New deterministic parser behavior excludes such HTML
signing sheets and `.sign/.sig/.p7s/.p7m` payloads even if a broad extension
allowlist would otherwise include them. The common document role classifier
no longer mistakes `Обоснование начальной цены контракта.pdf`,
`Определение начальной цены контракта.pdf`, or performance-security annexes
for a contract draft just because `контракта` appears in the filename.
The genuine signed smart-contract and its PIK annex still retain contract
roles. Paths, duplicate ZIP entries, symlinks and archive-size budgets retain
their existing fail-closed handling.

There is **no assertion here that a detached cryptographic signature was
verified**. Signature check and independently validated signer trust would
be an additional, separate capability. Here the bytes are preserved, and
non-substantive signing sheets are excluded from model input.

Original local stage: `ta-apr067-r4-sixth-signed-zips-20261015`. The
single real Gemma4-12B run was started as
`toa-run-20261015173500-78dec8`, with original 14-file source inventory,
without a current EIS fetch, ETP effects, signatures or spending. Pending
completion receipt: `apr067_r4_sixth_signed_zips_e2e.json`.

Preliminary negative ZIP/source-role checks: **33 passed**. Full local
regression on the changed code: **4,151 passed / 238 skipped / 0 failed**,
328 pre-existing warnings, 173.26s. Results are not production performance
metrics and do not establish commercial or legal GO.

At finish, record two **separate** measurements:
1. original immutable source container SHA coverage, and
2. successfully readable substantive nested documents and unsupported ZIP
containers. `14/14 original bytes preserved` is not `14/14 native text
extractors passed`. Never mask a ZIP's unsupported native extraction status.

A separate status register describes remaining APR-06/07 acceptance:
`APR067_E2E_ACCEPTANCE_REMAINING_GATES_2026-10-15.md`.
