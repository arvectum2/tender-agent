# One-file official EIS original recovery check

The verified getDocsIP SOAP transport returns official XML notices, not all
their binary attachments. The official XML contains attachment UIDs, which
are obtained via a separate public EIS filestore HTTPS GET.

Use the **read-only** recovery probe only after the filestore rate limit has
subsided, with an authorized private original receipt:

    PYTHONPATH=.:src python scripts/ops/recheck_eis_filestore_receipt.py \
      --receipts /authorized/private/receipts.json --index 0

It makes exactly ONE request through the existing production-equivalent
verified-TLS attachment downloader to the allowlisted 44-FZ official
filestore URL. It accepts only the exact HTTPS hostname/path, unique UID
query, 32-hex source UID, historical 64-hex SHA256, expected size (1..30MB)
and private receipt <= 1MB. Redirect, certificate and file bounds are still
enforced by the existing downloader. No credentials, original URLs, local
paths or original bytes are printed or stored.

Exit 0/result=verified only when **both** original SHA256 and byte length
match. Exit 2/result=unavailable for e.g. HTTP429/HTTP404; no automatic
retry and no fake success. Exit 2/result=mismatch for a different binary.
Malformed receipt is rejected before the network. No production/Data Platform
writes, bids, document edits or watchdog automation occur.

The 2026-10-12 single real official probe returned HTTP429, so it is NOT
proof the external filestore is back online. See
TDP_SOAP_BINARY_DOWNLOAD_BOUNDARY_2026-10-12.md for prior verified
168/168 historical cached SHA, 96/96 fresh SOAP XML hashes and remaining
72 official binary retransfer gaps.
