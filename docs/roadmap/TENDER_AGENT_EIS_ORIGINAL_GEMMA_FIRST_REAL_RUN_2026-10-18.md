# Tender Agent — официальный комплект ЕИС → Data Platform → первая настоящая Gemma

**ООО «Арвектум» · 18.10.2026 · TA-EIS-SOURCE-BOUND-GEMMA-20261018.**

## Какая модель действительно является основным quality-профилем

Непосредственная live-проверка Mac mini (не вывод из списка `ollama list`):

- Действует **`/opt/homebrew/bin/llama-server`** из llama.cpp, PID 53560, запуск GGUF `gemma4-12b-qat-q4.gguf` из ArvectumSSD runtime, сервер **`127.0.0.1:8081`**.
- `GET http://127.0.0.1:8081/v1/models` HTTP200, OpenAI-compatible model ID **`arvectum-gemma4-12b-it-qat-q4_0`**. Конфигурация llama.cpp: ctx 32768, одна параллельная сессия, GPU offload.
- **Ollama отдельный процесс** PID 56617, порт 11434, Gemma через него тоже доступна, однако ранее выбранный и сейчас работающий **основной Gemma quality backend — llama.cpp:8081, не Ollama и не Qwen3:4b**. Другой llama.cpp на Mac mini обслуживает Qwen3-Embedding-4B, это *эмбеддинги*, а не генеративная Gemma.
- В `analysis_queue_worker.py` новые CLI default `QUALITY_GEMMA_LLAMA_BASE_URL=http://127.0.0.1:8081/v1` и `QUALITY_GEMMA_LLAMA_MODEL=arvectum-gemma4-12b-it-qat-q4_0`. Не меняли запущенный сервер, глобальные настройки backend, другую production LLM или порт 8088. Шестичасовой ещё НЕ установленный раннер указывает на это качество по умолчанию; возможные локальные overrides остаются opt-in.

## Привязка первого официального оригинала к полным документам

Пилот строго по сохранённой ранее архивной версии ЕИС Смоленской областной Думы **0163200000326005243**, `epNotificationEOK2020`, **version 2**.

- Существующий privately stored официальный SOAP ZIP **SHA256 `4cec297f6bd040723105fab5ac03a3d10e986b3c03b03032a7da3c3769389d5d`**; выбранный XML **SHA256 `36556189a1bb0aeead937e06e9c4186206a465ba139fc09023b4c1d08e7cb719`**. Источник `candidate_unreviewed`, **это архивная версия**, не live legality/подписанный документ/текущая площадка.
- Новый `scripts/procurement_llm/prepare_eis_original_documents.py` сначала повторно сверяет original ZIP owner path/SHA/mode0600, версию, тип и XML SHA; извлекает реальные файлы из XML `extract_notice_attachments`. URL только строго разрешённого `zakupki.gov.ru/44fz/filestore/public/1.0/download/priz/file.html`; signed query никогда не пишется в SQL, PR, receipt или stdout; в манифесте только SHA URL.
- В реальном **dry-run 6/6** оригинальных приложений были загружены и верифицированы по magic/sha без DB/SSD изменений. После полного `pg_dump -Fc`, SHA **`ae094d4dc03cea97f82870481da25cd5f8351fe9577c0bc7405d9462589e33a7`**, `pg_restore --list` PASS — реально сохранены **6 файлов и immutable source-manifest** под `/Volumes/ArvectumSSD/Arvectum/private/tender-agent/eis-source-documents/<номер>/<sha>/` mode 0600. Импорт TenderResearch `procurement_tenders` 20→21; зарегистрировано 6 оригиналов (5 DOCX готовы к Data Platform, один ZIP оставлен opaque, не выдаётся за прочитанный/проиндексированный документ). `training_status` source не повышен.
- Новый независимый read-only `verify_registered_exact_source_set` заново проверяет оригинальный ZIP/XML/версию, **все 6 точных URL SHA из XML**, значения имен, локальные SHA оригиналов, манифест и совпадающие строки `procurement_tender_documents`, а также строгий `owner_attested_original_archive_sha256` в tender.raw_payload. Смена или подмена файла приводит к BLOCKED. Команда `--index-only` делает offline preflight, с отдельным `--apply --confirm-database arvectum` переиспользует **существующий** `prepare_tender_for_analysis` и Data Platform.
- Data Platform auth: существующий внутренний ключ из защищённого `~/.config/arvectum/apr04-local.env` mode0600; новые секреты не выдавались и в Git/логи не попадали. До этого без ключа API возвращал HTTP401; с существующим ключом нормальный статус отсутствующей тестовой коллекции HTTP404. Mount/ёмкость проверены `ARVECTUM_STORAGE_ROOT=/Volumes/ArvectumSSD/Arvectum`, состояние normal, gate PASS.
- Отдельный полный `pg_dump` перед документальной индексацией: SHA256 **`5ac55cd76c8f45c8720a49011b7ffbce3b6888ab4b3de3348f20f099bf836698`**. `prepare_tender_for_analysis` реально завершился `completed/ready_for_analysis=true` **без предупреждений/ошибок**: 5 DOCX extracted, **72 chunks, 72 embeddings** Data Platform. Рестарт backend или замена модели не потребовались.

## Первый настоящий source-bound Gemma run

После read-only проверки `work_cycle(probe_services=True)`: **1/10 готова** по полным оригиналам/индексу и реально доступной Gemma llama.cpp; оставшиеся 9 не готовы. Перед запуском полный `pg_dump` custom с проверенным каталогом SHA256 **`a5f9b90df2beb240ba1f264e7068eb9aa521910550454e444f92d70516e0684a`**.

**Результат реальной работы `analyze_tender` на Gemma 4 12B**, ~251 сек:

- Новый настоящий `tender_analysis_runs.id = ee8b1140-1cc6-46ef-b1db-661931fac69a`; `status=completed`, `used_llm=true`, `llm_model=arvectum-gemma4-12b-it-qat-q4_0`, `source=source_queue`, **10 разделов, 19 уникальных цитируемых источников**.
- Отдельный source-SHA-bound completion metadata candidate `manual:ta-ready-analysis:...` с реальным run ID + SHA оригинального ZIP и реального отчёта. Отчёт существует mode0600, SHA повторно вычислен и сверён с записью. Проверка `completed_source_versions` из базы после перезапуска уверенно распознаёт **1 завершённую версию**, очередь 10→**9**.
- Existing canonical DB: `procurement_learning_observations` **119→121** (+1 source-neutral аналитический run candidate и +1 completion link), `tender_analysis_runs` **45→46**, 0 human-gold, 0 legal BID_GO. Новые source files не считывались из другого тендера.
- **Не проводились** внешний ChatGPT dual-eval (ожидает техническую приёмку), автоматическое обучение весов Procurement LLM, запуск заявок/ЭТП/подписей, исходящие сообщения, релиз/слияние main, включение launchd. Никакого false claim на текущий статус ЕИС.

## Воспроизводимость и границы

Скрипт prep supports dry-run (network source checks without writes), apply (private binary + SQL после backup), `--index-only` offline exact-origin verification и отдельное guarded `--apply` для вызова уже имеющейся Data Platform preparation; final worker default Gemma via llama.cpp.

Регулярный запуск всех этапов требует ревью stacked PR и approval AM-4. Следующие этапы: подготовить оригиналы двух оставшихся ЕИС тендеров (НГТУ, ГИС МО), полностью обрабатывать ZIP вложения отдельно в source-bound режиме, добавлять легальные/коммерческие gating criteria, и лишь после приёмки — независимые dual-eval и human adjudication.
