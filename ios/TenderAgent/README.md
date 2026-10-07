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
