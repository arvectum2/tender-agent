# EIS SOAP getDocsIP — direct Russian network and TLS incident

Date: 2026-10-10. Canonical task TDP-REFACTOR-20261009.
Status: **TLS unavailable on the tested Russian egress networks during official EIS maintenance**. The EIS 16.3 maintenance notice covers 2026-10-09 22:00 through 2026-10-11 20:00 Moscow time. It lists the official EIS website and user interfaces as unavailable; the exact reason for the getDocsIP TLS reset has not been established independently.

## Confirmed read-only evidence

- Mac mini outbound direct HTTPS (proxies explicitly disabled) was independently
  geolocated RU/Moscow, AS25513 (Moscow City Telephone Network). DNS for
  int.zakupki.gov.ru was 95.167.245.200, also matching an independent DNS
  resolver. The local route used en0 and the home gateway.
- The public zakupki.gov.ru verified TLS and returned an HTTP response.
  That does not prove availability of the separate integration service.
- A genuine getDocsIP SOAP POST with the locally configured individual token,
  over a proxy-free urllib connection, failed with Connection reset by peer
  in approximately 0.02 seconds, prior to SOAP/HTTP reply.
- Independent direct macOS curl and TLS 1.2 OpenSSL handshake to the
  integration host also reset before ServerHello/certificate exchange.
- The new read-only preflight classified integration status as
  connection_reset_during_tls in 18ms and the public EIS HTTPS host
  as verified_tls in 40ms. It did not transmit the SOAP token.
- A separate Russian hosting egress produced the same integration TLS reset
  in approximately 18ms while its public EIS HTTPS worked.
  No token was copied to this host.
- Previous real getDocsIP success is documented in
  docs/r3/operator_session_preflight.md. This demonstrates the service
  had worked, but does not prove the current failure is permanent.

## Official endpoint and certificate changes

EIS communications retired old int44.zakupki.gov.ru and int223.zakupki.gov.ru
starting 2025-10-04 and designated int.zakupki.gov.ru for integration
with one-way GOST and supported non-GOST 44-FZ TLS clients.
The product's getDocsIP default already uses the new address. We updated
the deprecated services-vbs default hostname as well; its legacy method
cannot be validated while integration TLS is unavailable.

In July 2026 EIS changed its publicly trusted certificate. This
incident is **not proven to be a certificate-chain failure** because
the integration peer resets before certificate verification; the
public EIS host verifies successfully with current system trust.

Official EIS 16.3 maintenance announcement (9-11 October 2026):
https://t.me/s/gis_eiszakupki/3282
Official EIS domain migration notice:
https://t.me/s/gis_eiszakupki/2579
Independent public bulletin mirroring EIS changes:
https://xn--80aahqcqybgko.xn--p1ai/141/96/40252/40305/87931.html
Certificate transition bulletin:
https://xn--80aahqcqybgko.xn--p1ai/141/96/40332/40368/91114.html

## Fast deterministic operator check

From the Mac mini Russian egress, with no proxy:

    python scripts/ops/check_eis_direct.py --timeout 3

The probe uses an actual direct socket, verified native TLS and strict
official-host allowlist. It distinguishes DNS/TCP/TLS/CA errors and exits
with status 2 when integration TLS is unavailable. It does not send SOAP.
A passing TLS preflight is not proof that SOAP is available.

Only if TLS succeeds, opt in to exactly one authenticated read-only POST:

    python scripts/ops/check_eis_direct.py --timeout 3 --soap 0352300080626000109

Output is bounded JSON; no token, XML, archives or signed URLs. The
SOAP operation is explicitly opt-in to avoid unnecessary requests when
the peer is resetting. Do not turn this into aggressive polling.

Do not disable TLS verification, enable a proxy, pin a fixed DNS address,
install unverified root certificates, rotate tokens blindly or fabricate
facts from missing EIS source files.

## Escalation and unresolved acceptance gates

After 2026-10-11 20:00 Moscow time, recheck direct TLS and one authorized read-only SOAP request. If failure persists after maintenance, ask EIS integration support for confirmation
of service availability and supported non-GOST TLS ciphers/SNI on
int.zakupki.gov.ru, whether source IPv4 registration is mandatory, and
whether a known maintenance incident or edge ACL is involved. Attach only
timestamped sanitized diagnostic statuses and both RU network observations.
Never send individual authorization tokens.

The verified current failure is at the TCP-to-TLS boundary: it cannot be
repaired by editing an XML envelope in Tender Agent. Other explanations,
including an EIS-side incident, intermediary filtering common to both
Russian network paths, or a changed cipher policy, remain hypotheses.

R5 remains blocked for new originals: when TLS recovers, validate a
single authenticated getDocsIP response, archive, resource/chunk IDs,
persisted verified EIS metadata, source-truth JSON/HTML/PDF/DOCX and
human-reviewed corpus >=20 unique procurements. Preserve production
data, disabled watchdog and existing private pilot.
