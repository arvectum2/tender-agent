# Canonical checkpoint protection in consolidated PR674

Status: reviewed source-preservation fix, not permission for main merge or production deployment.

At exact approved base `abcd8727326c398d870edbc4a2da793e090ac8eb`, the canonical `.agent/current-task.yaml` is blob `54c21dcc5ecf5e84ca525db55e54933e4287e5f8`. Earlier PR657 carried a different historical snapshot, blob `74bb1ea81c35da9ca0e8aea30cdf8529b0bb5b6f`, adding 316 lines and replacing three lines, including the root `resume_instruction`. Those values refer to dated APR review activity and must **not** overwrite contemporary recovery instructions at merge time.

PR674 now restores the exact main canonical blob `54c21dcc5ecf5e84ca525db55e54933e4287e5f8` without rewriting it. The full original candidate snapshot is retained verbatim at `.agent/history/TA-APR-REVIEW-CANDIDATE-CURRENT-TASK-20261118.yaml` with blob `74bb1ea81c35da9ca0e8aea30cdf8529b0bb5b6f` for audit and reconciliation, not used as active agent state.

The MI worktree `/Users/master/ArvectumSafe/worktrees/tender-agent-mi` is a separately protected local execution checkpoint with nine unpushed commits, containing live sections including `dual_pitr_20261120`, `resource_governor_20261120`, `fresh_index_20261120` and `source_catalog_20261120`. It was not copied into PR674, committed, reset, deleted, or silently reconciled here. Owner-approved follow-up must compare against *current* runtime state and canonical MI checkout before authorizing a main merge.

A green CI validates integration tests and source consistency, **not** an independent human approval for operator credentials, ETP bidding, private evidence, source authenticity, legal gates, schema migration or production deployment.
