# APR-03B — Private Operator Workspace (local acceptance)

## Implemented
- Browser entry /pilot/tender-agent/workspace protected by existing pilot Basic Auth. Local single-operator mode, not public SaaS.
- Real EIS notices: 19-digit 44-FZ or 11-digit 223-FZ numbers, or official HTTPS URLs. Strict allowlisted origin and notice path.
- 44-FZ reuses configured getDocsIP; 223-FZ reuses conservative public-source loader. Missing documents do not fabricate success.
- Existing persisted runs, original documents, event log and human-triggered analysis; source-bound citations, risks, UNKNOWN, PDF/DOCX export.
- Read-only canonical procurement registry and Tender Research history. Bounded search/pagination; limited downloads within approved local data root. No SQL console.
- Offline first-party HTML/CSS/JS; sensitive source content rendered as text rather than executable HTML.
- No submission, signature, external messages, payment or automated GO/NO_GO.

## Truth and constraints
The existing private pilot protects /pilot/tender-agent/** and /api/demo/tender-agent/** with Basic Auth. No unknowns are invented: a database with zero procurement_tenders rows shows an empty registry. Pilot runs remain a separate persisted source rather than magically populated canonical DB records. This local product implementation is not evidence of multi-tenant isolation, a public VPS or production SLO.

## Human operator acceptance
1. Open the private Mac mini URL /pilot/tender-agent/workspace from a browser and authenticate.
2. Input a real 44-FZ notice number or official link, inspect original documents, warnings and extraction.
3. Trigger analysis explicitly, inspect cited requirements/risks/economics, UNKNOWNs, PDF and DOCX.
4. Reload and browse history of past runs and their files; inspect the canonical database or an honest empty state.
5. Try a real 223-FZ official URL; verify conservative behavior for missing/unsupported documents.
6. Sign off the browser journey; until then APR-03B remains open, regardless of repository/CI passing.

## Not part of APR-03B
No Russian VPS purchase, public DNS/TLS, offsite DR, multi-tenant paid SaaS, ETP submission, guaranteed correctness or commercial HUMAN acceptance.


## Mac mini isolated acceptance evidence (2026-10-09)

- Existing pilot API/worker/Redis/PostgreSQL preserved at loopback port 18082.
- Separate preview created on loopback port 18083 over the existing APR-06 image, preserving its implementation. Unauthenticated workspace returned HTTP 401; authenticated HTML/JS/CSS each returned HTTP 200.
- Live 44-ФЗ 0372200172326000015: getDocsIP archive obtained; run toa-run-20261009081852-401c21 persisted with six actual files (XML/XLS/DOC/2 DOCX/PDF). Human-triggered analysis completed_with_warnings; text extraction available 6/6; 10 report sections; report, events, DOCX and PDF each HTTP 200.
- Source-bound citation audit on this specific run yielded **zero fact-level citations**, hence **human quality acceptance is still OPEN**, not counted as successful citation coverage. The UI displays absent citations as UNKNOWN and retains HUMAN_REVIEW_REQUIRED, not an autonomous GO.
- Live 223-ФЗ 32615850735: read-only public-source route yielded docs_required, 0 extracted documents and one warning. No fake supported 223-ФЗ output.
- Canonical Tender Research database registry/history on this pilot showed zero rows; 12 historical operator runs were genuinely persisted. The interface deliberately distinguishes these stores.
- Targeted tests: 19 APR-03B; 100 related operator tests passed (10 skipped); roadmap tests 6 passed; make check, Ruff, Node syntax and YAML validation passed.
