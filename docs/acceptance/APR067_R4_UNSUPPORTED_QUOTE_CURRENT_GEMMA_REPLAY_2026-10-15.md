# APR-06/07 — recheck previously unsupported R4 quote on current local Gemma (15 Oct 2026)

**Development replay: full local model and eight originals PASS. Source-XML document-type selection defect FIXED.** This is a private, archived 44-FZ test only, not a legal decision or a currently active notice.

## Original case and reproduction

- Archived historical R4 development case: official competitive 44-FZ notice **0376300000126000193**, saved prior run `toa-run-20261009052414-56bbe6`. It was selected because the historical source audit found one **unsubstantiated literal excerpt among two selected old snippets** from this case. That does not prove that the original legal interpretation was false, but the claimed literal quotation was not supported.
- Original EIS `documentation-archive.zip` SHA-256: `467c0f69024305162c2af2fafd21d579a32d41700b84455bdf8971279da7a29a`, independently matching the pinned R4 20-case source manifest. All eight original input files were copied to an isolated private test directory and individually SHA-256 matched before and after analysis. Original source bytes, private text and credentials are not committed.
- Runtime: real local Gemma4 12B / llama-server localhost and private Data Platform localhost, isolated SQLite, fully authenticated FastAPI operator endpoint, **four model calls**, no fallback. Analysis call duration **358.92 seconds** (not full E2E SLO).
- **8/8 document text extraction flags successful**: one EIS `epNotificationEZK2020`, one `epProtocolEZK2020Final`, `fcsPlacementResult`, `fcsProposalsResult`, four DOCX. Zero source warnings. The saved run was reopened, history, registry and report endpoints each HTTP200; anonymous accesses denied (401). The report decision remains `needs_review` and historical official PDF/DOCX exports both return **409**.
- The **historically unsubstantiated literal excerpt was not present** in the new HTML after the real LLM replay. This is a *repetition check against that one saved excerpt*, not evidence of 100% faithfulness across all new model text. Current product projection already separates speculative LLM requirements/risks from verified excerpts and source_quote_binding fails closed on missing literal bytes.

## Product defect discovered and fixed

Before fix: source-evidence resolver chose XML candidates **solely** by the 19-digit `purchaseNumber`. A genuine EIS getDocsIP ZIP may include the official notice, auction/quote protocol, placement results and proposal results sharing that number. Four XMLs were incorrectly counted as four *notice revisions*, so title, deadline and NMCK were all forced to `UNKNOWN` and the HTML omitted official citations despite having one unique notice document.

Fix: select notice XML by the **direct top-level EIS document type**, restricted to the three independently verified 44-FZ competitive notice variants in the historical R4 corpus (`epNotificationEF2020`, `epNotificationEZK2020`, `epNotificationEOK2020`), before applying the existing unique-number and unique-value gates. Explicit protocol/result document types cannot masquerade as notice revisions. The legacy minimal `<notice>` fixture remains supported for existing parser tests; genuine multiple `epNotification…` editions remain **AMBIGUOUS** and all facts stay `UNKNOWN` rather than guessing which version is current.

Using the **exact saved result of the already-completed real local Gemma call** (no second inference), the corrected product HTML projection was rerun from the persisted structured report. The source validator now finds **one unique original notice XML**, three independently verified EIS facts — subject, deadline and NMCK — and the HTML cites their exact source `file_id`, original filename, XML tag and excerpt. Original inputs still 8/8 SHA unchanged. Saved HTML SHA:
- Before document-type fix: `6e8a01b165d215470bf638ec1d604f7cb0a6769202d48f829a10416cbe6f70ed`.
- After source-verified HTML regeneration: `c071d34f28a4b1c74fce5882…` (complete SHA stored in private JSON receipt).

All source-selection tests additionally preserve failure on two genuine competing notice editions, protocol-only archives, malicious nested notice-like tags, wrong registry number, malicious XML entities and escaping symlinks. There was no automatic GO, bid submission, ETP mutation, legal signoff, payment, email or production deployment.

## Independent private evidence

- Original-copy SHA manifest: private stage `ta-apr067-r4-quote-replay-20261015/output/original_file_hash_receipt.json`.
- Real completed model HTTP replay: `output/apr067_r4_problematic_quote_replay.json`.
- Before/after HTML source selection receipts: `output/report_before_notice_type_fix.html`, `output/notice_selection_fix_receipt.json`.
- Reproducible local runner: `scripts/acceptance/apr067_r4_problematic_quote_replay.py`; accepts **only** the isolated historical case source and refused altered SHA or case IDs.

This issue is a functional source-selection bug uncovered by testing an additional genuinely different official EIS notice with protocols, not by changing the legal status of a tender or silently elevating a ChatGPT statement to qualified-human gold. Following the Owner directive, only DEVELOPMENT E2E source-grounded review is accepted; independent legal and commercial acceptance remain separate.
