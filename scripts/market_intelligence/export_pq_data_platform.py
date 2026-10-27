"""Offline, idempotent Data Platform resource staging from MI-013 v8.

Produces JSONL to stdout. Does not connect to PostgreSQL or mutate any system.
The downstream ingester must independently validate permissions and data contracts.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from materialize_pq_research import materialize

COLLECTION_ID = "arvectum-market-pq-6-35kv"
SOURCE_TYPE = "market_intelligence_procurement_research"


def export_records() -> list[dict]:
    data = materialize()
    output = []
    ids = set()
    uris = set()
    for row in data["records"]:
        key = row["canonical_id"]
        identifier = hashlib.sha256(key.encode("utf-8")).hexdigest()
        resource_id = identifier[:48]
        canonical_uri = f"urn:arvectum:pq:procurement:{identifier}"
        if resource_id in ids or canonical_uri in uris:
            raise ValueError(f"duplicated resource {key}")
        ids.add(resource_id)
        uris.add(canonical_uri)
        evidence = row.get("evidence") or []
        if not evidence or not all(e.get("url", "").startswith("https://") for e in evidence):
            raise ValueError(f"no web-linked source evidence for {key}")
        content = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        metadata = {
            "data_version": "v8",
            "procurement_id": key,
            "procedure_id": row.get("procedure_id"),
            "date_basis": row.get("date_basis"),
            "publication_date": row.get("publication_date"),
            "deadline_date": row.get("deadline_date"),
            "regime": row.get("procurement_regime"),
            "family": row.get("family"),
            "scope": row.get("scope"),
            "market_scope": row.get("market_scope"),
            "buyer": row.get("customer"),
            "status": row.get("status"),
            "nmck_rub": row.get("nmck_rub"),
            "reported_price_kind": row.get("reported_price_kind"),
            "original_primary_registry_verified": bool(
                (row.get("registry_contract") or {}).get("signed_contract_registry_verified")
            ),
            "source_urls": [e["url"] for e in evidence],
            "source_tiers": [e.get("source_tier") for e in evidence],
            "research_not_market_population": True,
            "winning_supplier_only_if_verified": row.get("supplier_inn")
            if row.get("supplier_verified") is True else None,
        }
        output.append({
            "collection_id": COLLECTION_ID,
            "source_type": SOURCE_TYPE,
            "resource_id": resource_id,
            "canonical_uri": canonical_uri,
            "external_id": key,
            "content_hash": content_hash,
            "status": "staged_unreviewed",
            "metadata": metadata,
            "text": row.get("description") or "",
            "source_record": row,
        })
    if len(output) != data["verification_summary"]["total_records"]:
        raise ValueError("export count mismatch")
    return output


def main() -> int:
    for item in export_records():
        sys.stdout.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
