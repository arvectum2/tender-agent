# Tender Agent iOS

Native SwiftUI companion for the Tender Agent backend.

## Current slice — MOB-1

- Native SwiftUI manager inbox backed by `GET /mobile/v1/inbox`
- Procurement summary/detail with NMCK, deadline, recommendation, reasons, blockers and unknowns
- Explicit live-vs-demo state; mock data is never presented as live
- Pairing with the Mac mini mobile API through a dedicated Bearer token stored in Keychain
- Settings for the internal Tailscale HTTPS endpoint
- Read-only UI: GO / NO GO / DEFER remains a separate MOB-2 stage

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

MOB-1 is read-only. It reads manager-ready items and source evidence but does not expose a control that records GO / NO GO / DEFER, submit an application, sign, pay, send external messages, or mutate ETP state.

## Next slices

MOB-2 adds explicit authenticated GO / NO GO / DEFER writes through the existing canonical decision log. MOB-3 then adds APNs/deep links. Neither is part of MOB-1.
