# AI Trading: малые закупки — только offline/paper-simulation (22 ноября 2026)

Task TA-AI-TRADING-SOURCE-DISCOVERY-001, third explicit AUTO queue item
order 1150. Source/access evidence inventory lives in
ta_ai_trading_source_reuse_inventory_20261122.json.

This is a research and reusable-engine inventory, NOT a live bidding bot,
catalog updater, e-commerce buyer, market price feed or 99-percent
autonomous process acceptance. No registered supplier accounts or
platform credentials were used in this task.

## Independent marketplace sources and rights

| Source | Public official origin | Procedure / rights difference | Evidence limit |
| --- | --- | --- | --- |
| Moscow Supplier Portal | https://zakupki.mos.ru/ — Moscow government e-shop | Quotation sessions and direct small procurement, regional government operation; supplier registration/e-signature distinct | Public descriptions confirm an electronic shop. No captured current original notices or API authorization |
| ЕАТ «Берёзка» | https://agregatoreat.ru/ — first-party public announcement pages | Purchase sessions and direct orders, participant requirements can depend on regime and contract | November 17–20 first-party searchable individual 2026 notices exist. This inventory acquired ZERO original notice files and asserts ZERO currently open |
| РТС-Маркет | https://www.rts-tender.ru/ — platform root | Separate small-volume market from federal regulated RTS tender procedures | Public description attests small-volume e-shop; exact per-store API/public active coverage NOT independently measured |
| Сбер А small e-shop | https://utp.sberbank-ast.ru/ — official Sberbank-AST corporate UTP | Corporate 223-FZ SME e-shop, not automatically a public 44-FZ shopping source. Qualification, fees and applicability source-specific | Individual first-party public UTP cards exist, but no authorized bulk export, historical price denominator or original case snapshot |
| ЭТП ГПБ low-value / Click.Маркет | https://etpgpb.ru/ — ETP GPB platform root | Price-list-based direct order/low-value request differs from corporate large competitive tenders; registered supplier catalog and fees may apply | Public operator/group descriptions indicate low-value portal. Exact current official store route, API, case IDs and actual access NOT_VERIFIED |

Publicly indexed first-party EAT purchase announcement examples exist
on https://agregatoreat.ru/purchases/announcement/ from 19–20 Nov 2026.
They demonstrate the need for exact notice ID, timestamp, contract
terms and observed bid/result status, NOT proof of a permissible universal
crawler. Official Moscow city source https://moszakupki.mos.ru/
describes the Portal suppliers small-purchase workflow.
Any 2026 legal changes to electronic signatures, contract publication,
fees, security or regime must be source-checked and legally reviewed at
the actual procedure date, not estimated from third-party guides.

## Exact source and economic gates for a reproducible simulation

Each hypothetical bid needs a source and observation timestamp, seller
stock / SKU / unit and quantity, exact delivery place, expected lead
time, price and freight proof, platform fee, tax-regime assumptions,
funding/security cash timeline, procurement deadline and original
buyer/legal status. Missing stock, product specification, shipping
availability, original source bytes or financing constraints are UNKNOWN.

- SOURCE TIME: include only data available at simulated decision time;
  never use the subsequently observed winning price as an input
  to the original decision.
- PRODUCT IDENTITY: exact SKU/model/technical compatibility AND unit,
  quantity, approved substitutions only with legal/source evidence;
  lexical text match is not a proof of supply capability.
- COST: keep purchase, freight, insurance/returns, applicable fees,
  tax, reserve and own working costs separate; refundables/guarantees
  are liquidity requirements, NOT automatic profit-and-loss expenses.
- CASHFLOW: report peak tied-up capital and actual payment timeline,
  no assumed advances, no unverified vendor stock.
- OUTCOME: recorded real winning price/contract only with original
  dated outcome evidence. Hypothetical simulated win must never be
  labelled a contract or an earned margin.

The target 99 percent refers to measured eligible routine steps, not
to observed historical accuracy or successful winning. At this stage
ZERO cases, ZERO model-simulated bids and ZERO actual outcomes were
replayed or accepted. The target is NOT_MEASURED.

## Existing modules to reuse, not reimplement

| Capability | Existing path | Safe reuse |
| --- | --- | --- |
| Unit-normalized historical price observations and source evidence | src/tender_research/historical_prices.py | Separate comparable product/quantity from unsupported analogy and inferred win |
| Original competitive bid result baseline / owner break-even | src/tender_research/competitive_bid_protocol.py | Observed outcomes only, no invented future winner |
| Source-bound product/price normalization | src/modules/price_normalization/normalize.py | Preserve units, exact SKU and tax assumptions |
| Cost components and auditable breakdown | src/modules/cost_model/service.py | Fee/tax/freight/funding/cost items remain distinct |
| Comparable vendor offer selection | src/modules/quote_comparison/comparison_ready_offer_set.py | No simulated supplier quote from vague web prices |
| Supplier/product position matching | src/modules/supplier_search/position_offer_discovery.py | Need original vendor offer and deterministic SKU identity |
| Idempotence / snapshot management | src/tender_research/ingest_checkpoint.py | Future original snapshot only under admitted source access |
| Offline cost sensitivity / liquidity | scripts/ops/b2b_prebid_cost_scenarios.py | Owner-selected expenses, no real obligation |
| Price01 real historical winner-source baseline | scripts/price01/audit_aksay_baseline.py | Original proof and dated outcomes distinct from simulated cases |
| Reuse source discovery pipeline | scripts/procurement_llm/unified_source_pipeline.py | No live vendor login or bulk undocumented market API |

## Only bounded successors, no live trading

1. Obtain permissioned source snapshots for one selected individual
   public original per marketplace, with exact URL/ID/time/hash and
   provenance, not a bulk hidden data pull.
2. Define an offline frozen case packet with original demand, exact
   SKU, vendor stock proof, all-in landed cost and cashflow. Missing
   facts must trigger manual review, not a guessed bid.
3. Run deterministic no-side-effect paper simulations with
   separately documented observed future outcomes and calibration;
   measure coverage, errors, manual time and economic capital use.
4. Independently review legal eligibility, seller and platform access
   fees, per-platform API licensing, retention and any current
   statutory/electronic acceptance gate before contemplating a
   controlled private test.
5. Real bids, catalog postings, payment, communication, buying,
   signature and delivery are NOT authorized by this inventory, even
   if a simulation is profitable on paper.

No new database tables, live buy/sell bot, supplier CRM, full market
connector or external transaction functionality was needed to complete
this admitted source and reusable-module inventory.
