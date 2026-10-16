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
