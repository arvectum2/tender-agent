# Market Intelligence — отраслевые исследования на базе закупок

Контракт автономного исследования для Tender Agent. Эталонный пример — рынок Power Quality России (6–35 кВ). Реализация протокола должна начинаться по одному исходному исследовательскому заданию, продолжаться после прерывания и завершаться проверенным отчётом или отчётом с явно перечисленными ограничениями.

## Канонические материалы
- [AUTONOMOUS_RESEARCH_PROTOCOL.md](AUTONOMOUS_RESEARCH_PROTOCOL.md) — методология и state machine S0–S11 с self-audit, охватом рынка и моделью прав.
- [PQ_CASEBOOK_20261027.md](PQ_CASEBOOK_20261027.md) — фактические аналитические решения, недоступные источники и контрпримеры по PQ; это материал для разметки, не эталонный корпус «проверенных победителей».
- [RESEARCH_EVENT_SCHEMA.json](RESEARCH_EVENT_SCHEMA.json) — машиночитаемый контракт для append-only исследовательских событий.
- [PQ_TRAINING_CANDIDATES.jsonl](PQ_TRAINING_CANDIDATES.jsonl) — учебные НЕ-gold примеры с `training_eligible=false`.

## Правило для каждого следующего исследования
1. Сохранить `ResearchBrief`, конфигурацию поисковых волн и снимок версии источников.
2. Записывать после КАЖДОГО источника и решения append-only `research_events.jsonl`: включая неудачный запрос, отклонённый false-positive, пересмотр классификации, источник суммы и dedup merge/split.
3. Архивировать первичные документы с SHA и указателями на страницы/поля. Формировать `training_candidates.jsonl` лишь из воспроизводимых входов и цитат.
4. Никакие `training_eligible=true` без независимой экспертной проверки, проверки прав на использование и отсутствия утечки данных.
5. Перед финальным отчётом применить gates S10; отчёт без заполненного evidence/coverage считается черновиком.
6. Не смешивать ownership: Data Platform — общие acquisition/extraction/index, Tender Agent — закупочная семантика и аналитика, Procurement LLM — обучаемый классификатор.

## Реальный статус
В репозитории есть частичный source-bounded S0–S11 оркестратор, сохранение evidence и offline отчёт. Полный воспроизводимый E2E с подтверждёнными исходными договорами по всему рынку и validated training gold **ещё не принят**. Дальнейшие этапы и инструкция продолжения: `/.agent/checkpoints/TA-MI-AUTONOMY-20261027.yaml`. Не заменять и не перезаписывать активный unrelated `/.agent/current-task.yaml`.

- [SPECKIT_CHATGPT_ARC.md](SPECKIT_CHATGPT_ARC.md) — Spec Kit `none` + AES-001 для текущего ChatGPT → ARC процесса; [спецификация PQ](../../../specs/001-power-quality-evidence-closure/spec.md), [план](../../../specs/001-power-quality-evidence-closure/plan.md), [проверяемые задачи](../../../specs/001-power-quality-evidence-closure/tasks.md).

## Единый активный поток

[Сверка веток и процесс исследования профиля поставщика](../../market_intelligence/SINGLE_LANE_RESEARCH_RUNBOOK.md). Канонический исследовательский PR #521, checkpoint TA-MI-AUTONOMY-20261027. FGI — проверяемый пример, а не hardcoded производитель.
