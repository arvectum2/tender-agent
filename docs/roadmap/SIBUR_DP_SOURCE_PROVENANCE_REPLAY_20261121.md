# СИБУР: воспроизводимая историческая цепочка источников — 21.11.2026

Ранее сохранённые семь XLSX имеют доказанную историческую цепочку **официальная страница закупки СИБУР → ссылка на документ → источник файла SHA-256 → сохранённый файл → ресурс Data Platform**. **Четыре** URL/наблюдения происходят из проверенного полного 27-страничного снимка публичного реестра СИБУР, **три** — из отдельного исторического архива закупок (проверенные категории и оригинальные страницы). Последний архив полностью проверен в PR #688 (4 052/4 052 страницы, 48 536 наблюдений); для трёх дополнительных документов отдельно подтверждены URL, категория/страница, исходный page SHA-256, ID закупки, `source_row`, исходное упоминание URL в строке, hash сохранённого файла и идентификатор DP. **958** исторических фрагментов/эмбеддингов подтверждены архивным актом DP, а не новым чтением Data Platform.

Скрипт `scripts/research/verify_sibur_dp_source_provenance.py` воспроизводит эту цепочку **строго офлайн**, используя исходный код проверок из PR #524, #526, #688 и отдельные исторические DP подтверждения из PR #689. Входы: `--registry-snapshot`, `--documents`, `--archive-root`. В случае отсутствия хотя бы одной подтверждённой исходной связи возвращает ошибку, а не `first_party_verified=true`; проверяет SHA файлов и источников, идентификатор URL, формат и корректность JSON, ссылки только официального HTTPS-источника, отдельные archive category/page, точное совпадение `external_id` и строки закупки, защиту от небезопасных путей/символических ссылок. Вывод содержит лишь агрегированные сведения и детерминированный SHA состава проверенных связей. **Никаких запросов к сети, базам, Data Platform, новых индексирований, заявок или записи в исходники.**

Первый реальный воспроизводимый запуск: `original_sha256_count=7`, `primary_registry_source_count=4`, `historical_archive_category_source_count=3`, `historical_DP_matching_chunk_embeddings=958`, статус `historical_first_party_source_lineage_verified`, без сетевых запросов и записей в БД. Приватный независимый акт по конкретным оригиналам: `/Volumes/ArvectumSSD/Arvectum/private/tender-agent/sibur-dp-seven-original-url-proof-20261121.json` (`0600`). Узкая проблема происхождения трёх файлов [#690](https://github.com/arvectum2/tender-agent/issues/690) закрыта, однако это **исключительно историческое происхождение**: актуальность публикации закупок, живой индекс, источник доступа и правомерность принятия коммерческих решений не доказаны. Отдельные риски [#679](https://github.com/arvectum2/tender-agent/issues/679), [#685](https://github.com/arvectum2/tender-agent/issues/685) и [#686](https://github.com/arvectum2/tender-agent/issues/686) сохраняются.

## 22-Nov protected main PR709 follow-up

Existing source-only PR #691 has been reconciled onto protected main
faba2e775fde8d504e9d66d46434f2eccd10879d, without changing the
source-only validator or importing any document.
A fresh read-only execution using the already stored first-party
registry/archive and saved original files independently returned
original_sha256_count=7, public registry=4, archived category=3,
historic DP matching chunk/embedding records=958, and deterministic
membership SHA256 14a043aaf37fe99b935ac66f921cb7156f84851027df920fdbcc1aacc9060a48.
The distinct historical private receipt remains mode 0600 with original
bytes outside Git. After the main merge, 51 focused offline/checkpoint
regressions and Ruff/make check PASS. PR exact-head CI must be green before
merge. This does not query current live DP nor validate source/current
procurement status or authorize new network/DB access.

As part of PR #691, the prior merged PR #709 administrative checkpoint
is closed with the exact protected merge faba2e775fde8d504e9d66d46434f2eccd10879d
and 10/10 CI. The original EIS/PITR, current PPT source, and APR06 owner
release are still independent blocked gates.

## Protected closeout, 22-Nov 2026

PR #691 merged to main after all 10 required exact-head CI checks
SUCCESS, merge commit 251db2e127952a8fc4cd1e04ac215f1f76c1feb1.
The bounded historical source-to-DP provenance task is completed;
canonical parent/child checkpoints now agree. Seven first-party original
XLSX SHA receipts (four registry and three archived category pages)
match 958 historical saved Data Platform chunk/embedding identities;
the verified offline aggregate remains deterministic. No live DP service
read was made in this check, no contemporary notice status was asserted,
and no new source HTTP, DB/DP write or production deployment occurred.

Source-admitted production re-indexing, legal source rights, independent
staging and PITR remain separate future decisions; this checkpoint
does not authorize broader draft PR #527.
