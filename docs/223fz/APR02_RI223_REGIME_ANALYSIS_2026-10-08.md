# APR-02: RI223 source-specific analysis questions

Date: 2026-10-08. Scope: **procurement-regime-specific evidence retrieval questions**, reusing existing Data Platform and the ten-section analyst. Does not infer legal statuses, eligibility, or a GO/NO_GO decision.

## Measured failure
The actual 223-FZ procurement 32616445795 (public RI223 SOAP notice and 19 originals within an authentic RAR) is correctly registered with law_type=223fz and indexed into 300 source-bound chunks. The existing generic analyst previously asked whether participants met **44-FZ requirements**, even though the original is a 223-FZ marketing study. This is an unsupported cross-regime assumption.

## Bounded implementation
- Select an overlay only if the persisted tender law_type is exactly 223fz; keep the canonical 44-FZ, private and unknown-regime question registry completely unchanged.
- Preserve all 10 pre-existing section IDs, order, retrieval modes and source-citation machinery.
- Ask 223-FZ-specific questions about confirmed procedure, actual services vs OKPD2, contract price/terms, source-stated SME participation requirements and actual qualification evidence. Never invent buyer procurement policy or 44-FZ-specific eligibility restrictions.
- Keep retrieval-only results distinct from a synthesized LLM legal opinion. No ETP/EIS mutation, signing, payment or procurement participation action.

## Read-only authentic test
Re-run analyze_tender('32616445795', use_llm=False, record_history=False, analysis_mode='fast') against the isolated real corpus database indexed into the existing local Data Platform:
- 10/10 section questions, 25 retrieved source citations, all retrieval-only; no 44-FZ participation-compliance question.
- Source questions cover the media-monitoring service, 2027 period, SME restriction, methodology price 40% and non-price 60% and applicant experience obligations. These are **questions to evidence search**, not legal conclusions.
- Production secrets and original source files remain outside Git.

## Verification
- Unit tests ensure 223-FZ-only overlay, unchanged 44-FZ/unknown behavior and end-to-end dispatch through the existing Data Platform retriever.
- Exact-head CI and Owner REVIEW before merge.
