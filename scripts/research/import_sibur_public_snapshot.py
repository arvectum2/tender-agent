"""Import an independently SHA-replayed public registry snapshot into TA only."""
from __future__ import annotations

import hashlib
import json
import sys
import uuid
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlsplit

from sqlalchemy import create_engine, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.tender_research.models import ProcurementTender

SOURCE = "sibur_public"
PLATFORM = "SIBUR public procurement registry"


def source_scope(url, archive):
    if not archive:
        return url.startswith("https://www.sibur.ru/ru/procurement/buy/?")
    u = urlsplit(url)
    q = parse_qs(u.query)
    groups = {"107": "1", "108": "1", "109": "1", "112": "1", "132": "1",
              "999_08": "5", "999_10": "5", "999_11": "5"}
    cat = q.get("catNMK", [""])[0]
    page = q.get("PAGEN_1", [""])[0]
    return (u.scheme == "https" and u.netloc == "www.sibur.ru"
            and u.path == "/ru/procurement/buy/archive/" and not u.fragment
            and set(q) == {"PAGEN_1", "count", "catMTR", "catNMK"}
            and all(len(v) == 1 for v in q.values()) and q["count"] == ["12"]
            and cat in groups and q["catMTR"] == [groups[cat]]
            and page.isdecimal() and 1 <= int(page) <= 10000)


def build_rows(groups, *, archive=False):
    rows = []
    seen = set()
    allowed = {
        "external_id", "title", "subject", "method", "published_raw", "deadline_raw",
        "organizer", "status_raw", "category", "documentation_label", "source",
        "source_url", "source_sha256", "verification", "source_row",
        "documentation_urls", "unverified_document_links",
    }
    for group in groups:
        identity = group["external_id"]
        observations = group["observations"]
        if not observations or identity in seen:
            raise ValueError("empty or duplicate group")
        seen.add(identity)
        for row in observations:
            if (row["external_id"] != identity or row["source"] != SOURCE
                    or row["verification"] != "PUBLIC_SNAPSHOT_ONLY"
                    or not source_scope(row["source_url"], archive)
                    or len(row["source_sha256"]) != 64 or set(row) != allowed):
                raise ValueError("source or shape mismatch")
        def agreed(key, observations=observations):
            values = {r[key] for r in observations}
            return next(iter(values)) if len(values) == 1 else None
        published = agreed("published_raw")
        date = datetime.strptime(published, "%d.%m.%Y").replace(tzinfo=UTC) if published else None
        payload = {
            "verification": "PUBLIC_SNAPSHOT_ONLY", "observations": observations,
            "publication_date_precision": "date_only_utc_midnight_storage_convention",
            "deadline_timezone_verified": False,
            "platform_scope": "public registry; authenticated SAP SRM not verified",
        }
        if archive:
            payload["platform_scope"] = "public archive observation; award and signed contract not verified"
        digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                           separators=(",", ":")).encode()).hexdigest()
        now = datetime.now(UTC)
        rows.append({"id": str(uuid.uuid4()), "source": SOURCE, "external_id": identity,
                         "purchase_number": identity, "title": agreed("title") or observations[0]["title"],
                         "description": agreed("subject"), "platform_name": PLATFORM,
                         "platform_url": observations[0]["source_url"],
                         "publication_date": date, "application_deadline": None,
                         "status": agreed("status_raw"), "raw_payload": payload, "content_hash": digest,
                         "first_seen_at": now, "last_seen_at": now, "created_at": now, "updated_at": now})
    return rows


def import_rows(session, rows):
    table = ProcurementTender.__table__
    before = dict(session.execute(select(table.c.source, func.count()).group_by(table.c.source)).all())
    inserted = 0
    for row in rows:
        result = session.execute(insert(table).values(**row).on_conflict_do_nothing(
            index_elements=["source", "external_id"]).returning(table.c.id))
        inserted += int(result.scalar_one_or_none() is not None)
    actual = dict(session.execute(select(table.c.external_id, table.c.content_hash).where(
        table.c.source == SOURCE, table.c.external_id.in_([r["external_id"] for r in rows]))).all())
    if len(actual) != len(rows) or any(actual[r["external_id"]] != r["content_hash"] for r in rows):
        raise ValueError("snapshot conflicts with an existing record; no overwrite allowed")
    after = dict(session.execute(select(table.c.source, func.count()).group_by(table.c.source)).all())
    if {k:v for k,v in before.items() if k != SOURCE} != {k:v for k,v in after.items() if k != SOURCE}:
        raise ValueError("other source count changed")
    return {"inserted": inserted, "verified": len(actual), "by_source": after}


def main():
    import os

    from sqlalchemy import text
    rows = build_rows(json.load(sys.stdin))
    engine = create_engine(os.environ["AI_CORP_DATABASE_URL"])
    with Session(engine) as session, session.begin():
        if session.execute(text("select current_database()")).scalar_one() != "arvectum_local":
            raise ValueError("unexpected target database")
        result = import_rows(session, rows)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
