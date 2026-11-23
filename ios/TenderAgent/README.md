# Tender Agent iOS

Native SwiftUI companion for the Tender Agent backend.

## Current slice — MOB-4

- Native SwiftUI manager inbox backed by `GET /mobile/v1/inbox`.
- Canonical mobile portfolio backed by `GET /mobile/v1/portfolio`; the iPhone does not maintain a second procurement source of truth.
- Portfolio dashboard shows factual counts for considered, GO, submitted, won, not-won and cancelled cases plus canonical submission and win rates.
- Deterministic portfolio filters cover attention-needed, GO, NO GO, submitted, won, not-won, cancelled and submitted cases still waiting for an outcome.
- Procurement detail shows the canonical portfolio decision/source/timestamp, submission evidence/timestamp, grounded outcome/rationale/timestamp and postmortem root cause when present.
- Missing submission/outcome evidence is rendered as pending/unknown rather than inferred.
- Pull-to-refresh and procurement deep links refresh the canonical portfolio before presenting a cached case, keeping metrics and detail coherent after backend changes.
- Explicit human GO / NO GO / DEFER actions remain a separate two-step decision flow with optional rationale and required defer date.
- Decisions use `POST /mobile/v1/procurements/{deal_id}/decision` and are written into the canonical decision lifecycle.
- APNs registration, revocation, push events and safe `tenderagent://digest` / `tenderagent://procurement/{deal_id}` deep links from MOB-3 remain supported.
- Explicit live-vs-demo state remains visible; mock/offline data cannot be mutated.
- Pairing uses a dedicated mobile Bearer token stored in Keychain; the default backend endpoint remains Tailnet-only HTTPS.

## Generate project

Run:

    cd ios/TenderAgent
    xcodegen generate

For a simulator build without signing:

    xcodebuild       -project TenderAgent.xcodeproj       -scheme TenderAgent       -configuration Debug       -destination 'generic/platform=iOS Simulator'       CODE_SIGNING_ALLOWED=NO       build-for-testing

For focused simulator tests:

    xcodebuild       -project TenderAgent.xcodeproj       -scheme TenderAgent       -destination 'platform=iOS Simulator,name=iPhone 17,OS=27.0'       test

## Pairing

The iPhone app uses a dedicated mobile Bearer token, not the pilot Basic Auth password.

1. Mac mini: run `uv run python scripts/mobile_pairing_code.py`.
2. iPhone: Settings -> enter the 6-digit code -> `Подключить по коду`.
3. The returned Bearer credential is stored in iOS Keychain and reused automatically.

The default internal endpoint is the Tailnet-only HTTPS address on port 9443.

## APNs provider configuration

Push delivery is disabled by default. On the Mac mini, provision an Apple APNs token-auth key outside the repository and set:

    AI_CORP_MOBILE_APNS_ENABLED=true
    AI_CORP_MOBILE_APNS_TEAM_ID=<Apple Team ID>
    AI_CORP_MOBILE_APNS_KEY_ID=<APNs Key ID>
    AI_CORP_MOBILE_APNS_PRIVATE_KEY_PATH=/absolute/local/path/AuthKey_<id>.p8
    AI_CORP_MOBILE_APNS_BUNDLE_ID=com.arvectum.tenderagent

The backend uses HTTP/2 token authentication and never returns the APNs token or provider credentials from the mobile API. Invalid/unregistered APNs tokens are disabled and wiped from the active registration row.

For a lost phone, an operator can revoke both its server-side push registration and its mobile Bearer access independently:

    uv run python scripts/mobile_push.py --revoke-device <DEVICE_ID>

Deferred reminders can be retried from the same internal contour:

    uv run python scripts/mobile_push.py --due

## Safety boundary

MOB-4 is a read/decision UX slice. It does not autonomously decide participation, log into an ETP, submit or modify an application, use EDS/UKЭП/private keys, pay, buy a bank guarantee, or send supplier/customer messages. Portfolio metrics are derived from the canonical backend projection and missing evidence stays pending/unknown. Existing GO / NO GO / DEFER actions remain explicit human actions with a confirmation step.

## Verification

The bounded MOB-4 verification covers the canonical mobile portfolio contract, portfolio metric/outcome projection, Swift metric/filter mapping, deep-link refresh coherence, generic simulator build and focused iPhone simulator tests. Physical-device verification is attempted when a connected signed device/profile is available; Apple provisioning limitations are recorded rather than bypassed.

## DTR status projection (2026-11-15)

The owner mobile client additionally reads `/mobile/v1/digest/latest`. Pending, running, incomplete-source, failed, completed, and unknown legacy states are distinguished. Only an explicitly complete discovery with zero discovered items can display a successful empty search. A digest request failure does not discard the canonical portfolio/inbox. This is the existing owner-only mobile token surface, not an implementation of tenant mobile login; company portfolio and SaaS tokens remain separate. Verified by native unsigned `build-for-testing` and six actual Swift decoder/status projections; simulator-device XCTest execution and live backend acceptance are separate gates.

## Company portfolio (private pilot)

The separate Companies tab imports an existing SaaS Bearer credential using an explicitly trusted HTTPS origin. It does not redeem invitations or automatically accept pilot conditions. Conditions and revocation are handled in the existing web cabinet. Company credentials and their origin are stored together in a separate device-only Keychain item, not the owner mobile credential or UserDefaults. Each selected account is revalidated against `/api/saas/me` (tenant, customer and member); portfolio responses must match the authenticated customer. Old portfolio state is cleared when switching; no fallback to the global owner deals. Read-only case and decision display and role-gated evidence binding list are provided. Removing a connection is local-only and is not server-side revocation. Source references do not establish current eligibility. The native flow has no external submission, write, APNs or company activation path. Unsigned build-for-testing passed; 11 standalone Swift identity/decoding/HTTPS assertions passed. Live Keychain, simulator account-switching and device acceptance remain separate gates.

## Company decision write increment

Company case decisions now use the same authenticated `/api/saas/company-portfolio/cases/{case_id}/decisions` endpoint as the web cabinet. Only an accepted owner/admin session can prepare a decision for a case in the current company portfolio. Explicit confirmation includes company, registry number, action and displayed revision. A nonempty rationale and future timezone-aware DEFER date are required. The request carries the displayed expected revision and an in-memory idempotency key scoped to account, case and identical draft. A lost response keeps that key for an explicit identical retry; a conflict reloads the portfolio and requires opening and confirming the updated case. The response is checked against the submitted revision, action, rationale, deferred date and member identity before reporting success. Successful writes refresh the canonical portfolio; refresh failures are reported separately. No external application submission is initiated. The old legacy owner mobile token remains separate. Standalone Swift checks and unsigned build-for-testing passed, and HTTP fixture testing with separate owner/admin members confirms canonical shared history. Simulator/device and full live synchronization acceptance remain outstanding.
