"""Cross-check procurement outcomes without granting gold or writing to databases.

Combines original EIS protocol bytes (Kaluga), pre-existing archival derived
statistic (Aksay), and manually reviewed ETP email METADATA (not email bodies).
"""
from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path

from scripts.procurement_llm.source_recovery import inspect_final_eis_protocol

AKSAY = "0158300034526000388"
KALUGA = "0137200001226007700"
AKSIOMA = "0187200001726001304"
MUSEUM = "0372200172326000015"
EXPECTED = {
    "etp-aksay-20261005-receipt-v1": AKSAY,
    "etp-aksay-20261006-receipt-v1": AKSAY,
    "etp-museum-20261012-receipt-v1": MUSEUM,
    "etp-museum-20261015-receipt-v1": MUSEUM,
    "etp-axioma-20261004-submitted-v1": AKSIOMA,
    "etp-kaluga-20261005-app206-v1": KALUGA,
    "etp-kaluga-20261007-withdrawal-v1": KALUGA,
    "etp-kaluga-20261008-app193-admitted-v1": KALUGA,
}
MAX_JSON = 1024 * 1024


def _json(path: Path) -> tuple[dict, str]:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_JSON:
        raise ValueError("Missing, symlinked or oversized original evidence")
    raw = path.read_bytes()
    parsed = json.loads(raw.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise TypeError("Evidence must be JSON object")
    return parsed, sha256(raw).hexdigest()


def audit_outcomes(
    *,
    aksay_statistics: Path,
    kaluga_archive: Path,
    operator_batch: Path,
) -> dict:
    """Only source-bound, privacy-limited summaries; never exported source text."""
    archive, archive_sha = _json(aksay_statistics)
    summary = archive.get("summary")
    if not isinstance(summary, dict) or summary.get("procurement_number") != AKSAY:
        raise ValueError("Wrong Aksay snapshot registry number")
    if summary.get("applications_total") != 55 or summary.get("applications_admitted") != 45:
        raise ValueError("Unexpected archived Aksay protocol population")
    if summary.get("our_price_rub") != 119000 or summary.get("our_rank") != 38:
        raise ValueError("Unexpected derived Aksay result fields")
    if summary.get("winner_price_rub") != 28400 or summary.get("our_status") != "admitted":
        raise ValueError("Unexpected derived Aksay status or winner price")
    if not 1 <= summary["our_rank"] <= summary["applications_total"]:
        raise ValueError("Impossible Aksay rank")

    batch, batch_sha = _json(operator_batch)
    if batch.get("schema") != "manual-candidate-import-v1":
        raise ValueError("Unsupported private ETP batch schema")
    items = batch.get("items")
    if not isinstance(items, list) or len(items) != len(EXPECTED):
        raise ValueError("Unreviewed ETP event set")
    by_id = {}
    for event in items:
        if not isinstance(event, dict):
            raise TypeError("Expected metadata object")
        name = event.get("event_id")
        if name not in EXPECTED or name in by_id:
            raise ValueError("Missing, duplicate or foreign ETP event")
        if (
            event.get("procurement_ref") != EXPECTED[name]
            or not event.get("owner_identity_verified_by_etp_email")
            or not event.get("email_message_ids")
            or event.get("raw_emails_copied") is not False
            or event.get("training_label_approved") is not False
            or event.get("legal_gold") is not False
        ):
            raise ValueError("Event provenance/source-scope check failed")
        by_id[name] = event
    if set(by_id) != set(EXPECTED):
        raise ValueError("ETP event set incomplete")
    withdrawal = by_id["etp-kaluga-20261007-withdrawal-v1"]
    if withdrawal.get("application_number") is not None or withdrawal.get("participation") != "unknown":
        raise ValueError("Withdrawal cannot be bound to an application")
    if by_id["etp-kaluga-20261008-app193-admitted-v1"].get("application_number") != "193":
        raise ValueError("Incorrect accepted Kaluga application")

    eis = inspect_final_eis_protocol(kaluga_archive, KALUGA, "193")
    if eis["admitted_in_protocol"] != "true" or eis["final_price_rub"] != "449000.00":
        raise ValueError("Official Kaluga outcome changed unexpectedly")
    if by_id["etp-kaluga-20261008-app193-admitted-v1"]["original_eis_zip_sha256"] != eis["original_archive_sha256"]:
        raise ValueError("Kaluga private event no longer matches ZIP SHA")
    if by_id["etp-kaluga-20261008-app193-admitted-v1"]["original_eis_xml_sha256"] != eis["protocol_xml_sha256"]:
        raise ValueError("Kaluga private event no longer matches XML SHA")
    return {
        "verified_procurement_refs": 4,
        "operator_metadata_events_verified": len(by_id),
        "operator_email_bodies_rechecked_in_this_offline_audit": False,
        "original_eis_zip_sha256_verified": True,
        "kaluga": {
            "registry_number": KALUGA,
            "application_number": "193",
            "admitted_in_eis": True,
            "final_price_rub": 449000,
            "protocol_application_rating": eis["application_rating"],
            "operator_company_attribution": "previously_reviewed_company_eto_email_metadata",
            "withdrawal_application_number": None,
            "withdrawal_attributed_to_app206": False,
        },
        "aksay": {
            "registry_number": AKSAY,
            "submitted_operator_receipt_events": 2,
            "archived_snapshot_sha256": archive_sha,
            "archived_snapshot_status": "derived_statistics_not_reverified_original_protocol",
            "applications_total": 55,
            "applications_admitted": 45,
            "our_derived_rank": 38,
            "our_derived_price_rub": 119000,
            "derived_winner_price_rub": 28400,
        },
        "aksioma": {
            "registry_number": AKSIOMA,
            "operator_application_ordinal": "3630084",
            "our_bid_rank_proven_by_original_protocol": False,
            "our_bid_price_proven_by_original_protocol": False,
        },
        "museum": {
            "registry_number": MUSEUM,
            "operator_received_events": 2,
            "official_outcome_available_in_audit": False,
            "scheduled_result_date": "2026-10-20",
        },
        "private_event_batch_sha256": batch_sha,
        "pending_event_apply_executed": False,
        "new_postgres_records": 0,
        "approved_training_labels": 0,
        "mutations": 0,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--aksay-statistics", required=True, type=Path)
    p.add_argument("--kaluga-original-zip", required=True, type=Path)
    p.add_argument("--private-operator-batch", required=True, type=Path)
    args = p.parse_args(argv)
    print(json.dumps(audit_outcomes(
        aksay_statistics=args.aksay_statistics,
        kaluga_archive=args.kaluga_original_zip,
        operator_batch=args.private_operator_batch,
    ), ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
