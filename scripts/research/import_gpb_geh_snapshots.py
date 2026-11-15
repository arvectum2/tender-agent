"""Persist verified GEH-section GPB list observations, not award outcomes."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

SOURCE = "etp_gpb"
MONTHS = {name: i for i, name in enumerate(
    ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"], 1)}


def parse_date(value):
    m = re.fullmatch(r"(\d{1,2}) ([а-я]+) (\d{4}), (\d{2}):(\d{2}) Z", value)
    if not m or m[2] not in MONTHS:
        raise ValueError("unknown timestamp format")
    return datetime(int(m[3]), MONTHS[m[2]], int(m[1]), int(m[4]), int(m[5]), tzinfo=UTC)


def stage_for(url):
    u = urlsplit(url)
    q = parse_qs(u.query)
    stages = q.get("procedure[stage][0]")
    if (u.scheme != "https" or u.netloc != "etpgpb.ru" or u.path != "/procedures/"
            or q.get("procedure[section][0]") != ["geh_group"]
            or stages not in (["accepting"], ["completed"])
            or any(k.startswith("procedure[section]") and k != "procedure[section][0]" for k in q)
            or any(k.startswith("procedure[stage]") and k != "procedure[stage][0]" for k in q)):
        raise ValueError("unexpected GEH scope")
    return stages[0]


def price_for(value):
    if value == "Цена не указана":
        return None
    if not re.fullmatch(r"[\d \xa0]+(?:,\d{2})? ₽", value):
        raise ValueError("unexpected price")
    return Decimal(value[:-1].replace(" ", "").replace("\xa0", "").replace(",", "."))


def replay(root):
    from src.modules.tender_connectors.etp_gpb.parser import parse_list

    rows = []
    for receipt in json.loads((root / "gpb-geh-section-receipts.json").read_text()):
        if receipt.get("status") != 200:
            raise ValueError("failed source receipt")
        name = receipt["name"]
        if not re.fullmatch(r"geh_(?:active|hist)_p[0-9]+", name):
            raise ValueError("unexpected receipt name")
        raw = (root / (name + ".html")).read_bytes()
        if hashlib.sha256(raw).hexdigest() != receipt["sha256"]:
            raise ValueError("original SHA mismatch")
        stage_for(receipt["url"])
        items = parse_list(raw, receipt["url"])
        if len(items) != receipt["rows"] or [r["external_id"] for r in items] != receipt["ids"]:
            raise ValueError("replay count/identity mismatch")
        for row in items:
            rows.append({"observation": row, "observed_at": receipt["observed_at"]})
    return rows


def normalize(entry):
    row = entry["observation"]
    observed = datetime.fromisoformat(entry["observed_at"])
    if observed.tzinfo is None or observed > datetime.now(UTC):
        raise ValueError("unverified collection time")
    stage = stage_for(row["source_url"])
    published = parse_date(row["published_raw"])
    deadline = parse_date(row["deadline_raw"])
    if row.get("updated_raw"):
        updated = parse_date(row["updated_raw"])
        if not published <= updated <= observed:
            raise ValueError("inconsistent update timestamp")
    if published > observed or deadline < published:
        raise ValueError("inconsistent source dates")
    if (stage == "accepting" and deadline <= observed) or (stage == "completed" and deadline > observed):
        raise ValueError("source stage/date mismatch")
    if (row["source"] != SOURCE or row["verification"] != "PUBLIC_LIST_OBSERVATION_ONLY"
            or not re.fullmatch(r"(?:[a-z_]+:[0-9]+|gos:[0-9a-f-]{36})", row["external_id"])
            or not re.fullmatch(r"[a-f0-9]{64}", row["source_sha256"])):
        raise ValueError("invalid source-scoped observation")
    price = price_for(row["price_raw"])
    meta = {"verification": row["verification"], "observation": row,
            "group_filter": "geh_group", "stage_filter": stage,
            "observed_at": entry["observed_at"], "award_verified": False,
            "initial_price_decimal": str(price) if price is not None else None}
    digest = hashlib.sha256(json.dumps(meta, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return {"source": SOURCE, "external_id": row["external_id"],
            "purchase_number": row["number_raw"].removeprefix("№").strip(),
            "title": row["title"], "customer_name": row.get("customers_raw"),
            "region": row.get("regions_raw"), "platform_name": "ЭТП ГПБ",
            "platform_url": row["detail_url"], "publication_date": published,
            "application_deadline": deadline, "status": "list:" + stage,
            "nmck_amount": float(price) if price is not None else None,
            "currency": "RUB" if price is not None else None,
            "raw_payload": meta, "content_hash": digest}


def import_rows(session, entries):
    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert

    from src.tender_research.models import ProcurementTender

    table = ProcurementTender.__table__
    values = [normalize(e) for e in entries]
    if len({r["external_id"] for r in values}) != len(values):
        raise ValueError("duplicate batch identity")
    inserted = 0
    now = datetime.now(UTC)
    for row in values:
        result = session.execute(insert(table).values(
            id=str(uuid.uuid4()), first_seen_at=now, last_seen_at=now,
            created_at=now, updated_at=now, **row,
        ).on_conflict_do_nothing(index_elements=["source", "external_id"]).returning(table.c.id))
        inserted += int(result.scalar_one_or_none() is not None)
        actual = session.execute(select(table.c.content_hash).where(
            table.c.source == SOURCE, table.c.external_id == row["external_id"])).scalar_one()
        if actual != row["content_hash"]:
            raise ValueError("existing observation differs; reconcile explicitly")
    return {"inserted": inserted, "verified": len(values),
            "stage_accepting": sum(r["status"] == "list:accepting" for r in values),
            "stage_completed": sum(r["status"] == "list:completed" for r in values),
            "price_present": sum(r["nmck_amount"] is not None for r in values)}


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--replay":
        entries = replay(Path(sys.argv[2]))
        accepted, review = [], []
        seen = set()
        for entry in entries:
            try:
                normalized = normalize(entry)
                if normalized["external_id"] in seen:
                    raise ValueError("repeated observation; review separately")
                seen.add(normalized["external_id"])
            except (ValueError, KeyError) as exc:
                review.append({"entry": entry, "reason": str(exc)})
            else:
                accepted.append(entry)
        print(json.dumps({"accepted": accepted, "review": review}, ensure_ascii=False))
        return
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    engine = create_engine(os.environ["AI_CORP_DATABASE_URL"])
    with Session(engine) as session, session.begin():
        if session.execute(text("select current_database()")).scalar_one() != "arvectum_local":
            raise ValueError("unexpected working database")
        result = import_rows(session, json.load(sys.stdin)["accepted"])
    print(json.dumps(result))


if __name__ == "__main__":
    main()
