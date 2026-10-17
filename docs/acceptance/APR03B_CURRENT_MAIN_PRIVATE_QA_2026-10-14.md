# APR-03B current-main private preview: source-bound HTTP acceptance, 14 October 2026

**Status: TECHNICAL_QA_PASS / PRODUCT_SEMANTIC_AND_OWNER_BROWSER_ACCEPTANCE_OPEN.** A private test does **not** approve production deployment, legal GO, a procurement bid, signing, SaaS activation or payments.

## Exact environment and isolation

- Built `arvectum/tender-agent:apr03b-current-main-20261014` successfully from isolated checkout of `origin/main` commit `cc9efe6b0c6a9ceea29fd008b83de2e299af8563`; image digest `sha256:7950d3f17c5a120be7388f7501cf9351d4e32157d551f711f9bb62b78a9bdedb`.
- The existing owner's `arvectum-apr03b-preview-api` on **127.0.0.1:18083**, 9 Oct image `apr03b-owner-safari-fixed-v2`, **was not replaced**. QA runs separately as `arvectum-apr03b-current-main-qa-20261014` on **127.0.0.1:18087**, never public.
- QA container: **read-only root**, 5 application/source mounts all **read-only**, no files overwritten; Docker networks match the existing local private/egress scope so loopback publishing works. Reused existing protected private e2e environment (credentials were not disclosed); **no** production, external ETP, payment or communication effects.
- This snapshot tests the **application code** of the specified main revision; it does not claim that future main or older 18083 image is identical.

## Actual authenticated read-only HTTP checks

Existing historical 44-FZ original-source run `toa-run-20261012200402-7249ed`, procurement **0372200172326000015** (Museum of Bread). The prior 12 Oct protected preview had six acquired originals (XML/XLS/DOC/DOCX/DOCX/PDF); this check reads, and does not re-import or re-analyze, the saved state.

| QA observation on 127.0.0.1:18087 | Verified response |
| --- | --- |
| `GET /health` | 200, JSON status ok |
| Unauthenticated `GET /pilot/tender-agent/workspace` | **401**, authentication required |
| Authenticated workspace HTML | **200**, HTML 15,083 bytes |
| Authenticated canonical registry route | **200**, JSON 44 bytes; nonempty data or usable explorer is **NOT established** |
| Authenticated saved run detail | **200**, JSON 159,053 bytes, `completed_with_warnings`; `analysis_mode=fallback_deterministic_adapter` |
| Authenticated `/workspace/runs/<id>/evidence` | **200**, JSON 1,576 bytes; per-claim semantics not human-audited |
| Authenticated `/runs/<id>/report` | **200**, JSON 16,504 bytes; historical/report semantics require review |
| Authenticated `/runs/<id>/export/pdf` | **409**, archived/current-EIS-revision gate |
| Authenticated `/runs/<id>/export/docx` | **409**, same archived/current-EIS-revision gate |

The 409 explicitly warns that the published current ЕИС notice/revision and application deadline are not confirmed and historical decisions must not be used for participation. **This is correct fail-closed behavior**, not a failed export implementation.

## Current-code deterministic checks

Isolated Mac mini source worktree at `cc9efe6b0c6a9ceea29fd008b83de2e299af8563`:
- `pytest -q tests/test_apr03b_operator_workspace.py tests/test_operator_workspace_image_parity.py tests/test_tender_operator_agent_report_export.py`: **50 passed**, 0 failed, 5 warnings (third-party Starlette/httpx deprecation and SQLAlchemy test fixture FK cleanup cycle).
- Ruff focused router/workspace service: **PASS**.
- `node --check src/modules/tender_operator_agent_demo/assets/operator_workspace.js`: **PASS**.
- `git diff --check`: **PASS**.

## Explicit incomplete acceptance gates

1. Existing saved run uses **deterministic fallback**, not actual local LLM end-to-end review. No claim of an independent full legal/economic/qualification assessment or citation completeness.
2. Historical reported contract/status ambiguity must **not** be interpreted as absent original contract when an original draft is attached. The original report is stored history; a new authorized current-revision run and independent review are still required.
3. A 200 registry route does not prove the owner can browse a populated canonical read-only database. Verify substantive database content and navigation in a live owner browser session.
4. The actual latest official ЕИС revision must be pinned before any re-analysis or export promotion. The old saved run's PDF/DOCX fail closed.
5. **Owner personally using the browser and accepting claim-level citations/economics/risks remains required.** QA technical pass does not mark APR-03B DONE.

**Next:** preserve isolated QA container for an authorized Mac mini browser walk-through at `http://127.0.0.1:18087/pilot/tender-agent/workspace`; do not confuse it with the 18083 older image. Independently collect current ЕИС originals and owner-approved semantics before marking APR-03B accepted. No ETP actions or watchdog changes.
