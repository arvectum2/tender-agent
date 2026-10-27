# MI-013 Power Quality — PostgreSQL-synchronized 2024–2026 corpus v31 (27.10.2026)

## Verified operational state

As of 27 Oct 2026, 101 original-source procurement notices/lots are present **in both GitHub and production Data Platform PostgreSQL**, not only 71. The original 71 were updated in place; 30 previously GitHub-only inserted into `dp_resources` + `dp_records`. The 2024 original EPC primary-evidence addendum v31 updated **one pre-existing procurement record**. No external collection was touched.

| Metric, independently rechecked with read-only PostgreSQL | Result |
| --- | ---: |
| `arvectum_data`, `arvectum-market-pq-6-35kv`, source resources | **101** |
| JSONB structured `dp_records` | **101** |
| Unique resource procurement keys | **101** |
| Metadata base version v29 | 100 |
| Metadata enriched v31 | 1 |
| Existing procurement cases with at least one original source addendum v21–v31 | **13** |
| Additional original company name **occurrences** in sourced competition protocols | **30** (including rejected/runners-up; **NOT 30 unique winners**) |
| Original first-party registry **signed** contract cases | **5** (unchanged) |
| Named stand-alone signed 6–35kV hardware sales newly proven at v31 | **0** |
| Other Data Platform resources | **2,192** (unchanged) |
| Other Data Platform documents | **2,192** (unchanged) |
| Research review status | unreviewed, intentionally not claimed fully audited |

Historical source composition by **publication year**, directly from PostgreSQL `dp_records.data.publication_date` (101 lot/notice signals, **not national market coverage**):

| Year | Research records |
|---|---:|
| 2023 (from 27 Oct) | 3 |
| 2024 | **16** |
| 2025 | **23** |
| 2026 (through 27 Oct) | **56** |
| Not determined | 3 |
| **Total** | **101** |

Categorization by **discovered procurement subject**, not certified device voltage: `ukrm` **61**; `statcom` **5**; `capacitor_bank` **6**; `reactive_compensation_system` **10**; remaining categories combine filter components, dynamic compensation, SVC, and adjacent EPC. These category totals are **NOT** counts of technically verified 6–35kV devices. For example, original 2026 mixed-lot evidence revealed 26 low-voltage capacitor parts plus only one 11.55kV item; 2024 TP10/0.4kV UKRM nominal rating remains unproven.

Of 101 source observations, **37** have an NMCK / starting total in the source record. These are not signed equipment spend: many are EPC, project design, failed/repeated procurement, framework or mixed-voltage lots.

## v31 new original EPC bidder knowledge (one pre-existing 2024 case)

[Procedure 32413581034 / original EIS source listing](https://poisktenderov.ru/item/223/32413581034/), 2024 investment program **ПС 220 кВ Хани / Лопча**, `223fz:32413581034:lot2`.

Original [commission admission DOCX №3/3081547](https://zakupki.gov.ru/223/purchase/public/download/download.html?id=95400196), 05 Jul 2024, 33,206 bytes, SHA256 `40dc3e115650d6523c2935c4ddbabdcffb15e6d70391a679389750828284ecb3`: exactly 2 conforming bids and no rejections. Initial NMCK including VAT20 **1,518,147,770.00 ₽**.

Original [final commission DOCX №4/3081547](https://zakupki.gov.ru/223/purchase/public/download/download.html?id=95621445), signed **16 Jul 2024** (meeting 11 Jul), 44,306 bytes, SHA256 `f66c98a826fbfb7ede23ae18883614947c0fb74110d8579f4d20779707d1d545`:

| Applicant name from original first-party protocol | Rank | Final proposal **with VAT20**, ₽ | Procurement role |
| --- | ---: | ---: | --- |
| **ООО «ДИАПАЗОН»** | **1** | **1,517,360,443.50** | Selected EPC contractor |
| ООО «Строй Монтаж Инжиниринг» | 2 | 1,517,414,869.36 | Runner-up EPC bidder |

The commission instructed pre-contract talks to lower the price. Neither firm is thereby established as **manufacturer** of actual SKRM devices; winner proposal is **NOT a signed contract price**, much less a separate 6–35kV unit sale. The project title mentions 128/154Mvar compensation at 220kV substations; **exclude this EPC total from FGI 6–35kV hardware TAM**.

The original 2024 procurement was **already** in the corpus: **101→101, not 102**. Named original-protocol company *occurrences* incremented 28→30 (two additional entrants). Structured new source: `data/market_intelligence/power_quality/primary_2024_khani_epc_original_award_20261027.v31.json`. Correctly linked to existing canonical case `223fz:32413581034:lot2`.

## Production synchronization and safety trail

1. Before full import, official [MI-013 v29 production import receipt](../../data/market_intelligence/power_quality/mi013_production_import_receipt_20261027.v29_101.json) records `pg_dump -Fc` backup **37,423,404 bytes** SHA256 `55a31201d7d2620bba64e28e578ba325938a0613a33309f52fed1558c4819d7b`. Single atomic transaction updated 71 and inserted 30, independently read back 101/101 with all existing stable IDs.
2. A second guarded **single-case incremental v31 SQL transaction** created its own official verified PostgreSQL backup `data-platform-arvectum_data-20261027T190324Z.dump`, **37,464,672 bytes**, SHA256 `18a269110cd46747b3c4286dcf83ae826a00be882540557d79286cd8a8ba22ef`. One initial guarded attempt was rolled back safely on SQL NULL-absence mismatch; fixed with `COALESCE`, re-ran and confirmed **COMMIT** and exact new case content hash `361287c26ced10912de724ed5f76bfe5915b82dc84ffab897d9fb265c8b61094`.
3. Original full source script `scripts/market_intelligence/import_pq_postgres_v29.py` is now protected against **downgrade to v29** over the v31 evidence; use versioned guarded `scripts/market_intelligence/apply_pq_evidence_v31.py` for this incremental batch. Its follow-up `--check-db` reports `already-applied-idempotent`.
4. `tests/test_mi013_pq_import_v29.py`: **8 tests PASS** on 101 original rows. PostgreSQL independent read-back confirms 101 resources/records, 100 base metadata v29 and 1 v31, 13 original-source-enriched procurement records, other Data Platform collections unchanged. Separate 2024 Elga 6kV/600kvar **project engineering design** remains outside the 101 notices.
5. The existing working checkout `/Volumes/ArvectumSSD/Arvectum/repos/tender-agent` has unrelated uncommitted work and was not modified. Isolated Git worktree `/Volumes/ArvectumSSD/Arvectum/runtime/mi013-pq-import-v29` was used for staging/tests, source versioning committed to `research/mi013-pq-corpus-20261027-pass2` via GitHub.

## Commercial next steps

Focus *signed original RD223 agreements*, not secondary winner lists, for: 2025 Kuzbass 14×12kV KЭПФ `32514947144`, 2025 MES South 12×12kV `32515029641`, 2026 Nagornaya 6kV/200kvar `32515582393`, Meleuz 6.3kV/500kvar `32616296475`, and Rosseti NTC 2025/2026 two overlapping raw-materials frameworks. Other key tasks are ETGPB `ГП630876` original retrofit technical docs and 2024 original equipment/offer corpus, excluding low-voltage false positives.

**Do not multiply 101 source notices into claimed 101 signed sales, sum 37 NMCK values as PQ market turnover, or assign 1.517bn EPC quote as a 6–35kV compensator price.** All totals are sourced observations and require scope-specific attribution.
