# DTR parallel product increment (2026-11-15)

Owner approved the parallel roadmap while SIBUR research continues. No live Data Platform, database, job schedule or operator runtime changes are part of this increment.

## Reliability slice

- A PostgreSQL session advisory lock (separate connection, retained across stage commits) fences execution of the same run; the isolated SQLite development path uses an in-process guard. This is not yet a distributed scheduler/profile-level admission lock.
- Scheduled recovery includes PENDING and interrupted RUNNING, alongside existing human/outcome states. Discovery retries use the original run date window. An intentional empty search requires `success_empty`; source failures are not no-results and remain visible in the run and digest, even with actionable cases. Explicit retry reuses existing completed items, not their processing calls. Mid-item recovery can still repeat an interrupted processing step; exactly-once external work is not claimed.
- Cross-run reuse requires equal frozen profile snapshots. All three relevant image recipes include the saved-profile directory; invalid path-like IDs are rejected.
- Mobile digest exposes run ID/state/stage and explicit discovery-incomplete flag without inventing a successful empty result for queued/old runs. Legacy digest completeness is unknown when not recorded. Existing decision and trading boundaries remain unchanged.

## Next slice: company boundary, then mobile client

`_find_duplicate_deal_id` in `src/modules/tender_intake/service.py` currently deduplicates procurement identity globally, including `Deal.procurement_number`; DTR and mobile human decisions refer to the canonical `deal_id`, and mobile portfolio/latest digest are not company-scoped. The DTR intake also hardcodes IT service direction/domain. Simply adding a Sionika search JSON would risk reusing a different company's deal, decision and classification. Do not enable a second company in unattended DTR until scoped lookup/write authorization, separate company-specific decision identity, source sharing policy, migration/backfill strategy and cross-company negative tests are designed and implemented. Reuse the existing company profile and SaaS tenant/role boundaries where appropriate; do not duplicate procurement documents or infer actual Sionika eligibility/costs. Scope shared public procurement facts separately from company-specific qualifications, decisions, commercial data and reports.

Then implement mobile client digest state and profile access using that same canonical contract, improve the existing single Operator Workspace, and run isolated acceptance. Do not activate production, APNs, live LLM, automatic submission or collection while research is in progress.
