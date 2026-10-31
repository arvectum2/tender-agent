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

def source_bound_buyer_inn(data, metadata):
    proof = (metadata or {}).get("buyer_inn_field_enrichment") or {}
    source = proof.get("source") or {}
    if (proof.get("field") == "buyer_inn"
            and proof.get("value") == data.get("buyer_inn") == "2310031475"
            and source.get("sha256") == "02d956e85a58cd254b9e1503a892acc94bddb38849bf20f0b1ca721a679dc50f"
            and "ТАНДЕР" in source.get("exact_original_quote", "")
            and any(e.get("sha256") == source["sha256"] and e.get("url") == source.get("url")
                    for e in data.get("evidence", []))):
        return data["buyer_inn"]
    return None


def source_bound_bid(data, metadata):
    if verified_meleuz_contract(data, metadata):
        return data.get("commission_first_place_bid_rub")
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


def verified_rad_commission(data, metadata):
    proof = (metadata or {}).get("rad_commission_enrichment") or {}
    sha = proof.get("source_sha256") or []
    urls = proof.get("source_urls") or []
    member = proof.get("member_sha256") or ""
    if (proof.get("role") == "commission_recommended_contractor_not_signed_supplier"
            and proof.get("field") == "winner"
            and proof.get("value") == data.get("winner")
            and proof.get("signed_supplier_verified") is False
            and proof.get("signed_contract_verified") is False
            and data.get("winner") in proof.get("exact_original_quote", "")
            and len(sha) == len(urls) == 2
            and all(re.fullmatch(r"[0-9a-f]{64}", x) for x in [*sha, member])
            and all(u.startswith("https://tender.lot-online.ru/etp/") for u in urls)):
        return proof
    return None


def verified_nikitskaya_contract(data, metadata):
    proof = (metadata or {}).get("eis_nikitskaya_contract_enrichment") or {}
    sources = proof.get("sources") or []
    return (data.get("canonical_id") == "223fz:32615966040:lot1"
            and data.get("contract_registry_number") == "55036065113260035960000"
            and data.get("contract_registered_price_rub") == "5273763.77"
            and data.get("registered_signed_contract_verified") is True
            and proof.get("supplier_verified") is False
            and proof.get("payment_verified") is False
            and len(sources) == 2
            and sources[0].get("sha256") == "9f5241d6942c2eb62b69b03938224c1b64cba93995841a4e53db025b7c079317"
            and sources[1].get("sha256") == "0331902c360c21720c9aa38dfb94611a44ec31bfe664303fb9dce24d8677cb99")


def verified_bashkirenergo_contract(data, metadata):
    """Direct EIS contract proof; never infer supplier, delivery or paid sales."""
    proof = (metadata or {}).get("eis_bashkirenergo_contract_enrichment") or {}
    sources = proof.get("sources") or []
    return (
        data.get("canonical_id") == "223fz:32515582393:lot1"
        and data.get("scope") == "supply"
        and data.get("contract_registry_number") == "50277071467260001550000"
        and data.get("contract_number") == "РЭС-1.26.1/Д-01071"
        and data.get("contract_signed_date") == "2026-02-27"
        and data.get("contract_registered_price_rub") == "4850000.00"
        and data.get("registered_signed_contract_verified") is True
        and proof.get("supplier_verified") is False
        and proof.get("payment_verified") is False
        and len(sources) == 2
        and sources[0].get("sha256") == "284e532d010d202980375fb4d684dd0616d8665d7c726e7494e2b5c1a6670595"
        and sources[1].get("sha256") == "bac0d89f450f32cdfb6cada70f6976dfaec1ade599ff104898c5338a91a1d553"
    )


def source_bound_bashkirenergo_note(data, metadata):
    if not verified_bashkirenergo_contract(data, metadata):
        return None
    return (
        "Официальный реестр ЕИС подтверждает договор РЭС-1.26.1/Д-01071 "
        "от 27.02.2026 на 4 850 000,00 руб. по поставке УКРМ для ПО НЭС "
        "ООО Башкирэнерго, 1 шт. Реестровая цена не доказывает фактическую "
        "поставку, оплату или выручку изготовителя. Подписавший поставщик, "
        "OEM и цена изделия без иных затрат независимо не установлены."
    )


def verified_meleuz_contract(data, metadata):
    proof = (metadata or {}).get("meleuz_eis_20261031_enrichment") or {}
    sources = proof.get("sources") or []
    expected = (
        "51d201695c4aa97264e17922a053ba6eca03b0032c13d7cd815dff487c9de90f",
        "f598adc6ffb6281ac20b025a86a1632091d2f9851dc7c2e018e9b04514fae270",
        "b3a03bb02d5b84928e91e344de90310679189dc95e84f99d3b8cc7df989aa473",
        "ca9a840c69bce647287c4571b675d57f401f89a20ae3d24f3842d8e24485b781",
    )
    return (data.get("canonical_id") == "223fz:32616296475:lot1"
            and data.get("contract_registry_number") == "50263017332260000870000"
            and data.get("contract_registered_price_rub") == "3865725.99"
            and data.get("contract_signed_date") == "2026-09-21"
            and data.get("registered_signed_contract_verified") is True
            and data.get("supplier_verified") is False
            and data.get("pq_equipment_only_contract_rub") is None
            and data.get("voltage_kv") == "не более 6,3 кВ (требование ТЗ)"
            and data.get("power") == "не менее 500 кВАр (требование ТЗ)"
            and proof.get("supplier_verified") is False
            and proof.get("equipment_only_price_verified") is False
            and len(sources) == len(expected)
            and all(source.get("sha256") == sha
                    for source, sha in zip(sources, expected, strict=True)))


def verified_tyazhinskaya_contract(data, metadata):
    proof = (metadata or {}).get("eis_tyazhinskaya_contract_enrichment") or {}
    sources = proof.get("sources") or []
    expected = (
        "a3df999a678442b7b2050702d97141326464b3a493c47cdcae853bb880b7453f",
        "2815d451811c14e869a2d25fad8a0d2a888950dbb7d6baa1bc5f5c4853bdfb49",
    )
    return (
        data.get("canonical_id") == "223fz:32616354211:lot1"
        and data.get("scope") == "design"
        and data.get("contract_registry_number") == "65501231424260000440000"
        and data.get("contract_number") == "14-СБП/2026"
        and data.get("contract_signed_date") == "2026-09-23"
        and data.get("contract_registered_price_rub") == "7406851.40"
        and data.get("registered_signed_contract_verified") is True
        and data.get("supplier_verified") is False
        and data.get("pq_equipment_only_contract_rub") is None
        and proof.get("supplier_verified") is False
        and proof.get("payment_verified") is False
        and len(sources) == len(expected)
        and all(x.get("sha256") == y for x, y in zip(sources, expected, strict=True))
    )


def source_bound_tyazhinskaya_note(data, metadata):
    if not verified_tyazhinskaya_contract(data, metadata):
        return None
    return (
        "Первичный реестр ЕИС: договор №14-СБП/2026 от 23.09.2026 "
        "на 7 406 851,40 руб. за проектирование и инженерные изыскания "
        "по реконструкции ПС Тяжинская (БСК-110 → СКРМ 52 Мвар). "
        "Это НЕ продажа оборудования. Новый номинал СКРМ не подтверждён; "
        "подписавший подрядчик, фактическая оплата и стоимость "
        "отдельного оборудования не установлены."
    )


def source_bound_meleuz_note(data, metadata):
    if not verified_meleuz_contract(data, metadata):
        return None
    return (
        "Оригинал ТЗ: высоковольтная тиристорно-реакторная АУКРМ, "
        "номинальное напряжение сети не более 6,3 кВ, мощность не менее "
        "500 кВАр, фильтр высших гармоник. Это пределы требований, а не "
        "подтверждённый шильдик изделия. Протокол: заявка №79410, "
        "первое место, 3 865 725,99 руб. Официальный реестр ЕИС: "
        "договор №304/26 от 21.09.2026 на 3 865 725,99 руб. "
        "Цена включает поставку, шеф-монтаж, ПНР и измерения. "
        "Подписавший поставщик, OEM, оплата и отдельная цена "
        "оборудования не установлены."
    )


def source_bound_rad_note(data, metadata):
    if verified_nikitskaya_contract(data, metadata):
        return (
            "Официальный реестр ЕИС: договор №28912-26-100201 от 03.06.2026 "
            "зарегистрирован на 5 273 763,77 руб. (общий смешанный EPC). "
            "Протокол РАД рекомендовал ООО «ЭНЕРГОСЕТЬ», но реестр не "
            "подтверждает личность подписавшего поставщика. Оплата и "
            "стоимость отдельного PQ-оборудования не установлены. "
            "Вторичный источник завышал сумму на 0,23 руб."
        )
    if verified_rad_commission(data, metadata):
        return (
            "Первоисточник РАД, протокол МВС-61/26: одна допущенная заявка; "
            "закупка признана несостоявшейся, комиссия поручила заключить "
            "договор с ООО «ЭНЕРГОСЕТЬ» на 5 273 763,77 руб. за весь EPC. "
            "Это решение комиссии, НЕ подтверждение подписанного договора, "
            "оплаты или цены PQ-оборудования; вторичный реестр сообщает "
            "договор от 03.06.2026 без открытого оригинала."
        )
    return None


def source_bound_rad_sources(data, metadata):
    proof = verified_rad_commission(data, metadata)
    if not proof:
        return []
    return [
        {"url": u, "sha256": sha, "source_tier": "first_party_original"}
        for u, sha in zip(proof["source_urls"], proof["source_sha256"], strict=True)
    ]


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
            "buyer_inn":clean(customer.get("inn") or source_bound_buyer_inn(d,r.get("metadata")),24),
            "project":clean(d.get("project"),500),
            "description":clean(d.get("description"),2200),
            "family":clean(d.get("family"),120),
            "scope":clean(d.get("scope"),140),
            "platform":clean(d.get("platform"),180),
            "nmck":clean(d.get("nmck_rub"),50),
            "price_kind":clean(d.get("reported_price_kind"),140),
            "contract_price":clean(val(d,"contract_registered_price_rub",
                "verified_equipment_supply_contract_price_rub","reported_contract_total_rub"),50),
            "contract_no":clean(val(d,"contract_number","contract_registry_number","linked_contract_registry_number"),100),
            "contract_registry_number":clean(val(d,"contract_registry_number","linked_contract_registry_number"),100),
            "equipment_only_price":clean(val(d,"pq_equipment_only_contract_rub",
                "verified_equipment_price_as_of","pq_equipment_portion_rub"),60),
            "paid_amount":clean(val(d,"paid_amount_rub","actual_payment_rub","paid_rub"),60),
            "contract_date":clean(val(d,"contract_signed_date","contract_date","contract_register_date","reported_contract_date"),30),
            "signed_contract_verified":any(d.get(k) is True for k in (
                "registered_signed_contract_verified","actual_signed_contract_verified",
                "underlying_supplier_contract_verified")),
            "bid":clean(source_bound_bid(d,r.get("metadata")),50),
            "winner":clean(val(d,"commission_winner_name",
                "winning_supplier_name","commission_bidder_name","supplier_by_court")
                or (d.get("winner") if verified_rad_commission(d,r.get("metadata")) else None),210),
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
            "status":clean("official_registered_ukrm_supply_contract_supplier_unverified" if verified_bashkirenergo_contract(d,r.get("metadata")) else ("official_registered_contract_supplier_unverified" if verified_meleuz_contract(d,r.get("metadata")) else ("official_registered_design_contract_supplier_unverified" if verified_tyazhinskaya_contract(d,r.get("metadata")) else ("RAD_official_failed_single_application_committee_recommended_contract" if verified_rad_commission(d,r.get("metadata")) else d.get("status")))),200),
            "market_scope":clean("high_voltage_network_requirement_up_to_6p3kv_not_nameplate" if verified_meleuz_contract(d,r.get("metadata")) else d.get("market_scope"),220),
            "notes":clean(source_bound_bashkirenergo_note(d,r.get("metadata")) or source_bound_tyazhinskaya_note(d,r.get("metadata")) or source_bound_meleuz_note(d,r.get("metadata")) or source_bound_rad_note(d,r.get("metadata")) or d.get("notes"),2000),
            "review":r["review"],
            "source_urls":safe_urls((d.get("evidence") or []) + source_bound_rad_sources(d,r.get("metadata"))),
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
