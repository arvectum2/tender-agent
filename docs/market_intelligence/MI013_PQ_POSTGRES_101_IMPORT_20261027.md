# MI-013 — PostgreSQL Data Platform fully synchronized (27 October 2026)

## Outcome

Source corpus `v29` of **101** canonical procurement notice/lot records, independently materialised from original v20 (100) and v23 one first-party procurement plus v21–v28 original document evidence, has been imported successfully into **`arvectum_data` → `arvectum-market-pq-6-35kv`**. Source snapshot after import is `verified_public_leads_20261027.v30.manifest.json`: **101 PostgreSQL, 0 GitHub-only**. No new market-source procurement notice was discovered by database import.

| Property | Before | After |
| --- | ---: | ---: |
| Resources in dedicated PQ collection | 71 | **101** |
| Source-linked structured procurement records | 71 | **101** |
| Unique canonical procurement IDs | 71 | **101** |
| Source metadata at v29 | 0 | **101** |
| Former 71 records (review status unreviewed preserved) | 71 revision 1 | 71 revision 2 |
| Newly inserted lot/notice records | 0 | 30 revision 1 |
| Other Data Platform resources | 2,192 | **2,192 unchanged** |
| Other Data Platform records | 0 | **0 unchanged** |
| Other Data Platform documents | 2,192 | **2,192 unchanged** |
| Separately proven original RD223 signed contract cases | **5** | **5** |
| Named original-protocol company occurrences | **28** | **28** |

The data is a **non-exhaustive research corpus of procurement signals**, not 101 awarded contracts or an estimate of the national PQ TAM. Every record retains original source URLs, classification, tax-basis warnings and an explicit `research_not_market_population` flag.

## Recovery and safety

- The original checkout `/Volumes/ArvectumSSD/Arvectum/repos/tender-agent` with user's unrelated dirty changes was not modified. An isolated detached branch checkout was used at `/Volumes/ArvectumSSD/Arvectum/runtime/mi013-pq-import-v29`. Research branch changes were published via GitHub.
- Safe script `scripts/market_intelligence/import_pq_postgres_v29.py`, reviewed original 71-row import and table schema. Importer checks 71 matching legacy IDs, verifies collision isolation and source provenance, requires owner approval token and existing absolute backup directory, uses transaction and rollback on mismatch.
- **Official pre-write custom PostgreSQL backup** `/Volumes/ArvectumSSD/Arvectum/runtime/data-platform-backups/data-platform-arvectum_data-20261027T185330Z.dump`, **37,423,404 bytes**, SHA-256 **`55a31201d7d2620bba64e28e578ba325938a0613a33309f52fed1558c4819d7b`** independently verified against `.sha256` companion and `.manifest.json` before SQL.
- Input 101-source JSON staging digest SHA-256 **`5ed3a0ec5508bc65912d5743d141e7dfb7715cbae755712a8514b8ab652ea1e4`**.
- Full readback post-import: resources=101, records=101, distinct external ID=101, all source metadata v29=101, existing 71 updated and 30 added. No changes to other collections, documents or embeddings.
- Script follow-up change makes subsequent **`--check-db` idempotent** at either 71 (legacy) or 101 (applied). Verified post-apply read-only preflight 101 existing/0 missing, no foreign resources.
- `tests/test_mi013_pq_import_v29.py`: **8 tests PASS**. They verify unique stable IDs, no 2024 Elga design counted as tender, v23 related but not double-counted 2026 NTC framework, v28 **both** lots' voltage correction (26 LV+1 11.55kV MV), and signed-offer provenance separation.
- Restored original 2024 Elga design `engineering:2024:ps-elga-35-6kv-600kvar` lives in sidecar only, **not** as procurement no. 102.
- All source-evidence overlays v21, v22, v24–v28 are embedded as `mi013_source_enrichments` in the respective JSONB `dp_records.data`. For v28, both of the BESK two lot records reference the disaggregated itemized 27-piece BOM; whole price is NOT claimed for one MV capacitor.

## Reproducible read-only verification

On Mac mini in the isolated checkout:

```bash
python3 -m unittest discover -s tests -p 'test_mi013_pq_import_v29.py' -v
python3 scripts/market_intelligence/import_pq_postgres_v29.py --check-db
```

Import cannot rerun without the explicit `--apply` option, owner approval token and official backup dir. For subsequent source versions, add a new append-only source manifest and importer stage instead of rewriting the v29 historical manifest.

Structured receipt: `data/market_intelligence/power_quality/mi013_production_import_receipt_20261027.v29_101.json`. Current operational manifest: `verified_public_leads_20261027.v30.manifest.json`.

## Next research priorities

1. Original **RD223 signed contracts** for selected original 2025 `32514947144` (14×12kV), `32515029641` (12×12kV) and 2026 `32515582393` (6kV200kvar Nagornaya), plus Meleuz `32616296475`, Rosseti NTC frameworks `32515218366` and `32616355390`, to identify counterparties and prices.
2. 2024 original ETP technical questionnaires and original 2024 Elga engineering `Д-00001-ТМ-2024` project-to-contract linkage, not engineering demand counted as sale.
3. Original ETGPB `ГП630876` retrofit archive and buyer/supplier identification, repeat dedup with cancelled `ГП628666`.
4. Market-role graph under strict device voltage 6–35kV; do not equate 0.66/1.05kV capacitors, 110kV BSK, 220kV SVC, multi-year EPC framework ceiling, design fees and pure hardware revenue.
