# APR-06/07 — шестой независимый официальный 44-ФЗ E2E, подписанные ZIP (15.10.2026)

**Статус DEVELOPMENT E2E: исходный LLM/источники ПРОВЕРЕНЫ;
правка статусов ZIP и exact-head GitHub CI ещё проверяются.**
Нельзя приравнивать подписи и ZIP-контейнеры к PDF/DOCX нативным экстракторам.

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
single real Gemma4-12B run `toa-run-20261015173500-78dec8` completed:
**4 real calls / 368.53 seconds**, API200, no fallback; three original
XML citations (subject, NMCK 1,296,999.99 RUB, archived deadline),
real report/history/evidence re-opened successfully, original archive
PDF/DOCX exports rejected with 409 and recommendation
`manual_review_required`. The original output HTML SHA:
`2e7c8a58bbd199fa0a19e7751774818cd3523654633a05c3757faa36e56f9ae7`.
No EIS/ETP activity, signatures, payments or spending.

Preliminary negative ZIP/source-role checks: **33 passed**. Initial full
regression: **4,151 passed / 238 skipped / 0 failed**, 328 pre-existing
warnings, 173.26s. After source-container metadata repair a second full
regression and CI are independently run. This does not establish production
performance metrics or commercial/legal GO.

### Raw real E2E failure and repaired evidence without replaying the LLM

The first strict E2E runner deliberately exited **1** despite genuine
Gemma4 API200: metadata of the **four original ZIP containers** remained
`text_extraction_status=pending`. Ten flat XML/DOCX had
`extracted`, so the previous uniform `14/14 native extracted` assertion
reported `10 extracted, 4 failed`. Meanwhile the real model trace
contained **15 analysed documents**: 8 XML, 2 directly extracted DOCX,
and 5 substantive nested PDF/DOCX from 4 signed ZIPs. The report was
original and fully persisted, so the issue was faulty two-layer accounting,
not missing legal/source content.

Fixed in the generic `operator_document_collection.py`: ZIP metadata
now records `archive_extracted` only if at least one substantive child
was extracted and none failed; `archive_partial` and `archive_unreadable`
are fail-closed. It records nested source/valid/failed counts without
claiming the ZIP is itself a natively decoded PDF. The generic acceptance
receipt separately totals direct native-source extraction and safely
extracted ZIP child texts; pending, partial and unreadable original ZIP
containers never pass a strict source gate.

On a **separate copy** of the original 14 SHA-protected source files,
the new real Data Platform decoder returned: **10 flat document texts,
4/4 `archive_extracted` containers, 5/5 substantive child PDF/DOCX texts,
0 failed source/child documents**. No original bytes, model outputs or
historical old failure receipt were rewritten, **no additional Gemma run**.
A private `sixth_source_and_model_combined_acceptance_evidence.json`
checks this corrected source proof against the real saved analysis,
exact EIS citations, archived export409 and `manual_review_required`.

This dual-proof DEVELOPMENT result is not a fresh end-to-end LLM invocation
on already corrected ZIP metadata, and is not a declaration that detached
cryptographic signatures were validated. It is source-bounded evidence of
the repaired previously failing status gate. Native 10/10 direct files,
ZIP 4/4 source containers and ZIP-child 5/5 text extracts are kept separate.

Expert reading of the saved report found the project contract correctly
described as present; machine-generated English risk and scope hypotheses
remain visibly marked as unverified and require follow-up. These do
not establish all-claim legal accuracy.

A separate status register describes remaining APR-06/07 acceptance:
`APR067_E2E_ACCEPTANCE_REMAINING_GATES_2026-10-15.md`.
