"""Append novel archive identities only; never replace an earlier source observation."""
from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime

from scripts.research.import_gpb_geh_snapshots import import_rows, normalize


def separate(entries, existing):
    novel, replay, changed = [], [], []
    seen = set()
    for entry in entries:
        row = normalize(entry)
        key = row["external_id"]
        if key in seen:
            raise ValueError("repeated accepted identity")
        seen.add(key)
        prior = existing.get(key)
        if prior is None:
            novel.append(entry)
        elif prior == row["content_hash"]:
            replay.append(key)
        else:
            changed.append({"external_id": key, "prior_hash": prior,
                            "incoming_hash": row["content_hash"]})
    return novel, replay, changed


def apply(session, payload):
    from sqlalchemy import func, select

    from src.tender_research.models import ProcurementTender

    if payload.get("schema") != "gpb_deadline_archive_v1":
        raise ValueError("unexpected archive schema")
    table = ProcurementTender.__table__
    rows = payload["accepted"]
    if not 1 <= len(rows) <= 25000:
        raise ValueError("invalid archive batch size")
    ids = [normalize(e)["external_id"] for e in rows]
    where = table.c.source == "etp_gpb"
    before = session.execute(select(func.count()).select_from(table).where(where)).scalar_one()
    existing = dict(session.execute(select(table.c.external_id, table.c.content_hash)
                                    .where(where, table.c.external_id.in_(ids))).all())
    novel, replay, changed = separate(rows, existing)
    result = import_rows(session, novel) if novel else {"inserted": 0, "verified": 0}
    after = session.execute(select(func.count()).select_from(table).where(where)).scalar_one()
    if result["inserted"] != len(novel) or after - before != len(novel):
        raise ValueError("archive insertion count mismatch")
    return {"inserted": len(novel), "exact_replay": len(replay),
            "existing_changed_observations_retained": len(changed), "before": before, "after": after,
            "review_count": len(payload["review"]), "completed_partitions": payload["completed_partitions"],
            "changed": changed, "verified_at": datetime.now(UTC).isoformat()}


def main():
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    engine = create_engine(os.environ["AI_CORP_DATABASE_URL"])
    with Session(engine) as session, session.begin():
        if session.execute(text("select current_database()")).scalar_one() != "arvectum_local":
            raise ValueError("unexpected working database")
        result = apply(session, json.load(sys.stdin))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
