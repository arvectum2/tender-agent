# APR-03B: Development E2E acceptance — 15 October 2026

**Decision: ACCEPTED — bounded DEVELOPMENT E2E, with owner-delegated ChatGPT expert review.** This result is not an independent qualified-human legal opinion, a legal bid decision, a current-production readiness assertion or a live-EIS revision signoff.

## Tested flow and source scope

- **Actual archived official 44-FZ notice:** `0372200172326000015`, website and visual identity for the Saint Petersburg Museum of Bread. Saved original number-based EIS `getDocsIP` archive-download event, six official original attachments and XML notice, reproducibly copied into isolated Mac mini staging. This was a **replay of an actual EIS-number import**, NOT a fresh keyword search, new procurement submission, or assertion that the historical edition is current.
- **Isolated execution:** owner/operator workspace with Basic Auth, localhost only; private separate SQLite test database and dedicated localhost Data Platform on port 18094, not the existing production endpoint at 8094; local Gemma4 12B via localhost port 8081. No production, ETP, supplier-contact, signature or payment action.
- **Document processing:** all 6/6 original files extracted successfully using the separate Data Platform: XML, XLS NMCK, DOC contract, 2 DOCX and PDF; zero extraction errors and zero recorded document warnings in the final run.
- **Actual LLM:** 4 controlled model calls, `analysis_mode=llm_tender_operator_provider`, `llm_invoked=true`, no fallback. Final fresh model analysis elapsed **138.79 seconds**, HTTP 200; product state `needs_review` is intentional because no supplier TKP or live eligibility signoff is present.
- **Source-backed report:** verified against unique original matching XML, three cited, independently checked facts: exact purchase subject, original archived filing deadline (16 October 2026, 10:00 Moscow), NMCK (1,000,000 RUB). Saved final report is re-rendered deterministically from the actual persisted model output after fixing the product HTML projection; 3 EIS XML excerpt/field/file citations visible. The model's other risk/eligibility statements are review-only, NOT independent gold or verified legal conclusions.
- **Persistence / isolation:** authenticated workspace, saved run reopened, history, structured report, source-evidence API and read-only registry each HTTP 200; unauthenticated workspace/report/evidence each 401. Historical official PDF and DOCX **both HTTP 409** because no current official revision was verified; that is the correct safety behavior, not an export failure.
- **Corrected user-facing defects:** (1) report HTML previously omitted verified XML provenance; (2) preliminary heuristic incorrectly treated “Section 1. General requirements” as the procurement subject; (3) buyer NMCK XLS was presented as supplier TKP; (4) Cyrillic “ТКП” file names were not classified as actual supplier offers. Each fixed and tested without changing frozen raw original EIS files.

## Private reproducible evidence (kept off GitHub)

- Archive + official original SHA-256 receipt: `/Volumes/ArvectumSSD/Arvectum/runtime/ta-apr03b-e2e-20261015/sources/input`.
- Original local-LLM run: `runs/toa-run-20261012200402-7249ed`, final model replay machine record `output/isolated_real_llm_e2e_result.json`.
- Re-render of that exact saved model output with the fixed HTML path: `qa-final-render/runs/toa-run-20261012200402-7249ed/output/report.html`.
- Exact final HTML SHA-256: `9d3c82bd72b37d6a3305aac1343517d55f71434ac8c7c07f84ca6f14519c7444`.
- Independent acceptance evaluator receipt: `output/development_e2e_receipt.json` and `output/development_e2e_gate_result.json`; verdict `accepted=true`, `grants_bid_authority=false`, reviewer `owner_delegated_chatgpt`.
- Exact source material never copied to GitHub. Frozen independent-human gold and the blind review benchmark remained untouched.

## Acceptance boundaries and follow-up

This acceptance validates the **development process and report's checked factual citations**, not all material claims of the generated narrative. Full legal meaning, licensing, eligibility, contract economics and current revisions remain subject to later calibration and explicit owner procurement decisions. The report's `NEEDS_REVIEW` is not a failed E2E transport. Normal historical official PDF/DOCX export remains blocked until a verified current notice exists.

Next product step: **APR-04 customer onboarding** — actual company data, licenses/constraints and first personalized analysis; then APR-05 staged tenant/roles/isolation; APR-06/07 measured production-quality assessment. This bounded E2E removes the former artificial human-gold blocker without inventing any independent legal signature.
