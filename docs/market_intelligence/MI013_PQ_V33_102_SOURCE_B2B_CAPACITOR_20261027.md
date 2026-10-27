# MI-013 Power Quality — B2B-Center original one-unit 10.5 kV capacitor, 102nd legal notice (27 October 2026)

## Source-grade new case: 4643332

**New canonical key** `commercial:4643332:lot1` was independently absent from all 101 existing `arvectum-market-pq-6-35kv` records before this pass. Not a duplicate of commercial TЭК-Торг `РН61001644` or original Rossseti 12kV capacitor lots.

Original [B2B-Center tender №4643332](https://www.b2b-center.ru/market/808-kondensator-kep3-10-5-150-3u2/tender-4643332/) was accessed live by HTTP 200 and original HTML analyzed directly.

| Fact | Original platform states |
| --- | --- |
| Title | `808 - Конденсатор КЭП3-10,5-150-3У2` |
| Requested nominal equipment voltage | **10.5 kV**, strictly within 6–35 kV component subset |
| One capacitor nameplate reactive power | **150 kvar** |
| Total units requested | **1** |
| **Organizer (B2B original)** | **ООО «УК «Колмар»** |
| **Buyer (B2B original)** | **АО «ВТУ»** = АО «Ванинотрансуголь», INN **2709015787** independently established by [Kontur original external registration index](https://zakupki.kontur.ru/4643332_4) |
| Publish | **16 October 2026 07:45 Moscow** |
| Tender end | **19 October 2026 03:00 Moscow** |
| Original board result | **22 October 2026 05:39** |
| **Original applicant count** | **0** |
| **Original outcome** | **FAILED / not concluded**. Organizer archived the procedure. |
| Starting/offer price | **Not specified**, do not infer unit price from earlier KЭПФ lots |
| Awarded supplier, manufacturer, signed contract | **NOT known; zero applications means no winner via this procedure** |

### Why the buyer identity matters

Secondary [Energybase index](https://energybase.ru/tender/01a1493f-f5ff-706d-bbe1-009c2380bf5d) only prints *ООО «УК «Колмар»* under a buyer-like field. The **original platform explicitly has two different attributes**: `Организатор: ООО "УК "Колмар"`; `Заказчики: АО "ВТУ"`. [Kontur specific procurement](https://zakupki.kontur.ru/4643332_4) identifies that AO as **АО «Ванинотрансуголь», ИНН 2709015787** and confirms 4643332. **Do not count two buyer entities or attribute equipment order to Kolmar.**

Even though a clear 10.5 kV/150 kvar requirement demonstrates *demand interest*, the original first-party board confirms **zero received bids**. This is not one sold device, not a signed contract, not supplier market share and not proof of the Russian capacitor market size. It is a *failed technical procurement signal*; later reprocurement (if any) requires an independent number or actual signed contract. Current component item is also not a whole 10.5 kV statcom or 150Mvar filter bank.

## Versioned source and production update

- Append-only original-source file: `data/market_intelligence/power_quality/original_b2b_capacitor_vtu_20261027.v33.json`.
- **v32 101 → v33 102** procurement notices, **one** original commercial B2B source row added, **zero signed first-party contracts added**, no additional named winning companies.
- Operational manifest: `verified_public_leads_20261027.v33.manifest.json`, with **102 PostgreSQL + 0 GitHub-only**.
- Safe import: `scripts/market_intelligence/import_pq_b2b_original_v33.py`. It validates current tenant and 101 legacy row baseline, canonical ID and original URI absence, 0 applications, null winning company/price; requires official backup and uses one atomic PostgreSQL INSERT pair (source resource + structured JSONB record) with post-commit checks.
- Official PostgreSQL backup **`/Volumes/ArvectumSSD/Arvectum/runtime/data-platform-backups/data-platform-arvectum_data-20261027T200242Z.dump`**, **37,467,998 bytes**, SHA-256 **`71cfc2b274c3d3d7d1af8873a4aab031656554a4de499d4663473d45ef2ac61d`**, independently checked by the existing backup helper against checksum and manifest BEFORE any write.
- Deterministic new-source payload content hash **`e6bdaaf1768467f4688ed098a6790bba79210dadfc987f3c0169b3e1ff1c8983`**.
- Verified one-transaction result: 102 `dp_resources`, 102 `dp_records`, 102 unique external IDs, other Data Platform resources **2,192 unchanged** and `dp_documents` **2,192 unchanged**. Metadata versions in database: **98 v29 + 1 v31 + 2 v32 + 1 v33**.
- Crucially, source `scripts/market_intelligence/materialize_pq_research_v33.py` regenerates **all 102** rows from v29 original/verified base 101, original source overlays v31 and v32, and new B2B source v33; read-only independent equality of source `content_hash` for *all 102* with PostgreSQL passed **102/102, zero drift**.
- Older local checkout `/Volumes/ArvectumSSD/Arvectum/repos/tender-agent` contained unrelated dirty work and was never altered. Changes committed to existing `research/mi013-pq-corpus-20261027-pass2` branch. Isolated detachable worktree used.
- Checkpoint stays `in_progress`; queue `primary_evidence_retrieval_queue_20261027.v15.json` includes tracking the failed B2B original for potential independently numbered repeat procurement.

## Research next stages

Highest value remains recovering signed **RD223 contracts** for 2025 12 kV capacitor supplies (Kuzbass `32514947144`, MES South `32515029641`), 2026 6 kV/200 kvar Nagornaya `32515582393` and Meleuz `32616296475`, plus manufacturer identity and actual delivered prices. Other research streams: original ETGPB `ГП630876` 10kV UKRM retrofit; genuine 2024 engineering and signed power quality hardware awards; avoid 0.4/1.05kV false positives and don't double count EPC/framework ceilings or unsold 10.5kV item.

This is a source-backed **research sample**, not representative national market coverage, so procurement count growth does not imply a proportionate market increase.
