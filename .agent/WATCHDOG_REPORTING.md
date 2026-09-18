# Tender Agent Watchdog reporting contract

The single hourly `Tender Agent Watchdog` must leave one machine-auditable GitHub issue comment for every invocation, including interrupted, partial-progress and no-op runs.

## Fail-visible protocol

At the **start** of each invocation, before repository mutation, create exactly one placeholder comment in audit issue `#57`. The placeholder contains the actual Europe/Moscow timestamp, `RUN START / INCOMPLETE`, the canonical task (or `selection pending`) and the current head observed.

Keep that comment ID for the invocation. Before returning, update the **same comment** in place with the final run report. Do not add a second report comment.

If the invocation is interrupted after the placeholder is created, the stale `RUN START / INCOMPLETE` comment is intentional evidence that the run did not finish. A later watchdog run must not rewrite another run's placeholder; it may only report the stale run as evidence.

If the placeholder cannot be created, do not perform repository mutation in that invocation. Return/report the audit-channel failure through the Scheduled Task result when possible.

## Final report fields
The final update must include:

1. actual run timestamp in Europe/Moscow;
2. canonical task/state worked on;
3. concrete work completed in that invocation, with commit/PR/issue/test evidence when available;
4. blocker or waiting condition, if any;
5. exact next action for the next hourly run.

If no productive repository/checkpoint progress was made, explicitly state `NO PRODUCTIVE PROGRESS` and explain why.

An empty admitted queue is **not** `NO PRODUCTIVE PROGRESS` while `.agent/owner-directive.yaml` is active and permits deterministic continuation. In that state the watchdog must apply the canonical continuation-selection contract or report the exact gate that prevents materialization.
