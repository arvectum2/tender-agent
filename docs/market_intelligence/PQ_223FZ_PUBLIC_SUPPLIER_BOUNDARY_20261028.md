# MI-013 — 223-FZ public supplier / signed-document evidence boundary (2026-10-28)

Status: **research limitation / REVIEW**, not a legal participation decision.

## Why a public EIS registry lookup cannot close every winner/signed-document gap

The currently published text of Russian Government Decree No. 1132 (31 October 2014), Rules §2(e), identifies supplier details as registry fields. Rules §19(a) **excludes §2(e)**, along with §2(m) (the signed contract copy), from publication on the public EIS website. This distinction survives the displayed consolidated amendments through 30 September 2026. It does not mean that every other publicly accessible ETP protocol is unavailable or that a named participant is automatically the signed supplier.

Source for legal-text navigation (checked 2026-10-28):
https://www.consultant.ru/document/cons_doc_LAW_170528/93e5e111cbfb5c03e38e2cf2f18719c447302cfd/

- §2(e): supplier identity fields.
- §2(m): copy of the executed agreement with qualified signature.
- §19(a): public-site exclusions include §2(e) and §2(m).
- §2(d): contract subject and price may be represented in the public register, **not** necessarily as equipment-only turnover.

**Research consequence:** an inaccessible public supplier field is not evidence that no contract exists, and a public registry price is not proof of a signed original file or the PQ-equipment-only component of a mixed EPC/design contract. Mark supplier and signed-copy proof `not_publicly_disclosed_in_registry` where the only source is the public registry, while continuing independent original ETP/commission/first-party source searches. Do not attempt restricted API/identity/UKЭП access or infer the winner from the single admitted bidder.

## Existing SHA-bound local registry XML, not newly recovered contracts

The following are *previously recorded* local registry XML facts, not signed copies newly verified by this note:

| 223-FZ notice | Registry record | Public registry price field (RUB) | Scope and limitation |
| --- | --- | ---: | --- |
| 32615614821 | 50277071467260002650000 | 1,833,358.30 | PS 110 kV reconstruction/compensation, mixed EPC; supplier unverified |
| 32616280467 | 56450925977260018070000 | 3,680,106.21 | 10 kV dynamic compensation design/PIR; OCR commission candidate provisional; supplier unverified |
| 32616120582 | 57802312751260008280000 | 17,000,000.00 | Mixed turnkey 6 kV line construction; not equipment-only revenue |

Source-bound machine records: `pq-agent-pilot-live/contract-xml-evidence.json` and `contract-outcome-audit.json` on Mac mini, retaining source XML and archive SHA-256 per row. No signed contracts or suppliers were independently verified for these three cases.

## Fresh network observation and next research actions

At 2026-10-28 05:36 MSK, a bounded **HEAD** to the known official public EIS registry entrypoint `https://zakupki.gov.ru/epz/contractfz223` returned HTTP **404** with successful TLS verification and no redirect. Receipt is in `pq-agent-pilot-live/contract-registry-entrypoint-attempts.json`. A 404 for this entrypoint is **not** proof that a registry record or contract is absent.

Continue bounded first-party ETP notice/protocol/award retrieval and separate contract-status corroboration. Preserve distinction between commission selection, public register price, supplier disclosure, signed copy and contract performance. Use official source adapters only, with retry journals and SHA-bound original receipts. Do not elevate secondary card HTML to signed-contract proof.
