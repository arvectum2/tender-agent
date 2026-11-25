# Coordinated TA/DP release — 25 Nov 2026

STAGED ONLY / BLOCKED. PR756 exact protected CI9/9; merge tree equals
tested head. Target TA c4e38b86dcc7721cf6d4f366b2cfab890f1df8ac,
DP ec6cac92fa42897df8a908f4b7c3d5a3d292febe. Production TA
023d3670adcbf6d9ae8a318f4433615fa94b680c and DP
e4fdda34067dfd341e22a5ed53ea7d22f3d372f0 unchanged. No dependency or
schema changes. Actual schema 128_add_tender_async_index_receipts.

TA candidate: /Volumes/ArvectumSSD/Arvectum/releases/tender-agent-c4e38b86dcc7721cf6d4f366b2cfab890f1df8ac
(clean detached source, APFS-cloned Python3.15.2 venv; interpreter/source
pin PASS; 39MiB source, 102MiB venv). Canonical developer checkout has
unrelated uncommitted changes and was left unchanged.
DP candidate: /Users/master/ArvectumSafe/runtime-releases/data-platform-20261125-ec6cac92
(622/622 source blobs match, previous 42 tests and runtime import PASS).
Private coordination package:
 /Users/master/ArvectumSafe/runtime-releases/ta-dp-coordinated-20261125-c4e38b86
includes stage-manifest.json and preflight/rollback. Three original
launchers byte-identical to live files, checksums/modes recorded; syntax
PASS. DP/daily staged, backend INERT.template exits 78 and requires
approved manifest pin. Never install inert template. Actual rollback
execution not tested.

## Ordered gates and rollout

1. Obtain separate exact owner approval for WSF07B release rebind to
   c4e38b86: unchanged original 12 IDs, nine excluded, same DB binding,
   token hash, validity/expiry and scope. Preserve original grant. Use
   existing verify_macmini_backend.py contract; create private manifest
   and receipt only after approval, verify digest and finalize backend.
2. Confirm maintenance window and physical FileVault unlock. Owner
   previously confirmed ability, not immediate reboot approval. At
   14:29 MSK strict gate blocked: reduced governor, free35%, pressure,
   swap24395.75MiB. TA/DP HTTP200, PostgreSQL healthy, WAL receivers
   running. Verify backup/restore receipts, active jobs and recovery
   access before any reboot. Seven-day PITR not independently proven.
   Do not stop Docker alone to reclaim swap. Coordinate other services.
3. After authorized maintenance verify ARC/SSH/Tailscale, SSD, services,
   DB identity/schema, backup continuity and strict host gate. Stop if
   blocked. No migration needed. Use mandatory prewrite gate before DB
   mutation, existing locks and bounded rollback.
4. Under coordination lock switch exact DP launcher preserving mode
   and owner, restart only DP. Verify exact source, authenticated
   readiness, anonymous refusal and telemetry fields. On failure
   restore old bytes, restart once, verify. Do not infer SLO from HTTP200.
5. Coordinate TA backend and daily launcher pins under maintenance lock,
   verify private manifest/rebind, source and schema128. Restart backend;
   prove HTTP200, docs/openapi401, workspace anonymous403, original 12/12
   admitted read-only scope, marker and daily preflight without job.
   On failure restore both TA launchers together, old grant untouched;
   restore DP if cross-service failure requires it.
6. Only after current EIS revision and exact inventory, host and
   prewrite gates, perform targeted recovery for 0187200001726001774,
   one document per admitted operation. Offline integrated rehearsal:
   five originals, ten receipts, 235 chunks, zero unresolved pages,
   ensure_collection. First noncanonical fixture refused; corrected
   fixture PASS. Not proof of live index/analysis. Reconcile and index
   bounded batches, analyze once, present human decision. No DTR replay.
7. Resume roadmap and verify representative DP SLO windows.

No production file, DB row, grant, process, model setting or EIS source
changed. Keep blocked until explicit owner decisions and gates pass.
