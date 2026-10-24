# Market Intelligence: Supplier Market Entry — product contract v0.1 (MI-001)

Status: design + read-only offline evidence engine; **not** a completed 3-year market census. No customer-facing production endpoint is approved.

## Buyer job
A company enters the Russian market and uploads a URL, catalogue, deck, spreadsheet, or free-form portfolio. Receive auditable market sizing, buying-center and EPC/design/supply maps, competitors, a list of current/expected opportunities, and an account-by-account recommended action.

**Default window:** trailing three years inclusive, fixed by analysis snapshot (example: 2023-10-24..2026-10-24). Never substitute one calendar year or a small keyword sample. Keep historic awards separate from live tenders and separately observed project pipeline.

## Acceptance-level output
1. Supplier portfolio parsed into product families, approved synonyms (RU/EN, transliteration, abbreviations), technical characteristics, functions, use cases, exclusions and source locations.
2. Source coverage matrix by source × month × entity (notice, documentation, protocol, contract, plan) with expected/seen counts where known, collector errors, revision dates, license/access limits. **An outage or missing source is UNKNOWN, never zero purchases.**
3. Procurement universe: all discovered candidates; deduplicated notices, lots, amendments, protocols, awards and contracts with source links and document offsets. Precision/recall assessed with manually labelled evaluation samples.
4. Purchase chain: end customer/beneficiary, technical owner, designer, EPC/general contractor, purchasing agent, bidder, official winner, confirmed equipment manufacturer and service party. Role is per project or procurement with timestamp/source, not an eternal property of a legal entity. Do not infer all bidders from a contract.
5. Market metrics: (a) confirmed relevant standalone equipment awarded value, (b) referenced component/line value inside projects when explicitly priced, (c) full EPC/project envelope **separately**, (d) open addressable potential, (e) unpriced demand, (f) 3-year trends with per-source evidence/coverage and uncertainty. **Never equate full EPC contract price with niche product TAM; never sum project stages as a single market.**
6. Account map: ranking of owner organizations, EPCs, engineers and purchasers, ranked by confirmed demand, timing, access route and technical compatibility, with cited reasons, obstacles and next action.
7. Active procedures: official statuses/deadlines as of crawl time, refreshed before being described as live. Link to source platform. Proposals and forecast pipeline labelled as such.
8. Client-facing narrative + structured export (JSON, eventually XLSX/PDF), audit log and feedback loop. Every numeric claim has an explicit source set, denominator, date and computation rules.

## Evidence and entity grain
```text
ResearchRun(tenant, portfolio_id, window, snapshot, coverage)
  SupplierPortfolio -> ProductFamily -> normalized functions / hard specs / exclusions
  Source -> Document(revision, sha256, access, locator)
  Project(beneficiary, site) -> WorkPackage(stage: design|epc|supply|maintenance)
  Procurement -> Lot -> ProcedureEvent / Bidder / Protocol / Award -> Contract
  RoleEdge(organization, capacity, project/procurement, dates, evidence, confidence)
  ProductDemand(product_family, work_package, evidence, quantified?, confidence)
  Recommendation(product, target, project, reason, evidence, freshness, review)
```
- Join on stable EIS/ETP ID + customer INN + lot/contract where possible. Cross-postings only merge with demonstrable identity, not merely identical title/amount. Different contracts for a lot remain distinct. A project can contain multiple stages; they are related, never simply added for TAM.
- Entity aliases and holding/subsidiary links have versioned evidence. Exact INN/OGRN for legal entity identity; do not merge suppliers on fuzzy company name alone.
- `not_observed` ≠ `not_applicable` ≠ `confirmed_zero`; observations and estimates are separate fields.
- Fact lineage preserves document URL, published date, document hash, type, page/sheet/section/XPath, exact excerpt and extraction/matching method. Critical winner/award facts require primary protocols/registers or explicit review.

## Acquisition boundaries
- Public EIS 44-FZ notices, amendments, protocols, register of contracts (not only getDocsIP); 223-FZ notices, plans and register of contracts with coverage restrictions. Search is discovery, not proof of exhaustive coverage.
- Source-native commercial ETPs, company procurement portals, investment programs, public corporate reports, project/engineering references, trade news. Paid licensed API may improve completeness; prove rights and contracts before adoption.
- Three years of **bulk historical ingestion** via public official XML or licensed feeds, incremental refresh via change tracking and targeted document ingestion. Verify actual EIS endpoint/service capability; no hypothetical API promises and no captcha/login bypass.
- Extract embedded requirements from technical attachments, specification tables, SLDs and PDF text; OCR only with quality metrics/permissions. Link each requirement to an engineering stage. Retrieval: lexical + semantic candidate expansion + technical ontology + reranking + human-auditable source excerpts.
- Equipment-specific ontology is extendable, not hardwired to supplier name. Example Power Quality family: УКРМ (установка компенсации реактивной мощности), БСК, ТКРМ, тиристорные компенсаторы, СТАТКОМ/STATCOM/SVG, активные/пассивные фильтры гармоник, КРМ/компенсация реактивной мощности, quality-of-power upgrades; find these within substation modernization EPC TЗ. Distinguish engineering incompatibilities, abbreviations used in unrelated contexts, and only report genuine context-supported matches.

## Architecture / ownership
```text
URL / PDF / XLSX / free text
        |
Tenant-safe intake -> Data Platform extraction, revisions, chunking, embeddings, hybrid index
        |                                       ^
       Product family ontology                EIS/ETP/web sources -> raw snapshots -> dedup/revision
        |                                       |
Tender Agent market_intelligence: match/evidence -> work-package and role graph -> contract reconciliation
        |                                       |
        +----------> deterministic size/coverage metrics + opportunity/account scoring
                                            |
                           Analyst validation -> Market Entry report + CRM-ready actions
```
- Data Platform owns source connectors as reusable primitives, text extraction, search, indexing, provenance and bulk snapshots. Tender Agent owns procurement semantics, project/role resolution, market metrics and recommendations. Arvectum OS orchestrates runs and approvals; it must not become a duplicate source-of-truth database.
- Use existing `src/modules/procurement_source_graph` and guarded `electrical_ontology_shadow` as candidates, not unquestioned production truth. Current shadow ontology is acceptance-gated.
- Security: tenant separation, access control, remote URL SSRF blocking, file virus/type/size limits, source compliance, credential management; never scrape gated/private content, transmit confidential catalogues to unauthorized models, or autonomously contact targets.
- LLM extracts hypotheses, not final facts. Deterministic calculations over reconciled evidence; disputed/inferred winner and role explicitly flagged for review.

## Staged delivery
- **MI-001**: this contract, versioned normalized JSON boundary, deterministic evidence-aware aggregation, dedup, basic account ranking, tests. Offline/internally reviewed only.
- **MI-002**: ingestion coverage inventory (EIS 44/223 notices + protocols + registries + ETP source adapters), backfill with source/date/collection health; acceptance by verified counts and acquisition completeness.
- **MI-003**: portfolio URL/PDF/XLSX intake via Data Platform and ontology-assisted expansion; entity/project-role graph; held-out recall and citation quality benchmarks.
- **MI-004**: time series, project dedup and TAM/SAM/SOM confidence intervals, priority action recommendations; analyst review UX.
- **MI-005**: read-only customer portal with report generation/exports, trial with real Power Quality and second unrelated domain, then measured scale, pricing and SLA.
The offline analyzer accepts **normalized, source-evidenced data**, not the raw supplier URL. Building the URL→EIS full 3-year pipeline is **not** implied by completion of MI-001.

## Operational quality gates
- Per-category gold recall (false negatives are critical), precision, evidence-citation verification and independent human spot checks.
- Measured coverage of EIS/ETP periods/sources; duplicates/identity-conflict rate, percentage of winners/participants actually observed, open-tender freshness.
- Numeric reconciliation: protocol/contract/line-item precedence, cancellation, contract modifications, currency, VAT, multi-stage spending and explicit exclusions; no fabricated monetary data.
- End-to-end report completeness for at least two independent supplier categories with real evidence, not synthetic demos.
- Explicit `INSUFFICIENT_COVERAGE` result when the 3-year market size is not supportable; client still receives useful named leads and the source-gap inventory.

## Public policy/source references (verified 2026-10-24)
- Federal Treasury EIS overview: https://roskazna.gov.ru/gis/eis-zakupki-gov-ru
- 44-FZ: Federal Treasury EIS records and contract register; public discovery and register facts differ from participant protocols.
- 223-FZ Art. 4, 4.1: https://www.consultant.ru/document/cons_doc_LAW_116964/441d00be62e3224cdc0514cffaf2a26b5b40a1c7/
- Treasury 2026 updates: https://piter.roskazna.gov.ru/gis/edinaya-informacionnaya-sistema-v-sfere-zakupok
- Do not assume all commercial procurement is disclosed or every EIS record includes a winner/participants.
