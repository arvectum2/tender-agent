# Archived EIS deadline evidence — read-only operator tool

Scope: **historical EIS snapshot only**. This tool does **not** prove the
current, unamended EIS notice/revision, does not authorize any ETP action,
and never changes the DTR deadline_at field or its screening decisions.

## Invocation on an authorized source checkout

Use the existing production runtime environment read-only. Example:

    set -a
    source "$HOME/Library/Application Support/Arvectum/daily-tender-runtime.env"
    set +a
    PYTHONPATH=/path/to/verified/tender-agent/source \
      python -m scripts.ops.read_dtr_archived_eis_deadlines \
      --run-id DTR-20261124T050008Z-87f721ac \
      --archive-root /Volumes/ArvectumSSD/Arvectum/data/tenders/eis

The output includes source status ARCHIVED_ONLY, archived_deadline_utc,
official_timezone, artifact_registered_utc, and SHA256 fields. The
registration time is the database artifact creation time, NOT proof of
the exact HTTP fetch timestamp or current official EIS state. The explicit
current_revision_verified: false flag is mandatory; no consumer may
silently promote this result into deadline_at or active screening.

The tool executes one bounded SELECT joining the existing run's
MANAGER_READY items to stored procurement_raw_artifacts, inside
SET TRANSACTION READ ONLY. The original file is read from the
expected eis/<registry>/raw/public_detail_common_info.html path
and is bounded by the existing 6 MiB EIS HTML limit.

Admission requires exactly one source record per registry, expected
44-FZ source, exact first-party HTTPS URL, registry matching database
metadata and HTML identity, matching SHA256 and byte length,
owner-controlled non-writable directories and non-symlink regular
file, aware artifact registration time, strict EIS exact clock parser.

Any missing, duplicate, tampered, unsafe or malformed source
makes the entire batch fail closed (exit code 2, generic
ARCHIVED_EIS_UNVERIFIED). No private paths/document bytes in errors.
No HTTP clients, source downloads or database writes are used.

## Verified 24-Nov-2026 evidence

Read-only production DB and file audit found exactly 8 matching
procurement_raw_artifacts, all registered 24-Nov with matching hash,
length, notice identity and official URL. Real 8/8 smoke on the
source candidate, in the existing venv and isolated PYTHONPATH,
returned eight archived-only UTC deadlines, zero network requests,
zero DB mutations, and all stored DTR deadlines still absent.

This code is **source-only**, NOT installed in production. The prior
live EIS exact-proof path still needs owner-approved evidence root
configuration and independently permitted network requests; enabling
ARVECTUM_DAILY_EIS_EVIDENCE_ROOT may trigger a live EIS GET.

Issue #746 remains OPEN: current revision verification and
safe integration into live DTR still need separate admission.
Human approval, original-rights/financial gates and ETP actions
remain completely separate.
