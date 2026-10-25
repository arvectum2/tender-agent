# APR-03B — independent private staging parity & fail-closed registry check (17.10.2026)

## Authority and baseline

- Canonical Tender Agent main, verified before work: `3b899de42c50f7cc95d16e506ae2740597ba2256` (post-PR #459 consolidation). This task changes only a read-only registry error boundary, targeted tests and review evidence. No EIS/ETP mutation, filing, signature, payment, external communication, production deployment, benchmark-truth edits or owner legal acceptance.
- Existing Mac mini private preview **`127.0.0.1:18083` remains unchanged**: running Docker image label `a9f3bce914afc33347c9af0e6098849531011591`. Existing `scripts/ops/verify_operator_workspace_preview.py` correctly reports whole-source drift against new main. **This old preview must not be cited as owner acceptance of main.**
- Built a **separate** Docker image using the existing `deploy/pilot/Dockerfile.operator-workspace-preview`, which deletes the old `/app/src` and `/app/scripts` before copying the entire checkout. No cherry-picked runtime overlay.
- New staging Docker name `arvectum-apr03b-main-qa-20261017` and loopback-only port `127.0.0.1:18087`; run with immutable read-only image filesystem, isolated tmpfs, dropped capabilities, no-new-privileges and **zero Docker mounts**. Generated throwaway test-only basic authentication (0600 local temp file, never committed or printed), new empty ephemeral SQLite for a fail-closed test; no real `arvectum` PostgreSQL connection, secrets or private tender originals.
- Source parity script independently verified **1,163** `src` and `scripts` files by SHA256 against the built container, including image revision label. No claim that staging contains any real company account or business-accepted documents.

## Reproducible defect and change

**Before fix:** authenticated `GET /api/demo/tender-agent/workspace/registry` on a clean unmigrated staging DB returned HTTP **500** with underlying SQLAlchemy `no such table: procurement_tenders`. The browse shell still served 200, so an operator could see a broken registry despite healthy `/health`.

**Fix:** all three canonical registry read-only operations now intercept SQLAlchemy errors at the shared `read_session` boundary and return stable HTTP **503** with the generic Russian message `База закупок временно недоступна`. Failed DB state is **never** converted into an empty result or a fake ready schema. The API response never includes SQL text, private connection details, a stack trace or false missing-document claim. Once the DB exists, the existing real repository-backed search/detail/scoped-download behavior remains unchanged.

## HTTP checks on the corrected non-production Docker build

| Path | Anonymous | Authenticated | Result |
| --- | --- | --- | --- |
| `/health` | 200 | 200 | health endpoint available |
| `/pilot/tender-agent/workspace` | 401 | 200 | HTML search/history/registry controls present |
| `/pilot/tender-agent/workspace/assets/workspace.js` | 401 | 200 | protected JS |
| `/pilot/tender-agent/workspace/assets/workspace.css` | 401 | 200 | protected CSS |
| `/api/demo/tender-agent/workspace/registry` | 401 | 503 | unmigrated staging schema fails closed |
| `/api/demo/tender-agent/workspace/registry/{uuid}` | 401 | 503 | missing canonical schema fails closed |
| `/api/demo/tender-agent/workspace/registry/{uuid}/documents/{uuid}/download` | 401 | 503 | no raw file or DB exception exposure |
| `/api/demo/tender-agent/runs` | 401 | 200 | staging-only history endpoint (no real source import) |
| `/openapi.json` | 401 | 200 | protected API definition |

All **18** HTTP status assertions PASS. Original source parity after code fix: **1,163** file SHAs and the image label match the isolated branch's exact code commit. Tests in `tests/test_apr03b_operator_workspace.py` cover all three 503 routes, 401 without auth and positive real-schema cases. This is **development/staging readiness only**.

## Unclosed user/owner gates

1. Real owner browser acceptance on a controlled private deployment built from merged main: search actual permitted 44-ФЗ/223-ФЗ notice, retrieve original SHA-bound bytes and the correct revision, verify cited report/unknowns, safe PDF/DOCX export, history and read-only canonical PostgreSQL (not an empty SQLite staging).
2. Owner confirmation of business profile/capabilities, licence/SRO/qualification, economic fit, current official status and any human/legal GO. Do not infer human gold from development ChatGPT review.
3. Separately authorized staging with isolated real datastore credentials, tenant protection and legal consent (APR-04/05). Production VPS, signing, external bids, payments and model training **not authorized**.
4. R4 independent 15-case source-only external human review and R5 20 dated owner reviews remain unaccepted; do not claim independent gold or commercial accuracy.

No existing preview was replaced; the QA container is disposable. The source verification and 503 behavior were verified without mounting any private production volumes.

## Browser and completion update

- Google Chrome **155.0.8059.80**, using native Chrome DevTools Protocol (no mocked DOM), loaded the authenticated localhost-only workspace on the corrected staging image. **PASS**: page title `Operator Workspace · Arvectum Tender Agent`, search/history/registry controls present, rendered body 1,282 characters, `document.readyState=complete`, one external JS asset and **zero uncaught JavaScript exceptions**.
- The browser probe did **not** import or analyze a live tender, access real customer documents, or imply owner's subjective browser/legal approval.
- The disposable staging container was stopped and the generated test-only auth file deleted after the checks. Old private preview **18083 remains unchanged**, still on stale image `a9f3bce`.
- Source merged via PR **#460** into main `b28f3b3da2fd9f4dfe6225eb4250f5f6c3ca090d`; full local suite **4937 passed, 285 skipped, zero failed**; final exact-head GitHub CI passed. All 18 staging HTTP probes, 1,163 Docker source SHAs, and 31 targeted tests passed.
