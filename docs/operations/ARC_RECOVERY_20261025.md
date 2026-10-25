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