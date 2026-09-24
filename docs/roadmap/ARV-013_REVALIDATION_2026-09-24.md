# ARV-013 revalidation — 2026-09-24

ARV-013 historically requires replacing temporary CloudPub ingress with public HTTPS on a VPS and SSH/Tailscale administrative access. This slice is repository-only: it does not create a VPS, change DNS/TLS/network state, establish Tailscale/SSH access, or stop CloudPub.

## Current evidence

- `STATUS.md` still identifies CloudPub as temporary ingress and states that its long-term reliability/SLA is not proven.
- `docs/ops/r0/FINAL_REPORT.md` and `docs/ops/r0/BLOCKERS.md` preserve `PUBLIC_RELIABILITY_LIMITED_NOT_PROVEN` and explicitly block declaring CloudPub permanent production infrastructure.
- `docs/ops/arv-011-infrastructure-requirements.md` describes the desired VPS/reverse-proxy/TLS topology but also records that the main deployment has no production reverse proxy.
- `deploy/pilot/compose.yaml`, `deploy/pilot/nginx.conf` and `ops/nginx/*` provide bounded reverse-proxy preparation/examples; they are not evidence of a live VPS deployment.
- `scripts/local/start_cloudpub_tunnel.sh`, `check_macmini_backend.sh` and `stop_tunnels.sh` remain the local temporary-ingress lifecycle. `bash -n` passes for all three scripts in this revalidation.

## Proven residual

No repository-owned attributable evidence found in this slice proves that public HTTPS on a VPS plus SSH/Tailscale admin access has replaced CloudPub or that CloudPub has been retired. Therefore ARV-013 is not silently marked complete.

A future implementation/migration must be separately admitted and carry applicable production/network/provider authority. This revalidation does not choose a VPS, DNS/TLS design, VPN/overlay provider, or migration plan.
