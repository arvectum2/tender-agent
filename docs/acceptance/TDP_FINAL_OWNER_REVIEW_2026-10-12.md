# TDP final owner review (2026-10-12)

> Read-only machine source audit, NOT owner acceptance, current auction status or GO decision.

## Evidence

- R2 isolated HTTP+Postgres: five original EIS file hashes and 127/127 normalized chunks valid; live Data Platform has no matching five originals among 2034 scanned resources.
- R5 official SOAP: 17/20 ZIPs and 3 no_data; 168/168 cached historic original hashes matched, 96/96 original XML bytes matched official archives, 72 binary attachment UIDs anchored but external EIS filestore HTTP429 prevents fresh byte proof.
- Historic nine reports: 9/9 maximum prices and 7/9 deadlines match newest archived XML; three cached notice versions are stale.
- R4 local Gemma4 12B source-locked XML machine benchmark: 17 cases, 67/68 fields correct, 16/17 cases entirely correct, 105.5 model seconds. One incorrect registry number: 0895100000126000897. NOT human legal/commercial gold.

## Twenty real EIS cases requiring human signoff

All deadlines and max prices below are from the latest archived official XML, not guaranteed current published data.

| # | EIS registry | SOAP source | Cached->archived version | Price RUB | Archived deadline | Required next check |
|---:|---|---|---|---:|---|---|
| 1 | [0127100008626000013](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0127100008626000013) | ZIP | 1 -> 1 | 76800.00 | 2026-09-30T07:30:00+03:00 | Human source review |
| 2 | [0137200001226007700](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0137200001226007700) | ZIP | 1 -> 1 | 1019025.00 | 2026-10-08T08:00:00+03:00 | Human source review |
| 3 | [0148200000526000028](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0148200000526000028) | ZIP | 1 -> 1 | 3393000.00 | 2026-09-18T07:00:00+03:00 | Human source review |
| 4 | [0148300050426000047](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0148300050426000047) | no_data | UNKNOWN | UNKNOWN | UNKNOWN | Obtain official archive |
| 5 | [0149200002326001555](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0149200002326001555) | ZIP | 1 -> 1 | 1201200 | 2026-04-07T07:00:00+03:00 | Human source review |
| 6 | [0158300034526000388](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0158300034526000388) | ZIP | 1 -> 5 | 152033.33 | 2026-10-12T08:00:00+03:00 | STALE: verify notice version |
| 7 | [0162300005826000156](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0162300005826000156) | ZIP | 1 -> 1 | 495000 | 2026-06-17T07:00:00+05:00 | Human review of prior report |
| 8 | [0169300003326000181](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0169300003326000181) | ZIP | 1 -> 1 | 226938.66 | 2026-07-27T07:00:00+05:00 | Human review of prior report |
| 9 | [0169300008226000223](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0169300008226000223) | ZIP | 1 -> 1 | 4000000.00 | 2026-09-14T09:00:00+05:00 | Human review of prior report |
| 10 | [0169300008226000225](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0169300008226000225) | ZIP | 1 -> 1 | 2000000.00 | 2026-09-14T09:00:00+05:00 | Human review of prior report |
| 11 | [0318200087026000163](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0318200087026000163) | no_data | UNKNOWN | UNKNOWN | UNKNOWN | Obtain official archive |
| 12 | [0348100024426000039](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0348100024426000039) | ZIP | 1 -> 3 | 1245000.00 | 2026-10-19T10:00:00+03:00 | STALE: verify notice version |
| 13 | [0348100024426000052](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0348100024426000052) | no_data | UNKNOWN | UNKNOWN | UNKNOWN | Obtain official archive |
| 14 | [0349100009326000005](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0349100009326000005) | ZIP | 1 -> 1 | 130000 | 2026-03-02T07:00:00+03:00 | Human source review |
| 15 | [0349500000226000003](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0349500000226000003) | ZIP | 1 -> 1 | 3853453 | UNKNOWN | Human source review |
| 16 | [0360600005326000018](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0360600005326000018) | ZIP | 1 -> 2 | 2700000 | 2026-04-06T10:00:00+04:00 | STALE: verify notice version |
| 17 | [0372200172326000015](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0372200172326000015) | ZIP | 1 -> 1 | 1000000.00 | 2026-10-16T10:00:00+03:00 | Human review of prior report |
| 18 | [0376300000126000193](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0376300000126000193) | ZIP | 1 -> 1 | 251200 | 2026-06-02T07:00:00+03:00 | Human review of prior report |
| 19 | [0377100005726000128](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0377100005726000128) | ZIP | 1 -> 1 | 135083.33 | 2026-08-13T08:00:00+07:00 | Human review of prior report |
| 20 | [0895100000126000897](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0895100000126000897) | ZIP | 1 -> 1 | 10138500 | 2026-06-19T09:00:00+03:00 | Human source review |

## Blocking gates — do not declare refactor completed

1. R2 live Data Platform 0.6.0 must demonstrate matching persisted original resource/document/chunk evidence. Isolated 5/5 is not live proof. No production writes without separate approval.
2. Official EIS filestore original-binary re-fetch blocked by HTTP429; UID alone is not byte-level verification. No unsafe TLS bypass or retry storm.
3. R4 benchmark remains MACHINE XML oracle, not human-labeled legal/citation/commercial gold. Unsupported facts must remain UNKNOWN.
4. R5 independent human signoffs: 0/20. Use the already provided TDP_R5_20_CASE_HUMAN_REVIEW_QUEUE_2026-10-11.csv only after actual source review; no scripted GO.
5. Re-run complete authenticated product E2E and exact-head CI after closing gates. No public deploy, bid submissions, signing or watchdog changes.

## Reproduction

- Machine audit: TDP_R5_INDEPENDENT_AUDIT_2026-10-12.md, 20-case and 168-file CSVs in this directory.
- Local model: scripts/acceptance/benchmark_r4_official_eis.py (source ZIP SHA, notice revision and XML field checks); tests/test_tdp_r4_official_eis_benchmark.py.
- Private proof: Mac mini evidence/tdp-r5/independent-20261012, never checked into Git.
- Local benchmark result SHA256: 3514429a1b06c0412b64c3811da32e67a1d220374a1688317c09b6e295c4f28e
