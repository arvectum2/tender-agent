# ГЭХ / Мосэнерго — закупочные источники и reusable adapters (22.11.2026)

Task TA-GEH-SOURCE-DISCOVERY-001, explicit AUTO queue order 1140.
Sanitized typed matrix: ta_geh_source_reuse_inventory_20261122.json.
All statements below distinguish official source description, saved repo
capability and independently UNMEASURED live history. This is NOT a new
TEK-Torg/GPB integration, supplier registration or actual bid.

## Direct buyer versus contractor / platform

| Source | Official link / access | Exact relationship | Coverage, open gate |
| --- | --- | --- | --- |
| ПАО Мосэнерго procurement landing | https://www.mosenergo.ru/tenders/ — public company page and RSS link | First-party page says 223-FZ notices in EIS, electronic procurement conducted on ETP GPB; rows distinguish Заказчик, Организатор and EIS number | Site says trailing 99 days; actual number of independently acquired current rows: 0. Not 24–36 months proof |
| EIS 223-FZ / RI223 | https://zakupki.gov.ru/ — regulated source under its rules | Original legal buyer, notice GUID/registration ID, source edition and documents are authoritative only with exact original evidence | Existing RI223 read-only provider can be reused; no new EIS request, no new notice SHA proof in this task |
| ETP GPB | https://etpgpb.ru/ — supplier account for participation | Platform is venue, not automatically buyer or awarded contractor; first-party Mosenergo states its procurement uses this venue | Public procedure fragments exist; Mosenergo-specific corpus and authorized bulk API/export NOT_VERIFIED |
| Historical Mosenergo results | https://www.mosenergo.ru/tenders/archive/ — public company results | Distinguish original legal buyer, organizer, actual contract winner | Public example index displays 2016 and older result years, NOT proof of complete 2024–2026 history |
| Mosenergo qualification | https://www.mosenergo.ru/tenders/pre-qualification/ — public supplier rules | Being a qualified candidate is not a contract/award; qualifications can affect application documents and invitations | No corporate Arvectum/partner qualification evidence or private bidder state verified |
| TEK-Torg corporate sections | https://www.tektorg.ru/223-fz/procedures — public marketplace candidate | No first-party evidence that ALL GEH/Mosenergo direct purchases use TEK-Torg; a third-party supplier/contractor procedure must have independent buyer, contract and source identity | TEK-Torg supplier cabinet registration; specific GEH contractor relationship, API entitlement and 24/36 month history UNKNOWN |

Official evidence reviewed 22-Nov: Mosenergo procurement page explicitly
links EIS and ETP GPB; its table separately labels buyer, organizer and
EIS ID. Its result archive and procurement plan are different source
classes; a plan is not an actual tender. TEK-Torg's first-party supplier
documentation describes search filters, sections, subscription and
logged-in accounts, but proves neither GEH contract lineage nor open
authenticated access.

## Candidate SOAP endpoints — untested, not authorized

TEK-Torg publishes official API/procedures integration documentation
referencing https://api.tektorg.ru/procedures/wsdl and older corporate
integration material referencing
https://zakupki.tektorg.ru/soap-integration/index/wsdl.

This is evidence only of **documented candidate endpoints**, NOT proof of
current WSDL availability, entitlement, allowed public data export, live
procedure visibility, authentication rights, download access, GEH
buyer coverage or integration feasibility. No endpoint request was sent
by this task. Reuse of official RI223 EIS must be tested first before
adding a platform-specific connector.

## Attribution and coverage denominators

The historical 24–36 month buyer/project/contractor collection is NOT
measured. No new original EIS ZIP/XML or ETP GPB/TEK-Torg procedure file
was downloaded, no 2026 live buyer record was promoted to accepted and
there is no verified cross-platform 24/36-month denominator.

Candidate organization labels for future legal-entity checks include
ПАО Мосэнерго, ООО Газпром энергохолдинг, ПАО МОЭК, ПАО ОГК-2 and
ПАО ТГК-1. These are search labels only, NOT a current independently
verified corporate ownership/contract hierarchy. Match INN/OGRN and
original notice/contract party separately before aggregating.

A procedure posted by a general contractor for a GEH project is still
a contractor procurement, not a directly issued GEH tender. Do not
infer final asset owner or contractor role from a keyword, broad
holding affiliation, tender subject or identical company name.

## Existing code to reuse before developing any adapter

| Capability | Existing path | Required source boundary |
| --- | --- | --- |
| 223-FZ EIS/RI223 archival original and edition handling | src/tender_research/providers/ri223_soap_evidence.py | Use only admitted source account and verified revision/ZIP; no API authorization inferred |
| Public 223-FZ procedure discovery | src/tender_research/providers/public_223fz_search.py | Source-bound exact original legal buyer and timestamp, UNKNOWN otherwise |
| EIS/public registry discovery | src/tender_research/registry_discovery.py | Do not promote historical listing as current legal stage |
| Duplicate and URL controls | src/tender_research/dedupe.py | Separate official notice and ETP-derived procedure IDs, prevent duplicate buyer inference |
| Incremental checkpoint / idempotence | src/tender_research/ingest_checkpoint.py | Read-only plan first; writes need separate gate |
| B2B buyer / lot provenance | src/tender_research/corporate_procedure_identity.py | Requires original source card, independent contractor or asset-owner evidence |
| Source metadata catalog | scripts/research/source_catalog.py | Registration/credentials are distinct future permissions |
| Reusable source pipeline | scripts/procurement_llm/unified_source_pipeline.py | Future adapters must remain isolated; never auto-submit bids |

Repo search found NO dedicated ETP GPB / TEK-Torg / GEH live
procurement connector already implemented. A special connector is not
justified until observed demand/coverage gaps are measured against
existing 223-FZ EIS original-source intake.

## Bounded successors, no implicit authority

1. Verify independently the exact original buyer INN/OGRN and EIS 223-FZ
   notice IDs for a bounded Mosenergo historical sample under a separate
   read-only public-source admission; record missing original source bytes
   as UNKNOWN rather than retrying blindly.
2. For each sample, match ETP GPB platform procedure IDs and exact
   buyer/organizer source identities; do not merge merely by similar names.
   Derive a 24–36-month denominator only from verified original pages and
   documented source pagination/date windows.
3. Test the availability, API terms, credentials and coverage of any
   TEK-Torg SOAP WSDL only after explicit source admission. A WSDL URL
   alone is not a contract, working API, or authorization to download.
4. General-contractor intelligence is a separate link requiring an
   independently cited buyer/contractor contract relationship. Include
   unknown relationships in denominator, not fabricated verified edges.
5. Keep private qualifications, commercial access, any live source
   exports, DB ingestion, notifications or bid submissions outside
   this AUTO inventory. Introduce new feature only on a measured
   non-reusable gap and explicit Owner/MI/PITR deployment gates.

**Inventory done gate:** six source/access classes, exact legal-role
boundaries, unmeasured history explicitly acknowledged, existing code
reuse table, and narrow read-only successor plan. Commercial readiness,
live GEH coverage, procurement rights and contractor connections are
NOT accepted by this inventory.
