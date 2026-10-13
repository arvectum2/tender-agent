# APR-03B — Owner feedback correction: one search → download → analyze workflow

## Reproduced owner complaints

1. PR #257 added a second workspace in parallel to the earlier pilot wizard; the new page only exposed procurement number/URL import, omitting the old real EIS keyword search and filters.
2. The frontend used import with `analyze_after_download=false` and stopped after displaying the run. Analysis required a separate manual click. An attachment manifest was not sufficient proof of actual document bytes or a report.
3. Additional in-progress PR #258 improved original XML citation provenance but introduced an unresolved import of `extract_notice_revision_info` in the parser. This caused 16 regression failures for local upload/ZIP/DOC/XLS workflows. This correction supplies that strict parser function.

## Implemented change

- The canonical operator entrypoints `/pilot/tender-agent` and `/pilot/tender-agent/workspace` serve the SAME authenticated workspace document. Original demo wizard template stays as a non-primary legacy demo route, avoiding regressions to old demo tests.
- The single workspace now uses the same `POST /api/demo/tender-agent/procurement/public-44fz-search` source adapter as the old wizard, with 44-FZ, 223-FZ, and capital-repair search (capital-repair import explicitly disabled); keyword, region, official status, procedure, price/date/deadline filters and cursor-based pagination. No synthetic search results or second search engine.
- From a search result or official EIS number/URL the UI performs document intake, checks actual persisted `run.files`, starts analysis without a second click, reads the completed status, and renders source evidence, report and exports. If the EIS source supplies no original file, it does NOT call analyze, declares the gap and offers manual original-file upload into the same run followed by analysis.
- Buttons stay disabled unless analysis is valid, original file download links target the existing authenticated API, and source-unsupported or incomplete runs remain flagged for human review.
- Reuses source identity and verified XML field projections from PR #258, and fixes strict XML registry revision parsing without trusting an unmatched document title.

## Real Mac mini private tests

- Real EIS 44-FZ **0372200172326000015**: getDocsIP run `toa-run-20261009093646-5ec575` persisted six original documents (102910, 126976, 317440, 53606, 27424, 30479 bytes). Each corresponding server file exists and matches the stored size. Analysis completed with warnings, text was extracted from 6/6, generated 10 report sections.
- Verified 44-FZ EIS XML contains exact registry-bound procurement title, endDT and maxPrice, each with document identity, XML tag locator and literal excerpt; no invented provenance for other facts. This is not acceptance of the entire economic/legal analysis.
- Live keyword search `сайт`: the existing backend returned `success_with_results` with real cards for both 44-FZ and 223-FZ in the isolated private preview.
- 223-FZ **32616450723**: downloaded 2 real source documents (DOC, DOCX); partial analysis returned `needs_review` with a warning. 223-FZ does not falsely claim a complete original document set.
- JavaScript fake-browser regression test exercises search-result click → import → persisted files → auto-analysis → rendered report, plus docs-missing → no analysis, manual-upload recovery.
- Focused tests: 109 passed, 10 skipped; Ruff and Node syntax checks passed. Earlier 16 parser-induced failures are resolved.

## Gates still open

- Owner browser confirmation of real workflow, visual usability and PDFs; no automatic claim of owner acceptance.
- Quality of risks, economics and citation completeness beyond registry-bound XML facts requires human review.
- No VPS, public ingress, signatures, procurement submission, payments, external communications or automatic GO/NO_GO.
