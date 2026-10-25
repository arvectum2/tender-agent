# MI-012 — Original EIS technical annexes -> Data Platform

Evidence cut-off: 2026-10-25. This is a source-safety integration after MI-011 recovered official 44-FZ/223-FZ document download. It does not claim nationwide procurement coverage or actual award contracts.

## Architecture and trust boundaries

Tender Agent owns original EIS XML/ZIP provenance, exact procurement binding, tenant/workflow controls, SHA validation and source manifests. Data Platform is the ONLY generic native document extractor, chunker, index and terminology search service. The existing Python SDK is reused for collection and document ingestion.

A trusted caller builds TrustedTenant from authenticated tenant identity, consumer identity and server-authorized collection allowlist, NEVER from user JSON or third-party attachment metadata.

Document collection IDs are deterministic hashes of tenant + run and cannot collide across tenants. Stable canonical source URI uses scheme mi-eis and the exact registry number plus actual downloaded binary SHA. Replay is stable; do not mistake that alone for actual dedup until server behavior is confirmed.

## Batch invariants

Before any Data Platform network call:
1. Recheck original SOAP ZIP and XML through the existing MI source-ledger with SHA, number and statute subtype PRIZ or RI223.
2. Check every source record belongs to that original XML SHA, expected ZIP SHA and exact procurement number.
3. Check each downloaded file bytes SHA, filename/extension and allowed non-symlinked local path. Limit to 20 MiB per file and 96 MiB per batch; reject unsupported, HTML, 7z and raw ZIP parents as text input.
4. For ZIP children, ALSO rehash the downloaded ZIP parent, find the exact original member by filename-path SHA and verify the raw decompressed member byte SHA matches the staged child. ZIP bombs and symlinks rejected.
5. Reject ambiguous 223-FZ revisions by default; explicit historical research override retains review flag and never certifies legally operative specification.
6. Reject cross-tenant, unauthorized collection and incorrect owner/access-policy. Data Platform collection must have owner market-intelligence:tenant, matching tenant access policy and exactly the authorized consumer.
7. Indexing succeeds only after Data Platform returns matching collection, nonempty document_id and extraction_status extracted. A partial write is an error, never represented as a fully indexed batch.

Dry-run is the default; it performs no Data Platform network calls. Actual writes require execute=True and an authenticated SDK client.

## Owner-only CLI

Module: scripts.mi012_index_eis_originals.

Arguments include --receipt, --source-archive, --archive-sha256, --original-files-dir, --subsystem RI223/PRIZ, --source-region, --source-date, --run-id. Optional --execute explicitly permits Data Platform network access. --allow-unreviewed-revisions admits ambiguous historical docs only with a visible review flag.

Required authenticated operator environment, NOT client-provided JSON: ARVECTUM_MI_AUTH_TENANT_ID, ARVECTUM_MI_AUTH_CONSUMER_ID and ARVECTUM_MI_AUTH_COLLECTION_ALLOWLIST. For execute additionally ARVECTUM_DATA_BASE_URL, ARVECTUM_DATA_API_KEY and ARVECTUM_DATA_CONSUMER_KEY. Never log these credentials or raw EIS download UID links.

## Original source acceptance context

MI-011 successfully recovered original file bytes:
- 223-FZ 32313008364 STATCOM: three files; local Data Platform extractor previously confirmed 13,535 and 76,279 characters in source DOCX/DOC documents.
- 223-FZ 32615969197 UKRM: two original ZIPs, ten staged readable files, four opaque 7z entries not analyzed; Data Platform local extractor previously confirmed actual XLSX and DOCX text.
- 44-FZ 0373200026426000249: original active-revision #2, three downloaded PDF files source-bound to EIS XML.

During MI-012 the Mac mini was online, but accesses to its external ArvectumSSD stalled. The local running Data Platform HTTP health endpoint on 127.0.0.1:8094 timed out. The volume was attached/mounted, no forced remount/restart was performed, and no claim of new production Data Platform ingestion is made. Implementation and tests are verifiable independently in GitHub CI.

## Next verified result

Once source disk and Data Platform service recover: dry-run against SHA-qualified stored originals, then authorized --execute, inspect real DP resource/document IDs and tenant policy, rerun with identical source to validate idempotence, and perform hybrid terminology search for УКРМ, СТАТКОМ and other Power Quality families inside original EPC technical document chunks. Never elevate a technical mention into a verified supplier, award or signed contract price.
