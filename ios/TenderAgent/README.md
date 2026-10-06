# Tender Agent iOS

Native SwiftUI companion for the Tender Agent backend.

## Current slice

- Inbox with Daily Tender Run digest
- Procurement summary/detail
- Local GO / NO GO / DEFER actions
- Portfolio metrics
- Settings/connection placeholder
- Mock data only

## Generate project

Run:

    cd ios/TenderAgent
    xcodegen generate
    open TenderAgent.xcodeproj

## Next slice

Replace mock data with the mobile facade API on the Mac mini over Tailscale, then add authenticated decision writes and APNs device registration.

## Pairing

The iPhone app uses a dedicated mobile Bearer token, not the pilot Basic Auth password.

1. Mac mini: run `uv run python scripts/mobile_pairing_code.py`.
2. iPhone: Settings -> enter the 6-digit code -> `Подключить по коду`.
3. The returned device token is stored in iOS Keychain and reused automatically.

The default internal endpoint is the Tailnet-only HTTPS address on port 9443.
