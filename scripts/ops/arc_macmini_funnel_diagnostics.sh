#!/bin/zsh
# ARC Mac mini diagnostics — read-only, no changes to Funnel, OAuth or certificates.
set -u
HOST="mac-mini-master.tail786c4b.ts.net"
echo "ARC diagnostics $(date -u '+%F %T UTC')"
TS="$(command -v tailscale 2>/dev/null || true)"
for f in /opt/homebrew/bin/tailscale /usr/local/bin/tailscale /Applications/Tailscale.app/Contents/MacOS/tailscale; do
 if [[ -z "$TS" && -x "$f" ]]; then TS="$f"; fi
done
echo 'CHECK 1: Tailscale client/login state'
if [[ -z "$TS" ]]; then
 echo 'Tailscale CLI not found: check menu-bar app manually'
else
 "$TS" version 2>&1 | head -n 2
 "$TS" status --json 2>/dev/null | /usr/bin/python3 -c '
import json,sys
try:
 d=json.load(sys.stdin)
 print("BackendState="+str(d.get("BackendState")))
 print("Online="+str((d.get("Self") or {}).get("Online")))
 print("DNSName="+str((d.get("Self") or {}).get("DNSName")))
except Exception:
 print("Status not readable: inspect Tailscale GUI")
' || true
 echo 'CHECK 2: Current Funnel config'
 "$TS" funnel status 2>&1 | head -n 30
fi
echo 'CHECK 3: Local existing ARC backend'
curl --noproxy '*' -sS --connect-timeout 2 --max-time 6 -o /dev/null -w 'LOCAL_HTTP=%{http_code}\n' http://127.0.0.1:8788/ 2>&1 || true
echo 'CHECK 4: Public DNS'
for server in 1.1.1.1 8.8.8.8; do
 echo "resolver=$server"
 dig +time=2 +tries=1 +short "@$server" "$HOST" A 2>&1 | head -n 4
done
echo 'CHECK 5: Public direct HTTPS/TLS with certificate validation'
curl --noproxy '*' -sS --connect-timeout 5 --max-time 10 -o /dev/null -w 'PUBLIC_HTTP=%{http_code} TLS_VERIFY=%{ssl_verify_result}\n' "https://$HOST/" 2>&1 || true
echo 'No system settings were changed.'
