# Daily Tender Run + iPhone Tender Agent — MVP

Updated: 2026-10-07
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

## Implementation status — 2026-10-07

The pre-decision contour remains implemented from DTR-1/DTR-2: durable DailyTenderRun / DailyTenderRunItem state, versioned saved filters, public EIS discovery/dedupe/screening, canonical Deal/Intake linkage, Tender Research document ingestion, Data Platform preparation and deep analysis, fail-closed manager synthesis, run/latest/resume/digest API, mobile projection and unattended Mac mini CLI.

DTR-3 is merged in PR #180 (`3b25e10bab2930f954d39a444b8258ad597010c9`; exact-head CI `37575956723` SUCCESS 9/9). After an attributable HUMAN GO, a run can now continue through POST_DECISION → TRACK_SUBMISSION → TRACK_OUTCOME using the existing canonical services:

- readiness is reused or built only from coherent persisted bid-completeness, CEO-approval, finance and integrated-risk records;
- missing prerequisites or a non-READY readiness result stay explicitly blocked;
- submission-control preparation may be created locally, but the orchestrator never starts or performs a submission;
- a SUBMITTED state advances only when there is an attributable successful human execution or a source-bound registered receipt;
- outcome completion requires canonical outcome intake with an artifact binding; unbound or absent outcomes stay pending;
- pending WAITING_READINESS / WAITING_SUBMISSION / WAITING_OUTCOME runs are restartable and are resumed by the unattended CLI before a new discovery run.

MOB-4 is merged in PR #183 (`bdcd868f1c42f3d3165cc8cad2c83b63b682521b`; exact-head CI `37584606448` SUCCESS 9/9). The native iPhone Portfolio now completes the bounded mobile review slice by reusing the canonical Procurement Portfolio/mobile façade rather than creating a second data model:

- factual considered/GO/submitted/won/not-won/cancelled counts plus canonical submission and win rates;
- deterministic filters for attention-needed, GO, NO GO, submitted, won, not-won, cancelled and submitted-without-outcome cases;
- canonical portfolio decision/source/timestamp on case detail;
- grounded submission/outcome timestamps, rationale and postmortem root cause when present;
- explicit pending/unknown presentation when submission or outcome evidence is absent;
- refresh-before-open behavior for procurement deep links so portfolio metrics and case detail stay coherent after backend state changes.

The human-control boundary is unchanged: the system does not submit or modify applications, log into ETPs, use EDS/UKЭП/private keys, sign, pay, purchase guarantees, contact suppliers/customers, or replace the manager's GO / NO GO / DEFER decision. The prior 2026-10-06 Mac mini deployment evidence in the roadmap predates DTR-3/MOB-4 and is not evidence that these merged slices have already been deployed to that runtime.

## Arvectum IT screening profile v2 — 2026-10-06

The arvectum-it profile is calibrated to the manual selection workflow used on 2026-10-05 rather than to generic IT procurement volume.

Cheap screening now prioritizes custom software/site/GIS/module/integration work and rejects obvious non-target work before documents and LLM analysis: pure vendor support, ready-made license-right supply, hardware/crypto/security-infrastructure supply without a strong custom-development component, non-IT work, expired deadlines, and contracts above the current hard scale ceiling. NMCK above the preferred scale remains a ranking/review signal before the hard ceiling.

The deep-analysis decision policy then checks the factors used manually: mandatory vendor rights/partner status, participant licenses/SRO/certification, qualification-heavy narrow experience, onsite work, FSTEK/FSB/SKZI/attestation, security/cash-gap economics, source-code/data/API/access dependencies, acceptance clarity and execution deadline. Exclusive-rights transfer, remote region and no advance are not blockers by themselves.

The screening profile does not make the manager decision. It decides what deserves expensive analysis; the final agent recommendation remains advisory and GO / NO GO / DEFER remains human.

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
6. DTR-3 — **DONE** — post-GO readiness/submission/outcome automation (PR #180).
7. MOB-4 — **DONE** — Portfolio/metrics UX polish (PR #183).

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
