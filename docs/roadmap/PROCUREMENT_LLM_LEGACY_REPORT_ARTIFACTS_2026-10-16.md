# Arvectum Procurement LLM — два исторических отчёта без run ID

**16.10.2026.** Статус: два подтверждённых SHA-256 оригинала занесены как *неразмеченные артефакты* в **существующий** PostgreSQL `arvectum` (Alembic 107). Новая БД, отдельный датасет, экспорт текста и обучение модели **не создавались**.

## Что именно зарегистрировано

| Файл в каноническом ArvectumSSD `data/rag/reports` | Размер | SHA-256 |
| --- | ---: | --- |
| `analyze_tender_0323100010326000013_20260705T195400298896Z_09d21c02.md` | 168 443 байта | `a8285a58b68f2fda893312efbd81069a1fb174f79986195c4efd4011bfb03774` |
| `analyze_tender_0323100010326000013_20260705T195559914662Z_acbcfb55.md` | 88 832 байта | `b66ffb4fd4cb57a2a5224583f72fe89bc6ec865792fafdcd5df483ab6c5d8f38` |

Источник копии — `MacBook-Air-Nikita.local:/Users/master/Documents/AI-Corporation-live/data/rag/reports`; исходники не удалялись, копии на Mac mini созданы *в уже существующем* `Arvectum/data/rag/reports`. SHA-256 источника и канонической копии побайтно совпали.

Это **два дополнительных файла**, имена которых НЕ соответствуют 20 отсутствующим историческим путям в PostgreSQL. Следовательно, **22 прежних строки `report_path` всё ещё с отсутствующими полными файлами**, хотя все сохраняют короткий текстовый `report_markdown_preview`.

## Как фиксируем, не выдумывая прошлую историю

Добавлен ограниченный append-only тип `legacy_report_artifact`. Он записывает в `procurement_learning_observations` только путь, полный SHA-256, размер, реестровый номер из строго заданного имени и `historical_saved_run_id: null`. Статусы: `participation=unknown`, `review_state=system_recorded`, `training_status=candidate_unreviewed`, `visibility_scope=owner_internal`. Исходный Markdown, сторонние документы, личные данные, «правильные» ответы и пользовательские чаты **не копируются в БД**.

Импорт проверяет, что файл лежит непосредственно в текущем каноническом каталоге, является обычным файлом (не symlink), имеет допустимое имя/размер и точно соответствует переданному SHA-256. Без `--apply --confirm-database arvectum` только dry-run; идентичный повтор не создаёт запись. Нельзя использовать этот тип для приписывания исторического `run.id`, создания human gold или имитации подачи заявки.

Команда оператора на Mac mini для одного файла:

```bash
python -m scripts.procurement_llm.import_candidates \
  --legacy-report-file /Volumes/ArvectumSSD/Arvectum/data/rag/reports/analyze_tender_0123456789012345678_20260705T195400298896Z_12345678.md \
  --expected-report-sha256 SHA256_FROM_A_VERIFIED_ORIGINAL_RECEIPT
```

Оператор, убедившийся в корректной настроенной **существующей** PostgreSQL, добавляет `--apply --confirm-database arvectum`. Команда доступна также для двух файлов за один атомарный запуск.

## Фактическая контрольная сверка

| Kind | До | После |
| --- | ---: | ---: |
| `analysis_run` | 45 | 45 |
| `development_e2e` | 20 | 20 |
| `manual_review` | 10 | 10 |
| `legacy_report_artifact` | 0 | 2 |
| **Итого** | **75** | **77** |

- Первая запись: `candidates=2, inserted=2, existing=0`. Повтор: `inserted=0, existing=2`.
- Read-only аудит `python -m scripts.procurement_llm.audit_corpus --expect-total 77`: 77 уникальных ID, 2 SHA-verified unlinked legacy артефакта, 45/45 старых run ID на месте, 20/20 DEV source SHA + metrics SHA, 10 manual (только 1 индивидуальный SHA-bound primary receipt), 0 protected blind / gold / train-ready, 22 missing full report rows сохраняются.
- Запись Калужского итогового протокола `0137200001226007700` остаётся **отдельным непроведённым source-bound manual event** в приватной очереди (dry-run успешен). Она не входит в 77 и не имеет независимо доказанного owner attribution.

**Открытый этап:** установить настоящие исходные run ID двух новых файлов, если сохранились старые execution receipts; восстановить либо признать утраченными 22 другие полные отчёта; получить юридические подтверждения участия в трёх остальных ручных кейсах и принадлежности заявки Калуги. Без этого ничего не переводить в train-ready, а обучение самой модели не начинать.
