"""Link independently captured GPB documents to their source list identities."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path


def prepare(root):
    from src.modules.tender_connectors.etp_gpb.documents import parse_document_links

    captures = json.loads((root / "document-pilot-receipts.json").read_text())
    details = {r["external_id"]: r for r in json.loads((root / "receipts.json").read_text())}
    result = []
    for row in captures:
        if row["capture_status"] != "captured":
            continue
        detail = details[row["external_id"]]
        raw = (root / (row["external_id"].replace(":", "-") + ".html")).read_bytes()
        if (detail["status"] != 200 or not detail["number_present"]
                or hashlib.sha256(raw).hexdigest() != detail["sha256"]):
            raise ValueError("detail receipt mismatch")
        links = parse_document_links(raw, detail_url=detail["final_url"],
                                     external_id=row["external_id"])
        if not any(all(row[k] == v for k, v in link.items()) for link in links):
            raise ValueError("document not published on exact detail")
        f = root / "originals" / row["file"]
        if (f.is_symlink() or f.parent != root / "originals"
                or f.stem != row["sha256"] or f.stat().st_size != row["bytes"]
                or hashlib.sha256(f.read_bytes()).hexdigest() != row["sha256"]):
            raise ValueError("original mismatch")
        result.append({**row, "list_source_sha256": detail["source_sha256"],
                       "list_detail_url": detail["source_url"]})
    return result


def link(session, rows):
    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert

    from src.tender_research.models import ProcurementTender, ProcurementTenderDocument

    t, d = ProcurementTender.__table__, ProcurementTenderDocument.__table__
    inserted = 0
    for row in rows:
        if row["source"] != "etp_gpb" or row["capture_status"] != "captured":
            raise ValueError("unexpected source")
        if not re.fullmatch("[0-9a-f]{64}", row["sha256"]):
            raise ValueError("invalid source hash")
        tender = session.execute(select(t.c.id, t.c.raw_payload).where(
            t.c.source == "etp_gpb", t.c.external_id == row["external_id"])).one()
        obs = tender.raw_payload["observation"]
        if (obs["source_sha256"] != row["list_source_sha256"]
                or obs["detail_url"] != row["list_detail_url"]):
            raise ValueError("list provenance mismatch")
        meta = {"source": "etp_gpb", "capture_status": "verified_private_original",
                "capture_receipt": row, "dp_index": None}
        now = datetime.now(UTC)
        result = session.execute(insert(d).values(
            id=str(uuid.uuid4()), tender_id=tender.id,
            source_document_id=hashlib.sha256(row["document_url"].encode()).hexdigest(),
            file_name=row["original_filename"], file_url=row["document_url"],
            size_bytes=row["bytes"], content_type=row["mime"], sha256=row["sha256"],
            download_status="pending", text_extraction_status="pending",
            raw_meta=meta, created_at=now, updated_at=now,
        ).on_conflict_do_nothing(index_elements=["tender_id", "sha256"]).returning(d.c.id))
        inserted += int(result.scalar_one_or_none() is not None)
        actual = session.execute(select(d.c.raw_meta).where(
            d.c.tender_id == tender.id, d.c.sha256 == row["sha256"])).scalar_one()
        if actual != meta:
            raise ValueError("existing document differs")
    return {"inserted": inserted, "verified_links": len(rows)}


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--prepare":
        print(json.dumps(prepare(Path(sys.argv[2])), ensure_ascii=False))
        return
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    engine = create_engine(os.environ["AI_CORP_DATABASE_URL"])
    with Session(engine) as session, session.begin():
        if session.execute(text("select current_database()")).scalar_one() != "arvectum_local":
            raise ValueError("unexpected database")
        result = link(session, json.load(sys.stdin))
    print(json.dumps(result))


if __name__ == "__main__":
    main()
