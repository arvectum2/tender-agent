# APR-02 — four real 223-FZ secondary-card probes, 2026-10-08

Provenance: four publicly served `tendik.ru/tender/eis223/` pages, raw HTML and SHA-256 manifest stored **locally only** under `/tmp/apr02-223fz-real-cards-20261008/manifest.json` on Mac mini. These are not original EIS source documents and may not be used to assert EIS HTML-layout acceptance.

| Registry | Public secondary source | Initial price RUB | Publication | Deadline | Strict OKPD2 62 evidence |
|---|---|---:|---|---|---|
| 32616445866 | https://tendik.ru/tender/eis223/32616445866 | 514,800.00 | 07.10.2026 | 07.10.2026 | unconfirmed: card supplies description, not numeric code |
| 32616445175 | https://tendik.ru/tender/eis223/32616445175 | 630,000.00 | 07.10.2026 | 15.10.2026 | unconfirmed: card supplies description, not numeric code |
| 32616440359 | https://tendik.ru/tender/eis223/32616440359 | 1,273,050.00 | 06.10.2026 | 13.10.2026 | unconfirmed: card supplies description, not numeric code |
| 32616429050 | https://tendik.ru/tender/eis223/32616429050 | 3,300,433.16 | 01.10.2026 | 12.10.2026 | 62.01.29.000 explicitly shown |

EIS official documents endpoints for the four numbers returned HTTP 404 from Mac mini. No EIS attachment bundle was retrieved or parsed. This is an **independent real-secondary-card smoke probe**, not a successful EIS SOAP extraction.

Existing dedicated 223-FZ HTML parser was invoked against each archived external page: previously all four returned `network_status=success` without title, customer, or document links. This is a misleading empty success on an unrecognized layout. Now all four consistently return `unsupported_layout` with `requires_review=true` and no inferred fields; new regression test passes alongside four existing provider tests (5 passed).

The currently configured `getDocsIP` diagnostics speak the 44-FZ `fz44/get-docs-ip/ws` namespace with `PRIZ` document selection; the presence of a local SOAP token does not establish support for 223-FZ extraction. No private credentials are stored in this report. Next stage requires verified 223-FZ EIS-specific transport/evidence bundle and numeric OKPD2 cross-checks for the three unconfirmed cards.
