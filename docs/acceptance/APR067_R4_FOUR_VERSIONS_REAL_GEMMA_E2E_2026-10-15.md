# APR-06/07 — третий реальный исторический E2E, 44-ФЗ, четыре редакции ЕИС

15.10.2026. Development acceptance by Owner rule: source-grounded ChatGPT/Gemma analysis may be accepted as expert-level **for DEVELOPMENT E2E**, without requiring a separate human legal reviewer at this stage. Commercial/legal decisions about an *actual current* tender, ETP bid submission and production rollout remain separate.

## Reproduction: archived EIS original №0162200011826003089

- An already saved first-party, signed-off-by-none **development** source archive: official 44-FZ `documentation-archive.zip` SHA-256 `3daf341cee2e26c670ccd1b6101105ce21706497b38cd15989ff9db3a4708ded`. No new getDocsIP, ETP requests, signing or payments during the replay.
- Original archive has **12 XML**: `epNotificationEF2020` revisions 1, 2, 3, 4; clarifications, protocol and cancellation/result documents. Revision 4 archive XML pinned SHA-256 `6712bf2058e7f7d047d6fb15467b7d173de48e06dbd82fff6295e8f69f6b6b20`. **Not an attestation that v4 is currently published or live for bidding.**
- Five original attachment bytes (one ODT and four DOCX) recovered earlier through verified first-party EIS filestore receipts; local replay copies all five only after SHA/byte-size/official selected v4 UID verification. All 12 XML and 5 attachments have a separate immutable private SHA receipt. `17` input source SHA unchanged after the real model replay.
- Offline cached original ZIP/attachments were passed through the **real production-format EIS archived ZIP unpacker, procurement document-set completeness gate, Data Platform document process endpoint, FastAPI operator analysis endpoint, local Gemma4 12B, persisted report/history and source citation renderer**. Network SOAP and filestore were replaced with local SHA-verified source copies; this is *not* an unmocked live EIS network test.

## First run, observed defect (preserved, not rewritten)

Local model: four actual calls, **350.92 s** analysis. 12 XML + four DOCX extracted; one official ODT price justification returned `unsupported`: **16/17**, not 17/17. All original SHA unchanged, report/history HTTP200, PDF/DOCX archival export 409, `needs_review`.

Data Platform previously had no native ODT extractor even though that format is allowed in official attachments. **Fixed in separate Data Platform PR #125**, bounded in-process ODT `content.xml` parser (no external converter, DTD entities or unbounded decompression). Independent local HTTP test on the saved genuine ODT: **3,447 characters, three processed text chunks**. Data Platform CI and mirror checks passed on substantive commit `bc13d8bf`. Nothing changed in the saved original archive.

## Corrected current E2E, proven results

- Gemma4-12B local: 4 real model calls, no fallback, analysis 150.08 s (not rolling production p95).
- Data Platform: 17/17 original documents `extracted`; 0 failed; source hashes 17/17 and archive ZIP identical before/after.
- UI/workflow: analysis HTTP200, reopening run / steps / history / report / evidence / read-only registry all HTTP200, export PDF/DOCX HTTP409 for historical notice, run remains `needs_review`.
- Original notice: 4 genuinely different epNotification revisions; a strict original ZIP/registry/version/SHA gate chooses only v4 for historical evidence. Three selected original XML facts (subject / archived deadline / NMCK) are `KNOWN` with three attributable source citations visible in the actual HTML report. This **does not** upgrade the document to current live EIS revision or remove business review.
- The old model's known unsupported literal excerpt (prior historical SHA `78547f12cf481dd2ab1ebd5a507cbf08042eb7fe3064d6b733a559bd99863024`) is not repeated literally in the new HTML. This single-quote comparison is not proof of the new model's all-claim or legal precision.

### Source ambiguity regression fixed

Before: the APR-03B evidence provider correctly withheld facts if several XML notices shared the same registry, but did not distinguish *several safely versioned true archived notices* from genuinely ambiguous competing sources. Unlike simply picking the maximum model-inferred version, the new gate:
1. Reclassifies the **saved original ZIP bytes**, rechecking official procedure type and procurement ID.
2. Requires recorded ingest archive SHA, selected notice SHA and version to match the freshly reclassified first-party archive.
3. Requires exactly **one** official highest archived-version notice ZIP member and identical saved extracted XML bytes.
4. Rejects altered highest-edition XML (rather than silently falling back to v1), forged stored metadata, changed archive hash, absent or symlinked ZIP and two conflicting highest-version members.

When the original cannot establish the selected archived edition, subject/deadline/NMCK remain `UNKNOWN`. The HTML source panel distinguishes historical archive evidence from current EIS business eligibility. All existing strict one-revision and unsupported-source guards remain.

## Tests, privacy, and next engineering priority

- Tender Agent local full regression **4104 passed / 238 skipped / 0 failures** (159.26 s), Ruff clean; **51 focused tests passed**, including 12 adversarial archived notice selector tests and 17-original staging source integrity tests.
- Data Platform `tests/documents/` full **61 passed**, Ruff clean; PR #125 code CI and GitVerse mirror both passed. 
- All source original files, exact source text, offline metadata and machine receipts stay in a private Mac mini source stage. Public commits contain only generic code, SHA fingerprints and non-sensitive case registry numbers.
- Remaining objective: expand the number of distinct real E2E cases and decide workflow stability from repeatability, then incorporate the owner's expert corrections. Neither another qualified-human gold task nor currently active bid approval is a prerequisite for **DEVELOPMENT E2E acceptance**.

Private stage: `ta-apr067-r4-four-revisions-20261015` under the Mac mini's protected runtime, with immutable source receipts and separate before/after ODT E2E outputs. No automatic merges or deployments.
