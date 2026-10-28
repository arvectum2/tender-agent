# PQ EIS 7z source recovery — 28 October 2026

## Original-document-backed exclusion from the 6–35 kV market

The secondary Energybase discovery https://energybase.ru/tender/01a02eb4-f3f2-7195-9554-9ebc29fc5fce identified EIS 223-FZ notice **32616247401**, Novgorod branch of PАО «Россети Северо-Запад», titled *Поставка устройств обеспечения качества электроэнергии*. The stated **16,708,000 RUB is NMCK, not a signed contract amount**. This candidate is absent from immutable MI-013 v20 (100 records); it was investigated separately, without changing v20.

The exact EIS public 223-FZ documents page was fetched through the existing notice-number/GUID-bound provider. Its HTML SHA-256 is 136e2fdd56519f56d4806db67db77f2a3e713aa1c3d54b245ee31636314d96ef. All six attachments were 7z, previously rejected as unsupported. A narrow **opaque-only** 7z downloader gate now requires the exact EIS public-page provenance, two 64-character source SHA fields, verified HTTPS host, bounded size and correct archive signature. No automatic extraction or award inference is permitted.

Four original 7z files were downloaded without repeating previously verified originals:

- Protocol 2 archive SHA-256 5288fa3633146e65281463bc9060ad63f2e27e951f25985b7cfad6d62fa53cfb.
- Protocol 3 archive SHA-256 d2ccaf1b3c2760efc5356d691e34f29918a6866947ff1ebc3ceabadcd81a8983.
- Protocol 6 archive SHA-256 2175e90642cba1299928afc59086f8ccfde5a613d51cba335042320714f63c68.
- Technical documentation archive SHA-256 ed157cad52f4114c965964e1313835fd1db2310fc00a4d703eaa17305b5e4f47.

Only individually selected small DOCX members were streamed from these archives after parent-SHA verification and bounded DOCX/ZIP validation; arbitrary paths were never extracted to the filesystem. The runtime preserves the original 7z bytes, child hashes and parent/page SHA mappings. The original EIS public page remains a weaker evidence tier than SOAP-XML revision binding.

The original technical specification DOCX SHA-256 915b65d003b724c3ee79c99bf8dc63d5dc7aeb737df5c841baf81f8292a7e086 states:

> Регулирование нагрузки, напряжения и тока в сети 0,4 кВ с трансформатором Y/Y0 или Y/Y0 симметрирующим устройством.

It also specifies installation on VL-0.4kV and identifies **УАБ 100** and **ПКС 3-100-5С** low-voltage devices. Protocol 6 child SHA-256 ad3a9826217e26f2a0c46c454d2a67b9d7b1b308642e10e6ed65936e4a18349b only extends the results deadline to 27 October 2026; it is not a signed award.

ChatGPT via ARC reviewed and accepted the protocol-only packet 32616247401-549f2edb9b293ab80c20942d as UNCERTAIN and the later original technical packet 32616247401-ca850ee97eb3487af939ee6b as **IRRELEVANT to 6–35 kV**. Both source-quote/SHA-bound reviews remain immutable. Do not count the 16,708,000 RUB NMCK in the medium-voltage equipment market or treat it as a signed equipment sale. Winner, manufacturer, final contract price and contract signature remain unverified.

## Wider gap recovery and next step

The refreshed 100-row v20 gap inventory has 31 case-specific local-document cases and 31 reviewed cases. No new EIS search was eligible: 33 existing official attempts remain under retry. Nine distinct new public Kontur source probes returned HTTP 403 and were recorded as inaccessible with a 12-hour retry interval; ETP card journal now has 46 entries. No access controls were bypassed.

The new candidate remains separate from the v20 corpus; the review queue has two additional accepted packets and one earlier unreadable PDF pending. No newly verified signed contracts or suppliers. Continue original signed-contract and native B2B-Center/RAD retrieval for eligible 6–35kV cases. PR stays DRAFT/REVIEW while baseline CI architecture audit fails on the direct Data Platform import; do not weaken audit or alter unrelated current-task/Watchdog.
