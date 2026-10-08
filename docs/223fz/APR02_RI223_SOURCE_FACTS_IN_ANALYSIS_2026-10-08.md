# APR-02 — Source-grounded RI223 facts in Tender Research analysis

Date: 2026-10-08. Read-only original XML field projection into the existing
Data Platform-backed report and API, NOT a procurement decision.

## Measured gap

Original 223-FZ RI223 notice 32616376947 contains 3 versions, 6 explanations,
2 separate lots. Prior parser/PR #236 preserved them in raw_payload but the
existing ten-section Tender Research analysis displayed only document chunks.
Therefore revision chronology, source deadlines and clarification questions
were not visible as structured evidence in user reports.

## Bounded design

- Reuse the existing Tender Research 10-section analyzer and Markdown report;
  no parallel RAG, no second procurement decision engine.
- Surface ri223_source_observations in result, AnalyzeResponse API and CLI JSON.
  Each observation includes its specific kind (notice_revision, lot,
  lot_position, explanation), fields, XML member and SHA-256/XPath.
- Require law_type=223fz, source_regime=223fz, RI223 subsystem, valid SHA-256
  and original per-record archive hash equal to parent archive hash.
  Unverified, mismatching or unsupported sources do not become facts.
- Structured XML observations are distinct from Data Platform chunk
  citations or LLM synthesis. Sources_count is not inflated by XML records.
- Do not infer live effective version, legal status, explanation-to-lot binding,
  supplier eligibility or combined NMCK from separate lots. Unknowns remain
  explicitly UNKNOWN.
- Do not change 44-FZ or other regimes. No EIS/ETP writes, signing, payment
  or autonomous procurement participation.

## Real acceptance from original local artifacts (not in Git)

- Registry 32616376947, original EIS ZIP SHA-256:
  840927b8dddba00cc682e78192ffb263cbd89d3fec1acbaba3fa60af63fd3575.
  13 individually cited XML facts: 3 notice revisions, 2 lots, 2 positions,
  6 explanations. The report includes original source deadline values,
  including observed version 3: 2026-10-20T16:00:00. Global NMCK UNKNOWN.
- Registry 32616445795, original EIS ZIP SHA-256:
  65004d53a4d198857a192ad21052c95cfa7d812208c3ac6702324e42d7487de3.
  3 source facts: 1 notice version, 1 lot, 1 position. Existing RAR path
  remains a separate Data Platform document extraction stream.
- Adversarial regression verifies missing source marker, 44-FZ regime,
  forged parent/hash, invalid XML hash, unsupported nested payload.

## Verification and next step

- Full Tender Research: 502 passed, 1 skipped (42 warnings).
- Focused source/parser/RAG tests: 39 passed, 3 warnings.
- make check, new-file Ruff and git diff --check: PASS.
- Exact-head GitHub CI and Owner REVIEW remain required before merging.
- Content-based eligibility, financial risk, version legal effect and GO/NO-GO
  assessment remain separate downstream evidence-based work.
