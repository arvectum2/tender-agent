# Tender Agent iOS

Native SwiftUI companion for the Tender Agent backend.

## Current slice — MOB-2

- Native SwiftUI manager inbox backed by `GET /mobile/v1/inbox`
- Full mobile portfolio backed by `GET /mobile/v1/portfolio`
- Procurement summary/detail with NMCK, deadline, recommendation, reasons, blockers and unknowns
- Explicit human GO / NO GO / DEFER actions from procurement detail
- Two-step decision flow: choose an action, then confirm it in a separate sheet; optional rationale and required defer date
- Decisions use `POST /mobile/v1/procurements/{deal_id}/decision` and are written as human decisions into the canonical event/decision lifecycle
- Explicit live-vs-demo state; mock/offline data cannot be mutated
- Pairing with the Mac mini mobile API through a dedicated Bearer token stored in Keychain
- Settings for the internal Tailscale HTTPS endpoint

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
      build

## Pairing

The iPhone app uses a dedicated mobile Bearer token, not the pilot Basic Auth password.

1. Mac mini: run `uv run python scripts/mobile_pairing_code.py`.
2. iPhone: Settings -> enter the 6-digit code -> `Подключить по коду`.
3. The returned device token is stored in iOS Keychain and reused automatically.

The default internal endpoint is the Tailnet-only HTTPS address on port 9443.

## Safety boundary

MOB-2 records only an explicit human GO / NO GO / DEFER decision. It does not autonomously decide, submit an application, sign, pay, send external messages, or mutate ETP state. Demo/offline mode is read-only.

## Next slice

MOB-3 adds APNs push notifications and deep links into the relevant Tender Agent case.
