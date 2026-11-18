"""Project already attested archive observations into existing Decision Core.

Only the local owner review calls this adapter. It is not a public input schema,
does not independently attest arbitrary dictionaries, and cannot decide a bid.
"""
from __future__ import annotations

from .decision_core import build_decision_core


def archived_decision_projection(notice: dict, inventory: dict, dossier: dict,
                                 risks: dict, economics: dict) -> dict:
    unknown={"status":"UNKNOWN","recommendation":"DEFER","owner_decision":"NOT_DECIDED",
             "go_eligible":False,"external_action_allowed":False}
    if (notice.get("status")!="PINNED_RI223_ARCHIVED_NOTICE"
            or not inventory.get("archived_bytes_complete") or not inventory.get("projection_complete")
            or dossier.get("status")!="RI223_ARCHIVED_REVIEW_ONLY"
            or dossier.get("notice")!=notice or dossier.get("inventory")!=inventory):
        return {**unknown,"reason":"VERIFIED_CONSISTENT_ARCHIVED_DOSSIER_REQUIRED"}
    model={"procurement_law":"223fz","notice_revision_requires_review":True,"field_evidence":{},
           "risks":[],"evidence_map":[],"contract_draft_evidence_ids":[]}
    fields=notice["fields"]
    for origin,target in (("subject","procurement_title"),("single_lot_initial_sum","nmck")):
        if origin=="single_lot_initial_sum" and (notice["lot_count"]!=1 or fields.get("single_lot_currency")!="RUB"):
            continue
        refs=[c["source_ref"] for c in notice["citations"]
              if c["source_ref"].endswith(":"+origin) and c["excerpt"]==fields.get(origin)]
        if refs and origin in fields:
            model[target]=fields[origin]
            model["field_evidence"][target]=refs
    # Keep archival deadline separate; never expose it as a current open window.
    for clause in risks.get("clauses",[]):
        source=clause.get("source")
        if clause.get("status")!="VERIFIED_LITERAL_FRAGMENT" or not isinstance(source,dict):
            continue
        n=len(model["risks"])+1
        locator=source.get("ri223_container",{}).get("member_path")
        if not locator or not source.get("chunk_id") or not source.get("original_sha256"):
            continue
        eid=f'risk:{n}:{source["original_sha256"]}:{source["chunk_id"]}'
        model["risks"].append({"risk":clause["operator_review_note"],"operator_decision_required":True})
        model["evidence_map"].append({"evidence_id":eid,"document":locator,"row":clause["section"],
                                      "short_excerpt":source["quote"]})
        model["contract_draft_evidence_ids"].append(eid)
    core=build_decision_core(model)
    if core["decision"]["status"]!="NEEDS_REVIEW" or core["decision"]["external_action_allowed"]:
        return {**unknown,"reason":"ARCHIVE_DECISION_INVARIANT_FAILED"}
    return {**unknown,"status":"ARCHIVED_DECISION_REVIEW_ONLY","decision_core":core,
            "archive_deadline":fields.get("archived_submission_deadline"),
            "current_revision_attested":False,"source_consistency_exhaustive":False,
            "scenario_price_comparison":economics.get("offer_within_archived_initial_sum"),
            "review_gates":[
                {"code":"CURRENT_SOURCE","status":"UNKNOWN"},
                {"code":"LOT_REQUIREMENTS_AND_APPLICABILITY","status":"REVIEW"},
                {"code":"AUTHORIZED_CURRENT_SUPPLIER_PROFILE","status":"MISSING"},
                {"code":"SME_REGISTRY_AND_QUALIFICATION","status":"UNKNOWN"},
                {"code":"APPLIED_SCORING","status":"REVIEW"},
                {"code":"ACTUAL_COSTS_SECURITY_AND_CASHFLOW","status":"UNKNOWN"},
                {"code":"FINAL_CONTRACT_AND_LIABILITY","status":"REVIEW"},
                {"code":"INDEPENDENT_REVIEW","status":"NOT_PERFORMED"},
                {"code":"OWNER_COMMERCIAL_DECISION","status":"NOT_DECIDED"},
            ]}
