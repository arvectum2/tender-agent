"""Validate hand-reviewed commission outcomes against immutable ARC packets.

This proves what commission protocols *state*, not signatures, conclusion of a
contract, delivery or a supplier's final economic role.
"""
from __future__ import annotations
import argparse
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path


def _normal(value: str) -> str:
    return " ".join(value.split())


def verify(*, facts: Path, queue: Path) -> dict:
    src = json.loads(facts.read_text(encoding="utf-8"))
    if src.get("schema_version") != "pq-commission-facts/1":
        raise ValueError("Unexpected commission facts schema")
    results = []
    for row in src["facts"][:200]:
        identity = str(row["queue_id"])
        number = str(row["procedure_id"])
        if not identity.startswith(number + "-") or any(
                c not in "0123456789abcdef-" for c in identity):
            raise ValueError("Invalid ARC queue identity")
        packet_file = queue / (identity + ".json")
        if packet_file.is_symlink():
            raise ValueError("Symlinked review record")
        packet = json.loads(packet_file.read_text(encoding="utf-8"))
        if (packet.get("schema_version") != "pq-review-queue/1"
                or packet.get("state") != "reviewed"
                or packet.get("packet", {}).get("registry_number") != number):
            raise ValueError("Only reviewed source-bound packets can establish protocol facts")
        doc = next((x for x in packet["packet"]["documents"]
                    if x.get("sha256") == row["source_sha256"]), None)
        if doc is None:
            raise ValueError("Source document SHA missing from reviewed queue")
        text = _normal(doc.get("text") or "")
        if not _normal(row["source_quote"]) in text:
            raise ValueError("Quoted commission decision missing in source document")
        if not _normal(row["amount_quote"]) in text:
            raise ValueError("Quoted proposed offer amount missing in source document")
        if not _normal(row["nmck_quote"]) in text:
            raise ValueError("Quoted NMCK amount missing in source document")
        if not _normal(row["proposed_or_selected_participant"]) in _normal(row["source_quote"]):
            raise ValueError("Named participant not bound to commission decision quote")
        try:
            offer = Decimal(row["offer_rub"])
            initial = Decimal(row["nmck_rub"])
        except InvalidOperation as exc:
            raise ValueError("Invalid numeric offer or NMCK") from exc
        if offer < 0 or initial <= 0:
            raise ValueError("Invalid non-positive offer/NMCK")
        if row.get("signed_contract_verified") or row.get("supplier_of_signed_contract_verified"):
            raise ValueError("Commission minutes alone cannot certify signed contract supplier")
        results.append({
            "procedure_id": number,
            "lot": row.get("lot"),
            "market_category": row["market_category"],
            "committee_participant": row["proposed_or_selected_participant"],
            "decision_type": row["decision_type"],
            "price_kind": row["price_kind"],
            "bid_price_rub": str(offer),
            "initial_price_rub": str(initial),
            "bid_minus_nmck_rub": str(offer - initial),
            "source_sha256": row["source_sha256"],
            "source_quote": row["source_quote"],
            "signed_contract_verified": False,
            "supplier_of_signed_contract_verified": False,
            "commission_decision_source_verified": True,
            "ocr_visual_review_required": doc.get("method") == "ocr_unverified",
        })
    return {
        "schema_version": "pq-commission-fact-audit/1",
        "facts_accepted": len(results),
        "verified_signed_contracts": 0,
        "records": results,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--facts", type=Path, required=True)
    p.add_argument("--queue", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    result = verify(facts=a.facts, queue=a.queue)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "records"},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
