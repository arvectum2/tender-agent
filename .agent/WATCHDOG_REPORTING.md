# Tender Agent Watchdog reporting contract

The single hourly `Tender Agent Watchdog` must produce one concise report for every invocation, including partial-progress and no-op runs.

Each report must include:
1. actual run timestamp in Europe/Moscow;
2. canonical task worked on;
3. concrete work completed in that invocation, with commit/PR/issue/test evidence when available;
4. blocker or waiting condition, if any;
5. exact next action for the next hourly run.

If no productive repository/checkpoint progress was made, the report must explicitly state `NO PRODUCTIVE PROGRESS` and explain why.

A persistent GitHub issue is used as the machine-auditable run log. The Scheduled Task output is also required to report the same summary to the user.
