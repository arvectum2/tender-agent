# APR-06/07 — три следующих независимых E2E на оригиналах ЕИС

**Статус при создании протокола:** три разных исторических закупки
подготовлены и проверены по первоисточникам; настоящая локальная Gemma4
выполняет их последовательно. Результаты LLM до наличия отдельных
сохранённых receipts не считаются подтверждёнными.

| Порядок | Номер | Архивный тип | Исходные файлы | Особенность |
|---|---|---|---|---|
| 11 | 0149200002326001555 | epNotificationEZK2020 v1, запрос котировок | 4 XML + 5 вложений = 9 | Старый DOC обоснования НМЦК; проект контракта DOCX |
| 12 | 0148200000526000028 | epNotificationEF2020 v1, аукцион | 5 XML + 4 вложения = 9 | Два независимых источника восстановленных DOCX |
| 13 | 0349100009326000005 | epNotificationEOK2020 v1, конкурс | 4 XML + 5 вложений = 9 | Два настоящих DOC, отдельный порядок оценки заявок |

Все 27 исходных файлов проверены SHA-256; оригинальные архивы getDocsIP
и конкретные XML извещений проверены по замороженному R4-манифесту.
Каждое приложение связано с конкретным UID, номером позиции, официальным
именем, длиной, SHA исходного бинарного файла, одним из двух
first-party receipts от 14.10 и выбранной версией XML. Два независимых
оригинальных набора: `competitive-missing-11-originals-20261014` и
`competitive-older-missing-4-originals-20261014`.
В GitHub сохраняются только проверочные манифесты, не сами DOC/DOCX.

Штатная EIS intake дала `ready_to_analyze` для всех трёх
без bypass и без сетевых запросов к ЕИС:
- 11: `toa-run-20261015214553-a71602`
- 12: `toa-run-20261015214553-a75201`
- 13: `toa-run-20261015214554-288eac`

Настоящая Data Platform при preflight извлекла 5/5, 4/4, 5/5
содержательных вложений соответственно, включая все три оригинальных
старых Word .doc. Оригинальная НМЦК из XML:
1 201 200 руб.; 3 393 000 руб.; 130 000 руб.
Архивные сроки окончания подачи: 07.04.2026 07:00 +03:00,
18.09.2026 07:00 +03:00, 02.03.2026 07:00 +03:00.
Текущая действующая редакция ЕИС не проверялась.

Единый serial process PID6706 на Mac mini запускает модель Gemma4-12B
строго в порядке 11 → 12 → 13 и лишь если предыдущий завершился без
ошибок. Каждому кейсу соответствует отдельный приватный запуск/отчёт.
Ни один анализ нельзя автоматически перезапускать, если уже существует
его подтверждённый receipt. 27 негативных тестов split-receipt плюс
23 регрессионных source-теста: 50 PASS; полная регрессия и CI
отслеживаются отдельно.

По принятому решению владельца source-grounded разбор ChatGPT считается
экспертной проверкой на стадии DEVELOPMENT. Это не
криптографическая проверка ЭП, разрешение на реальное участие в торгах,
коммерческое GO, проверка актуальности ЕИС или production-SLO.


## Case 11 — actual single Gemma run verified

Case №0149200002326001555: **one genuine local Gemma4 run, 4 calls /
379.06 s, HTTP200, no fallback**; all 9 original source SHA/text
passed and 3 original `eis-xml:` citations on Murmansk Investment
Portal services, archived deadline 07.04.2026 07:00 +03:00,
NMCK 1,201,200 RUB. HTML SHA-256
`3870519c557b701c3e60da73a99f16cf683448fc71325261bf719b2e03f581e6`.
The read-only registry/report/history HTTP200, unauthorized workspace401,
historical PDF/DOCX export 409; the decision is
`manual_review_required`. The report says the MIXED category's
specialized automated analysis is not validated. Five contract risk
hypotheses are explicitly marked for manual verification: do not treat
them as attested legal clauses. This is source-grounded developmental
review, not actual participation approval.


## Case 12 — real source-backed provider analysis completed

Case №0148200000526000028: **one real Gemma4 run, 4 calls / 389.27s,
HTTP200, no fallback, 9/9 original SHA/text**. Original `eis-xml:` source
citations 3/3 for the site support services, archived deadline
**18.09.2026 07:00 +03:00**, NMCK **3,393,000 RUB**. Saved HTML SHA
`2883659a2d5afbf2cdd00655313f06ae776023fa58e3da2d9d58560c4d81fd15`.
Four substantive restored original DOCX documents (NMCK justification,
genuine draft state contract, technical description and participation
requirements) all extracted and correctly classified. Real output
`manual_review_required`, contract found, no claim of confirmed pricing
or internal capacity. Five English model-proposed contract risks remain
labeled `[Гипотеза LLM — проверить договор]`, **not legally verified**.
Report, history, read-only registry HTTP200; unauthorized access401;
historical PDF/DOCX export409. Third case automatically started only
after this result was saved and first code gate returned 0.
