# MI-003 Power Quality: portfolio matching / evidence readiness
Reporting window: 2023-10-24..2026-10-24.
**Status:** source-limited technical matching evaluation, not national market research.
Curated positive procurement descriptions: 12; correctly recognized family labels: 12.
Description-level labelled recall: 1.0. **Does NOT measure embedded EPC technical-annex recall.**
Synthetic negatives: 8; false-positive controls: 0.
Known buyer organization names in existing seed: 10; verified EPC/winners/designers from original protocols: 0.
Tracked source-month slots: 259; complete: 0; unknown: remainder. Zero verified completeness does NOT mean zero market.

## Lead-level technical label evaluation
| Lead | Family label | Matched | Source tier |
|---|---|---|---|
| pq-2023-mogocha-service | statcom | yes | third_party_only |
| pq-2024-chirkheygestroy | ukrm | yes | third_party_only |
| pq-2025-suhodol | statcom | yes | third_party_only |
| pq-2025-lukoil-ukrm1 | ukrm | yes | third_party_only |
| pq-2025-kuzbass-statcom | statcom | yes | third_party_only |
| pq-2026-lukoil-ukrm2 | ukrm | yes | third_party_only |
| pq-2026-lebedinsky | statcom | yes | third_party_only |
| pq-2026-ngk | ukrm | yes | third_party_only |
| pq-2026-rusal-data | statcom | yes | third_party_only |
| pq-2026-bashkirenergo-pir | ukrm | yes | third_party_only |
| pq-2026-rosseti-nw-epc | ukrm | yes | third_party_only |
| pq-2026-bidzaar-filter | harmonic_filter | yes | primary_platform |

## Initial sales qualification (not proven open tenders or EPC roles)
| Priority | Reported buyer | Observed procedures | Next actions |
|---|---|---:|---|
| P1 | ООО «ЛУКОЙЛ-Западная Сибирь» | 2 | Запросить техническую спецификацию, напряжение, диапазон мощности, условия аналогов и план следующих закупок |
| P1 | ООО «Морской порт «Суходол» | 1 | Выяснить действующего технического заказчика, проектировщика и EPC; предложить совместную комплектацию только после подтверждения ролей |
| P1 | ПАО «Россети Северо-Запад» | 1 | Выяснить действующего технического заказчика, проектировщика и EPC; предложить совместную комплектацию только после подтверждения ролей |
| P2 | АО «Лебединский ГОК» | 1 | Выяснить установленную базу, сервисные потребности и возможные планы модернизации, не считать обслуживание новой поставкой |
| P2 | АО «УК «Кузбассразрезуголь» | 1 | Запросить техническую спецификацию, напряжение, диапазон мощности, условия аналогов и план следующих закупок |
| P2 | АО «ЧиркейГЭСстрой» | 1 | Запросить техническую спецификацию, напряжение, диапазон мощности, условия аналогов и план следующих закупок |
| P2 | ООО «Башкирские распределительные электрические сети» | 1 | Уточнить судьбу ПИР и график утверждения проектных решений; предложить проверку характеристик и допустимых аналогов |
| P2 | ООО «Инженерно-Строительная Компания» | 1 | Запросить техническую спецификацию, напряжение, диапазон мощности, условия аналогов и план следующих закупок |
| P2 | ООО «НГК Ресурс» | 1 | Запросить техническую спецификацию, напряжение, диапазон мощности, условия аналогов и план следующих закупок |
| P2 | ПАО «Россети» / Забайкальское ПМЭС | 1 | Выяснить установленную базу, сервисные потребности и возможные планы модернизации, не считать обслуживание новой поставкой |

## Available independently of live SOAP
- Supplier upload intake: bounded text / file / URL through Data Platform SDK; source collection isolated by tenant + run.
- Portfolio family proposals: exact/expanded synonyms and context control; supplier claim not automatically verified.
- Search: Data Platform hybrid ranking within separately **authorized** procurement collections; exact chunk/document references and optional SHA-256.
- Role graph: only explicitly reviewed, original signed contract / official protocol / primary project documents support EPC, designer and supplier edges.
- Annual finance, TAM, competitor shares and full-Russia procurement count: NOT AVAILABLE until historical source and award coverage established.
- PPTX support implemented separately in Data Platform PR #126; requires review + service rollout before this upload type is live.

## Limitations
- Description-level recall on purposefully discovered examples is not recall on hidden technical annexes or the Russian procurement population.
- Synthetic negative controls are smoke/regression examples, not independently sampled false-positive prevalence.
- Per-month official EIS/commercial coverage denominator is unknown, no national TAM or historical growth claims.
- Buyer and engineering role from third-party procurement cards is unverified; no signed contract or winner inferred.
- Two EIS October 2026 failures represent source access errors, not zero relevant tenders.
