# Indexed daily analysis recovery

Index-only recovery completed 2026-11-20: five existing collections,
543 new resources, independently verified 563/563 exact resources; 176
terminal verified batch journals. No further indexing of those collections.

This change adds a separate reviewed operator for an exact daily item whose
Data Platform collection is already complete. It never calls preparation,
discovery, intake, post-decision actions or external submission. Uses the
stored profile and independently verified chunk/model identity, existing
daily/run/host admission, and a private append-only attempt journal. Analysis
and synthesis use the stored profile; reports are uniquely named and created
without overwrite. Analysis history, enabled learning capture, item status
and refreshed digest are staged in one PostgreSQL transaction. Prior item
failure and the original discovery error survive as provenance. A missing
verified journal end marker must be reconciled before replay.

Default command is read-only; after review and immutable release activation:
`python -m scripts.ops.recover_daily_analysis --run RUN --registry NUMBER --deal DEAL --fingerprint FULL_SHA256`.
Use the active release venv/source. To apply, explicitly add
`--apply --confirm-release ACTIVE_SHA --expected-identity-sha PLAN_SHA`.
Do not substitute a digest from the old release. One notice per invocation.
Actual live analysis completion remains unverified; local transaction,
artifact and dry-run tests are not a production apply receipt. Scope does not
include missing-document preparation. Four cards need separate bounded
document acquisition and projection before using this analysis operator.
