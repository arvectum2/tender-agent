"""Read-only public-evidence snapshot of all Arvectum PQ procurement lots."""
from __future__ import annotations

import argparse
import collections
import datetime
import hashlib
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

SQL="""BEGIN READ ONLY;
SELECT jsonb_build_object('lot',r.external_id,'payload',d.data)::text
FROM dp_resources r JOIN dp_records d USING(resource_id)
WHERE r.collection_id='arvectum-market-pq-6-35kv' ORDER BY r.external_id;
COMMIT;
"""
BUCKET={
  "equipment_supply_new":"supply","equipment_supply_request":"supply",
  "signed_equipment_supply":"supply","supply":"supply","supply_candidate":"supply",
  "supply_with_mixed_work":"mixed_supply","supply_components":"components",
  "capacitor_component_supply_spares":"components","component_supply_voltage_unknown":"components",
  "mixed_epc":"epc","epc":"epc","adjacent_epc":"epc","mixed_epc_installation":"epc",
  "mixed_epc_repair_services":"epc","mixed_supply_install_pnr":"epc","electrical_auxiliary_works":"epc",
  "design":"design","design_and_survey_only":"design",
  "engineering_design_only":"design","design_harmonic_filtration":"design",
  "maintenance":"service","modernization_existing_equipment":"service",
  "commissioning_service_existing_ukrm":"service",
  "market_sounding":"sounding","request_for_quotation":"sounding",
  "mixed_MTR_market_sounding_with_PQ_component":"sounding",
}
def take(d,*keys):
    if not isinstance(d,dict):return None
    for key in keys:
        v=d.get(key)
        if v is not None and v!="" and v!=[] and v!={}:
            return v
    return None
def clean(v,max_chars=1000):
    if v is None:return None
    if isinstance(v,(dict,list)):
        v=json.dumps(v,ensure_ascii=False,separators=(",",":"))
    s=re.sub(r"\s+"," ",str(v)).strip()
    return s[:max_chars] + ("…" if len(s)>max_chars else "")
def safe_url(s):
    if not isinstance(s,str):return None
    try:
        x=urlsplit(s)
        if x.scheme!="https" or not x.hostname or x.username or x.password or x.port not in (None,443):return None
        host=x.hostname.lower()
        if host in ("localhost","127.0.0.1") or host.endswith((".local", ".internal")):return None
        return s[:1600]
    except ValueError:
        return None
def source_list(payload):
    candidates=payload.get("evidence") or []
    for extra in (payload.get("protocol_role_original_sources") or []):
        if isinstance(extra,dict):candidates.append(extra)
    links=[];seen=set()
    for src in candidates:
        if not isinstance(src,dict):continue
        url=safe_url(src.get("url"))
        if not url or url in seen:continue
        seen.add(url)
        links.append({"url":url,"tier":clean(take(src,"source_tier","kind","source_grade"),140),
                      "excerpt":clean(take(src,"excerpt","locator","description"),380),
                      "sha256":clean(src.get("sha256"),75),
                      "original_bytes":src.get("bytes") if isinstance(src.get("bytes"),int) else None})
    return links[:14]
def grade(sources):
    tiers=[(s["tier"] or "").lower() for s in sources]
    if any(("original" in s or "first_party" in s or "primary" in s) and
           (src["sha256"] or src["original_bytes"]) for s,src in zip(tiers,sources)):return "A"
    if any("original" in s or "first_party" in s or "primary" in s for s in tiers):return "B"
    return "C" if sources else "D"
def technical_fields(payload):
    out={}
    for item in ("technical","equipment","product_lines","registry_contract"):
        val=payload.get(item)
        if isinstance(val,(dict,list)):out[item]=val
    return out
def compact_nested_facts(payload):
    facts={}
    enrich=payload.get("mi013_source_enrichments") or {}
    if isinstance(enrich,dict):
        for version,group in sorted(enrich.items()):
            if not isinstance(group,dict):continue
            for k in ("verified_primary","verified_original"):
                val=group.get(k)
                if not isinstance(val,dict):continue
                for key,v in val.items():
                    if isinstance(v,(str,int,float,bool)) and any(t in key for t in (
                        "supplier","bid","winner","contract","price","protocol","award",
                        "signed","status","date","equipment")):
                        facts[f"{version}.{key}"]=clean(v,120)
    return dict(list(facts.items())[:18])

def protocol_bidders(payload):
    """Keep source-original participant records, not inferred signed suppliers."""
    out=[]
    enrichment=payload.get("mi013_source_enrichments") or {}
    if not isinstance(enrichment,dict):return out
    for edition,group in sorted(enrichment.items()):
        if not isinstance(group,dict):continue
        for name in ("verified_primary","verified_original"):
            doc=group.get(name)
            if not isinstance(doc,dict):continue
            for field in ("participants","named_original_bidders","original_protocol_participants",
                          "original_bidders","other_bids"):
                bids=doc.get(field)
                if not isinstance(bids,list):continue
                for b in bids[:15]:
                    if not isinstance(b,dict):continue
                    details={k:clean(v,240) for k,v in b.items()
                             if v is not None and isinstance(v,(str,int,float,bool))}
                    if details:
                        out.append({"edition":edition,"source_list":field,"fields":details})
    return out

def normalize(lot,p):
    buyer=p.get("customer") or {}
    if not isinstance(buyer,dict):buyer={"name":buyer}
    org=p.get("organizer") or {}
    if not isinstance(org,dict):org={"name":org}
    equipment=p.get("equipment") or {}
    if not isinstance(equipment,dict):equipment={}
    technical=p.get("technical") or {}
    if not isinstance(technical,dict):technical={}
    voltage=(take(p,"equipment_voltage_kv")
             or take(technical,"ukrm_voltage_kv","voltage_kv","equipment_nominal_kv")
             or take(equipment,"nominal_voltage_kv","voltage_kv"))
    power=(take(p,"equipment_reactive_power_mvar")
           or take(technical,"power_mvar","reactive_power_mvar","bsk_power_mvar"))
    power_unit="Mvar" if power is not None else None
    if power is None:
        power=(take(technical,"power_kvar","bsk_power_kvar","reactive_power_kvar")
               or take(equipment,"total_nameplate_kvar","power_kvar"))
        power_unit="kvar" if power is not None else None
    sources=source_list(p)
    signed=any(p.get(k) is True for k in (
        "registered_signed_contract_verified","signed_contract_registry_verified",
        "actual_signed_contract_verified","underlying_supplier_contract_verified"
    ))
    if isinstance(p.get("registry_contract"),dict):
        signed|=p["registry_contract"].get("signed_contract_registry_verified") is True
    paid=p.get("paid_verified") is True
    row={
      "id":lot,"notice":clean(take(p,"procedure_id"),115),
      "regime":clean(take(p,"procurement_regime"),60),
      "platform":clean(take(p,"platform"),170),
      "date":clean(take(p,"publication_date"),40),
      "deadline":clean(take(p,"deadline_date","bid_deadline"),40),
      "buyer":clean(take(buyer,"name"),190),
      "buyer_inn":clean(take(buyer,"inn"),30),
      "organizer":clean(take(org,"name") or take(p,"procurement_organizer"),155),
      "beneficiary":clean(take(p,"beneficiary"),200),
      "region":clean(take(p,"region","region_name"),110),
      "project":clean(take(p,"project"),900),
      "description":clean(take(p,"description"),2300),
      "family":clean(p.get("family"),95),
      "scope":clean(p.get("scope"),120),
      "scope_group":BUCKET.get(p.get("scope"),"other"),
      "status":clean(p.get("status"),190),
      "review_status":"unreviewed",
      "nmck":clean(take(p,"nmck_rub"),75),
      "bid":clean(take(p,"commission_bid_rub","winning_bid_rub"),75),
      "bidder":clean(take(p,"commission_winner_name","winning_supplier_name","commission_bidder_name"),160),
      "bidder_inn":clean(take(p,"commission_winner_inn","winning_bidder_inn"),28),
      "contract_price":clean(take(p,"contract_registered_price_rub","actual_signed_contract_price_rub","contract_price_rub","reported_contract_total_rub"),80),
      "contract_no":clean(take(p,"contract_registry_number","registered_contract_number","contract_register"),115),
      "contract_date":clean(take(p,"original_signed_contract_date","contract_register_date","reported_contract_date","signed_date"),45),
      "contract_signed_verified":signed,
      "signed_supplier":clean(take(p,"registered_supplier_name","contract_signatory_name"),160)
         if p.get("signed_supplier_verified") is True else None,
      "signed_supplier_verified":p.get("signed_supplier_verified") is True,
      "supplier_inn":clean(p.get("supplier_inn"),28) if p.get("signed_supplier_verified") is True else None,
      "oem":clean(take(p,"manufacturer_name","equipment_manufacturer"),160)
         if p.get("manufacturer_verified") is True else None,
      "oem_verified":p.get("manufacturer_verified") is True,
      "epc":clean(take(p,"epc_contractor","epc_name"),165),
      "designer":clean(take(p,"designer","design_organization","project_designer"),165),
      "equipment_only_price":clean(take(p,"pq_equipment_only_contract_rub","verified_equipment_supply_contract_price_rub"),80),
      "equipment_price_scope":clean(take(p,"equipment_only_price_basis","equipment_price_scope"),170),
      "paid_amount":clean(take(p,"paid_rub","actual_payment_rub"),70) if paid else None,
      "paid_verified":paid,
      "voltage_kv":clean(voltage,100),
      "rated_power":clean(power,100),
      "rated_power_unit":power_unit,
      "quantity":clean(take(p,"quantity") or take(technical,"quantity") or take(equipment,"quantity"),45),
      "quantity_unit":clean(take(p,"quantity_unit"),35),
      "model":clean(take(p,"model") or take(equipment,"type","model1") or take(technical,"type","model"),180),
      "technical_details":technical_fields(p),
      "extra_verified":compact_nested_facts(p),
      "protocol_bidders":protocol_bidders(p),
      "notes":clean(take(p,"notes","market_scope"),1350),
      "reported_price_kind":clean(take(p,"reported_price_kind","reported_contract_total_source_tier"),170),
      "sources":sources,
      "evidence_grade":grade(sources),
    }
    return row

def export(out):
    q=subprocess.run(["docker","exec","-i","arvectum-postgres","sh","-c",
        'psql -X -A -t -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d arvectum_data'],
        input=SQL,text=True,capture_output=True,timeout=45,check=True)
    rows=[normalize(x["lot"],x["payload"]) for line in q.stdout.splitlines()
          if line.startswith("{") for x in [json.loads(line)]]
    ids=[r["id"] for r in rows]
    if len(ids)!=len(set(ids)) or len(ids)<123:
        raise ValueError("Duplicate canonical lot or corpus shrunk")
    def eis(row):
        return re.fullmatch(r"223fz:(\d{11}):lot\d+",row["id"])
    notices={m.group(1) for r in rows if (m:=eis(r))}
    data={
       "schema":"arvectum-pq-client-exhaustive/1",
       "as_of":"2026-11-04",
       "snapshot_utc":datetime.datetime.now(datetime.UTC).isoformat(),
       "collection":"arvectum-market-pq-6-35kv",
       "unique_lots":len(rows),
       "distinct_procedures":len({r["id"].split(":")[1] for r in rows}),
       "eis_223_lots":sum(bool(eis(r)) for r in rows),
       "eis_223_notices":len(notices),
       "research_not_signed_sales_population":True,
       "scope_counts":dict(collections.Counter(r["scope_group"] for r in rows)),
       "family_counts":dict(collections.Counter(r["family"] or "unknown" for r in rows)),
       "grade_counts":dict(collections.Counter(r["evidence_grade"] for r in rows)),
       "items":rows,
    }
    txt=json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2)+"\n"
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(txt,encoding="utf8")
    print(json.dumps({"out":str(out),"sha256":hashlib.sha256(txt.encode()).hexdigest(),
        "lots":len(rows),"procedures":data["distinct_procedures"],
        "eis_223_notices":len(notices),"grades":data["grade_counts"],
        "bytes":len(txt.encode())},ensure_ascii=False))
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    export(a.out)
