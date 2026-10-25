# APR-03B / Safari owner-reproduction — private image parity and safe retry

Owner clicked real EIS keyword-search card for **0372200172326000015** in Safari on Mac mini at 2026-10-09 10:13 UTC. HTTP access logs show both UI actions reached API: search 200, import 200, GET run/events 200, POST analyze 200. The business status on both attempts was FAILED, with `Analysis failed safely: int() argument must be ... not 'NoneType'`. Saved runs:
- `toa-run-20261009101316-306d54`
- `toa-run-20261009101331-bfdddd`

Each has all six actual original EIS files on disk, extracted text 6/6. The issue was **not** Safari, search, getDocsIP, HTTP authorization or download. The private preview Docker image had two stale backend sources relative to the full exact-head CI-tested `main`: `upload_service_legacy.py` and `procurement_intake_service.py`. The stale legacy source called `int(revision["version"])` even when the source XML has no optional version, causing the exact failure in owner workflows. Prior CI only tested correct checkout source and could not detect Docker overlay drift.

## Reproducible safe preview deployment

Run **only on the authorized Mac mini** with repository on ArvectumSSD, using the already available private base image and existing private infrastructure. No VPS/public ingress. No environmental secrets should enter Git.

From an exact reviewed and tested git commit on ArvectumSSD:

```sh
SOURCE_SHA=$(git rev-parse HEAD)
docker build -f deploy/pilot/Dockerfile.operator-workspace-preview \
  --build-arg SOURCE_COMMIT="$SOURCE_SHA" \
  -t arvectum/tender-agent:apr03b-source-locked-verified .
python scripts/ops/verify_operator_workspace_preview.py \
  --repo . --container arvectum-apr03b-preview-api --commit "$SOURCE_SHA"
```

**Do not** use the former UI-only Dockerfile: every release must copy the **entire src/** and **scripts/** trees from one exact commit, clearing stale source folders first and run byte-for-byte source integrity verification of **all src/ and scripts/** files on the **running** container before claiming browser acceptance.

Use a separate `127.0.0.1:18086` staging container for pre-promotion checks; inherit the private pilot's existing, access-controlled volumes and private network. Preserve Basic Auth, no public ports, `--read-only`, `--tmpfs /tmp`, `--security-opt no-new-privileges:true`, `--cap-drop ALL`, and do not change original live pilot on `18082`. Test the original stored files, exact 44-FZ notice source identity, EIS XML citations, reports and PDF/DOCX. Promote the verified image to loopback `18083` only after staging succeeds; check HTTP 401 anonymous and 200 authorized, source parity and container health.

The failed runs may be retried using the existing POST `/api/demo/tender-agent/runs/{run_id}/analyze` (manual re-run, not an external procurement action). Preserve original failure in the persisted event feed. The successful retry should not continue to display stale failure warnings; the implementation specifically removes only legacy `Analysis failed safely:` and `Fallback report generation failed.` markers, preserving all other substantive cautions.

Even a `completed_with_warnings` status is not a legal/commercial GO. No ETP submissions, signatures, messages, payments or external communications.
