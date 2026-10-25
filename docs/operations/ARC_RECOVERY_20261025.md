# ARC v17: Mac mini TLS/Funnel recovery (25 October 2026)

## Verified current state
ARC Site and installed private Plugin/App remain available. devices_list returns mac-mini online:false, macbook-air online:true, windows-dev online:false. Five separate real ARC Mac mini API calls failed HTTP 525 or JSON parse of Cloudflare 525 body. No command has run on Mac mini through ARC. Plugin manifest/read/release via Plugin Creator confirmed; there is no verified Site code or origin control available from the Plugin Creator manifest.
RDC Mac mini stays paired but Desktop Commander reports a monthly usage limit and explicitly says not to retry or reconnect. A prior Mac mini check showed loopback ARC 8788 responding while public TLS failed; needs a fresh check.

## Recovery entry point
Run scripts/ops/arc_macmini_funnel_diagnostics.sh locally on Mac mini (no sudo). Checks Tailscale BackendState / Funnel config, local port 8788, public DNS, trusted direct TLS. Does not print secrets or reset any configuration.
Read output before any change. If Tailscale is Logged out, owner signs in in the official Tailscale GUI. If Funnel config is wrong, repair only existing 443 to localhost 8788 mapping with separate explicit approval and after capturing prior routing state. If public DNS/TLS is failing while Funnel is healthy, verify active Tailscale incident and certificate status; do not blindly renew or reset certificates, downgrade clients, weaken SSL or replace Site/App/OAuth.

## Engineering boundaries
Preserve site https://arvectum-remote-cloud.alivespark256.chatgpt.site/, app asdk_app_sites_ea145157ac688191924762a48a899bce, plugin plugin_asdk_app_sites_ea145157ac688191924762a48a899bce, OAuth, 44 v17 tools and secrets. Do not touch MacBook/Windows or use as proxy without new owner permission. Mac mini direct origin must not depend on RDC.
Acceptance: ARC devices_list reports mac-mini online:true, three actual independent harmless read-only calls succeed, verified HTTPS, original tool schemas intact, launchd persistence checked, unauthorized calls fail safely. Record commit/test proof in .agent/checkpoints/ARC-RECOVERY-20261025.yaml.

This is an isolated branch and its branch .agent/current-task.yaml MUST NOT be merged on top of the active Tender Agent roadmap checkpoint from main.
## 25 October — owner-approved repair and true Site route

Original Mini Funnel 443 TLS-terminated TCP forwarded to unrelated free_gateway.server at localhost:8788. With explicit owner permission, verified the authenticated ARC MCP supergateway at localhost:18765 returns 401 without an API key, backed up full original Tailscale serve status to private Mac mini /tmp, disabled only old TCP 443, then enabled `tailscale funnel --bg --https=443 http://127.0.0.1:18765`. Confirmed preserved routes 8443/10000/9443. Tailnet HTTPS 443 now reaches protected ARC MCP with valid TLS and unauthorized status 401, which is correct.

**However, the deployed Site uses port 10000, not 443**. Exact source of truth in MacBook Air `arvectum-remote-agent/sites/FULL_ACCESS_INTEGRATION.md`: POST to `https://mac-mini-master.tail786c4b.ts.net:10000/v1/full`; other read-only features use `:10000/v1/read-only`. 10000 maps to Mini localhost:18767 (existing ping/full API server). Authenticated local read-only full_status request, with secret loaded from protected Mini file and not printed, returned HTTP 200, `ok:true`, dict result. Same server's unauthenticated path returned 401; internal HTTPS 10000 TLS verified, unauthorized response 401. But real installed ARC plugin mac-mini read methods and ping still show HTTP 525, mini `online:false`. MacBook works. Thus public 10000 Funnel ingress is not operating for the Site even though the backend works internally.

Next bounded repair **requires additional permission** because the prior owner authorization was expressly limited to port 443: save pre-10000 status, selectively stop/re-publish *only* HTTPS Funnel 10000 with the same original target `127.0.0.1:18767`, retry actual Site calls (not simulated HTTP). Do not change other ports, Site/App/Plugin/OAuth, 44 tools or secrets. If still HTTP 525, investigate Tailscale ingress and Mini macOS networking/App Proxy Launcher versus independent userspace daemon; do not shift tailnet identity or configure a new Site without explicit approval.
