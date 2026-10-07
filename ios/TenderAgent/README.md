# Tender Agent iOS

Native SwiftUI companion for the Tender Agent backend.

## Current slice — MOB-3

- Native SwiftUI manager inbox backed by `GET /mobile/v1/inbox`
- Full mobile portfolio backed by `GET /mobile/v1/portfolio`
- Procurement summary/detail with NMCK, deadline, recommendation, reasons, blockers and unknowns
- Explicit human GO / NO GO / DEFER actions from procurement detail
- Two-step decision flow: choose an action, then confirm it in a separate sheet; optional rationale and required defer date
- Decisions use `POST /mobile/v1/procurements/{deal_id}/decision` and are written as human decisions into the canonical event/decision lifecycle
- APNs permission and device-token registration through `POST /mobile/v1/devices`
- Revocation of the current device through `DELETE /mobile/v1/devices/{device_id}`; a lost device can also be revoked from the Mac mini CLI
- Push events for report-ready, deferred-due, procurement-change, deadline-risk and outcome-available signals
- Safe `tenderagent://digest` and `tenderagent://procurement/{deal_id}` deep links
- A push/deep link loads the referenced procurement from the same Bearer-authenticated mobile API when it is not already cached
- Explicit live-vs-demo state; mock/offline data cannot be mutated
- Pairing with the Mac mini mobile API through a dedicated Bearer token stored in Keychain
- Settings for the internal Tailscale HTTPS endpoint and notification state

## Generate project

Run:

    cd ios/TenderAgent
    xcodegen generate

For a simulator build without signing:

    xcodebuild \
      -project TenderAgent.xcodeproj \
      -scheme TenderAgent \
      -configuration Debug \
      -destination 'generic/platform=iOS Simulator' \
      CODE_SIGNING_ALLOWED=NO \
      build-for-testing

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

MOB-3 adds notifications and navigation only. It does not autonomously decide, submit an application, sign, pay, send external messages, or mutate ETP state. Push delivery is a non-authoritative side effect: canonical Tender Agent state is committed before notification dispatch, and APNs failures do not roll domain state back.

## Verification

The bounded MOB-3 verification includes backend registration/idempotency/deep-link tests, Swift deep-link and payload-encoding tests, simulator build/tests, and a physical-device/APNs attempt when Apple credentials/provisioning are available.
