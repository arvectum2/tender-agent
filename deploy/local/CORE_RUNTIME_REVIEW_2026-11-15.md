# Consolidated core runtime — offline review and switch gates

Status: isolated candidate, not deployed. Source commit `03cb55f1774cc1a4b07dc1a276c13f45ca5d2e1b`. Local ARM64 image `arvectum/tender-agent:core-review-03cb55f1`, image ID `sha256:087c73bad201a7141d265ad0908633e47f0a27d189bbb9b27e3a6f3975147e9b`. Base `arvectum/tender-agent:qa-full-460091af`, SDK 0.4.0. Offline build with networking disabled; no host volumes, production configuration or database attached.

Current rollback image (as observed): `arvectum/tender-agent:89d4bb433e285af165f58596a89dfe0cdcb8d01a`, image ID `sha256:c3b400771b93c566017e68f32f6b94777d4bce79225a7b6471632afdac7e0ff6`, SDK 0.3.0. Existing API is healthy. Current and candidate Alembic revisions both `107_add_procurement_learning_observations`. A matching revision is not proof of runtime behavior or data compatibility.

## Before any switch (separate approval)

- Accept core and PRICE01 review PRs #529 and #530 and runtime packaging changes; verify exact final candidate SHA and CI. Rebuild from the accepted SHA, never relabel an earlier image as a different commit.
- Keep current image by immutable ID and verify existing Compose project, image references, mounts, queue state and DB/Redis backup/restore evidence; no new database, parallel permanent workspace, migration or volume deletion.
- Confirm active research does not rely on the API/worker to be switched. Quiesce only approved consumers and establish rollback criteria; do not stop Data Platform or source collection services.
- Confirm authorized Data Platform endpoint health/metadata/stats and extraction compatibility. Intermittent HTTP timeouts remain open; no claim of accepted live Gemma.
- Only after explicit switch approval, review exact Compose commands using the existing external operator env, project and image IDs. Use the matching accepted image for API and worker, without rebuilding during the switch or recreating DB/Redis. Never run `down -v`.

## Acceptance after a separately approved switch

Verify API/worker health and matching revision, unauthenticated denial and authenticated existing workspace access, original evidence loaders, existing history/document access, safe queue handling and absence of regressions. Do not launch a live model, invoke EIS/ETP writes or mutate source data just to test packaging.

If any gate fails, restore previously pinned API/worker image using the original Compose configuration, preserve volumes and recheck health, auth, history and worker state. If schema/data changes occurred unexpectedly, stop and review recovery separately; never blindly restore a backup over active research data. No rollback or switch has been executed.
