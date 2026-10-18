# Единый конвейер обнаружения и фиксации закупок Tender Agent

**ООО «Арвектум» · 18 октября 2026 · TA-UNIFIED-SOURCE-PIPELINE-20261018.** Код создан в независимом ArvectumSSD worktree; действующий Operator Workspace 18082 и main не менялись. Canonical PostgreSQL — **только** действующая база arvectum, таблица procurement_learning_observations (Alembic 107).

## Реальные этапы конвейера

1. **Обнаружение.** Ограниченный RSS Workspace (публичный https://workspace.ru/tenders/rss/), три индексные категории B2B-Center и *независимый публичный поиск ЕИС 44-ФЗ* через уже имеющийся RegistryNumberDiscovery/external_public_44fz. Старый SOAP searchProcurements действительно ошибается и НЕ используется. ЕИС поиск выборочный, 3 дня/до 30 публичных карточек; IT-title heuristic, никогда не является юридическим заключением или источником gold. Не подставляем demo/seed при ошибке. 223-ФЗ и полное покрытие ЕИС пока не заявлены.
2. **Балансировка.** Лимит максимум 5 новых коммерческих карточек +1 ранее известная на цикл. Round-robin между Workspace и B2B-Center предотвращает вытеснение второго провайдера большой RSS. Из публичного ЕИС максимум 2 новых подходящих по заголовку номера/цикл +3 закреплённых архивных номера. Внешних действий на ЭТП, оплаты и отправки заявок нет.
3. **Подтверждение оригинала.** Повторно используем ранее созданные Workspace/B2B exact URL, canonical/og:title/HTTP200, и ЕИС SOAP getDocsIP + проверку XML purchaseNumber/версии/ZIP SHA. При отказе внешнего источника запись ошибки явно видна; цикл не объявляется полностью успешным. Никакой оригинал не получает автоматический BID_GO.
4. **Надёжность.** Каноническая SQL дедупликация по SHA/ID. Приватные исходные HTML/ZIP под ArvectumSSD с mode 0600, только source/provenance metadata в PostgreSQL; один предварительный **полный pg_dump -Fc + проверка каталога и SHA** до любого --apply цикла; single-runner fcntl lock; отдельный приватный JSON receipt mode 0600. Сбой источника фиксируется, а уже безопасно записанные наблюдения не теряются. Повтор той же версии idempotent, новая версия append-only, человеческий gold не создаётся.
5. **Очередь анализа.** Восстанавливается из существующих source observations и записей analysis_run той же PostgreSQL; не создаём вторую БД или неисполняемый fake LLM-run. В receipts явно pending_actual_tender_agent_analysis. Она пока **очередь**, а не фактически исполняющий AI worker; пост-приёмочные независимые ChatGPT/Tender Agent прогоны запускать преждевременно.
6. **Предстоящий регулярный запуск.** Подготовлены scripts/runtime/run_source_intake.sh и com.arvectum.source-intake.plist.template: Mac mini launchd каждые 21600 секунд (6 часов), RunAtLoad=false, KeepAlive=false. Без явного TENDER_SOURCE_INTAKE_APPLY=1 сценарий безопасен как dry-run. **Plist не установлен и не загружен**: до reviewer-approved merge/release производственный scheduler и новый runtime НЕ активны. Это не вторая ChatGPT Scheduled Task и не копия Tender Agent Watchdog.

## Выполненные реальные проверки и DB-состояние

- Оригинальная перед началом этапа PostgreSQL — **113** observations; предыдущие 31 исторические research entries и 5 ZIP/marketplace additions НЕ импортировали заново.
- Первый реальный read-only прогон: 4 каталога HTTP200, девять точных первоисточников оригинала проверены без ошибок.
- Первый реальный apply с разрешённым Owner обязательным сохранением: **5 свежих source refs + 1 новая версия ранее записанного Workspace 19043** (6 source observation rows, а не 6 новых закупок), 3 pinned ЕИС оригинала дедуплицированы (0 новых). Source ref примеры: Workspace 19052, 19044, 19042 и 19043 (новая версия), B2B-Center 4643484 и 4632699.
- До apply автоматически создан полный архив старой БД, режим 0600, SHA256 **bed6cd2987b248b50f3e0ac80c3e494e49d677195fde956f5e7288d465932801**, 2 109 508 байт, успешная проверка pg_restore catalogue, без восстановления live БД.
- SQL **113 → 119**, 6 новых unreviewed source versions, первоисточники на SSD; 10 источников стоят в очереди **реального** анализа, 0 BID_GO, 0 human/model gold. Отдельный private receipt создан. После записи отдельный аудит проверил SHA/0600 всех **11** первоисточников (8 marketplace versions +3 EIS ZIP) и что все они owner_internal/candidate_unreviewed.
- После подключения реального публичного 44-ФЗ EIS discovery был новый dry-run: 4 каталога OK, 6 выборочных публичных ЕИС карточек, **0 подтверждённых IT-title новых номеров**. Один getDocsIP вызов НГТУ временно завершился RuntimeError; dry-run честно вернул exit=2 и ноль DB writes. Отдельный безопасный повтор getDocsIP для НГТУ после этого прошёл (20 736 байт ZIP), SQL осталась 119. Пропуски не скрываются.
- 36 targeted tests PASS (балансировка, original-source gates, EIS source sampling, fail-closed, queue, redacted receipt, backup/lock/cadence), расширенная регрессия **847 PASS / 4 SKIP** до финального добавления 1 static launchd test; Ruff PASS, bash -n PASS, plutil -lint PASS. Финальный расширенный запуск повторяется на последней версии.

## Открытые пункты

- [ ] AM-4 review, stacked PR exact-head CI и авторизованное развёртывание с включением launchd. Пока feature branch НЕ исполняется автоматически.
- [ ] Поставить настоящий job/worker анализа Tender Agent на сформированную очередь и сохранить реальный output/LLM provenance в той же БД; лимиты, права и доступ к ТЗ определить отдельно.
- [ ] Расширить ЕИС discovery за пределы 44-ФЗ sampled страницы (включая 223-ФЗ), улучшить семантический IT eligibility gate и исключить частные/нерелевантные коммерческие карточки *до* назначения приоритета, но не переписывать исходные receipts.
- [ ] После фактической технической приёмки запускать два независимых реальных анализа ChatGPT и Tender Agent по одинаковому SHA-манифесту, сравнить расхождения, пройти человеческую adjudication, лишь затем тренировать Procurement LLM.
- [ ] Непрерывное гарантированное сохранение произвольных ChatGPT чатов невозможно без отдельного поддерживаемого внешнего триггера. Сейчас защищённый explicit external-analysis importer готов (PR491), но не является auto-subscribe ко всем чатам.

**Безопасность:** нет второй БД, подписи, платной отправки, корпоративного BID_GO, ложных обучения/gold, production деплоя, изменения Operator Workspace или включённого scheduler.
