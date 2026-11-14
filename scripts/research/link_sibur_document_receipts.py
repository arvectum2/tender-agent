"""Link verified private capture receipts to existing SIBUR tender identities."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import uuid
from datetime import UTC, datetime

from sqlalchemy import create_engine, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.tender_research.models import ProcurementTender, ProcurementTenderDocument

SOURCE = "sibur_public"
COLLECTION = "tender-agent:sibur-public-research"


def reconcile_meta(actual, proposed):
    """Allow monotonic evidence additions, never removal or replacement."""
    if actual == proposed:
        return False
    if not actual or set(actual) != set(proposed):
        raise ValueError("existing metadata differs; explicit reconciliation required")
    base = {"capture_receipts", "dp_index"}
    if {k: v for k, v in actual.items() if k not in base} != {
        k: v for k, v in proposed.items() if k not in base
    }:
        raise ValueError("existing metadata differs; explicit reconciliation required")
    previous = {json.dumps(x, sort_keys=True, ensure_ascii=False) for x in actual["capture_receipts"]}
    current = {json.dumps(x, sort_keys=True, ensure_ascii=False) for x in proposed["capture_receipts"]}
    if not previous <= current:
        raise ValueError("existing source receipt removed or replaced")
    if actual["dp_index"] is not None and actual["dp_index"] != proposed["dp_index"]:
        raise ValueError("existing DP index receipt removed or replaced")
    return True


def link(session, captures, indexed):
    tender = ProcurementTender.__table__
    doc = ProcurementTenderDocument.__table__
    groups = {}
    for receipt in captures:
        sha = receipt["sha256"]
        if receipt["status"] != "captured" or len(sha) != 64:
            raise ValueError("unverified capture")
        for ref in receipt["references"]:
            key = (ref["external_id"], sha)
            group = groups.setdefault(key, {"captures": [], "sha": sha})
            group["captures"].append({
                "url": receipt["url"], "bytes": receipt["bytes"],
                "mime": receipt["mime"], "file": receipt["file"], "reference": ref,
            })
    added = 0
    for (external_id, sha), group in sorted(groups.items()):
        t = session.execute(select(tender.c.id, tender.c.raw_payload).where(
            tender.c.source == SOURCE, tender.c.external_id == external_id
        )).one()
        for capture in group["captures"]:
            ref = capture["reference"]
            if not any(o["source_sha256"] == ref["source_sha256"]
                       and o["source_row"] == ref["source_row"]
                       and o["source_url"] == ref["source_url"]
                       and capture["url"] in o["documentation_urls"]
                       for o in t.raw_payload["observations"]):
                raise ValueError("capture not linked to original DB observation")
        items = sorted(group["captures"], key=lambda c: (c["url"], c["reference"]["source_row"]))
        first = items[0]
        meta = {"source": SOURCE, "capture_status": "verified_private_original",
                "capture_receipts": items, "dp_index": indexed.get(sha)}
        if meta["dp_index"]:
            dp = meta["dp_index"]
            if (dp["collection_id"] != COLLECTION or dp["canonical_uri"] != "content-sha256://" + sha
                    or dp["extraction_status"] != "extracted" or not dp["embeddings"]):
                raise ValueError("invalid persistent DP receipt")
        now = datetime.now(UTC)
        # Keep TA download/extraction pending until its own file-serving path is implemented.
        # External captures and DP processing state are represented explicitly in raw_meta.
        values = {
            "id": str(uuid.uuid4()), "tender_id": t.id,
            "source_document_id": hashlib.sha256(first["url"].encode()).hexdigest(),
            "file_name": first["file"], "file_url": first["url"],
            "size_bytes": first["bytes"], "content_type": first["mime"],
            "sha256": sha, "download_status": "pending", "text_extraction_status": "pending",
            "raw_meta": meta, "created_at": now, "updated_at": now,
        }
        result = session.execute(insert(doc).values(**values).on_conflict_do_nothing(
            index_elements=["tender_id", "sha256"]).returning(doc.c.id))
        added += int(result.scalar_one_or_none() is not None)
        actual = session.execute(select(doc.c.raw_meta).where(
            doc.c.tender_id == t.id, doc.c.sha256 == sha).with_for_update()).scalar_one()
        if reconcile_meta(actual, meta):
            session.execute(update(doc).where(
                doc.c.tender_id == t.id, doc.c.sha256 == sha).values(
                    raw_meta=meta, updated_at=now))
    return {"inserted": added, "verified_links": len(groups),
            "distinct_originals": len({sha for _, sha in groups}),
            "indexed_links": sum(sha in indexed for _, sha in groups)}


def main():
    payload = json.load(sys.stdin)
    engine = create_engine(os.environ["AI_CORP_DATABASE_URL"])
    with Session(engine) as session, session.begin():
        if session.execute(text("select current_database()")).scalar_one() != "arvectum_local":
            raise ValueError("unexpected database")
        result = link(session, payload["captures"], payload["indexed"])
    print(json.dumps(result))


if __name__ == "__main__":
    main()
