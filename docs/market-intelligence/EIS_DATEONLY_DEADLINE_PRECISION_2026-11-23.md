# Daily Tender — date-only EIS deadline precision gate (23 Nov 2026)

## Proven defect

The Daily Tender public-EIS discoverer can supply a **calendar date without a clock time**. Previously `src/modules/daily_tender_run/service.py::_parse_deadline` accepted `30.11.2026` or `2026-11-30` with `strptime`, attached the Moscow timezone and returned UTC `2026-11-29T21:00:00+00:00`. This was **false precision**: the parser silently invented midnight.

Reproduction in business data, 23 Nov: run `DTR-20261123T050145Z-09c1523f`, procurement `0845500000526000021` (44-FZ, development of MAX chatbot, GKU LO Lenobltранс, 551,315 RUB) stored the instant above. A [third-party contemporaneous listing](https://synapsenet.ru/search/populyarnie-zaprosi/razrabotka-programmnogo-obespecheniya) displays **30 Nov 2026 09:00** for the same procurement. A secondary listing is **not** official confirmation of the exact deadline. [Official EIS notice](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0845500000526000021) requires explicit clock+timezone verification before any bidding decision. Neither 00:00 nor 09:00 may be adopted automatically as the official time.

## Source-only containment

- Exact date-only strings `DD.MM.YYYY`, `YYYY-MM-DD` (and a Python `date` string rendering to the latter) now produce `deadline_at=None`, already a nullable database/response field.
- `_screen_card` preserves eligibility screening based on actual title/category and emits both `deadline_unknown` and `deadline_date_only_time_unverified`. Date-only never becomes an apparent `application_deadline_expired` solely because it is past midnight. A human must check the official card.
- Explicit full Moscow times `30.11.2026 09:00`, `30.11.2026 00:00`, or an offset-aware ISO time **remain exact** and convert to UTC as before; the change does not silently hard-code the third-party 09:00.
- Null/unknown deadline no longer generates false 24-hour deadline notifications that depend on an exact instant. This avoids premature alerts, but does **not** assert that the tender is still open.

## Evidence and boundaries

Isolated synthetic and existing Daily Tender regression suite: **36 tests PASS**, Ruff PASS, Python compile PASS. No production DB update, no historical row rewrite, no source signed-in access, no ETP submission, no downstream deadline override, no deploy of a new pinned service release.

**Issue [#721](https://github.com/arvectum2/tender-agent/issues/721) remains open** for checking official EIS clock+timezone, tracing source-level precision, and carefully reconciling existing stored `deadline_at` with explicit Owner approval and rollback. This PR fixes only the root parser behavior for future new run ingestion; previously persisted records may retain the old imputed midnight until source-verified remediation.
