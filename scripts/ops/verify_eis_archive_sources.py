"""Audit first-party archived getDocsIP notice and filestore bytes in existing run.

Default offline check is NO-NETWORK and read-only. --live performs only EIS GET/
getDocsIP read-only; --save-receipt writes no binaries or signed URLs. Never
claims current legal notice status or authorizes bids.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

if __package__ in (None, "") and __file__ != "<stdin>":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.modules.tender_operator_agent_demo.eis_archived_source_integrity import (
    RECEIPT_NAME,
    fetch_current_getdocs_and_binaries,
    valid_original_retrieval_timestamp,
    verify_saved_source_snapshot,
)
from src.modules.tender_operator_agent_demo.upload_service import (
    get_demo_run_procurement_dir,
)


def save_receipt(run_id: str, record: dict) -> bool:
    if (record.get("fresh_getdocs_original_zip_matches") is not True
            or record.get("fresh_official_filestore_bytes_match") != record.get("published_links")
            or record.get("current_live_notice_status_verified") is not False
            or record.get("owner_legal_go") is not False):
        raise ValueError("cannot save incomplete or misleading EIS original receipt")
    if not valid_original_retrieval_timestamp(record.get("fresh_observation_utc")):
        raise ValueError("missing, naive or implausibly future original retrieval observation time")
    if record["run_id"] != run_id:
        raise ValueError("receipt run identity mismatch")
    source = verify_saved_source_snapshot(run_id)
    if any(record.get(k) != value for k, value in source.items()):
        raise ValueError("source changed since original EIS GET verification")
    folder = get_demo_run_procurement_dir(run_id)
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("unsafe saved procurement source directory")
    target = folder / RECEIPT_NAME
    contents = json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if target.is_symlink():
        raise ValueError("refusing existing symlink receipt")
    if target.exists():
        if target.read_text("utf8") == contents:
            return False
        raise ValueError("different existing EIS receipt; preserve earlier source record")
    handle, temp = tempfile.mkstemp(prefix=".archived-eis-verify-", suffix=".tmp", dir=folder)
    try:
        os.fchmod(handle, 0o600)
        with os.fdopen(handle, "w", encoding="utf8") as output:
            output.write(contents)
            output.flush()
            os.fsync(output.fileno())
        if target.exists():
            raise ValueError("new receipt appeared before atomic save")
        os.replace(temp, target)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id")
    parser.add_argument("--live", action="store_true", help="read-only official SOAP and 5 filestore GET")
    parser.add_argument("--save-receipt", action="store_true", help="persist safe checksums only, requires --live")
    args = parser.parse_args()
    if args.save_receipt and not args.live:
        parser.error("--save-receipt requires --live")
    try:
        if args.live:
            from src.modules.tender_operator_agent_demo.settings import (
                get_zakupki_soap_settings,
            )
            from src.modules.tender_operator_agent_demo.zakupki_soap_client import (
                ZakupkiSoapClient,
            )

            settings = replace(get_zakupki_soap_settings(), timeout_seconds=15)
            if not (settings.configured and settings.require_direct_ru_route and settings.disable_proxy_for_eis):
                raise ValueError("official EIS direct read-only transport not configured")
            client = ZakupkiSoapClient(settings, runtime_status_enabled=False)
            receipt = fetch_current_getdocs_and_binaries(args.run_id, client=client)
        else:
            receipt = verify_saved_source_snapshot(args.run_id)
        if args.save_receipt:
            receipt["saved_new_receipt"] = save_receipt(args.run_id, receipt)
        print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
        return 0
    except (ValueError, OSError, RuntimeError) as exc:
        # Do not echo exception strings, which could include transport secrets.
        print(json.dumps({"ok": False, "error_type": type(exc).__name__,
                          "live_current_eis_status_verified": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
