"""Operator-only CLI: SHA-verified EIS files -> Data Platform SDK.

Never expose this command to unauthenticated users or accept a tenant id from
an HTTP payload. The trusted environment must originate from server policy.
Dry-run is default and never contacts Data Platform.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from src.modules.market_intelligence.eis_dp_ingest import (
    TrustedTenant,
    ingest_original_eis_documents,
)


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"Server-authenticated operator environment {name} is required")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prevalidate original EIS XML and downloaded bytes before Data Platform ingest",
    )
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--source-archive", type=Path, required=True)
    parser.add_argument("--archive-sha256", required=True)
    parser.add_argument("--original-files-dir", type=Path, required=True)
    parser.add_argument("--subsystem", choices=["RI223", "PRIZ"], required=True)
    parser.add_argument("--source-region", required=True)
    parser.add_argument("--source-date", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--execute", action="store_true",
                        help="Permit authenticated Data Platform writes (default is dry-run)")
    parser.add_argument("--allow-unreviewed-revisions", action="store_true",
                        help="Index ambiguous historical documents but retain review flag")
    args = parser.parse_args()

    from src.modules.market_intelligence.eis_dp_ingest import procurement_collection

    tenant_id = _env("ARVECTUM_MI_AUTH_TENANT_ID")
    consumer_id = _env("ARVECTUM_MI_AUTH_CONSUMER_ID")
    allowlist = frozenset(
        x.strip() for x in _env("ARVECTUM_MI_AUTH_COLLECTION_ALLOWLIST").split(",")
        if x.strip()
    )
    collection_id = procurement_collection(tenant_id, args.run_id)
    if collection_id not in allowlist:
        raise ValueError("Server policy did not authorize target EIS collection")
    if args.receipt.is_symlink() or not args.receipt.is_file():
        raise ValueError("Receipt must be a readable non-symlink file")
    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    trusted = TrustedTenant(
        tenant_id=tenant_id,
        consumer_id=consumer_id,
        authorized_collection_ids=allowlist,
    )
    client = None
    if args.execute:
        from arvectum_data_client import DataPlatformClient

        client = DataPlatformClient(
            base_url=_env("ARVECTUM_DATA_BASE_URL"),
            api_key=_env("ARVECTUM_DATA_API_KEY"),
            consumer=consumer_id,
            consumer_key=_env("ARVECTUM_DATA_CONSUMER_KEY"),
        )
    try:
        output = ingest_original_eis_documents(
            client, receipt=receipt,
            source_archive=args.source_archive,
            original_archive_sha256=args.archive_sha256,
            source_region=args.source_region, source_date=args.source_date,
            subsystem=args.subsystem,
            original_files_dir=args.original_files_dir,
            trusted=trusted, tenant_id=tenant_id, run_id=args.run_id,
            execute=args.execute,
            allow_unreviewed_revisions=args.allow_unreviewed_revisions,
        )
    finally:
        if client is not None:
            client.close()
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
