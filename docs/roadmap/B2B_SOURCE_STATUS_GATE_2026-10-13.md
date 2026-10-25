# Corporate-source status-first triage — bounded engineering regression

**Purpose.** An original-platform card with **Завершён** or **Прием заявок завершен** cannot be promoted to an active B2B procurement because it has a future printed deadline. Workspace case 19004 displayed «Завершён» while showing 14 October 2026 as the application deadline. The indexed status is a point-in-time public-source observation, not a live ETP booking check.

Module: `src/tender_research/corporate_lead_gate.py`. Local pure function `triage_corporate_card(card, checked_at=aware_datetime)`; it performs **no network, crawling, authentication or bid action**. It requires the approved exact HTTPS source URL, original-platform status observation timestamp, asserted legal-entity organizer and an ISO deadline. Outputs are `CLOSED`, `REVIEW_REQUIRED` and `PUBLIC_CANDIDATE_ONLY`; never `GO`, `BID_READY` or an authenticated application permission.

Contract:
- Platform **terminal status wins before a printed future deadline**. Explicit cancellation/closed status is not rescued by a stale date.
- Absent organization/legal identity, unknown or outdated original status evidence and unsupported/source-spoofed URL fail to REVIEW_REQUIRED.
- Today-only deadline with no time is REVIEW_REQUIRED; a precisely elapsed offset-aware deadline is CLOSED.
- Even fresh open-status evidence plus a future full deadline yields only PUBLIC_CANDIDATE_ONLY. Official ETP eligibility, tariffs, participation right, attachments, live state and owner decision remain independently required.

**Integration boundary:** this is a unit-tested library for a prospective lawful corporate-source adapter/manual triage pipeline. It is **NOT wired into an authenticated B2B-Center/Workspace connector or ETP response**, and no such connector should be enabled until platform access and legal terms are verified. It changes no existing EIS 44-FZ/223-FZ submission path.

Evidence: `docs/roadmap/B2B_SOURCE_DISCOVERY_INITIAL_2026-10-12.md` (13 Oct status addendum), direct original [Workspace 19004 card](https://workspace.ru/tenders/internet-portal-dlya-obschstvnnoy-organizacii-19004/) and [Workspace tender-status guide](https://workspace.ru/help/).
