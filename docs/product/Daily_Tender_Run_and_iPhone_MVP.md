# Daily Tender Run + iPhone Tender Agent — MVP

Updated: 2026-10-06
Owner: Product Owner / ООО «Арвектум»
Backend: Tender Agent on Mac mini
Client: native iPhone app (SwiftUI)

## Goal

Turn the proven daily procurement routine into one reliable system:

1. discover relevant procurements;
2. filter and deduplicate;
3. deeply analyze only the shortlist;
4. send manager-ready summaries to iPhone;
5. collect GO / NO GO / DEFER from the manager;
6. continue the operational workflow after GO;
7. preserve the full history for conversion, win/loss and decision-quality analytics.

The manager should not need to run searches, download documents, request analyses one-by-one or manually maintain the dashboard.

## Implementation status — 2026-10-06

Implemented in feature/daily-tender-run-autonomy:

- durable DailyTenderRun / DailyTenderRunItem state with migration 100_add_daily_tender_runs;
- versioned saved-filter profile arvectum-it;
- multi-query public EIS discovery, deduplication and deterministic cheap screening;
- canonical Deal/Intake linkage for shortlisted procurements;
- public EIS detail/document ingestion into Tender Research before preparation;
- Data Platform preparation/index readiness gate and source-grounded deep analysis;
- fail-closed manager synthesis with advisory GO / NO_GO / NEEDS_REVIEW, confidence, reasons, blockers and unknowns;
- run/latest/resume/digest backend API;
- mobile inbox/portfolio projection of NMCK, deadline and DTR recommendation metadata;
- /mobile/v1/digest/latest with canonical human decision state;
- unattended CLI scripts/run_daily_tender_run.py.

The implemented contour stops at WAIT_HUMAN. It does not submit applications, log into ETPs, sign, pay, or replace the manager's GO / NO GO / DEFER decision.

## Daily Tender Run

DailyTenderRun is a durable orchestration record, not an ephemeral cron script.

Pipeline:

DISCOVER → DEDUPE → SCREEN → ACQUIRE_DOCS → ANALYZE → SUMMARIZE → WAIT_HUMAN → POST_DECISION → TRACK_SUBMISSION → TRACK_OUTCOME

Persist:

- run id, start/end/status;
- saved-filter/profile version;
- source query/cursor and acquisition evidence;
- counts: discovered, duplicate, screened out, deeply analyzed, needs manager, failed;
- per-procurement stage and error;
- source/document revision used for analysis;
- agent recommendation and model/rule version;
- link to the generated manager digest/report.

Rules:

- each stage is idempotent and restartable;
- one procurement failure does not invalidate the whole run;
- cheap deterministic screening happens before expensive deep analysis;
- already-seen procurements are reprocessed only on material source/status change;
- EIS documents are acquired through the Mac mini direct-access path and analyzed locally via Data Platform;
- agent recommendation is stored separately from the human decision.

## Manager digest

One run produces one actionable inbox summary: found, duplicates, screened out, deeply analyzed, agent GO, agent NO GO, needs review, and human decisions still pending.

The digest opens only cases requiring manager attention.

## iPhone UX

### Inbox

Each card shows:

- procurement number;
- short title and customer;
- NMCK;
- submission deadline/time left;
- agent recommendation;
- 1–3 strongest reasons;
- risk/unknown indicator;
- NEW, DEFERRED, CHANGED or RESULT badge.

Quick filters: decision needed, deferred, changed, submitted, results.

### Procurement report

Header:

- title and customer;
- law/procedure;
- NMCK;
- deadline;
- EIS link;
- lifecycle state.

Decision block:

- agent recommendation and confidence;
- hard blockers;
- critical unknowns;
- strongest GO arguments;
- strongest NO GO arguments.

Sections:

1. What the customer wants.
2. What Arvectum has to do.
3. Entry/application requirements.
4. Execution risks and onsite requirement.
5. Contract/payment/security/penalty risks.
6. Technical dependencies and access.
7. Documents/evidence.
8. Commercial facts.
9. Change history.

Evidence opens the relevant document/page/fragment or the full web report.

### Decision bar

Persistent actions:

- GO
- NO GO
- Отложить

GO/NO GO opens a lightweight confirmation sheet with optional comment and reason code.

Отложить requires a return date/time in MVP.

### Portfolio

Mobile Procurement Portfolio:

- selected;
- GO / NO GO / deferred;
- submitted;
- won/lost/rejected/cancelled;
- submission rate;
- win rate;
- high-priority pending cases.

### Settings

- Mac mini/Tailnet connection status;
- notification categories;
- quiet hours;
- device registration;
- diagnostics/version.

## Mobile backend façade

Initial API surface:

- GET /mobile/v1/inbox
- GET /mobile/v1/digest/latest
- GET /mobile/v1/procurements/{deal_id}
- POST /mobile/v1/procurements/{deal_id}/decision
- POST /mobile/v1/procurements/{deal_id}/defer
- GET /mobile/v1/portfolio
- POST /mobile/v1/devices
- DELETE /mobile/v1/devices/{device_id}

The façade maps to canonical deal/decision/event/submission/outcome records and never becomes a second source of truth.

Decision writes include decision, rationale/comment, reason codes, actor/device id, idempotency key and client timestamp. The backend records authoritative server timestamp and audit metadata.

## Connectivity and security

Internal MVP:

- iPhone connects to Mac mini over Tailscale;
- no raw public Mac mini API port;
- app credential stored in iOS Keychain;
- device registration can be revoked;
- decision writes require authenticated device and idempotency key;
- sensitive tokens never appear in UI/logs.

A public Internet/API gateway is a later deployment decision.

## Push notifications

Use APNs. Mac mini sends outbound pushes.

MVP events:

- REPORT_READY;
- DEFERRED_DUE;
- PROCUREMENT_CHANGED;
- DEADLINE_RISK;
- OUTCOME_AVAILABLE.

Each push deep-links to the correct procurement or digest.

## Human-control boundary

The system may autonomously search, filter, download, parse, analyze, recommend, summarize, notify, prepare readiness artifacts, monitor published results and update factual lifecycle state when grounded in evidence.

The system may not autonomously replace the manager's bid decision.

GO / NO GO / DEFER is always attributable to a human actor.

Where ETP/EDS/signature semantics require explicit human confirmation, that remains a human step even after GO.

## Acceptance

Daily Tender Run is accepted when a saved-filter run completes end-to-end without chat orchestration, restart/deduplication is deterministic, each shortlisted case produces a grounded report or explicit failure/unknown state, and the digest contains only actionable cases.

iPhone MVP is accepted when the phone securely reads live Mac mini reports, push opens the right case, GO/NO GO/DEFER is persisted to the canonical decision log, Procurement Portfolio updates immediately, retries cannot create duplicate decisions, and a lost device can be revoked independently.

## Delivery order

1. DTR-1 — durable Daily Tender Run and stage state machine.
2. DTR-2 — manager digest and mobile façade API.
3. MOB-1 — SwiftUI shell, Tailnet auth, Inbox + Procurement read-only.
4. MOB-2 — GO/NO GO/DEFER with idempotent audited write.
5. MOB-3 — APNs registration, push and deep links.
6. DTR-3 — post-GO readiness/submission/outcome automation.
7. MOB-4 — Portfolio/metrics UX polish.

## Deferred from MVP

- Android;
- public App Store launch for external tenants;
- public Internet exposure of Mac mini;
- custom notification infrastructure instead of APNs;
- offline decision mutation/merge;
- full ETP automation from the phone;
- autonomous GO/NO GO;
- multi-tenant SaaS mobile auth;
- finance/guarantee workflows.
