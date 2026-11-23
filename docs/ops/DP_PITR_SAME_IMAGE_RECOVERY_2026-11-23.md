# Восстановление проверки PITR Data Platform без перезагрузки PostgreSQL — 23.11.2026

**Связанная задача:** `TA-SIBUR-GEH-CLOSURE-20261123`. Система: Mac mini, действующий автономный индексатор СИБУРа, Data Platform / PostgreSQL 17 (`arvectum_data`) в контейнере `arvectum-postgres`. Производственный Tender Agent и его плановое обслуживание не изменялись.

## Проблема и причина

К 23 ноября 2026 года последний подтверждённый PITR restore receipt (22.11.2026, 12:18 UTC) стал старше максимального окна **25 часов**. Предзаписной guard честно отказал с `PITR acceptance missing or stale`. Отдельный периодический сервис `com.arvectum.dp-pitr-maintenance` пытался пересоздать подтверждение каждые 300 секунд, но завершался ошибкой:

`FileNotFoundError: /opt/homebrew/opt/postgresql@17/bin/pg_verifybackup`

Код обслуживания был привязан к удалённой версии Homebrew, хотя исходный PostgreSQL 17 уже находился в Docker и имел собственный `pg_verifybackup`. Последовательные неуспешные попытки оставили частичные каталоги base; **никакое автоматическое удаление или pruning не выполнялось**.

## Минимальное исправление

Исследовательская локальная ветка `feat/ta-pitr-gate-20261120` имела чистый HEAD `0971e57e226057c3e0f6d95f65ab88ebd67c2dd9`. В отдельном изолированном worktree был создан и проверен коммит `14e56ca2bc5ef79a1a6e2bee822b152142cbdc52`, после чего он fast-forward установлен в рабочий исходный каталог LaunchAgent:

`/Users/master/ArvectumSafe/worktrees/ta-pitr-gate-20261120`.

Затронуты **только три файла**:

- `scripts/research/verify_live_dp_basebackup.py`: функция `verify_backup(data, image)`, принимает исключительно идентификатор образа формата `sha256:<64 hex>` и реальный `ROOT/base-*/data` без символьных ссылок. Выполняет `docker run --rm --pull never --network none --entrypoint pg_verifybackup --mount type=bind,src=<path>,dst=/backup,readonly <exact-image> /backup` без интерпретации shell.
- `scripts/research/verify_live_dp_pitr.py`: использует ту же функцию для обязательной проверки исходного backup перед изолированным WAL replay.
- `tests/test_dp_pitr_guard.py`: проверяет pin образа, отсутствие сети и прав записи в mount, отказ на unpinned image, unsafe directory и symlink.

**Нет** отключения или остановки моделей, изменения конфигурации production PG17, установки и переключения Homebrew PostgreSQL, отключения проверки/подмены результата, удаления backup или снижения требований PITR.

## Точные доказательства

1. Перед установкой и после fast-forward: профильный pytest **13/13 PASS**, Ruff PASS, Python compile PASS.
2. Реальный прежний base подтвердил `backup successfully verified` из **точно совпадающего Docker image** `sha256:ac08538c6f8b9904c33c8224c5e5706dbe760aca29db1d096972b4052c22a75d` в контейнере `--network none`.
3. Старый запущенный periodic maintenance процесс был дождался завершения; переключён исходный каталог; штатный модуль `scripts.research.dp_pitr_maintenance` запущен один раз. Между процессами сохраняется существующий `maintenance.lock`.
4. **23.11.2026 13:36:54 UTC** создано свежее физическое backup:
   `.../data-platform-pitr/base-20261123T133546087769Z/data`.
   - Манифест SHA-256 `4cc1b44b70e1de30300556e9571b32ce903045cc6b46691c59d89983c55ad5c7`.
   - Изолированный same-image restore: `arvectum_data`, `pg_is_in_recovery=false`, system identifier `7692004809331994662`, `resources=18750`, `records=123`, `collections=74`.
   - Реальный named target `arvectum_pitr_check_20261123T133641212040Z`; LSN `B/F20000C8`; **2/2 проверенных WAL сегмента** и `exact_target_observed_in_server_log=true`.
   - Получатель WAL async, `lag_bytes=0`.
5. `/Users/master/ArvectumSafe/runtime/dp-pitr-maintenance/health.json`: `status=pass`, `daily_base_refreshed=true`; независимый read-only `python -m scripts.research.dp_pitr_guard --readiness` прошёл успешно.
6. СИБУР продолжил работать единственным PID, без обхода PITR и изменения лимитов ресурсоёмкости.

## Остаточные вопросы

- Локальный hotfix `14e56ca2` ещё **не перенесён в общедоступный upstream `main`**, поскольку сами модули `verify_live_dp_*.py` в этой исследовательской ветке не присутствуют в `main`; не публиковать весь неразобранный research branch автоматически. Код и тесты сохранены в локальном Git, recovery-ветке и активном worktree. При объединении research-source с основной веткой перенести этот трёхфайловый fix через обычный review.
- Проверить следующую штатную итерацию LaunchAgent, чтобы убедиться, что обновление защищает от повторения ошибки на следующем запуске.
- Не удалять без отдельного анализа прежние `base-...` каталоги, образовавшиеся из-за повторных ошибочных запусков: сначала сверить ссылки на backup и PITR proofs.
- Продолжить основной исходный индексатор СИБУРа до доказанного исчерпания `eligible` очереди; на 16:37 МСК индекс **7 183 / 7 790 (92,21%, 607 в текущем хвосте)**, Data Platform **9 352** docs, chunks=embeddings=107 377, `verified_pitr` PASS, rate ограничен `resource governor reduced: 3` ради памяти.

**Граница полномочий:** запланированное владельцем отключение всех LLM, рестарт PG17/PG18 и выпуск EIS parser пока НЕ запускались.
