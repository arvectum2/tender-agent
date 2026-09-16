# Procurement monitoring v1

This module stores source-bound procurement watches, deterministic snapshots/diffs and an internal API feed. It reads existing public-source procurement state and writes only repository-owned monitoring/audit records.

External notification transports (email, SMS, Telegram, customer webhooks/CRM delivery) are intentionally disabled and out of scope. Unsupported or ambiguous source-state changes fail closed to `NEEDS_REVIEW`; the module performs no procurement submission, signing, supplier/customer communication, payment or other external commercial action.
