# APR-02 / RI223: authentic RAR inner-document processing and evidence projection

Date: 2026-10-08. Scope: **read-only, source-bound document acquisition and Data Platform text extraction**, not automatic award/legal/participation decisions.

## Verified authentic evidence
- EIS public RI223 procurement **32616445795**. Original getDocsIP ZIP SHA-256: 65004d53a4d198857a192ad21052c95cfa7d812208c3ac6702324e42d7487de3.
- XML subject: **МИ №3727/МИ — Мониторинг СМИ и информационного пространства (D27P100523)**; source initial sum **1,020,000 RUB**. Exact notice lot: 1, observed protocol records: 0. No legal/status interpretation.
- Original RAR5 attachment 3727_МИ.rar: SHA-256 36ef971be08ba1c4040e717239b78e464743542ee180f63bf37eb2ce79774241; 3,606,714 bytes.
- Authentic bounded libarchive extraction: **19/19 inner files** (8 PDF, 8 DOCX, 1 legacy DOC, 2 XLSX); total original expanded bytes **4,044,608**.
- Live internal Data Platform accepted and extracted **19/19 documents, 0 failed, 300 projected chunks**. Repeated source acquisition reused the same canonical records; source archive/member hashes retained.
- Original artifacts and isolated analysis DB are outside Git at /Users/master/arvectum-runtime/eis-223fz-corpus/2026-10-08/32616445795/analysis/.

## Content-grounded observations (not legal conclusions)
From original extracted documents, not guessed title:
- Извещение.docx: organizer/agent ООО «ГЭХ Закупки», customer ПАО «ТГК-1»; open electronic marketing research reserved for SME participants.
- 2_Техническое задание_1.docx: Monitoring media and information space. Geography: Saint Petersburg, Leningrad region, Karelia and Murmansk region. Work period from signing, not before 2027-01-01, until 2027-12-31. Price stated as 1,020 thousand RUB **excluding VAT**.
- РАЗДЕЛ 9. МЕТОДИКА ОЦЕНКИ (работы-услуги) 40х60.doc: Price weight 40%, non-price weight 60%. Subcriteria include reputation, financial condition and qualifications; exact formulas must be cited from the original document.
- Full procedure-specific eligibility, contract and outcome review is not asserted.

## Architecture, controls and reusable services
- Reuse libarchive bsdtar (Docker package libarchive-tools); no new proprietary RAR engine.
- Enforce RAR4/5 magic, max compressed and uncompressed sizes, per-document size, entry counts, compression ratio, safe paths, regular-only files, allowlisted document extensions and bounded subprocess time.
- Extract bytes via bounded stdout, never with archive-authored file paths. Reject archives whose listing is unsafe or unsupported; encrypted/unsupported members remain review-only.
- Canonical document repository produces stable child file identities, hashes and original source XML/member provenance. Existing Data Platform owns document text/OCR and chunk projection. The RAR container itself remains unparsed.
- Preserve explicit stages: acquired, child files registered, text ready for analysis, separately reviewed domain/GO decision. Text-ready never implies completed legal/participation analysis.
- No EIS/ETP mutation, signing, payment, customer communication or autonomous procurement participation.

## Validation
- Real original 19/19 decompressed and processed by Data Platform with 300 traceable chunks.
- Synthetic positive/negative tests cover unsafe and duplicate archive paths, links, oversized members, wrong signature, source gating, idempotent database projection, Data Platform document reuse, and review-required fallback.
- Focused tests, make check, Ruff, git diff --check and exact-head CI required.
