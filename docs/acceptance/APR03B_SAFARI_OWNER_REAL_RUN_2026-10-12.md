# APR-03B browser verification — real Museum of Bread EIS case, 12 Oct 2026

**Status:** BROWSER_FLOW_PASS / REPORT_SEMANTIC_GAPS / HUMAN_GO_DEFER.

The authorized Mac mini Safari front tab was inspected through Safari Apple Events (no System Events accessibility approval). Exact old UI URL: `http://127.0.0.1:18083/pilot/tender-agent/workspace`, private loopback Basic Auth. This UI container is `arvectum/tender-agent:apr03b-owner-safari-fixed-v2` built **9 Oct**, not the canonical 12 Oct current main.

### Actual user-interface run

1. Opened History in Safari and found persisted run `toa-run-20261012200402-7249ed`, linked to EIS `0372200172326000015` (Museum of Bread) with six original source files.
2. Opened saved run from History into the single operator UI and pressed **«Запустить анализ загруженных файлов»**. Status transitioned `ready_to_analyze -> completed_with_warnings`; all six original files show `extracted_text_available=true` (XML/XLS/DOC/DOCX/DOCX/PDF). Journal events updated.
3. Report displayed in Safari: official XML title, exact deadline 16 Oct 10:00 MSK, and 1,000,000 ₽ NMCK with source filenames/tag excerpts. Other risk and readiness claims are explicitly `UNKNOWN` without verified statement-level citations; **semantic/legal/commercial acceptance NOT established**.
4. Runtime recorded `analysis_mode=fallback_deterministic_adapter`: no full local LLM tender analysis. Old saved report retains an ambiguous statement about the project contract being absent or needing verification although `Приложение_1_Проект_контракта.doc` is present, extracted and tagged `contract_draft`. Do not treat old narrative as actual absence. Current main contains an explicit missing-vs-unparsed reconciliation.
5. Historical preview export PDF and DOCX: HTTP 200 with valid MIME and sizes about 32 kB and 38 kB, but this older preview lacks the later archived-notice gate.

### Read-only latest-main side-by-side acceptance

Built private Docker image from canonical TA source `6e737d69dda1ed32394f803f261157c128df5bcf`; started standalone `127.0.0.1:18086`, only loopback published, Basic Auth, old input volumes **read-only**, no production/owner preview changes. It returned:
- /health HTTP 200, unauthorized workspace HTTP 401, authenticated workspace HTTP 200.
- Historical same-run /report HTTP 200 with prominent `АРХИВНОЕ ИЗВЕЩЕНИЕ ЕИС` warning and `manual_review_required`.
- Original XML evidence fields title/deadline/NMCK `KNOWN` with proper locators.
- Official PDF **409**, DOCX **409** until a verified currently published EIS revision is attached. Correct fail-closed behavior.
- Saved historical contract prose remains historical, and should be recomputed on an explicitly authorized current-version run; GET projection must not overwrite stored legal/commercial history.

### Fix implemented in repo, not falsely claimed deployed

`operator_workspace.js/html` now expose explicit deterministic-without-LLM status at the top of the result and intercept PDF/DOCX export errors, displaying the backend's archived-EIS reason in the UI rather than navigating to raw 409 JSON. Frontend JS simulation checks blocked PDF and DOCX and valid PDF direct download with content-type guard, with no UI navigation on rejection. Backend's authorized gate and original evidence must not be relaxed.

**Remaining owner/legal gate:** latest current official EIS revision, independent legally/commercially grounded full document review, actual local-LLM evaluation where appropriate, complete source quote support, final owner decision. No bid submission, signing, VPS/production deploy, paid OpenAI API or watchdog activation.
