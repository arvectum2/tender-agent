# Gemma 4 12B — источник, цитирование и повторные попытки

ООО «Арвектум», 19.10.2026. Проверенный архивный XML ЕИС № 0163200000326005243, исходный getDocsIP ZIP SHA256 4cec297f6bd040723105fab5ac03a3d10e986b3c03b03032a7da3c3769389d5d. SQL 86 чанков, Data Platform 86 ресурсов и 86 эмбеддингов — исходный индекс сохранён.

## Диагноз

Предыдущий настоящий полный прогон Gemma 4 12B, источник source_quality_rerun, ID eeaed777-48ff-4e12-89fb-55eb01cb8e10, длительность 1550.6728 сек: 6 из 10 ответов прошли. Ошибки из PostgreSQL warnings_json: subject — неверный chunk ID; customer_requirements, evaluation_criteria, contract_terms — unsupported explicit percent. Отброшенные ответы не являются фактами, не используются для обучения.

## Что изменено в отдельной review-only ветке

- Источниковый маршрутизатор для archived Smolensk EIS only: дополнительно поднимает оригинально привязанный XML для notice_info, subject, deadlines, а подтверждённую из DOCX таблицу 30/70 и 80/20 — для evaluation_criteria. Проверяются Registry Number, Tender ID, Document ID, ZIP SHA, версия, схема provenance, фактический SHA физического owner-private DOCX и mode0600; не допускается чужая закупка.
- При подменённом SHA или некорректном документе привилегированная подборка отключается, исходная выборка фильтруется строго по тому же тендеру. Новых чанков, поддельных цитат и данных в SQL не добавляется.
- Допускается максимум одна дополнительная генерация исключительно для подробного ответа, который не прошёл numeric/citation guard; во второй запрос передаются только те же доказательства, их реальные chunk IDs и точно встречающиеся проценты. Старый отклонённый текст не используется; любая повторная ошибка остаётся rejection/fallback. Число фактических LLM-вызовов теперь учитывает повторные попытки.
- Новый проверочный скрипт выполняет 4 реальных вопроса к Gemma на 86/86 источниках. Он использует read-only PostgreSQL транзакцию и Data Platform search, пишет только частный JSON 0600, без новой TenderAnalysisRun, без gold и BID_GO.

Реальный read-only source probe подтвердил правильные первые документы: для subject два чанка XML, для evaluation_criteria подтверждённый DOCX с процентами; для двух других — официальные оригинальные требования к заявке и проект контракта. Была выполнена общая регрессия 918 passed/2 skipped и отдельные 12 адресных тестов (включая чужой тендер, подмену SHA и отрицательный retry), Ruff PASS.

## Следующий gate

Дождаться результата ровно 4 вопросов Gemma в частном каталоге /Volumes/ArvectumSSD/Arvectum/private/tender-agent/quality-benchmarks/gemma-four-retry-20261019, проверить фактическое время, accepted/rejected, доказательность цифр и цитат. Не запускать повторно PID 5363 при работе. Если 4/4 не доказаны, блокер остаётся; полный 26-минутный quality rerun не запускать. Если 4/4 доказаны, отдельно согласовать versioned full rerun с backup и жёсткими исходниковыми guard. Ни один результат не имеет человеческого gold.

## Four-section experiment observed at 20:30 MSK

Actual Gemma 4 12B / llama.cpp source-only read-only four-section probe completed with 2/4 accepted answers. Customer requirements (298.02 seconds, 2 attempts) and evaluation criteria (297.66 seconds, 2 attempts; explicit 30/70 and 80/20) passed strict evidence checks. Subject failed on unsupported rub amount (272.94 seconds, 2 attempts), and contract terms failed on unsupported percentage (351.01 seconds, 2 attempts). Total 1219.63 seconds, zero new TenderAnalysisRun and zero gold.

An additional owner-private two-question experiment PID 39834 (subject, contract_terms only) was launched with stricter same-context repair lists of actual monetary and percent values; it writes ONLY retry2-result.json to private quality benchmarks, preserves first report. Broad regression 922 PASS/2 SKIP, targeted 15 PASS, Ruff PASS. If repeat still fails, do not claim overall 4/4 nor repeat full 10-question baseline. Final source semantic review remains separate from citation acceptance.

## Verified further source-format root causes

Second real source-only two-question Gemma probe finished with 1/2 **formal** acceptance: subject (287.7 seconds) and rejected contract_terms (348.03 seconds; unsupported percent). Manual audit of subject found **false negative**: it claimed that the NMC was not confirmed, despite the original XML source chunk explicitly stating NMC RUB: 497178.33. This formally accepted answer is NOT semantically accepted or training gold.

Exact-source SQL inspection showed that the attested XML represents RUB as the name of the NMC field, preceding the numeric amount, rather than after it. The prior generic numeric guard only recognized money units after the number. Original contract contains 1 процента and 10 процентов as written Russian words (not the percent sign), plus 0,5% explicitly. The initial guard only recognized the percent sign and rejected even source-supported normalized wording.

Targeted source-format improvements recognize ONLY the explicit NMC RUB colon-labelled numeric source value and Russian written 'процента / процентов' as percent units when adjacent to an original number. They do not permit other arbitrary money, percentages, or inferred calculations. Added narrow false-absence check for actual NMC denial only when exact canonical labelled NMC source exists, rather than treating unrelated experience thresholds as NMC. **Replayed the previously model-accepted but false NMC absence statement against the real pinned XML chunk: now rejected for contradictory price absence.** Relevant broad test suite **930 PASS, 2 SKIP**, Ruff PASS; original 86/86/86 index untouched.

Third real read-only, no-training-gold Gemma probe of ONLY subject and contract terms now running on Mac mini PID 48543. Its new private receipt is retry3-result.json, leaving older result.json and retry2-result.json immutable. No full ten-section production re-evaluation until the two final source answers substantively pass and tests remain green.

## 20.10.2026 — targeted retry update
Third real Gemma focused source-only probe completed: subject PASS (87.84 s, one attempt, actual NMC 497178.33 RUB and two original XML chunk citations); contract_terms PASS (326.39 s, two attempts, 11 contract citations and original 0.5% execution security). Read-only, no training gold. Earlier first four-question probe PASS 2/4 (customer_requirements, evaluation_criteria), BUT these passes span different code revisions: not a same-run 4/4 result.
At 07:51:57 MSK launched a new same-version four-section read-only benchmark PID 85359 via allowlisted probe_final4, expected exclusive owner-private result final4-result.json and log final4-v2.log. An earlier invalid CLI argument attempt failed before contacting the model. All guards still active; source index unchanged 86/86/86. Regression on this revision: 972 passed, 4 skipped; Ruff and diff check pass. Do not start another probe while PID 85359 is active. Production DB history and gold are unchanged. Await result, check real facts and citations, only then consider a distinct new 10-section production version.

Additional same-code-version quality gate: scripts/procurement_llm/audit_gemma_four_same_version.py requires exact NMC 497178.33 RUB, criteria 30/70/80/20, security 0.5%, UUID citations present in original 4-section source manifest, and rejects false golden labels or other tender/model. Even four mechanical passes remain unreviewed, not legal human gold. Ten adversarial tests PASS. Final regression 987 pytest passed, 4 skipped, Ruff PASS.
