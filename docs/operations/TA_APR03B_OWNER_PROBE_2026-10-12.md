# APR-03B controlled live-source probe — 2026-10-12

Status: TECHNICAL_PARTIAL / OWNER_ACCEPTANCE_PENDING. This report does not authorize production, contract signing, bid submission, owner GO, or automatic legal conclusions.

- Canonical TA ref: `6e737d69dda1ed32394f803f261157c128df5bcf` (CI 9/9 PASS). The existing preview on `127.0.0.1:18083` runs an older APR-03B image and is **not** a demonstration of the latest main.
- Mac mini preview is loopback-only and Basic Auth protected. Anonymous `GET /pilot/tender-agent/workspace` yielded HTTP 401. Authenticated HTML, JavaScript and registry yielded HTTP 200. The local preview registry initially had zero items.
- Staging-only authorized read-only upstream procurement `0372200172326000015` (Museum of Bread). Authenticated preview import yielded HTTP 200 and operator run `toa-run-20261012200402-7249ed`; run reports `ready_to_analyze`, **6 locally acquired original files**, no run warnings.
- `GET /api/demo/tender-agent/workspace/runs/<run_id>/evidence` shows original notice XML-derived `KNOWN` for title, filing deadline and NMCK; absence of warning does NOT confer complete contractual accuracy or verified report-level semantic citations.
- Independent current-main focused verification: 48/48 APR03B workspace, source evidence, image-parity and independent review gate tests pass (one warning). Production database and runtime not modified by this probe. Preview is on dedicated `arvectum_local` e2e database, not the production `arvectum-postgres` database.
- Protected preview analysis trigger was not executed. Exact model-generated final report, owner browser acceptance, contemporary first-party legal eligibility, complete source citations and official PDF/DOCX release remain **NOT VERIFIED**. Refuse to promote to DONE on XML three-field presence alone.
- Human decision state: `DEFER`. No ETP interaction, signing, paid API or watchdog activation.

Next action: authorized UI analysis on the actual saved run, inspect claim-level attribution and official revised originals, and get explicit owner browser/semantics acceptance. In parallel APR-04 code can be audited without merging or claiming APR-03B complete.
