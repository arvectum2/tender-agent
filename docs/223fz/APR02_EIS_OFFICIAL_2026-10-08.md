# APR-02 official EIS 223-FZ acquisition — verified 2026-10-08

## Mac mini network policy (important for future sessions)

Use Mac mini for EIS; `zakupki.gov.ru` must be fetched **directly, bypassing HTTP proxies** (`no_proxy`/`NO_PROXY` should cover `zakupki.gov.ru`, `.zakupki.gov.ru`; Python may use `urllib.request.build_opener(ProxyHandler({}))`). Proven live: opening `https://zakupki.gov.ru/epz/opendata/search/results.html` directly returns HTTP 200. Current shell had no proxy variables; direct connection succeeds without NO_PROXY env. Do not assume an EIS HTTP 404 means all routes fail: use correct 223-FZ paths.

## Open-data versus SOAP

`/epz/opendata/search/results.html` is **open datasets search** with a 223-FZ dataset selector `/epz/opendata/dataset/modal.html?inputId=dataset223...`, not itself a SOAP WSDL or method specification. Existing `scripts/diagnose_eis_soap_matrix.py` `getDocsIP` uses **44-FZ** namespace `http://zakupki.gov.ru/fz44/get-docs-ip/ws` and subsystem `PRIZ`; do not pretend that envelope is valid for 223-FZ. The specific 223-FZ SOAP service, namespace, operations and authentication must be confirmed from official 223-FZ service instructions and schemas before implementing its client. SOAP credential remains only in local protected Mac mini file, not in git.

## Working read-only official 223-FZ paths

1. Search: `https://zakupki.gov.ru/epz/order/extendedsearch/results.html?fz223=on&searchString=<number>` returns HTTP 200 and embeds `purchaseNoticeGuid` plus link to correct `notice223` documents endpoint.
2. Documents: `https://zakupki.gov.ru/epz/order/notice/notice223/documents.html?purchaseNoticeNumber=<number>&noticeGuid=<guid>` returned HTTP 200 for all four numbers.
3. Attachments: explicit links on documents page to `https://zakupki.gov.ru/223/filestore/public/1.0/download/fz223/file.html?uid=<uid>`; use the exact published links and SHA-256 manifest, no guessed IDs.

## Actual results: 4 official notices, 14 actual files

| Registry | Official documents HTTP | Downloaded files | Candidate OKPD2 62 status |
|---|---|---:|---|
| 32616445866 | 200 | 2 (both PDF, duplicate bytes to be reconciled) | IT development; exact numeric OKPD2 to verify |
| 32616445175 | 200 | 4 (Office ZIP payloads) | Exclude unless official item code shows 62; aggregator-linked evidence points to 63.11.11.000 |
| 32616440359 | 200 | 2 (1 legacy OLE file + 1 Office ZIP payload) | Licensing; exact numeric code to verify |
| 32616429050 | 200 | 6 (Office ZIP payloads) | 62.01.29.000 explicit in official purchase title |

All files downloaded on Mac mini into `/tmp/apr02-223fz-official/<number>/`; local `downloads-manifest.json` stores source URLs, retrieval timestamps, SHA-256 and payload types. No raw third-party documents committed to the repo.

## Parser observations

Existing `parse_223fz_detail` against all four **official documents HTML pages** returned `SUCCESS`, extracted explicit titles, and yielded 22/14/18/14 candidate links. These candidate-link counts are too high: they include navigation links such as `/documents.html`; the true independently extracted `/223/filestore/.../file.html?uid=` attachment counts are 6/2/4/2. Next focused improvement is filter attachment links to concrete file endpoints and preserve exact source provenance; do not infer every URL containing `document` is an attachment.

This resolves the original inaccessible-EIS blocker **for public official 223-FZ HTML and document downloads**, but not by establishing the 223-FZ SOAP protocol. Before claiming 3–4 filtered OKPD2-62 cases, replace the misclassified 63.11 case and verify numeric OKPD2 for every inclusion.
