# APR-02 — RI223 document evidence dossier (technical, qualification, contract)

2026-10-08. Read-only decision-preparation view in existing Tender Research.
Not legal interpretation, verified requirement satisfaction, supplier eligibility,
scored financial/contractual risk, or an autonomous GO/NO-GO.

## Measured issue

Authentic RI223 32616445795 contains 19 original documents from the source RAR
and 300 Data Platform-extracted canonical document chunks (8 PDF, 8 DOCX,
1 DOC, 2 XLSX). Existing ten-section Data Platform RAG report exposed source
citations per section but did not offer a bounded, auditable domain-by-domain
review matrix for practical screening of technical scope, applicant qualification,
application composition, evaluation, terms, participation, and schedule.

## Implementation — reuse existing analyzer and source citations

- A deterministic seven-domain matrix is generated from already retrieved
  ten-section Tender Research results; no new retriever, OCR, LLM or Decision Core.
- Only exact-confirmed RI223 source-bound 223-FZ tenders with original XML
  observations are eligible. 44-FZ and unknown-source analyses remain unchanged.
- Each domain points to at most three original Data Platform document citations:
  exact registry number, document ID/name, chunk ID and bounded verbatim source
  excerpt. Cross-registry or empty snippets are rejected.
- Every domain explicitly remains NEEDS_HUMAN_DOCUMENT_REVIEW (excerpt found)
  or NO_CITED_DOCUMENT_EXCERPT (not found in bounded search), with
  requirements_verified=false, supplier_fit=UNKNOWN,
  contract_risk=NOT_ASSESSED and decision=NOT_DECIDED.
- Several source-bound RI223 lots cause explicit UNRESOLVED_MULTI_LOT: a shared
  excerpt is not assigned to an individual lot without additional source proof.
- The existing Markdown report, AnalyzeResponse API, and CLI JSON expose the
  same matrix. No misleading source counts are added to Data Platform citation
  totals and no external EIS/ETP actions are performed.

## Original source acceptance — live Data Platform and offline audit

- Original RI223 SOAP archive 32616445795 SHA-256:
  65004d53a4d198857a192ad21052c95cfa7d812208c3ac6702324e42d7487de3
- Preserved isolated original database (outside Git):
  /Users/master/arvectum-runtime/eis-223fz-corpus/2026-10-08/32616445795/analysis/real-archive-analysis-smoke.sqlite3
- The original SQLite has 20 registered records (RAR container + 19 child
  documents) and **300 canonical extracted document text chunks**.
- **Real authenticated Data Platform acceptance (read-only, no mock retriever):**
  after passing the existing internal API credential via the authorized
  Mac mini production runtime environment (never printed/stored in Git),
  analyze_tender('32616445795', use_llm=False, record_history=False,
  analysis_mode='fast', save_report=False) returned **completed**,
  **10/10 source-retrieval sections, 25 distinct source chunk citations,
  7/7 dossier categories, 3 original-chunk excerpts per category**,
  **0 errors**, no LLM synthesis and no procurement decision.
- An initial same-machine call without the production internal key returned
  no_context. Direct collection stats revealed **HTTP 401 invalid internal
  API key** (NOT a missing index); reusing the authorized runtime credential
  verified that the original collection and embeddings were ready.
  Never interpret a failed authentication check as missing/expired index.
- Separate read-only offline SQLite source audit matched seven domain
  excerpts to actual filename/document/chunk rows by literal keyword. This
  is independent support for source provenance, not simulated vector search.
- All dossier rows remain review-only and unverified for legal status,
  company fit, lot applicability and contractual/commercial risk.

## Test and safety boundary

- Unit/adversarial checks include 44-FZ bypass, cross-registry exclusion,
  no-source fail-closed state, duplicate chunk elimination, multi-lot unknown
  binding, bounded snippets and unchanged ten canonical sections.
- Full Tender Research regressions, make check, exact-head CI and Owner review
  are required before merge.
