# Pinned Data Platform release staging — 25 November 2026

Status: RELEASE STAGED, RESOURCE ADMISSION BLOCKED. Nothing live changed.

## Exact source and rollback

Existing live Data Platform release is
/Users/master/ArvectumSafe/runtime-releases/data-platform-20261123-e4fdda34
with source commit e4fdda34067dfd341e22a5ed53ea7d22f3d372f0.
New source-only diagnostic commit ec6cac92fa42897df8a908f4b7c3d5a3d292febe
was archived into isolated candidate:
  /Users/master/ArvectumSafe/runtime-releases/data-platform-20261125-ec6cac92

The candidate has cloned pinned Python3.15.2 venv, exact Git-archive
source, 42 focused offline tests PASS, and independent live-runtime
import checks PASS. No migration or dependency change since old pin.
Protected DP PR #139/#140 CI12/12 and mirror1/1 PASS each.

Active launchd script:
  /Users/master/arvectum-ops/arv-075/scripts/data-platform-ssd.sh
Exact active and rollback launcher SHA256:
  1dea946debe5478ff5a08e9f2efe9e1d69942f9f532e934f39126d4a62c9c809
Candidate launcher SHA256:
  4e9bd3ab2553ca4e457f08871c51e1390805c7a257aed10b96e591d81a015beb

The candidate/rollback/ and candidate/preflight/ directories hold
the exact old/new launchers, each with four proved source-path
substitutions and successful bash -n. The live launcher stayed unchanged.

## Real admission: blocked

At 25-Nov-2026 07:54:54 MSK the actual source-only resource
check-only exited 2 with exactly these reasons:
  memory_headroom_low
  memory_pressure_high_or_unknown
  swap_used_too_high_or_unknown

Swap used 15640MiB against strict 2048MiB maximum, pressure1,
memory free ~49-50%. Fresh governor pass/normal/10 does not override
this separate safety gate. Existing Tender Agent ingest-P0 checkpoint
prohibits restarting a running model/service while it fails.
No Qwen process, Data Platform restart or DB mutation occurred.

Current live read-only GET status: 200, version0.6.0, but RED.
Search p95 11468ms/80 vs 1500ms target, ingest p95 37608ms/256
vs 10000ms, embedding phase p95 37330ms. No source improvement
can be claimed from staged code or these readiness values.

## Owner-gated resumption and rollback

Before switching, independently verify a fresh fully green resource
gate: memory>=50%, pressure0, swap<=2048MiB, governor normal,
CPU/GPU/thermal/disk requirements and no active ingest/client jobs.
Recheck old launcher hash, rollback bytes, candidate package,
process identity and exact source. Admit a bounded maintenance
window with service continuity and rollback authority.

Only then atomically replace the launch script with the candidate,
preserving owner, mode, time-bounded rollback and original backup.
Restart only com.arvectum.data-platform via launchd. After the
restart verify new source, localhost health and authenticated
readiness, absent anonymous access (401), search_phases and
embedding_batches_sum/retries_sum fields. On failed health/auth/
contract, restore the old exact launcher atomically and restart
only once under guarded rollback, then independently verify recovery.

Real p95 recovery requires >=20 representative observations per
cohort, adequate observation duration, <=1% error rate, and
unchanged search<=1500ms/ingest<=10000ms SLO. Stage timings
are not causal proof or evidence of recovered HTTP performance.
No automatic deployment or Qwen load is authorized by this runbook.
