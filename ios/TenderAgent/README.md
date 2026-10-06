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
