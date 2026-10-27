"""Read-only enrichment of existing MI-013 procurement examples with verified original documents."""
from __future__ import annotations
import copy
import json
from pathlib import Path
from decimal import Decimal
from materialize_pq_research_v11 import materialize as materialize_v11

DATA=Path(__file__).resolve().parents[2]/"data/market_intelligence/power_quality"
MANIFEST="verified_public_leads_20261027.v12.manifest.json"


def materialize():
    manifest=json.loads((DATA/MANIFEST).read_text(encoding="utf-8"))
    evidence=json.loads((DATA/manifest["source_document"]).read_text(encoding="utf-8"))
    overlay=json.loads((DATA/manifest["amendment_file"]).read_text(encoding="utf-8"))
    baseline=materialize_v11()
    original=baseline["records"]
    if len(original)!=manifest["base_lot_level_records"]:
        raise ValueError("v11 base count drift")
    if len(overlay["patches"])!=manifest["target_existing_records"]:
        raise ValueError("unexpected evidence patch count")
    if evidence["original_archive_sha256"]!=manifest["primary_original_archive_sha256"]:
        raise ValueError("archive SHA mismatch between evidence and manifest")

    net=Decimal(evidence["summary"]["net_initial_price_rub"])
    computed=sum((Decimal(part["net_rub"]) for part in evidence["equipment_components"]),Decimal("0"))
    if net!=computed or (net*Decimal("1.22")).quantize(Decimal("0.01"))!=Decimal("452016000.01"):
        raise ValueError("original BoQ and notice VAT22 totals do not reconcile")
    if evidence["summary"]["gross_initial_price_rub"]!= "452016000.01":
        raise ValueError("original notice gross NMC unexpected")

    ids=[r["canonical_id"] for r in original]
    if len(set(ids))!=len(ids):
        raise ValueError("duplicate baseline canonical IDs")
    changes={p["canonical_id"]:p for p in overlay["patches"]}
    if len(changes)!=len(overlay["patches"]) or not set(changes).issubset(set(ids)):
        raise ValueError("duplicate or missing overlay target")

    rows=[]
    for previous in original:
        cid=previous["canonical_id"]
        item=copy.deepcopy(previous)
        if cid in changes:
            patch=changes[cid]
            for name,value in patch["fields"].items():
                if name=="canonical_id" or name=="procedure_id":
                    raise ValueError("cannot edit canonical identifier")
                item[name]=value
            if item.get("source_original_docs_verified") is True:
                item["notes"]=(item.get("notes") or "").replace(
                    "номиналы, количество и полные ТЗ не прочитаны.",
                    "оригинальные ТЗ и поэлементная смета прочитаны; МПУ 10 кВ, БСК 110 кВ, по 1 шт.; классификация ОКПД2 до 1 кВ не является фактическим номиналом МПУ."
                )
            item["notes"]=(item.get("notes") or "")+patch.get("notes_append","")
            item["evidence"]=item.get("evidence",[])+patch.get("evidence_append",[])
        rows.append(item)
    if len(rows)!=manifest["total_lot_level_records"] or [r["canonical_id"] for r in rows]!=ids:
        raise ValueError("enrichment changed record identity or count")
    updated=next(r for r in rows if r["canonical_id"]=="223fz:32616435269:lot1")
    if updated["market_scope"].startswith("strict_") or updated["family"]!="hybrid_reactive_power_source":
        raise ValueError("incorrect voltage segmentation")
    if updated["supplier_verified"] or updated["reported_contract_total_rub"] is not None:
        raise ValueError("no winner or signed price available")
    if updated["nmc_gross_rub"]!=updated["nmck_rub"]:
        raise ValueError("published NMC differs from original notice")
    if sum(1 for r in rows if r.get("project_demand_group")=="TYAZHINSKAYA-SKRM52-2025-2026")!=3:
        raise ValueError("lost Tyazhinskaya project-level link")

    return {
        **baseline,
        "records":rows,
        "data_version":"v12",
        "materialization_manifest":MANIFEST,
        "verification_summary":{
            "prior_lot_level_records":len(original),
            "changed_source_quality_records":len(changes),
            "added_lot_level_records":0,
            "total_lot_level_records":len(rows),
            "source_archive_original_sha_verified":True,
            "known_mid_voltage_converter_net_nmc_rub":"335351974.38",
            "mid_voltage_converter_awarded_contract_rub":None,
        },
        "delta_note":"71 same lot-level research IDs; one primary-authored archived source verified SHA and 10/110kV BoQ reconciled; three Tyazhinskaya procurement notices linked to ONE underlying project, distinct design and supply contracts.",
    }


if __name__=="__main__":
    print(json.dumps(materialize(),ensure_ascii=False,indent=2))
