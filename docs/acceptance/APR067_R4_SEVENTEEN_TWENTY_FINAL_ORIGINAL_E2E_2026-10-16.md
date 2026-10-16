# APR-06/07 — последние четыре независимых исторических оригинала ЕИС

На момент создания протокола четыре новых архивных (не действующих)
44-ФЗ кейса проверены по оригинальным frozen getDocsIP ZIP/XML и
первичным бинарным вложениям. Реальные вызовы Gemma4 запущены
**последовательно** с индивидуальными приватными receipts;
их результат не заявляется до индивидуальной проверки.

| № | Реестровый номер | Тип извещения | Комплект оригиналов | Архивная НМЦК |
|---|---|---|---|---:|
| 17 | 0137200001226007700 | EZK2020 v1 | 4 XML + 4 вложения = 8 | 1 019 025 ₽ |
| 18 | 0169300008226000223 | EZK2020 v1 | 8 XML + 4 вложения = 12 | 4 000 000 ₽ |
| 19 | 0169300008226000225 | EZK2020 v1 | 8 XML + 4 вложения = 12 | 2 000 000 ₽ |
| 20 | 0377100005726000128 | EF2020 v1 | 7 XML + 4 вложения = 11 | 135 083,33 ₽ |

Всего **43/43 SHA-проверенных оригинала**, из них **16/16
подлинных бинарных DOC/DOCX/XLSX**, содержательно прочитанных
Data Platform (включая старые Word DOC и Excel). Каждое вложение
связано с исходным official EIS selected XML, реестровым номером,
filestore UID, официальным именем, заявленным размером, номером
позиции, оригинальным сохранённым именем и SHA. Для 17-го
существуют два локальных запуска с одинаковым official EIS ZIP;
выбран ровно один: toa-run-20261009052411-91c154 (его собственные
metadata SHA и оригинальные binary SHA закреплены). Второй не
смешивается с первым и не подменяет его источники.

Исходные сохранённые архивные сроки подачи:
17 — 08.10.2026 08:00 +03; 18/19 — 14.09.2026 09:00 +05;
20 — 13.08.2026 08:00 +07. Совпадающий срок у 18/19 **не**
означает одинаковую закупку: реестровые номера, НМЦК, исходные
файлы, UID и SHA различны. Native EIS intake: ready_to_analyze
для всех 4, zero external EIS/ETP calls, no bypass:
- 17: toa-run-20261016052530-1f98d7
- 18: toa-run-20261016052530-467820
- 19: toa-run-20261016052531-e9600f
- 20: toa-run-20261016052531-ca97b5

56 adversarial source guard tests PASS. Full local regression
and exact-code GitHub CI need independent recording. One real
Gemma4 sequence PID33179 proceeds 17 -> 18 -> 19 -> 20 only
after successful previous result, avoiding duplicate inference.
Raw original sources and output receipts remain offline.

Acceptance is DEVELOPMENT only under source-grounded delegated
ChatGPT expert review. No approval to bid, sign, pay, make
legal judgments or act on ETP. Current EIS relevance not checked.

Unresolved debt: historical case13 original model/source succeeded,
but its previously persisted report/history still contains
misleading training/vehicle-service template; corrected source-only
projection exists and original audit output is preserved unchanged.
**Case13 is not completed** until the corrected history report is
properly published and validated.


## Case 17 — actual original-source Gemma report verified

Archived EIS EZK 0137200001226007700: one actual local Gemma4
four calls / 351.32s HTTP200, no fallback, 8/8 original first-party
source SHA/text including original Word DOC contract draft; 3 original
EIS XML citations attest tourism site 'Калужское гостеприимство',
archived deadline 08.10.2026 08:00 +03 and NMCK 1,019,025 RUB.
HTML sha256 fc616ee5373fc7981a4b2b6db3f6f7704df41a20aae50a6349ccd7657021e818.
Site-maintenance general_services projection is not incorrectly
education or motor vehicle repair. Original project contract found.
Read-only report/history/reopen/registry HTTP200; unauthorized401;
archived PDF/DOCX exports409; manual_review_required pending
price and internal execution-resource evidence. One of two original
saved-run ZIP duplicates was pinned to its OWN metadata SHA and
binary SHA; no unverified mixing between copies.

Full post-code local regression: **4272 PASS / 238 SKIP / 0 failures**
and 56 focused source tamper PASS, Ruff PASS. GitHub exact-head CI
pending at this report revision. Second distinct source model
began only after 17th completed and original receipt persisted.


## Case 18 — real original-source E2E accepted

Archived EZK 0169300008226000223: one true Gemma4 analysis four calls
in 346.49s, API HTTP200, no fallback; 12/12 original SHA source XML
and first-party XLSX/DOCX/DOC documents extracted; 3 original EIS XML
source citations describe multimedia content for an interactive Troytsk
tourism excursion (NOT AR), historical deadline 14.09.2026 09:00 +05:00,
NMCK 4,000,000 RUB. Original HTML sha
8de3c8a59e8655b500856dcfb17126db8b1961b5a63f1c6d770002f5f7cfa036.
Contract draft present. Domain works; unsupported domain-specific
commercial readiness not fabricated: manual_review_required.
Report/history/registry/reopen HTTP200, unauthorized 401,
archived PDF/DOCX409. Distinct from next AR-excursion 2m case19.

Both cases17/18 source-model evidence and original code exact-head
GitHub Actions CI run38856008266 on commit
68879954bc33f7187aa082e952d50b9d158ae629 9/9 jobs SUCCESS.
Local full regression 4272 PASS/238 SKIP and focused56 source PASS,
Ruff PASS. Case17 and case18 child checkpoints COMPLETED.


## Case 19 — authentic original AR case and source-backed decision

Historical EZK 0169300008226000225: one genuine local Gemma4
4 calls / 351.99 s HTTP200/no fallback; original-source file SHA
12/12 including original XLSX price, DOCX draft/TZ and old DOC
application requirements. Three source-linked original EIS XML citations:
AR excursion multimedia and integration into the customer website
in Troytsk, archived deadline 14.09.2026 09:00 +05, NMCK2m RUB.
Saved original report HTML SHA
e0d41bd555fb0f6f42a15ebeeac2449c89e2d1ad69b07c919374f6bc7a1f41c0.
Separate registry ID, price and source binary SHA from case18.
Actual original contract present; work-specific commercial workflow
not externally validated; manual_review_required. Original
report/history/reopen/registry200, unauth401, historical exports409.
Full4272 local PASS/238SKIP/0fail and 56 source tests PASS;
substantive code CI commit68879954 run38856008266 SUCCESS9/9 jobs.
Case19 checkpoint COMPLETED. Case20 is the only remaining real
model in the serial process.
