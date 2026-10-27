# MI-013 Power Quality — 2024 original engineering source backfill (2026-10-27)

## Recovery, established baseline

Continuation from canonical v28, *not* a new 20-case research ledger. Original 101 source procurement notices preserved; 71 in live `arvectum_data` PostgreSQL, 30 Git-only, five first-party verified signed RD223 contracts, 28 original-protocol named-company **appearances** rather than unique winners.

This pass prioritized 2024, the sparsest years of the early v7 ledger (6 of its 58 source records; **not** a census of all v28/v29 101-year distribution). Exact original technical source added as independent **design-stage project lead, not a procurement announcement**. 2024 commercial candidates chges24621PR and RMC 895449 continue to have unproven medium-voltage ratings; source titles referencing a 10/0.4kV transformer do **not** qualify the attached UKRM as 10kV.

## Original 2024 electrical engineering document — Elga PS35/6kV

Original [PDF (65 pages)](https://etp.metal-it.ru/files/get/887fjTd5bkcxpDUVom6f4xnhpi5ckc7fAoLfrqRfYwazHE1fTNkT9shm7XVC3vdh3L/%D0%94-00001-%D0%A2%D0%9C-2024-%D0%98%D0%9B%D0%9E5.1.1_%D0%B8%D0%B7%D0%BC.0_02.10.24.pdf), retrieved via ETP's original file URL to Mac mini with HTTP200, **5,936,108 bytes; SHA256 `358293efaea44266e32a291a21bfcc87554fe4f404b02633d125df68975bf208`**, original volume title `Д-00001-ТМ-2024-ИЛО5.1.1`, 30 September 2024 (file revision `02.10.2024`), section 7, physical PDF page **20**. The page was *visually rendered and checked against text*; PDF title and procurement hosting are not enough alone.

Project title: `Строительство ВЛ 35 кВ Вахтовый поселок — Эльга; строительство ПС 35/6 кВ Эльга`. The engineering document states:
- install **one УКРМ 6 кВ nominal, 600 квар**, **three switchable 200 квар steps** at КРУН 6 кВ;
- locate unit in the OПУ premises;
- compensation uses fully automated factory-built compensators and multifunction control/monitoring;
- `ООО «Албынский рудник»` appears in the page of general designer signatories, *not equipment tender winner*.

Procurement reference number: **unknown**. Signed contractor/OEM: **unknown**. Installed/operating unit: **not proved**. Contract value: **unknown**. Strict 6–35kV **technical project demand** is verified but not a new 223-FZ tender. The company and location `Эльга` alone must not be matched to unrelated projects or Russian Copper 2024 electrical works.

First-party file and machine-verifiable evidence: `data/market_intelligence/power_quality/primary_engineering_elga_2024_20261027.v29.json`.

## Historical 2024 source audit: avoid voltage errors

| Canonical earlier record | What sources actually show | Implication for 6–35 kV TAM |
| --- | --- | --- |
| `223fz:chges24621PR:lot1` | 4 UKRM for kiosks KТП-400 / KТП-630kVA for ChirkheyGESstroy, 2024-11, original spec not obtained | **Nominal UKRM voltage unknown**; can be LV, do not count 4 confirmed MV units |
| `commercial:895449:lot1` | Russian Copper, 6 UKRM in 10/0.4kV TP-2,3,5; source a secondary commercial card | **UKRM voltage unknown**; 10kV transformer primary does not prove medium-voltage unit |
| `commercial:РН41205245:lot1` | 25 Dec 2024 Rosneft TEK-Torg multi-buyer UKRM procurement | One multi-buyer **notice**, not 4 completed vendor contracts; no original equipment rated voltage or price |
| `223fz:judicial-contract-03-34-24:lot1` | Court-confirmed Oct 29 2024 actual contract for **one 10.5kV/13Mvar UKRM** incl metal container by НАО «Электрощит», equipment price **21,307,585.20 ₽** as modified 10 June 2025, delivery UПД 16 June 2025 | **Already included** verified 2024 source. Do NOT duplicate contract, convert 2025 revised price to initial Oct 2024 award, infer OEM, or treat it as typical market €/Mvar |

References: [ЧиркейГЭСстрой](https://synapsenet.ru/zakupki/lotonline/chges24621pr--stavropolskij-kraj-postavka-4-chetireh-shtuk-avtomaticheskih), [РМК 895449](https://zakupki.kontur.ru/IS44114609), [РН41205245](https://zakupki.kontur.ru/IS48834468), [original 2024 contract documented by court](https://sudact.ru/arbitral/doc/adOxeAqN4doN/).

## Research governance

`v28→v29`: **101→101 tender notices** (0 new notices), **+1 separate source-proven 2024 design-stage lead**, 71 PostgreSQL +30 Git-only unchanged, **5** primary registered signed RD223 contracts unchanged, **28** original-company appearances unchanged. No claimed new revenue, OEM, signed contract or independent procurement winner. Initial 2024 triage is not exhaustive.

Queue advanced to `primary_evidence_retrieval_queue_20261027.v12.json`, includes stage-critical independent 2024 Elga lead and voltage verifications. Other pending original tasks unchanged: 2025 filter capacitor 12kV original signed RD223, 2026 Nagornaya UKRM 6kV200kvar signed supplier, Meleuz, Rosseti NTC component framework, 2026 Novatek GP630876 technical archive.

**Recommendation for next engineering source collection:** search ETP original procurement by the *exact design project code* `Д-00001-ТМ-2024` and Elga PS35/6, then obtain contractor BOQ, actual procurement number and supplier, rather than counting a project design as market won.
