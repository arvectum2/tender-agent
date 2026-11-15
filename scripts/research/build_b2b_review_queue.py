"""Retain indexed discoveries without making them original platform evidence."""
from __future__ import annotations

from src.tender_research.corporate_lead_gate import triage_corporate_card


def build(snapshot, *, checked_at):
    if snapshot.get("schema") != "b2b_indexed_discovery_v1":
        raise ValueError("unexpected snapshot schema")
    rows = []
    seen = set()
    for row in snapshot["observations"]:
        if row["candidate_key"] in seen:
            raise ValueError("duplicate discovery identity")
        seen.add(row["candidate_key"])
        if row.get("source_kind") not in {"indexed_card_text", "indexed_catalog_text"}:
            raise ValueError("unexpected provenance")
        card = {"source_url":row["source_url"],"platform_status":row["status_text"],
                "organizer_type":row.get("organizer_type"),"submission_deadline":row.get("deadline"),
                "source_observed_at":None}
        decision = triage_corporate_card(card,checked_at=checked_at)
        rows.append({**row,"source_observed_at":None,"result_state":decision.state,
                     "result_reason":decision.reason,"original_platform_verified":False,
                     "bid_ready":False,"legal_eligibility_verified":False})
    return {"schema":"b2b_indexed_review_queue_v1","checked_at":checked_at.isoformat(),
            "candidates":rows,"qualified_current_opportunities":0,"execution_allowed":False}
