# СИБУР: источники, полнота истории и reuse (22 ноября 2026)

Task TA-SIBUR-SOURCE-DISCOVERY-001, admitted AUTO queue order 1130.
Machine-readable evidence: ta_sibur_source_reuse_inventory_20261122.json.
This is a sanitized public/previously saved source inventory, NOT a live
source connector, procurement authorization or commercial GO.

## Source/access and buyer/contractor matrix

| Scope | First-party URL / access | Buyer, contractor and source distinction | Coverage / gate |
| --- | --- | --- | --- |
| SIBUR public registry | https://www.sibur.ru/ru/procurement/buy/ — public listings | Organizer name and exact procedure ID with revision suffix; organizer NOT automatically signed contracting party | 27/27 saved AJAX pages, 313 unique historical IDs as of 14-Nov. No 22-Nov live original revision or current open status verified |
| SIBUR archive | https://www.sibur.ru/ru/procurement/buy/archive/ — public historical pages | Historical organizer, not evidence of winner or contractor | Nine-category historical corpus 4052/4052 SHA verified pages, 48332 unique IDs. No claim of current notices or 24/36-month completeness |
| SAP SRM | https://srm.sibur.ru/ — supplier registration and qualification | SIBUR officially names SRM the main marketplace for goods, works, equipment, materials and services | Authenticated export, API and qualified account access NOT established; no source retries |
| B2B-Center / ООО СИБУР | https://www.b2b-center.ru/companies/tendery-ooo-sibur/ — public company list | Distinct legal entity from ПАО СИБУР Холдинг and separate industrial subsidiaries. Original B2B card 4586338 is a SALE/disposal of IT equipment, not a procurement | History and present legal statuses UNKNOWN; no automatic SIBUR general contractor inference |
| Generic B2B-Center | https://www.b2b-center.ru/app/next/market-search/ — partial public market | Buyer and contractor only when explicitly evidenced in source card; a mention of SIBUR in text is insufficient | Restricted procedure details/API and total historical coverage UNKNOWN |
| 7Rights | https://lk.7rights.ru/ — logistics qualified supplier portal | Separately named by SIBUR for logistics; not equivalent to SAP SRM/B2B-Center | Outside current task; requires separate admission |

Official source pages observed via public search/retrieval 22-Nov:
https://www.sibur.ru/ru/procurement/procedure/ (SAP SRM vs 7Rights)
and https://sibur.ru/ru/procurement/start/ (registration/qualification).
Indexed November public registry pages cannot be treated as a fresh
time-correct official notice capture. B2B-Center first-party sale example:
https://www.b2b-center.ru/market/vybor-dolgosrochnogo-partnera-na-vyvoz-it-tekhniki-sibura-1-god/tender-4586338/.

## Historical coverage, NOT present-day tender opportunities

| Saved evidence | Verified historical counts | Still NOT proven |
| --- | --- | --- |
| Public registry 14-Nov | 27 pages, 314 observations, 313 exact unique IDs, 516 document references | Current status or 516 original files at capture |
| Nine-category historical archive 21-Nov | 4052 original pages, 48536 observations, 48332 distinct IDs, 204 repeat observations | Current active list, contractual outcomes, actual full timespan |
| Working research database, read-only evidence 21-Nov | arvectum_local PG16 30632 distinct sibur_public IDs, intersection 30081, 18251 archived IDs absent, 551 working-only | Why missing/extra IDs exist; any mass-import authority |
| Saved reference files | 516/516 byte/size SHA verified, 515 matching URL/file extensions | One .ppt URL and .pptx saved blob issue #686: not a proven .ppt original |
| Historical Data Platform | Seven source hashes, 958 chunk/embedding identities, 4/7 URLs grounded to this registry | Source URL proof for other three; current live indexing |

Archive gap per category: 107=2035, 108=4883, 109=1008,
112=3925, 132=3891, 999_08=653, 999_10=803, 999_11=994,
999_19=59; sum=18251. This is a HISTORICAL source-coverage discrepancy
(issue #692), NOT 18251 active or bid-ready tenders.

Working arvectum_local PG16 and production arvectum PG17 are separate
clusters. This task neither queried nor wrote them; uses existing
historical read-only receipts. Zero new EIS, SAP SRM or B2B requests via
private credentials, zero document/DP/DB mutations.

## Reusable components — no replacement connector required for inventory

| Capability | Proven existing path | Contract |
| --- | --- | --- |
| Public AJAX parser, exact ID/version and source URL | src/modules/tender_connectors/sibur/parser.py | Allowlisted origin, bounded response and pagination; do not invent current open |
| Nine-category archive, SHA-bound page receipts | src/modules/tender_connectors/sibur/archive_parser.py | Offline exact category/page validation |
| Replay original source snapshot | scripts/research/verify_sibur_public_snapshot.py | No new write or live network |
| Independently audit historical pages | scripts/research/audit_sibur_archive_corpus.py | Do not recrawl already verified 4052 original pages |
| Verify 516 saved document references | scripts/research/audit_sibur_saved_documents.py | Fail closed one PPT/PPTX, issue #686 |
| Historical Data Platform SHA/resource receipt reconciliation | scripts/research/reconciled_sibur_index.py | Seven saved sources; no live DP indexing |
| B2B source-bound original parent/lot identity | src/tender_research/corporate_procedure_identity.py | Requires exact original buyer/source, no source conflation |
| Reusable checkpoint and public-source planning | src/tender_research/ingest_checkpoint.py and scripts/procurement_llm/unified_source_pipeline.py | Any live import requires separate approval |

## Narrow successor work, not admitted by this inventory

1. Issue #692: deterministic local read-only original-page/ID/SHA vs a
   separately authorized REPEATABLE READ READ ONLY working-DB snapshot;
   deduplicate 204 repeated observations and account for 18251 absent
   and 551 extra records. Determine actual cause, do not speculate.
2. Issue #686: independently inspect ONLY the ambiguous .ppt URL/.pptx
   saved blob byte signature and provenance; leave NEEDS_REVIEW until
   source-backed format. Do not redownload 515 other files.
3. Define source-specific legal-entity IDs and distinct roles for original
   buyer, organizer, contractor, asset owner and sale/disposal.
4. If actual supplier/contractor history or SAP SRM private access is
   commercially needed, separately request scope, data-rights and
   source admission; source/API coverage not inferred from public links.
5. For any future mass historical import or DP index require explicit
   Owner decision, MI/prewrite/PITR/retention/rollback checks and isolated
   staging. The seven-day PITR issue #685 remains blocked, unrelated
   official EIS originals issue #679 remains blocked.

**Inventory done gate**: six source/access classes with provenance and
role restrictions; verified saved archive/working gaps; exact reusable
modules; narrow follow-up work. No live connector accepted, no actual
bid/payment/supplier message and no production deployment.

Previously saved private SHA-bound receipts were independently re-read
without exposing raw source data: archive receipt SHA256
07c4ce310b28dec397aa927f9cbcbfaeb6d9374017038c03c2a59a0af25c7f0d
(pass_historical_source_window); saved documents receipt SHA256
959c845b24e8fe0c911def07c5a4f2046cd141c625eabf9805b8cde012a975ea
(needs_review); historic DP proof SHA256
47fe7dffd0bff3c73fc71ab9ce2493a2cd65245a06d238c41d994ffa7821b8d9
(pass_historical_saved_DP_evidence_only). No new source access.
