"""Store immutable source-bound protocol decisions on existing document records."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree


def prepare(root):
    from scripts.research.capture_gpb_priority_details import Visible
    from scripts.research.link_gpb_document_receipts import prepare as prepare_originals
    from scripts.research.read_gpb_named_decisions import parse_named_protocol
    from scripts.research.read_gpb_protocol_decisions import parse_protocol

    rows = []
    for receipt in prepare_originals(root):
        if receipt.get("document_role") != "published_protocol":
            continue
        raw = (root / "originals" / receipt["file"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != receipt["sha256"]:
            raise ValueError("protocol original mismatch")
        try:
            decision = parse_protocol(raw)
        except (ValueError, KeyError, zipfile.BadZipFile, ElementTree.ParseError):
            try:
                detail_raw = (root / (receipt["external_id"].replace(":", "-") + ".html")).read_bytes()
                if hashlib.sha256(detail_raw).hexdigest() != receipt["detail_sha256"]:
                    raise ValueError("detail original mismatch")
                visible = Visible()
                visible.feed(detail_raw.decode("utf8"))
                decision = parse_named_protocol(raw, visible.tokens[0])
            except (ValueError, KeyError, IndexError, zipfile.BadZipFile, ElementTree.ParseError):
                continue
        rows.append({"external_id": receipt["external_id"], "protocol_sha256": receipt["sha256"],
                     "document_url": receipt["document_url"], "parser_schema": "gpb_best_bid_v2",
                     **decision})
    return rows


def attach_decision(meta, row):
    if not meta or meta.get("source") != "etp_gpb":
        raise ValueError("unexpected source metadata")
    refs = meta.get("capture_receipts") or [meta.get("capture_receipt")]
    if not any(r and r.get("sha256") == row["protocol_sha256"]
               and r.get("document_url") == row["document_url"]
               and r.get("external_id") == row["external_id"]
               and r.get("document_role") == "published_protocol" for r in refs):
        raise ValueError("protocol capture evidence mismatch")
    if (row.get("decision") not in {"BEST_BID_SELECTED_NOT_SIGNED_CONTRACT", "PROCEDURE_DECLARED_UNSUCCESSFUL"}
            or row.get("parser_schema") not in {"gpb_best_bid_v2", "gpb_outcome_v3", "gpb_named_outcome_v4"}
            or row.get("participant_legal_identity") is not None
            or row.get("contract_amount") is not None):
        raise ValueError("unsupported or unverified decision")
    if row["parser_schema"] == "gpb_named_outcome_v4" and (
        row.get("decision") != "BEST_BID_SELECTED_NOT_SIGNED_CONTRACT"
        or row.get("participant_platform_id") is not None
        or row.get("participant_identity_verification") != "PUBLISHED_NAME_AND_ADDRESS_IN_EXPLICIT_DECISION_NOT_INN_VERIFIED"
        or not all(row.get(k) for k in ("participant_name_as_published", "participant_address_as_published",
                                        "protocol_procedure_reference", "detail_title_evidence", "protocol_reference_evidence"))
    ):
        raise ValueError("unverified named participant")
    if "protocol_decision" in meta:
        prior = meta["protocol_decision"]
        # The same immutable original may have several publication URLs.
        # Validate the incoming receipt above, keep the first verified decision,
        # and never allow any semantic field to change.
        if {k: v for k, v in prior.items() if k != "document_url"} != {
            k: v for k, v in row.items() if k != "document_url"
        }:
            raise ValueError("prior decision conflicts")
        return meta
    return {**meta, "protocol_decision": row}


def persist(session, rows):
    from sqlalchemy import select, update

    from src.tender_research.models import ProcurementTender, ProcurementTenderDocument

    t, d = ProcurementTender.__table__, ProcurementTenderDocument.__table__
    changed = 0
    for row in rows:
        actual = session.execute(select(d.c.id, d.c.raw_meta)
            .join(t, t.c.id == d.c.tender_id)
            .where(t.c.source == "etp_gpb", t.c.external_id == row["external_id"],
                   d.c.sha256 == row["protocol_sha256"])).one()
        meta = attach_decision(actual.raw_meta, row)
        if meta != actual.raw_meta:
            session.execute(update(d).where(d.c.id == actual.id).values(
                raw_meta=meta, updated_at=datetime.now(UTC)))
            changed += 1
    return {"updated": changed, "verified": len(rows)}


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
        result = persist(session, json.load(sys.stdin))
    print(json.dumps(result))


if __name__ == "__main__":
    main()
