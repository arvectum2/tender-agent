# Resource admission by operation — owner approved 25 November 2026

This policy supersedes the incorrect use of the isolated Qwen synthetic
stage gate as a blanket production rollout prerequisite. No threshold
in a model stage, full DTR, recovery, or existing governor is relaxed
by this policy. No additional model launch is admitted.

| Operation | Admission |
|---|---|
| Replacement of one existing TA/DP Python service, identical schema/dependencies, no extra model | Fresh governor <=100s, PASS normal/10 or reduced/3, actual macOS pressure 1 (normal) or 2 (warning), free memory >=25%, thermal 0 or 1, disk >=20 GiB; no critical pressure, no active affected requests/jobs; exact release/rollback and backup/PITR evidence |
| Normal production work | Existing governor and operation-specific admission, locks, prewrite checks unchanged; full DTR still requires its own full admission |
| Additional model or synthetic resource-heavy experiment | Separate strict model-stage admission; fix the pressure enum bug separately with tests before any future stage, not as part of this rollout |

macOS kern.memorystatus_vm_pressure_level returns 1/2/4
(normal/warning/critical), not 0. Absolute used swap alone does not
indicate ongoing critical pressure. Record it for diagnosis; no arbitrary
2GiB cutoff for replacement-only Python services. The above 25% headroom
is an explicit conservative rollout-only policy, not a general compute
budget. Unknown/stale telemetry, paused governor, pressure 4, active
affected workloads, or any loss of service integrity blocks rollout.

Owner explicitly authorized this policy and exact staged releases.
Use existing cooperation locks, no model launch, no DB migration,
no restart of Docker or unrelated services. Acquire deployment lock,
validate current source and candidate/rollback hashes, drain affected
clients, check recent backup and MI/PITR evidence. One service at a time;
preserve owner/mode and use atomic file replacement. On failed exact
pin/health/auth/contract, restore original bytes and restart once;
verify rollback and stop. Record actual observations; do not equate
HTTP200 with SLO acceptance. Existing WSF07B original 12-ID approval
and expiry retained; verify rebind and daily preflight. No DTR replay.
