"""Read-only, deterministic client-safe snapshot of all PQ research lots."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

QUERY = """BEGIN READ ONLY;
SELECT jsonb_build_object('id',r.external_id,'data',d.data,
       'metadata',d.metadata,'review',d.review_status)::text
FROM dp_resources r JOIN dp_records d USING(resource_id)
WHERE r.collection_id='arvectum-market-pq-6-35kv'
ORDER BY r.external_id;
COMMIT;
"""
ALLOWED = (
    "zakupki.gov.ru", "www.b2b-center.ru", "bidzaar.com",
    "tektorg.ru", "www.tektorg.ru", "etp.roseltorg.ru", "www.roseltorg.ru",
    "roseltorg.ru", "sudact.ru", "energybase.ru",
    "zakupki.kontur.ru", "synapsenet.ru", "rostender.info",
    "www.tender.pro", "tender.pro", "www.dv-tender.ru", "www.tenderguru.ru",
    "kontendus.ru", "www.lot-online.ru", "tender.lot-online.ru",
    "b2b.house", "zakaz.etp-region.ru", "etpgpb.ru", "www.etpgpb.ru",
    "metall-it.ru", "www.metall-it.ru", "zakupki.tochka.com",
    "www.fgi-energyrouter.com", "www.vsem-podryad.ru"
)
def val(obj, *keys):
    for key in keys:
        if isinstance(obj, dict):
            x = obj.get(key)
            if x is not None and x != "":
                return x
    return None

def source_bound_bid(data, metadata):
    value = val(data, "commission_bid_rub", "winning_bid_rub")
    if value is not None:
        return value
    proof = (metadata or {}).get("roseltorg_field_enrichment") or {}
    sources = proof.get("source_sha256") or []
    if (proof.get("role") == "bidder_not_winner"
            and proof.get("fields", {}).get("bid") == data.get("bid")
            and len(sources) == 2
            and all(re.fullmatch(r"[0-9a-f]{64}", s) for s in sources)):
        return data.get("bid")
    return None


def clean(text, limit=2400):
    if text is None: return ""
    s = re.sub(r"[\x00-\x1f]+", " ", str(text)).strip()
    s = re.sub(r"\s+", " ", s)
    return s[:limit] + ("… [длинное поле сокращено]" if len(s) > limit else "")

def safe_urls(src):
    urls=[]
    for e in src if isinstance(src, list) else []:
        if not isinstance(e, dict):continue
        u=e.get("url")
        if not isinstance(u,str) or not u.startswith("https://"):continue
        host = u.split("/")[2].lower()
        if host not in ALLOWED:continue
        if u not in urls:
            urls.append({"url":u,"tier":clean(e.get("source_tier"),120),
                         "sha":clean(e.get("sha256"),75)})
    return urls[:6]

def capture():
    p=subprocess.run(["docker","exec","-i","arvectum-postgres","sh","-c",
        'psql -X -A -t -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d arvectum_data'],
        input=QUERY,capture_output=True,text=True,timeout=35,check=True)
    records=[json.loads(line) for line in p.stdout.splitlines() if line.startswith("{")]
    ids=[r["id"] for r in records]
    if len(ids)!=len(set(ids)) or len(ids)<114:
        raise ValueError("Corpus cardinality must be unique and ≥114")
    out=[]
    for r in records:
        d=r["data"]
        if d.get("canonical_id") != r["id"]:
            raise ValueError("Canonical ID mismatch")
        customer=d.get("customer") or {}
        if not isinstance(customer,dict):customer={"name":customer}
        technical=d.get("technical") or {}
        if not isinstance(technical,dict):technical={"details":technical}
        out.append({
            "id":r["id"],"procedure":clean(d.get("procedure_id"),80),
            "regime":clean(d.get("procurement_regime"),80),
            "organizer":clean(val(d,"procurement_organizer","organizer"),240),
            "beneficiary":clean(d.get("beneficiary"),240),
            "region":clean(val(d,"region","region_name"),160),
            "customer_contract_number":clean(val(d,"customer_contract_number","registered_contract_number"),160),
            "date":clean(d.get("publication_date"),20),
            "buyer":clean(customer.get("name"),230),
            "buyer_inn":clean(customer.get("inn"),24),
            "project":clean(d.get("project"),500),
            "description":clean(d.get("description"),2200),
            "family":clean(d.get("family"),120),
            "scope":clean(d.get("scope"),140),
            "platform":clean(d.get("platform"),180),
            "nmck":clean(d.get("nmck_rub"),50),
            "price_kind":clean(d.get("reported_price_kind"),140),
            "contract_price":clean(val(d,"contract_registered_price_rub",
                "verified_equipment_supply_contract_price_rub","reported_contract_total_rub"),50),
            "contract_no":clean(val(d,"contract_registry_number","contract_number","linked_contract_registry_number"),100),
            "equipment_only_price":clean(val(d,"pq_equipment_only_contract_rub",
                "verified_equipment_price_as_of","pq_equipment_portion_rub"),60),
            "paid_amount":clean(val(d,"paid_amount_rub","actual_payment_rub","paid_rub"),60),
            "contract_date":clean(val(d,"contract_date","contract_register_date","reported_contract_date"),30),
            "signed_contract_verified":any(d.get(k) is True for k in (
                "registered_signed_contract_verified","actual_signed_contract_verified",
                "underlying_supplier_contract_verified")),
            "bid":clean(source_bound_bid(d,r.get("metadata")),50),
            "winner":clean(val(d,"commission_winner_name",
                "winning_supplier_name","commission_bidder_name","supplier_by_court"),210),
            "supplier_inn":clean(d.get("supplier_inn"),28),
            "contract_signatory":clean(val(d,"registered_supplier_name",
                "contract_awardee","supplier_name"),230),
            "epc":clean(val(d,"epc_contractor","epc_name"),220),
            "designer":clean(val(d,"designer","design_organization","project_designer"),220),
            "oem":clean(val(d,"equipment_manufacturer","manufacturer_name","oem"),220),
            "manufacturer_verified":d.get("manufacturer_verified") is True,
            "supplier_verified":d.get("supplier_verified") is True,
            "signed_supplier_verified":d.get("signed_supplier_verified") is True,
            "paid_verified":d.get("paid_verified") is True,
            "quantity":clean(d.get("quantity"),35),
            "quantity_unit":clean(d.get("quantity_unit"),50),
            "voltage_kv":clean(val(d,"equipment_voltage_kv","voltage_kv") or
                val(technical,"voltage_kv","voltage"),100),
            "power":clean(val(d,"power") or
                val(technical,"power_kvar","power_mvar","nominal_power"),100),
            "technical":{k: clean(v,220) for k,v in list(technical.items())[:12]},
            "status":clean(d.get("status"),200),
            "market_scope":clean(d.get("market_scope"),220),
            "notes":clean(d.get("notes"),2000),
            "review":r["review"],
            "source_urls":safe_urls(d.get("evidence")),
        })
    counts=Counter(x["scope"] for x in out)
    return {"schema":"fgi-client-deck/2",
            "snapshot_date":datetime.now(ZoneInfo("Europe/Moscow")).date().isoformat(),
            "snapshot_time_moscow":datetime.now(ZoneInfo("Europe/Moscow")).isoformat(),
            "database":"arvectum_data","collection":"arvectum-market-pq-6-35kv",
            "unique_lots":len(out),
            "distinct_procedures":len({x["id"].split(":")[1] for x in out}),
            "eis_223_lots":sum(bool(re.fullmatch(r"223fz:\d{11}:lot\d+",x["id"])) for x in out),
            "eis_223_notices":len({x["id"].split(":")[1] for x in out if re.fullmatch(r"223fz:\d{11}:lot\d+",x["id"])}),
            "scope_counts":dict(counts),"items":out}
if __name__=="__main__":
    cli=argparse.ArgumentParser()
    cli.add_argument("--out",required=True,type=Path)
    args=cli.parse_args()
    s=capture(); args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(s,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(json.dumps({"path":str(args.out),"unique_lots":s["unique_lots"],
       "distinct_procedures":s["distinct_procedures"],
       "eis_223_notices":s["eis_223_notices"],
       "scope_counts":s["scope_counts"]},ensure_ascii=False))
