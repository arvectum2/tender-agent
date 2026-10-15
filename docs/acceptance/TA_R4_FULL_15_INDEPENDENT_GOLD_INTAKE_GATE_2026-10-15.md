# R4 — транзакционная приёмка независимого юридического gold всей когорты

**15 октября 2026.** Слепая выборка 3+4+4+4, всего **15 конкурентных закупок 44-ФЗ** и **73 официальных бинарных первоисточника**. Все материалы на ArvectumSSD, независимые исходные SHA зафиксированы в опубликованном source-only audit. **Ни один экспертный ответ не поступил и не создан программно.**

## Что сделано

Создан приватный пустой манифест full15-independent-gold-intake-BLANK-private.json: 15 пар case_id → lock index, конкретные source-only evaluator bundle и исходные бинарные документы для каждого кейса, поле signed_submission_path=null. Он автоматически построен из четырёх неподменённых source-lock и всех 15 исходных evaluator-пакетов; для каждого ещё раз сверены SHA оригиналов и case manifest. Ведомость хранится только на ArvectumSSD; в Git добавляется лишь агрегированная квитанция с SHA: data/TA_R4_FULL_15_INDEPENDENT_GOLD_INTAKE_GATE_2026-10-15.json.

Для будущих реальных подписанных экспертом JSON добавлена CLI scripts/acceptance/freeze_r4_independent_human_cohort.py. Отдельная существующая freeze_r4_independent_human_gold.py уже проверяет источник, локатор, дословную цитату, Ed25519-подпись и предварительно проверенный владельцем ключ для одного случая. Новый CLI не заменяет юридическую проверку; он объединяет её в механизм «все 15 или ничего».

1. **До чтения внешних ответов** сверяются четыре неизменяемых source-lock с опубликованными SHA в Git, все 15 номеров и размеры групп, отсутствие пропущенных или дублирующихся кейсов, индекс каждого lock.
2. Для каждого из 15 подписанных человеком входов вызывается исходная схема проверки benchmark_pipeline и доверенного reviewer roster, включая источник и криптографическую подпись. Вся проверка проходит в памяти до первой записи gold.
3. **Только после успешной проверки всех 15** строится суммарная SHA-ведомость экспертных меток; SHA непосредственно перед сохранением повторно проверяются. Все 15 файловых троек (blind_discovery_label, blind_document_truth, frozen_label) сначала пишутся в один приватный временный каталог, который публикуется единым переименованием. Прежняя папка не перезаписывается.
4. Пустая ведомость, отсутствующая подпись, неверная привязка к источнику, изменённая цитата, случай вне слепого набора или сбой записи на середине означают **отказ без частичного результата**. На реальной пустой ведомости приёмка проверенно отказала, ничего не создав. Подписи и юридические ответы в тестах исключительно искусственные; тестовая генерация никогда не применяется к реальной blind-выборке.

## Что остаётся внешней зависимостью

Владелец отдельно подтверждает личность, квалификацию и независимость эксперта и принадлежность Ed25519-публичного ключа; это невозможно установить по одному JSON с owner_identity_verified=true. Эксперт независимо изучает официальные документы и заполняет 15 source-anchored подписанных ответов, не видя вывода Tender Agent. Только после действительной приёмки и заморозки всех 15 независимых ответов можно **отдельно принимать решение** о запуске оценки. Новый CLI сам не выдаёт разрешение на SUT, не подписывает документы, не присваивает legal GO, не делает bid_ready.

**Фактический статус:** human gold 0/15, проверенный внешний key roster отсутствует, замороженных реальных меток нет, SUT на blind-сборке не запускался, precision/recall NOT_MEASURED, bid_ready=false. PR #432 остаётся draft.

Формальное соответствие SHA гарантирует лишь неизменность и происхождение источников при доверенном внешнем ключе; правовая истинность ответов требует отдельной квалифицированной оценки.

## Финальная техническая проверка

Релевантные source-only/private приемочные тесты: **17 пройдены**, включая реальную пустую ведомость 15 EIS-кейсов и искусственные Ed25519-подписи только в тестовой среде. Полный pytest на ArvectumSSD: **4 316 passed, 242 skipped, 0 failed**, 329 прежних warnings, **153.97 секунды**. Ruff — PASS. Полный журнал хранится приватно на SSD; SHA-256 журнала: 53af6c13514955a793da10dfe1a5a5573f3784f1649d7266edf8b69626d07984.


## Signed original provenance retained for later independent re-verification

After *all* signed reviewer answers have passed the original Ed25519 and first-party EIS source checks, each case's original signed JSON is saved **privately** as independent-human-signed-submission.json next to discovery, document truth and the frozen label. The SHA-256 of the entire signed answer is included in the cohort's sealed per-case ledger and cumulative checksum. The writer re-checks the signed source against the already verified snapshot, including the signature, before publishing the staged directory. A modified signature or quote after preflight rejects the entire cohort; interrupted writes do not leave partial gold.

This creates a verifiable audit trail for future re-checks using the owner's independently vetted reviewer public key. It does NOT certify the reviewer's qualifications or permit SUT evaluation, bid submission or Owner GO. No real reviewer answers have been received: signed gold 0/15, precision/recall NOT_MEASURED, bid_ready=false. No signed answers are uploaded to Git.

### Final source-provenance regression

Full local ArvectumSSD pytest after signed-original retention: **4,317 passed, 242 skipped, 0 failed; 329 pre-existing warnings; 167.91 seconds**. Ruff clean. A private, byte-for-byte QA log is kept on ArvectumSSD with SHA-256 6d3a686159bafbcba09325f0f0f7cd47fbd4d94812e27f64b4b920e7f0c04543. External legal-reviewer gold remains **0/15**. Signed originals only persist privately after the full validated 15-case freeze.
