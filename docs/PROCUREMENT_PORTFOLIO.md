# Procurement portfolio

/procurement-portfolio is the canonical read model for procurement funnel analytics.

It intentionally does not introduce a second lifecycle database. It projects the existing
Tender Agent sources of truth:

- deals for the procurement registry and current workflow status;
- decision_records and tender screening for GO / NO GO / review rationale;
- submission-control events/state for participation;
- outcome intake for WON / LOST / REJECTED / CANCELLED;
- postmortems for root-cause learning.

## API

- POST /procurement-portfolio — manual intake with canonical deduplication;
- GET /procurement-portfolio
- POST /procurement-portfolio/{deal_id}/decision
- GET /procurement-portfolio/ui

The decision endpoint records an auditable human portfolio decision only. It does not submit
a bid, sign anything, or bypass the existing status/approval workflow.

## Metrics

- submission rate = submitted / GO;
- win rate = WON / (WON + LOST + REJECTED);
- NO GO reasons are counted from structured reason codes, with UNCLASSIFIED only when a
  NO GO decision has no structured code.

## Suggested NO GO reason codes

Use stable codes where possible so portfolio analytics become useful over time:
SCOPE_MISMATCH, LOW_MARGIN, HIGH_EXECUTION_RISK, ONSITE_REQUIRED,
IMPOSSIBLE_DEADLINE, BAD_PAYMENT_TERMS, EXPERIENCE_REQUIREMENT,
LICENSE_REQUIREMENT, SECURITY_REQUIREMENT, GEOGRAPHY, COMPETITION, OTHER.
