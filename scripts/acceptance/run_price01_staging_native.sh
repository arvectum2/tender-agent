#!/bin/bash
set -euo pipefail
repo="${PRICE01_REPO:?}"
api="$repo/ios/TenderAgent/TenderAgentApp/Networking"
# The JSON decoder is the real implementation; extract just this self-contained enum.
sed -n '1,/^}$/p' "$api/TenderAgentAPIClient.swift" > TenderAgentJSON.swift
swiftc "$api/CompanyAPIClient.swift" TenderAgentJSON.swift "$repo/ios/TenderAgent/TenderAgentAppTests/CompanyStageAcceptance.swift" -o stage-native
./stage-native
