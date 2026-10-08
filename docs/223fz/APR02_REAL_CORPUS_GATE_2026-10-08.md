# APR-02 / ARV-006 — real-source corpus admission gate

Date: 2026-10-08. Scope: **public, read-only 223-FZ evidence only**.

## Existing implementation (do not duplicate)

- `docs/223fz/INGEST_SUPPORT_MATRIX.md`: dedicated `fz223` public search, source-labelled basic facts, explicit document links, revision ambiguity detection.
- `docs/223fz/DECISION_REGRESSION_MATRIX.md`: regime-aware fail-closed decision support.
- `docs/roadmap/ARV-006_REVALIDATION_2026-09-21.md`: remaining lots, positions, change history, clarifications, protocols and lifecycle/status.
- `tests/tender_research/test_public_223fz_provider.py`: **synthetic only**, not a real-layout acceptance basis.

## Candidate public source and actual probe

- Notice **32616226131**, referenced as a 223-FZ quotation notice dated 2026-07-22 in Novosibirsk FAS decision 054/01/18.1-2139/2026, dated 2026-08-10 (public decision text: `https://base.garant.ru/483670691/`). This is a **candidate number**, not a verified downloadable EIS fixture.
- On Mac mini, GET `https://zakupki.gov.ru/223/purchase/public/purchase/info/common-info.html?regNumber=32616226131`: **HTTP 404**, 146-byte nginx page.
- On Mac mini, GET `https://zakupki.gov.ru/epz/order/extendedsearch/results.html?fz223=on&searchString=32616226131`: **HTTP 404**, 146-byte nginx page.
- These requests do **not** establish whether the notice itself is still published: routing or access policies may differ. No HTML or attachments were harvested; no claim about actual layout compatibility is justified.

## Frozen-corpus gate before parser changes

1. Obtain permissionless public **real** notices from EIS, with original URL, retrieval timestamp, effective URL, HTTP status, SHA-256, procurement method and source attribution. Maintain source-original files out of the repository when licensing, privacy, size or authenticity is uncertain; a sanitized representative fixture may be committed once verified.
2. Cover at least one concrete public notice with labelled lots/positions and, where available, source-explicit changes, clarification, protocol and status artifacts. Missing artifact types must be marked `NOT_OBSERVED`, not fabricated or inferred.
3. Record per-field ground truth: source document/URL, page/fragment, observable value, unsupported/unknown and the existing parser result. Freeze checksum(s) before adjusting extraction logic.
4. Only then implement measured deltas inside `src/tender_research/providers/public_223fz_search.py` and existing read-only intake path. No 44-FZ semantic fallback, legal-positive GO rule, platform login, external mutation or benchmark-truth rewriting.
5. Acceptance: repeatable deterministic tests using verified sanitized source fixtures, negative ambiguity tests, explicit UNKNOWN/NEEDS_REVIEW and no drift in existing 44/223 regressions.

## Current outcome

**Blocked for implementation by lack of verified real EIS fixtures.** This is a source/access blocker, not evidence that 223-FZ procurement information does not exist. Next safe action: obtain a verified public 223-FZ notice/document bundle through an authorized EIS access path and freeze the evidence matrix above.
