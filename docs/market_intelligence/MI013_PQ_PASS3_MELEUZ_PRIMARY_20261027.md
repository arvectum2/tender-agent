# MI-013 Power Quality — primary-source enrichment pass 3 (27.10.2026)

**Canonical**: 100 active procurement leads in `verified_public_leads_20261027.v21.manifest.json` (v20 100 retained; 1 existing row enriched, 0 added). **71** records previously independently verified in production PostgreSQL `arvectum_data` → `arvectum-market-pq-6-35kv`, **29** GitHub-only. Original documents stored on owner Mac mini or linked from source, not committed as binaries.

## Verified: existing notice 223-ФЗ №32616296475, ООО «Водоканал» (Мелеуз)

Original [ETP Region listing](https://torgi.etp-region.ru/app/OfferCard/page?OfferCard.offerUUID=Scorebofs002080000q03ju2cimtcd2js). Notice 17.08.2026; ETP procedure `0052026007DP`; NMC **3,904,773.73 RUB**.

**Original buyer's technical task**, [DOCX](https://zakaz.etp-region.ru/fx/gpms/etpGetFileServlet?fileUUID=dbfilefs002080000q03kmh4j5tmvv6g), source SHA256 `ca9a840c69bce647287c4571b675d57f401f89a20ae3d24f3842d8e24485b781` (28,240 bytes; source DOCX text extraction):

- High-voltage 6.3 kV network, one UKRM, **at least 500 kvar**; thyristor + controllable shunt reactor + higher-harmonics filter, regulation 0–100%, step at most 50 kvar.
- Controller ≤5 ms and load-change response ≤10 ms, cos φ at least 0.98 ±0.02, IP54, indoor operating ambient **−40…+45 °C**, automatic/manual regimes; 14-day archive.
- Buyer performs assembly; supplier provides supervised installation and commissioning. Before/after power-quality measurements at least seven days each, harmonic analysis up to 50th order. The scope includes transport, installation, commissioning and compliance documentation. Equipment-only selling price **not separately evidenced**.
- Docs refer to RF government decree 1875 restriction marker: exact admissibility for foreign equipment requires legal scrutiny, not an automatic inference of import ban.

**Original final commission protocol**, [PDF scanned 4 pages](https://zakaz.etp-region.ru/fx/gpms/etpGetFileServlet?fileUUID=dbfilefs002080000q0qrilg879gm7mk), SHA256 `9e2812d778f3e4534a3fcc02dec65d04df999d8d9ca11032fd1c8ff5000eb3d0` (1,655,628 bytes): protocol of **4 September 2026** (ETP document posted September 7). Native PDF text extraction yields none. A single fallback ru-RU macOS Vision OCR pass was checked visually on the rendered scan, p.3:

| Rank | Application | Price for entire lot, RUB |
|---|---|---:|
| 1 | №79410 | **3,865,725.99** |
| 2 | №79376 | **3,885,249.86** |

Both were admitted, no rejections. **Names/INNs are not disclosed in the published final protocol.** No first-party registry contract was obtained; do not label the first-ranked proposal a signed contract/supplier revenue. Relative to NMC, first proposal is 39,047.74 RUB lower (≈1.00%); not a market price of an individual capacitor bank.

**FGI fit**: a generic SVG/STATCOM is not automatically equivalent to this thyristor-reactor installation; require a technical-compliance matrix for −40…+45 °C, IP54, 5ms response, controller functionality, filter and after-sales operations.

## Source discipline and remaining problems

- Exactly **one prior corpus row** enriched; 100→100, not 100→101. Protocol counts are two **anonymous** applications; historical **two other named participants** and **four original registry signed contracts** remain unchanged.
- The real winner's legal identity and RD223 signed contract price for #32616296475 are still unknown; possible secondary statement “contract signed 07.09.2026” is not sufficient original registry proof.
- Next priority: `32515218366` (“Россети НТЦ”, protocol PDF and technical DOCX HTTP404 via EIS), `32616296475` legal-identity/registered-contract confirmation, `ГП630876` technical archive, `4565274/4538400/4561228` repeat dedup. Expand 2024 original source windows and 71→100 only through separate approved database import workflow.
- Official EIS attachments might be unavailable via both direct and noproxy; avoid “not found” as a claim no tender exists.

Evidence structure: `data/market_intelligence/power_quality/primary_spec_protocol_enrichment_20261027.v21.json`.
Cross-check: v21 manifest base100/active100/new0; primary case SHA lengths64, ranked prices below NMC, signed price null, production unchanged; all verified PASS through independent GitHub round-trip parse.
