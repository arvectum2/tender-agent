"""MI-013 v17: append public archival 2023-25 market enquiries separately from awards.

Research only: never connects to a live database. Source-indexed solicitation
IDs without actual EIS/ETP number are NEVER represented as official IDs.
"""
from __future__ import annotations

import json
from pathlib import Path

from materialize_pq_research_v16 import materialize as v16

DATA=Path(__file__).resolve().parents[2]/"data/market_intelligence/power_quality"
MANIFEST="verified_public_leads_20261027.v17.manifest.json"


def materialize():
    m=json.loads((DATA/MANIFEST).read_text(encoding="utf-8"))
    d=json.loads((DATA/m["delta_file"]).read_text(encoding="utf-8"))
    parent=v16()
    items=list(parent["records"])
    if len(items)!=m["base_rows"] or len(d["records"])!=m["delta_rows"]:
        raise ValueError("v17 parent/delta item count drift")
    seen={r["canonical_id"] for r in items}
    if len(seen)!=len(items):
        raise ValueError("duplicate earlier PQ research record")
    for raw in d["records"]:
        cid=raw["canonical_id"]
        if cid in seen:
            raise ValueError("repeated archive source: "+cid)
        date=raw.get("publication_date")
        event_date=raw.get("source_event_date")
        if date is None:
            if raw["date_basis"]!="final_date_known_publication_date_unverified":
                raise ValueError("missing publication date without original explanation")
        elif not m["period"]["from"]<=date<=m["period"]["to"]:
            raise ValueError("source outside requested rolling window")
        if not event_date or not m["period"]["from"]<=event_date<=m["period"]["to"]:
            raise ValueError("archive date out of analysis scope")
        if not raw["source_url"].startswith("https://"):
            raise ValueError("missing dated public source")
        if raw["scope"]=="market_sounding" and any(
            raw.get(x) is not None for x in
            ["nmck_rub","reported_contract_total_rub","reported_final_price_rub"]
        ):
            raise ValueError("market survey cannot invent a price")
        if raw.get("reported_final_price_rub") and raw.get("reported_contract_total_rub"):
            raise ValueError("aggregated final-price signal promoted to executed contract")
        if raw.get("procedure_id") is None and not cid.startswith("index:"):
            raise ValueError("unknown EIS number must have explicit research index canonical ID")
        rec={
            "id":"pq-v17-"+cid.replace(":","-"),
            "canonical_id":cid,
            "procedure_id":raw.get("procedure_id"),
            "publication_date":date,
            "date_basis":raw["date_basis"],
            "source_event_date":event_date,
            "procurement_regime":"commercial" if "rosneft" in cid or raw["scope"]=="request_for_quotation" else "223-fz",
            "platform":"ТЭК-Торг / корпоративный архив Роснефти" if "rosneft" in cid else "отраслевой каталог закупок",
            "customer":{"name":raw["customer"],"inn":None},
            "beneficiary":raw["beneficiary"],
            "description":raw["title"],
            "project":raw["title"],
            "family":raw["family"],
            "scope":raw["scope"],
            "equipment_voltage_kv":raw["equipment_voltage_kv"],
            "nmck_rub":raw["nmck_rub"],
            "reported_price_kind":None,
            "reported_contract_total_rub":raw["reported_contract_total_rub"],
            "reported_final_price_rub":raw["reported_final_price_rub"],
            "contract_awardee":None,
            "supplier_verified":False,
            "pq_equipment_only_contract_rub":None,
            "deadline_date":raw["deadline_date"],
            "status":"public_index_market_enquiry_not_verified_award" if raw["scope"] in ("market_sounding","request_for_quotation") else "public_index_original_protocol_missing",
            "demand_group":raw["demand_group"],
            "source_identifier_masked":raw["procedure_id"] is None,
            "market_scope":"nominal_PQ_voltage_unverified",
            "evidence":[{"url":raw["source_url"],"source_tier":raw["source_tier"],"locator":raw["title"],"excerpt":raw["notes"]}],
            "notes":raw["notes"],
        }
        if cid=="commercial:РН50303773:lot1":
            rec["platform"]="ТЭК-Торг"
        items.append(rec)
        seen.add(cid)
    if len(items)!=m["total_rows"] or len(seen)!=len(items):
        raise ValueError("v17 observed population unexpectedly changed")
    return {
        **parent, "records":items, "data_version":"v17",
        "materialization_manifest":MANIFEST,
        "verification_summary":{
            "total_lot_level_records":len(items),
            "parent_lot_level_records":len(parent["records"]),
            "new_archive_records":len(d["records"]),
            "new_primary_signed_contracts":0,
            "registered_signed_contracts_in_baseline":4,
            "production_structured_records_imported":71,
            "new_records_pending_import":28,
            "market_population_complete":False,
        },
        "seed_completeness":"Not all 2023-2026 PQ procurements; missing official ETP IDs and protocols for many archival market enquiries.",
    }


if __name__=="__main__":
    print(json.dumps(materialize(),ensure_ascii=False,indent=2))
