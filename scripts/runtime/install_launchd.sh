#!/usr/bin/env bash
set -euo pipefail
root=$(git rev-parse --show-toplevel)
embedding_launcher="/Users/master/arvectum-ops/arv-075/scripts/embeddings-ssd-launch.sh"
if [[ ! -f "$embedding_launcher" ]]; then
  echo "Missing approved embedding launcher: $embedding_launcher" >&2
  exit 1
fi
/bin/bash -n "$embedding_launcher"
backend_target="$HOME/Library/LaunchAgents/com.arvectum.backend.plist"
embeddings_target="$HOME/Library/LaunchAgents/com.arvectum.embeddings.plist"
mkdir -p "$(dirname "$backend_target")" "$HOME/Library/Logs/Arvectum"
sed -e "s|__ROOT__|$root|g" -e "s|__LOG_DIR__|$HOME/Library/Logs/Arvectum|g" "$root/scripts/runtime/com.arvectum.backend.plist.template" > "$backend_target"
sed -e "s|__LOG_DIR__|$HOME/Library/Logs/Arvectum|g" "$root/scripts/runtime/com.arvectum.embeddings.plist.template" > "$embeddings_target"
plutil -lint "$backend_target"
plutil -lint "$embeddings_target"
launchctl bootout "gui/$(id -u)" "$backend_target" 2>/dev/null || true
launchctl bootout "gui/$(id -u)" "$embeddings_target" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$embeddings_target"
launchctl bootstrap "gui/$(id -u)" "$backend_target"
