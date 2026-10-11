# R5 historical EIS archive report: read-time fail-closed guard

Canonical task: TDP-REFACTOR-20261009.
This is a source-preserving UI/API safety projection, not a review signature,
update of a live EIS publication or rewrite of the historical audit trail.

## Reproduced risk on Mac mini (read-only)

- The APR-06 source queue includes 20 procurement runs, all 20 have metadata in
  the isolated local-e2e Docker artifact volume, 9 have persisted report.json.
- None of those nine historical reports has a verified archived revision
  selection in persisted metadata. One historical report for procurement
  0162300005826000156 says participate_conditionally. That is **not** an
  owner-reviewed GO decision or a verified current-publication status.
- Real archived official EIS XML for procurements 0158300034526000388 (v1-v5,
  latest endDT 2026-10-12T08:00:00+03:00) and 0348100024426000039 (v1-v3,
  latest endDT 2026-10-19T10:00:00+03:00) was reprocessed on current main.
  Highest archived version won regardless input order, four checks passed,
  but archived maximum still does not verify current live EIS status.
- Source receipts: private Mac mini evidence/tdp-r5/
  legacy-saved-runs-readonly-audit-20261011.json, plus
  official-revision-batch-20261011/real-archive-current-main-revision-parity.json.
  Evidence manifests omit run IDs, sensitive provider tokens and source text.

## Read-only fail-closed guard

Archived getDocsIP notice snapshots are review-only unless a *separate*
current_live_eis_verified marker is explicitly TRUE and no review override
exists. Missing marker is UNKNOWN, never a GO or hard expired NO_GO.

- Fresh report construction and metadata enrichment propagate
  notice_revision_requires_review consistently, including single-version ZIPs.
- For an old persisted API report, the response is a copy: top-level
  recommendation becomes manual_review_required, a review note is prepended,
  and Decision Core is marked as historical / current status UNKNOWN.
- The run summary drops a stale historical final_recommendation and adds
  limitations and warnings (without writing metadata).
- HTML preview and download get a prominent static alert, without altering
  the file on disk; unrelated manual uploads retain their normal behavior.
- Existing original JSON and HTML bytes remain available as historical
  evidence; no automatic EIS, database, or tender submission occurs.

## Remaining boundary

This mitigation cannot establish the current EIS publication state and cannot
retroactively make the stored report's internal original calculations valid.
Owner independent review is still 0/20. R2 live DP original five-document
provenance remains unverified; keep overall task status in_progress.
