# MI-002 — EIS SOAP getDocsIP: transport diagnosis and safe resume

Date: 2026-10-24, Moscow local 22:10–22:20. Status: **NETWORK BLOCKED DURING PUBLISHED MAINTENANCE**, token not lost.

## Proven, not inferred

- A real Mac mini credential file exists at `~/.config/arvectum/r3-soap-token.env` with permissions `0600`, last modified 2026-10-07. Its actual token bytes are never recorded in this document or Git. `ZakupkiSoapSettings.from_env()` loads it and returns `configured=true`, `enabled=true`, `token_configured=true`, `owner=individual`.
- The existing validated endpoint from Oct 8: `https://int.zakupki.gov.ru/eis-integration/services/getDocsIP`. A real Oct 8 RI223 request fetched `getDocsByOrgRegion(orgRegion=77, exactDate=2026-10-08, documentType44=purchaseNotice)` and 2 genuine ZIP archives; see `docs/223fz/APR02_RI223_SOAP_VERIFIED_2026-10-08.md` with source hashes.
- Repeated authentic, token-configured `getDocsByReestrNumber` requests for **32616447910 (RI223)**, **32615969197 (RI223/PQ)** and **0372200172326000015 (PRIZ)** on 2026-10-24 all aborted before an HTTP/SOAP response with `[Errno 54] Connection reset by peer`. This does **not** mean token rejected or procurement not found.
- Direct TLS GET to `int.zakupki.gov.ru` and obsolete `int44.zakupki.gov.ru` from Mac mini failed during the handshake; the main website `zakupki.gov.ru` separately returned a normal HTTP response. Network route to `95.167.245.200` uses Wi-Fi `en0` and gateway `192.168.1.254`, bypassing local PAC as intended.
- TLS access from the already-authorized Russian SSH hosting (`arvectum-hosting`) independently failed during SSL handshake to the **same integration host**. The alternate network check did **not** send the SOAP token.
- One actual bounded regional SOAP collector request for 2026-10-08/RI223/region 77 returned `retryable_network_failure`; exact operational receipt persisted privately at `/Volumes/ArvectumSSD/Arvectum/runtime/market-intelligence/eis/RI223/purchaseNotice/2026-10-08/region-77.json`, where `archive_count=null` (not zero).
- The EIS information channel announced **planned maintenance 2026-10-24 20:00–2026-10-25 01:00 MSK** with the public site and 44/223 user accounts unavailable: https://t.me/gis_eiszakupki and https://xn--r1a.website/s/gis_eiszakupki . That **correlates** with transport failure, but does not prove the getDocsIP integration endpoint shares the same maintenance window.
- The older `int44.zakupki.gov.ru` was superseded by `int.zakupki.gov.ru` for getDocsIP; don't fall back to obsolete 44-FZ integration endpoint.

## Implemented now

`src/modules/market_intelligence/eis_soap_backfill.py` — bounded, read-only regional/date loader:

1. `--region` (repeatable), `--date-from`, `--date-to` (up to 90 days per invocation), `--max-requests` (<=200). Defaults to a **one-call dry run**. Requires explicit `--execute` to contact ЕИС.
2. Calls existing authenticated `getDocsByOrgRegion` with the proven `RI223`/region/date/`purchaseNotice` combination. No token rotation, no TLS bypass, no unauthorized scraping.
3. Each SOAP request writes one atomic, durable JSON receipt under `ROOT/<subsystem>/<documentType>/<ISO day>/region-XX.json`: outcome/status/time, number of archives (or null on error), XML source SHA-256, named lexical candidate source excerpts when archive scanning is enabled.
4. Optional `--download-archives` invokes the already-proven EIS allowlisted downloader, scans each ZIP's XML members in memory without filesystem extraction, checks uncompressed limits and forbidden XML DTD/entities, captures official registry numbers, hashes, field locator, matching term and original excerpt. Source classification is **`lexical_candidate_not_verified`**, not a signed contract, EPC award or supplier.
5. Circuit breaker: on TLS/network error record `retryable_network_failure`, stop immediately rather than proceed across dates, don't convert it to 0 records. Re-run with `--force-retry` only when service availability has been rechecked. Completed persisted requests are skipped.
6. Search uses current Power Quality ontology `ontology.v1.yaml`, including inflected `фильтром гармоник` and explicit exclusions for misleading `SVG` (vector graphics). Semantic extraction of EPC technical attachments remains a separate acceptance scope.
7. Never commit EIS bulk binaries, session data, private token, URLs carrying authorizations or contact personal data. Persist downloaded archives to excluded local runtime folder only.

## Command after scheduled maintenance

First check a **known real 223-FZ** notice via the existing diagnostic client, without downloading:

```bash
cd /Volumes/ArvectumSSD/Arvectum/worktrees/tender-agent-soap-recovery
/Volumes/ArvectumSSD/arvectum/repos/tender-agent/.venv/bin/python \
  scripts/diagnose_zakupki_soap.py \
  --method getDocsByReestrNumber \
  --reestr-number 32616447910 \
  --subsystem-type RI223 --disable-proxy --no-download
```

If and **only if** SOAP succeeds, run one bounded regional retrieval with archives:

```bash
/Volumes/ArvectumSSD/arvectum/repos/tender-agent/.venv/bin/python \
  -m src.modules.market_intelligence.eis_soap_backfill \
  --region 77 --date-from 2026-10-08 --date-to 2026-10-08 \
  --subsystem RI223 --document-type purchaseNotice \
  --max-requests 1 --download-archives --force-retry --execute \
  --ontology data/market_intelligence/power_quality/ontology.v1.yaml \
  --root /Volumes/ArvectumSSD/Arvectum/runtime/market-intelligence/eis
```

Compare retrieved EIS ZIP SHA-256 against the already archived genuine Oct 8 snapshots (archive revisions may differ; do not assume bytes must match). Then batch additional bounded date/region slices and **persist source-month completeness**. Do not call the deprecated `int44` endpoint and do not treat HTML status 434 or provider maintenance as a procurement count.

## Offline acceptance and limits

- Parsed archived real RI223 SOAP ZIP `.../eis-223fz-corpus/2026-10-08/region77-discovery/archive-01/documentation-archive.zip`: **100 genuine XML notice documents inspected**, SHA-256 prefix `7a7e8aad022ac6d7`; **0** matching Power Quality terms in that limited archive. This is parser smoke evidence only, **not** market evidence for any other day/region.
- Deterministic tests cover candidate detection in deep EPC lot, dedicated УКРМ, malicious XML DTD, false SVG, max-date bounds, completed-request skip, archive SHA provenance, circuit breaker, forced resume and redaction of a synthetic test token.
- Latest results and code SHA should be recorded in `.agent/checkpoints/MI-002-SOAP-RECOVERY-20261024.yaml`. True SOAP post-maintenance acceptance remains **BLOCKED** until next observed handshake success.

## Next data scope

SOAP regional/date requests solve discovery of XML notices **only by incremental iteration**, not instant semantic querying across three years. Market sizing and contractor-role graph also require `purchaseProtocol`, contract registries, amendments, relevant line-item and project attachment evidence, plus commercial ETP feeds. This loader must not be conflated with completed nationwide capture.
