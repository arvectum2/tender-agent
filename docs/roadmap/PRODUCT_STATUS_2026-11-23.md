# Tender Agent — полная продуктовая дорожная карта

Дата управленческой сверки: 23 ноября 2026 года, 22:30 МСК. Репозиторий: arvectum2/tender-agent. Этот документ — актуальный статусный слой к историческому MASTER_ROADMAP.md и master-roadmap.yaml, а не замена реестра задач, не расширение полномочий executor/watchdog и не юридическое разрешение на заявки.

## 1. Реально подтверждённый текущий срез

- Защищённая ветка GitHub main: **023d3670adcbf6d9ae8a318f4433615fa94b680c** от 23 ноября (PR #737). Проверено чтением удалённого Git и GitHub PR.
- ARC read-only, 23 ноября 22:30 МСК: backend 127.0.0.1:8001/health = **HTTP 200**, Data Platform 127.0.0.1:8094/health = **HTTP 200**.
- PR #737 https://github.com/arvectum2/tender-agent/pull/737 подтверждает live Python 3.15.2, Data Platform SDK 0.4.1, TA migration 128 / DP migration 0014, 15/15 read-only runtime checks OK на действующем при проверке релизе **e98bfe90…**. В DP отмечено 9 427 документов и 108 184 чанка. Для уже слитого позже **023d3670** отдельная exact-release аттестация не подтверждена.
- Кодовые PR #734/#735/#736/#737 интегрированы в main. PR #735 подтвердил 7055 PASS / 292 SKIP / 1 локальный R9 deselected, отдельно 6 R9 PASS на PG16, 9/9 durable E2E источниковых RAG попаданий на изолированных TA/DP PG17. Это **инженерные тесты**, не rolling production SLO.
- Исполнительная очередь после PR #702: **65 DONE, 0 READY, 1 BLOCKED REVIEW** из 66. Это только про ограниченный admitted executor scope и **не процент готовности всего Tender Agent**. Родительский TA-ROADMAP-EXEC-20261012 остаётся in_progress.
- Коммерческий публичный SaaS, платная подписка, внешние заявки, автоматическая подпись и платежи не активированы этой сверкой.

**Стадия продукта:** действующий внутренний procurement-intelligence контур, реализованный объёмный pilot foundation и незакрытые эксплуатационная, коммерческая и независимая приёмки. Не «только концепт» и ещё не «полноценный коммерческий релиз».

## 2. Основная продуктовая матрица — одиннадцать этапов APR

| Этап | Подтверждено | Осталось до закрытия | Статус |
|---|---|---|---|
| APR-01 — Быстрый анализ | Bounded source-cited workflow реализован и принят | Регрессии при обновлении runtime | DONE в утверждённых границах |
| APR-02 — 223-ФЗ | Original-source frozen corpus и ограниченная RI223/extraction приёмка | Не считать поддержкой всех процедур; точечная ревизионная полнота | DONE в утверждённых границах |
| APR-03 — Runtime | Внутренний Mac mini production, реальные миграции, backup/rollback, Python 3.15 / DP SDK в живом процессе | Аттестация exact deployed commit, надёжность ежедневного прогона, полноценный российский VPS/ingress, доказанные 7 суток PITR обеих production DB | PARTIAL |
| APR-03B — Operator Workspace | Существующий приватный workspace, цитаты, source history, отчёты, archived E2E | Текущая ревизия ЕИС и оригиналы #679, свежий end-to-end live quality, production approval | DEVELOPMENT ACCEPTED / LIVE OPEN |
| APR-04 — Onboarding | Company/profile gates и private isolated review; отдельные кандидаты #660 и #662 | Оригинальные документы и действительная квалификация ООО, совместимость черновиков, закрытая реальная бизнес-приёмка | PARTIAL |
| APR-05 — Pilot/SaaS | Tenant isolation primitives, role/entitlement, company-scoped web/mobile cases, manager inbox, bounded discovery, PRICE-01 integration | Staging 2-tenant E2E, права, реальная компания, physical-device acceptance, коммерческая упаковка/оплата/отдельный owner GO | PARTIAL, paid/public OFF |
| APR-06 — Коммерческая оценка | Archived source-backed DEVELOPMENT 20 кейсов / 96 приложений; источник-зависимое competitive qualification risk 70/30 как отдельное измерение | Independent human/legal gold и критерии допуска, актуальная реальная ситуация, подтверждённые референсы и фактическая полезность | DEVELOPMENT ONLY |
| APR-07 — Качество/observability | QA source/claim и замеры, rolling metrics инструмент, реальный TA↔DP E2E | Независимые precision/recall, проверка фактов свежего LLM, rolling production SLO; DP sync ingest p95 на измеренном срезе **21 635 мс при цели 10 000 мс — RED** | PARTIAL, SLO RED |
| APR-08 — Evidence Copilot | **Уже реализован и прошёл DEVELOPMENT acceptance**: первичные архивные XML/DP цитаты, проценты, условия обеспечения/оплаты, исторические выдержки 44/223-ФЗ, явные UNKNOWN, Chromium smoke, source re-attestation | Официальная актуальность права, live original corpus, production acceptance; автоматический legal GO запрещён | DEVELOPMENT ACCEPTED / PRODUCTION OPEN |
| APR-09 — Supplier RFQ/TKP | Supplier Engine, TKP/economics, readiness workspace и базовая коммерческая упаковка существуют | Реальные TKP; минимум 2 оплачиваемых пилота с повторяющимся запросом и отдельный scope | FOUNDATION / TRIGGER-GATED |
| APR-10 — Feedback и controlled learning | Provenance/benchmarks и механизмы фиксации опыта имеются | 30 подтверждённых исправлений минимум в 3 пилотных контекстах и отдельное допущенное обучение, не AI-silver as gold | DEFERRED / TRIGGER-GATED |

## 3. Сквозные функции, клиентские поверхности и параллельные направления

| Направление | Что есть сейчас | Что осталось |
|---|---|---|
| Daily Tender Run (DTR) | Поиск, фильтрация, dedupe, screening, загрузка разрешённых оригиналов, DP-анализ, digest, HUMAN GO/NO GO/DEFER, readiness и evidence-gated outcomes. DTR 1–3 merged. Пример 20 ноября: 17 MANAGER_READY, 22 DUPLICATE, 20 SCREENED_OUT, 3 FAILED | Свежий полный автономный прогон после release cutover; источник/тайм-аут и три original gaps #679; проверить launchd last exit 20 по журналу, не выдавать health 200 за успешный DTR |
| ARV-044 iPhone | MOB1–4 merged: native SwiftUI manager inbox/detail, человеческое подтверждение решения, портфель, APNs registration/deep link. Также есть company-scoped mobile primitives | Тест на физическом iPhone, реальный APNs delivery/provisioning, tenant end-to-end, отдельный release gate. Tender Agent не объявлен опубликованным App Store приложением |
| Company SaaS | Company portfolio, immutable human decision journal, tenant-aware roles, bounded saved-profile discovery, commercial source references, web + iOS projections, owner-controlled per-company schedule | Финальный staging/конфиденциальная реальная идентичность, rights and entitlements, стратегия глобального Deal→company cases, paid pilot и SLA |
| PRICE-01 / ARV-057 | Инженерно интегрирован PR #603; cost/tax/collateral и what-if расчёты | Reviewed signed contracts, comparable outcomes и живой калиброванный рекомендательный price model. Registry без подтверждённых договоров не выдаёт маркетную победную цену |
| 44/223 + B2B market discovery | Реальные источники, source SHA, Workspace/B2B-Center/EIS наблюдения и qualification exclusions | Свежие даты, подлинные приложения, допуск ООО и 15–20 **актуальных уникальных пригодных** IT-заказов — архивные карточки не заменяют этот критерий |
| SIBUR intelligence | Verified archive originals, source provenance, отдельный рабочий research PG16; 48 332 уникальных архивных ID, gap 18 251 по сравнению с рабочей базой, последующая проверка причины selection/import; исходный #692 CLOSED | Проверка dynamic source worker, исторической полноты и document-to-DP integration (#527 open), текущих 607 pending dynamic по checkpoint, точечная .ppt/.pptx аномалия #686; не массово переимпортировать без gate |
| ГЭХ / Мосэнерго / ЭТП ГПБ | Inventory основных источников, bounded public-source parser; checkpoint 23 ноября: 4 из 6 historical review reconciled/imported, 2 source anomalies quarantined | Полнота первичных закупок, contractor attribution, точная история и 24-месячная сверка, непрерывный source monitor |
| AI Trading | Public-source reuse inventory, малые электронные магазины, deterministic модель затрат и бумажные what-if | Verified SKU/supplier/availability, независимый backtest до реальной торговли; **PAPER ONLY**, никакой автономной ставки/платежа |
| Power Quality 6–35 кВ | Отдельная выборка и source provenance/coverage protocol | Первичные протоколы итогов и реально подписанные договоры, verified suppliers, project dedupe |
| ARV-069 competitive forecast | Детерминированная экономика уже есть, но 66-я задача queue остаётся BLOCKED REVIEW | Independently verified comparable outcomes, frozen benchmark outperforming baseline; отдельное одобрение forecast |

## 4. Критический путь, в порядке выполнения

1. **P0 — подтвердить эксплуатацию после 23 ноября.** Exact runtime SHA и 128/0014 миграции, current deployment verifier; настоящий fresh DTR, разбор последнего exit code по логам; DP sync/async SLI порознь, исправление измеренного SLO RED без отключения проверок.
2. **P0 — убрать недоказанные места в цепочке первоисточника.** Три original EIS/DOCX/ZIP gaps #679, date-only→actual-time parsing и источниковые ревизии. При UNKNOWN/FAILED — не отправлять дальше как DONE, не делать blind EIS retry.
3. **P0 — завершить recovery safety.** #685: историческая полная PITR непрерывность для **обеих** настоящих production DB. Ранее доказан ограниченный exact WAL restore, но не 7 суток; самый ранний известный physical base — 20 ноября, значит теоретический семидневный горизонт не ранее 27 ноября. Нужны целевой restore и полная WAL непрерывность. Ресурсный governor и взаимное влияние Qwen/DP/DB проверять отдельно.
4. **P0 — сквозной внутренний pilot APR03B/04/05.** Один существующий Operator Workspace, актуальный первоисточник, source cited DP/LLM, отчёт, handoff human decision, audit, две изолированные компании, web+iOS physical device. Никаких ETP внешних действий.
5. **P0 — независимое качество и ценность APR06/07.** Frozen benchmark не подменять auto-silver; human review фактов/документов/риск 70/30/денежные числа; precision, recall, false-positive, production SLO и прозрачные non-GO.
6. **P1 — полноценная разведка и customer discovery.** SIBUR/ГЭХ/EIS/B2B актуальные источники, подрядчик/объект, dedupe, research completeness, stable refresh; только доказательная корректировка отсутствующих записей.
7. **P1 — коммерческий pilot → коммерческий релиз.** Реальные клиенты, коммерческая ценность и повторное использование, customer isolation, опубликованные условия, поддержка, подтверждённое качество и экономика. VPS, paid SaaS и платежи — по отдельному owner decision.
8. **P2 — расширенные поставщики/предиктивное ценообразование/обучение.** APR09, ARV069, APR10 включаются исключительно после их триггеров; не начинать из-за «пустой очереди».

## 5. Definition of Done для коммерческого релиза

- Материальный вывод привязан к первичному документу/ревизии/фрагменту; отсутствие доказательства означает UNKNOWN и fail-closed, а не уверенный вывод.
- Один стабильный production release с проверенными DB/DP схемами, rollback, реальным свежим DTR, rolling SLO и полноценной защитой двух DB.
- Tenant isolation, entitlement и human audit проверены на staging и в разрешённых рабочих сценариях; мобильный клиент принят на физическом устройстве.
- Актуальные источники и независимый человеческий legal/commercial review подтверждают качество ключевых решений; не выдавать архивный DEVELOPMENT за production gold.
- Есть подтверждённый оплачиваемый пилот/клиентская ценность, согласованные договорные и эксплуатационные условия и явно разрешённый запуск.
- HUMAN GO/NO GO/DEFER остаётся атрибутированным; без отдельного разрешения нет автоматического ETP submit, подписи, заявок, закупок, сообщений поставщикам или платежей.

## 6. Обязательные ограничения и ссылки

Работа ведётся ARC-only; второй watchdog не создавать. Не менять baseline/historical registry, admitted queue, operator credentials, production DB и права внешних действий через обновление roadmap. Сведения из живого GitHub источника и точечного ARC health проба отделяются от исторических checkpoint и development tests.

Источники: [сверка 22.11](TA_ROADMAP_STATUS_RECONCILIATION_20261122.md), [закрытие queue и исключения](TA_SOURCE_EXECUTION_QUEUE_COMPLETION_20261122.md), [postmerge blockers](TA_POSTMERGE_CHECKPOINT_TRUTH_20261122.md), [APR08 development gate](../acceptance/APR08_INTEGRATED_DEVELOPMENT_ACCEPTANCE_2026-11-17.md), [prod rollout 21.11](../operations/TA_PROD_ROLLOUT_REHEARSAL_20261121.md), [issue #679](https://github.com/arvectum2/tender-agent/issues/679), [issue #685](https://github.com/arvectum2/tender-agent/issues/685), [issue #686](https://github.com/arvectum2/tender-agent/issues/686), [PR #737](https://github.com/arvectum2/tender-agent/pull/737).
