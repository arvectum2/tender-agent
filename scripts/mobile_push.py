#!/usr/bin/env python3
"""Operate Tender Agent mobile push registrations from the Mac mini.

This command only manages notification registrations and due reminders. It
never records a procurement decision or performs an ETP/signature/payment
action.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.modules.mobile_api.push import dispatch_due_deferred_notifications
from src.modules.mobile_api.service import revoke_mobile_device
from src.shared.db import models as _db_models  # noqa: F401
from src.shared.db.session import SessionLocal


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Tender Agent mobile push maintenance")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--due", action="store_true", help="Dispatch due DEFER reminders")
    group.add_argument("--revoke-device", metavar="DEVICE_ID", help="Revoke a lost device")
    return parser


def main() -> int:
    args = _parser().parse_args()
    with SessionLocal() as session:
        if args.revoke_device:
            revoked = revoke_mobile_device(session, device_id=args.revoke_device)
            print(json.dumps({"device_id": args.revoke_device, "revoked": revoked}))
            return 0 if revoked else 4

        summaries = dispatch_due_deferred_notifications(session)
        print(json.dumps([summary.__dict__ for summary in summaries], ensure_ascii=False))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
