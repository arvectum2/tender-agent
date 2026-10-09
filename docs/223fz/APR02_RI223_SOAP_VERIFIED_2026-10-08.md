# APR-02: RI223 getDocsIP live validation — 2026-10-08

## Canonical repository and executable environment

- Canonical: `https://github.com/arvectum2/tender-agent`, `main` initially `958e94c740e73a052f275d46fea713f01ab4d117`.
- Active feature checkout on Mac mini: `/tmp/tender-agent-roadmap-20261008`, branch `feature/apr02-223fz-evidence-gate`, PR #227. Tests and commands execute against **this checkout**.
- `/Users/master/arvectum-runtime/AI-Corporation` is another checkout pointing to the same GitHub via its `canonical` remote, but its local `main` was `f7a01d3`; it is **not** the branch under verification. Its existing `.venv/bin/python` provides dependencies only, while the imported product code is the canonical branch. Python SDK is exposed via `PYTHONPATH=/Users/master/arvectum-runtime/data-platform/sdk/python/src`.
- EIS on Mac mini is reached **directly without HTTP(S) proxy**. The SOAP token is read by the already existing secure loader from `~/.config/arvectum/r3-soap-token.env` (0600), never printed or committed.

## Definitively working SOAP operations

Endpoint: `https://int.zakupki.gov.ru/eis-integration/services/getDocsIP`.

1. `getDocsByOrgRegionRequest`: `subsystemType=RI223`, `orgRegion=77`, `documentType44=purchaseNotice`, `periodInfo/exactDate=2026-10-07` returned **completed**, **4 archives** (394 XML entries). Same operation for `2026-10-08` returned **completed**, **2 archives** (196 XML entries). These are regional date-scoped samples, **not** an exhaustive all-Russia ranking.
2. `getDocsByReestrNumberRequest`: `subsystemType=RI223`, with the real registry number returned **completed** and a downloadable archive for every shortlisted record.
3. Archive downloads returned actual ZIP XML. For 223-FZ files, attachment metadata is under `attachments/document`, not `attachmentInfo` (used by the 44-FZ path); the diagnostic downloader now accepts both and deduplicates by published content ID / contentUid / guid.

Reproduce in canonical checkout with suitable installed dependencies and the already configured token:

```bash
python scripts/diagnose_zakupki_soap.py --method getDocsByReestrNumber --reestr-number 32616447910 --subsystem-type RI223 --disable-proxy --download-archive
python scripts/diagnose_zakupki_soap.py --method getDocsByOrgRegion --reestr-number 32616447910 --subsystem-type RI223 --org-region 77 --exact-date 2026-10-08 --document-type purchaseNotice --disable-proxy --no-download
```

## Final four recent **verified OKPD2 62** notices, prices <= 5m RUB

All facts in the table are extracted from the actual EIS `RI223` SOAP XML, not inferred from software-related titles.

| 223-FZ registry | XML sample date | XML OKPD2 | XML initialSum RUB | SOAP + attachments | EIS public documents | Archive SHA-256 |
|---|---|---|---:|---|---|---|
| 32616447910 | 08.10.2026 | 62.02.20.120 | 280800 | completed, 2/2 files | HTTP 200, 2 links | `5469022ea690c3ede66ed63040390fb0f846176668545c5e9fdff587b026a278` |
| 32616445866 | 07.10.2026 | 62.01.11.000 | 514800 | completed, 2/2 files | HTTP 200, 2 links | `1629ed15c2698b02dab34f11c03c458aa2cf2290c2dadaaadb7d801e3cd75cba` |
| 32616445632 | 07.10.2026 | 62.09 | 143640 | completed, 2/2 files | HTTP 200, 2 links | `8c199ae237919f981bca2a93543ef0102d91301a9117dd19a0085d14236ca4a1` |
| 32616444788 | 07.10.2026 | 62.01.29.190 | 191352 | completed, 4/4 files | HTTP 200, 4 links | `494da21fc92e14d950e6cdc767b06ade83708f964cbac67332128f77692dbcc4` |

**Persistent original evidence**, not committed to Git: `/Users/master/arvectum-runtime/eis-223fz-corpus/2026-10-08/`. The private working directory contains per-number SOAP ZIP, official EIS document-page HTML, ten actual binary attachments (with retrieval URLs and SHA-256 in `manifest.json`). Source is public EIS; repository stores only this sanitized source-bound truth table.

## Source-bound truth matrix / measured gaps

| Source or capability | Observed | Not observed or not established |
|---|---|---|
| Exact registry and code | Verified from EIS XML and four source URLs | Nationally newest across **all** regions not established (samples for Moscow only) |
| Lot / position | `lots/lot` and `lotItems/lotItem`, one of each in the inspected XML for each record | Multi-lot/multi-position procurement not in this sample |
| Notice documents | `attachments/document` (2, 2, 2, 4 downloaded), public `notice223/documents.html` matches | Signatures, document legal sufficiency and business suitability not assessed |
| Notice versions | SOAP archives for 32616447910 and 32616445866 have two XML members | The semantics and ordering of revisions require comparison before claiming amendment support |
| Clarifications / protocols | Clarifications NOT_OBSERVED in notice XML; two separately archived `purchaseProtocol` XML members (32616445866 and 32616447910), verified on the same 2026-10-08 frozen ZIP originals | No legal effect, award result or complete lifecycle inferred; see `APR02_RI223_STRUCTURED_EVIDENCE_2026-10-08.md` |
| Lifecycle/status | SOAP response `completed`; four public HTML layouts recognized, parser returns SUCCESS with title/customer and 2/2/2/4 links | Contract award and protocol status not covered by purchaseNotice-only corpus |
| Attachment extraction | Verified original 223-FZ `attachments/document` vs 44-FZ `attachmentInfo` divergence; fixed downloader; navigation links no longer counted as files | RAR `.rar` safety policy for excluded 32616445795 remains unsupported_extension, separately measured |

Original initial candidate 32616445175 **is 63.11.11.000**, 32616440359 **is 58.29.50.000**, so neither satisfies strict OKPD2 62 despite IT/software titles. The 32616445795 notice **is** OKPD2 62.09.20.190 and has a valid SOAP archive, but its attachment is RAR and the downloader flags `unsupported_extension`; exclude from this *fully downloaded* four-case acceptance sample, without lying that it is unqualified by OKPD2.

## Test and acceptance results

- All 4 final notices: SOAP `getDocsByReestrNumber(RI223)` → completed → archive downloaded → attachments complete (2/2, 2/2, 2/2, 4/4).
- All 4 public EIS document pages: HTTP 200, existing `parse_223fz_detail` reports SUCCESS, title and customer present, documents count correct; no 44-FZ fallback.
- 223-FZ and SOAP diagnostics focused regression: **14 passed**, one unrelated Starlette deprecation warning.
- This completes the APR-02 **source-corpus acquisition / transport verification** acceptance. Future lifecycle/protocol/revision implementation needs a separate bounded evidence-driven successor, not invented behavior.
