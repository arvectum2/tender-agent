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

The tool requires PostgreSQL, the production database and role arvectum,
and the arvectum-it profile. Inside REPEATABLE READ READ ONLY it checks
database identity and executes one bounded source SELECT with LEFT JOINs
from every MANAGER_READY item, including items with missing tender or
artifact rows. A missing item-law, wrong 44-FZ law, missing original,
duplicate, or more than 12 joined rows rejects the whole batch; no item
can disappear because it lacks a source. The transaction always rolls
back before a report is emitted. The original file is read from the
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

## 25-Nov source-only completeness and scope hardening

The previous inner join could silently omit a MANAGER_READY item with
no corresponding tender or common-info artifact. This is a false-success
risk; no observed missing source is implied for the 24-Nov eight records.
The revised bounded query keeps missing-source rows so the existing
fail-closed verifier rejects the whole report. Tests execute the actual
SQL against disposable in-memory tables, including absent tender/incorrect
artifact and foreign-profile cases; no production writes.

86 focused tests PASS (42 archived-deadline tests plus the adjacent
read-only status, deadline-precision and exit20 regressions); Ruff PASS.
Read-only smoke on existing pinned Python using isolated source:
24-Nov run DTR-20261124T050008Z-87f721ac, 8/8 archived records;
25-Nov run DTR-20261125T050005Z-cd0a5087, 3/3 archived records.
All 11 stored DTR deadlines absent; current_revision_verified false,
zero external source requests, zero database mutations.
25-Nov latest actual DTR WAITING_HUMAN: 47 items, 23 duplicate,
20 screened out, 3 manager-ready and 1 failed. No failure recovery or
decision was made by the archive tool.
Issue #746 remains OPEN for current revision verification and approved
production integration. No deployed runtime or resource gate changed.
