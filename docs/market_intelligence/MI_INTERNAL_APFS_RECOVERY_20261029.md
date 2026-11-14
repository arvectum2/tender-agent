# Tender Agent Market Intelligence — восстановление записи на Mac mini (29.10.2026)

## Что произошло

Внешний том `/Volumes/ArvectumSSD` (APFS, USB, `disk7s1`) монтируется как доступный на чтение и запись, свободно **~2,8 ТиБ**. Однако операции `os.listdir`, `pwd`, `git` и иногда `cp` из рабочего дерева на нём завершались `Interrupted system call` или `SIGKILL`, даже через независимый маршрут MacBook Air → SSH → Mac mini. Журналы macOS содержат повторяющиеся отказы `SystemPolicyRemovableVolumes` для процессов, обращавшихся к `ArvectumSSD/Arvectum/relocated-home/.../logs`. Причинная связь с отказом `getcwd` не доказана: повреждение APFS **не установлено**; `diskutil verifyVolume` из SSH был заблокирован политикой macOS. Нельзя без подтверждения стирать, отмонтировать, перенастраивать TCC или чинить том.

## Стабильный контур для текущего исследования

| Назначение | Внутренний APFS на Mac mini |
|---|---|
| Git checkout единственного PR #521 | `/Users/master/ArvectumSafe/worktrees/tender-agent-mi` |
| Python 3.14 + зависимости проекта | `/Users/master/ArvectumSafe/.venvs/tender-agent-mi` |
| Исходные HTML/PDF/DOCX, SHA-256 и квитанции | `/Users/master/ArvectumSafe/runtime/market-intelligence/pq-agent-pilot-live` |
| Полные резервные копии PostgreSQL | `/Users/master/ArvectumSafe/backups/data-platform` |
| Данные базы | прежняя **`arvectum_data`** в Docker (`arvectum-postgres`), коллекция `arvectum-market-pq-6-35kv` |

Использовать прямой ARC на Mac mini, только когда он стабилен. Если `run_command` выдаёт тайм-аут, использовать разрешённый ARC `device_execute(device="macbook-air")` и пакетный SSH `ssh -o BatchMode=yes Mac-mini-master.local '<команда>'`. Маршрут проверен. Старое рабочее дерево внешнего SSD, его исходники и незакоммиченные файлы **не удалять**; не делать конфликтующих `git push --force`.

## Команды приёмки и записи

Запускать из внутреннего клона:

```bash
cd /Users/master/ArvectumSafe/worktrees/tender-agent-mi
PY=/Users/master/ArvectumSafe/.venvs/tender-agent-mi/bin/python

# Обязательный preflight перед записью: чистый Git, scandir,
# atomic write+fsync+rename, SHA источника и полного backup, PostgreSQL readback.
"$PY" -m scripts.market_intelligence.verify_internal_runtime

# Перед каждым разрешённым новым импортом: полный pg_dump custom,
# проверенный PostgreSQL pg_restore --list, SHA manifest в том же каталоге.
"$PY" -m scripts.market_intelligence.backup_pq_postgres

# Снимок с официальной публичной ЭТП; каждый раз новый путь, старые не теряются.
"$PY" -m scripts.market_intelligence.capture_primary_source \
  --case-id 223fz:32616065155:lot7 \
  --url 'https://www.b2b-center.ru/market/postavka-elektrotekhnicheskogo-oborudovaniia-vykliuchateli/tender-4469608/?action=positions'

# Для live KPI: только чтение БД.
"$PY" -m scripts.market_intelligence.pq_corpus_kpis
```

Основной импортёр `scripts/market_intelligence/append_pq_delta_20261029.py` предпочитает внутренний runtime (если каталог существует), но допускает явное `ARVECTUM_MI_RUNTIME_ROOT`. Для **новых**, уникальных закупок нужны: первичный источник с проверенными байтами/SHA, строгий canonical `procedure:lot`, fresh backup, защита от существующего ключа и от изменения общего количества, атомарная транзакция и readback `dp_resources/dp_records`. Не импортировать повторно уже добавленный `223fz:32616065155:lot7`.

## Доказанная приёмка

- Внутренний Git-клон клонирован из `arvectum2/tender-agent`, единственная ветка PR #521, fast-forward и чистый working tree.
- Окружение Python 3.14 установлено из `pyproject.toml`; выборочные тесты безопасности импорта прошли.
- Полная резервная копия `arvectum_data`: **37 487 137 байт**, SHA-256 `b97ea3900b7a875ab4a3f214b24aa19ffd26c2a95fec438e7d951f6364644502`, проверено через `pg_restore --list`. Манфест и архив на внутреннем диске; этот `pg_dump` не менял базу.
- Новый неизменяемый снимок исходной страницы B2B-Center Tatneft №4469608 (лот №7): **67 396 байт**, SHA-256 `162fdca84e601e93a4038ff08bac29f28147ebbb7d11be54d6777d94a3c8dbb4`; сохранён отдельным новым байтовым оригиналом и квитанцией, а не поверх архивного. У динамической HTML-страницы новый SHA может отличаться от предыдущего захвата — это не ошибка.
- Скрипт `verify_internal_runtime` дал `status: pass`: `scandir`, запись, `fsync`, `rename`, обратное чтение, SHA backup и source, live PostgreSQL.
- Контрольный счётчик на момент приёмки: **109 уникальных лотов**, **98 идентификаторов процедур**, **37 различных извещений ЕИС 223-ФЗ**; 109 — корпус кандидатных закупок, не рынок выполненных продаж.

## Принципы

Никакой принудительной переписи старых ключей, `git push --force`, переноса секретов в Git и присвоения агрегированной НМЦ рынку 6–35 кВ. Контур защищает запись источников и БД; статус приватных SDK и старого внешнего диска отслеживается отдельно. Автоматизации разрешается менять только исследовательскую коллекцию, с подтверждёнными первичными источниками и резервной копией. Единственный Watchdog продолжает работу по расписанию, новый не создаётся.

**Оставшийся инфраструктурный вопрос:** при необходимости вернуть разработку на внешний SSD официальным способом проверить права доступа macOS к съёмному тому для соответствующих процессов (Settings → Privacy & Security → Files & Folders / Full Disk Access) и запустить Disk Utility First Aid в разрешённом контексте. До этого не использовать внешний SSD как активное рабочее дерево.
