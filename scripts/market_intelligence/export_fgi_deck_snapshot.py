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
    "roseltorg.ru", "rosseti.roseltorg.ru", "sudact.ru", "energybase.ru",
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


def verified_lopcha_p0(data, metadata):
    """Only expose direct-EIS buyer INN and URLs when the exact SHA-bound CAS is present."""
    from scripts.market_intelligence.enrich_pq_lopcha_p0_20261031 import CASES, INN

    cid = data.get("canonical_id", "")
    number = cid.split(":")[1] if cid.count(":") == 2 else ""
    if number not in CASES or cid != f"223fz:{number}:lot1":
        return False
    scope, _, sha = CASES[number]
    proof = (metadata or {}).get("eis_lopcha_p0") or {}
    source = proof.get("source") or {}
    url = f"https://zakupki.gov.ru/epz/order/notice/notice223/common-info.html?regNumber={number}"
    return (data.get("procedure_id") == number and data.get("scope") == scope
            and data.get("buyer_inn") == INN
            and proof.get("fields") == ["buyer_inn", "source_urls"]
            and source.get("url") == url and source.get("sha256") == sha
            and source.get("exact_original_quote") == "ИНН 4716016979"
            and data.get("source_urls") == [{"url": url, "tier": "first_party", "sha": sha}])


def source_bound_lopcha_sources(data, metadata):
    if not verified_lopcha_p0(data, metadata):
        return []
    return [{"url": x["url"], "sha256": x["sha"],
             "source_tier": "first_party_byte_original"}
            for x in data["source_urls"]]


def verified_ntc_vanino_p0(data, metadata):
    from scripts.market_intelligence.enrich_pq_ntc_vanino_p0_20261101 import (
        CID,
        INN,
        PLATFORM,
        QUOTES,
        SHA,
        URL,
    )

    proof = (metadata or {}).get("eis_ntc_vanino_p0") or {}
    src = proof.get("source") or {}
    return (data.get("canonical_id") == CID and data.get("procedure_id") == "32616506708"
            and data.get("scope") == "design"
            and data.get("buyer_inn") == INN and data.get("platform") == PLATFORM
            and data.get("source_urls") == [{"url": URL, "tier": "first_party", "sha": SHA}]
            and proof.get("fields") == ["buyer_inn", "platform", "source_urls"]
            and src.get("url") == URL and src.get("sha256") == SHA
            and src.get("exact_original_quotes") == list(QUOTES))


def source_bound_ntc_vanino_sources(data, metadata):
    if not verified_ntc_vanino_p0(data, metadata):
        return []
    return [{"url": data["source_urls"][0]["url"],
             "sha256": data["source_urls"][0]["sha"],
             "source_tier": "first_party_byte_original"}]


def verified_roseltorg_commission(data, metadata):
    """Only show field evidence from exact original-SHA-backed CAS receipts."""
    from scripts.market_intelligence.enrich_pq_roseltorg_commission_20261101 import (
        CASES,
        KEY,
    )

    cid = data.get("canonical_id")
    case = next((x for x in CASES if x["cid"] == cid), None)
    proof = (metadata or {}).get(KEY) or {}
    source = proof.get("proof") or {}
    fields = proof.get("fields") or {}
    if not case or not fields or any(data.get(k) != v for k, v in fields.items()):
        return False
    return (source.get("sha256") == case["sha"]
            and source.get("url") == case["url"]
            and source.get("role") == "anonymous_bidder_not_signed_supplier"
            and proof.get("signed_supplier_verified") is False
            and proof.get("paid_sale_verified") is False
            and data.get("winner") is None
            and any(e.get("sha256") == case["sha"] and e.get("url") == case["url"]
                    for e in data.get("evidence", [])))


def source_bound_commission_note(data, metadata):
    if not verified_roseltorg_commission(data, metadata):
        return None
    note = data["protocol_status_note"]
    if data["canonical_id"] == "223fz:32616433248:lot1":
        role = data.get("protocol_role_evidence") or {}
        if (role.get("original_protocol_named_bidder") == "ООО «СТРОЙЭНЕРГОИМПОРТ»"
                and role.get("original_protocol_named_bidder_inn") == "7801564611"
                and role.get("original_protocol_accepted_bid_rub") == "56330673.93"):
            return "Участник №1: ООО «СТРОЙЭНЕРГОИМПОРТ» (ИНН 7801564611); не подтверждён как подписанный поставщик. " + note
    if data["canonical_id"] == "223fz:32616497692:lot1":
        role = (metadata or {}).get("roseltorg_field_enrichment") or {}
        if role.get("role") == "bidder_not_winner" and role.get("participant"):
            return "Названный участник (не победитель): " + role["participant"] + ". " + note
    return note


def source_bound_bid(data, metadata):
    if verified_meleuz_contract(data, metadata):
        return data.get("commission_first_place_bid_rub")
    # Exact EIS 32616280467 protocol SHA; anonymous commission rank is not a named winner.
    signed = (metadata or {}).get("eis_20261031_contract_enrichment") or {}
    if (data.get("canonical_id") == "223fz:32616280467:lot1"
            and data.get("commission_first_place_application") == "1"
            and data.get("commission_first_place_bid_rub") == "3680106.21"
            and signed.get("fields", {}).get("commission_first_place_bid_rub") == "3680106.21"
            and any(x.get("sha256") == "32b17b6891e29ba60734590f6ff2bbf029c082c8bc75262889da713b92f38554"
                    for x in signed.get("sources", []))):
        return data["commission_first_place_bid_rub"]
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
    if (data.get("canonical_id") == "223fz:32616433248:lot1"
            and verified_roseltorg_commission(data, metadata)):
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


def verified_filter_signed_contract(data, metadata):
    proof = (metadata or {}).get("eis_contract_enrichment") or {}
    sources = proof.get("sources") or []
    return (
        data.get("canonical_id") == "223fz:32514947144:lot1"
        and data.get("contract_registry_number") == "54716016979250029010000"
        and data.get("contract_registered_price_rub") == "3158400.00"
        and data.get("pq_equipment_only_contract_rub") == "3158400.00"
        and data.get("contract_execution_completed") is True
        and data.get("registered_signed_contract_verified") is True
        and proof.get("role") == "signed_completed_12kv_capacitor_components_for_500kv_substation"
        and proof.get("supplier_verified") is False
        and proof.get("payment_verified") is False
        and len(sources) == 3
        and [x.get("sha256") for x in sources] == [
            "66134a163aa0327c095ca0d68d691a597190d2d993c67dbf3cdb4fddc390d234",
            "ed1399c65155df6f9728e7a2ded84257d175663ae21830110a14e5b2753e6233",
            "bd23d3b1f01add4850de79eb46d20ef04f9cf51a7e28a43e39c24d5948c71d63",
        ]
    )


def source_bound_filter_signed_note(data, metadata):
    if not verified_filter_signed_contract(data, metadata):
        return None
    return (
        "Официальный реестр ЕИС: договор №1423177 от 24.07.2025, "
        "реестровый №54716016979250029010000, 3 158 400 руб. "
        "Предмет: 14 конденсаторов КЭПФ-12-450-2УХЛ1 по 225 600 руб. "
        "каждый (12 кВ, 450 кВАр); сумма целиком относится к "
        "конденсаторным компонентам. 23.09.2025 реестр отметил "
        "«Исполнение завершено», но отдельное подтверждение оплаты "
        "и личности подписавшего поставщика отсутствует. "
        "Объект применения — ПС 500 кВ; это не доказательство продажи "
        "полной системы компенсации 6–35 кВ."
    )


def verified_filter_south_signed_contract(data, metadata):
    proof = (metadata or {}).get("eis_filter_32515029641_enrichment") or {}
    sources = proof.get("sources") or []
    return (
        data.get("canonical_id") == "223fz:32515029641:lot1"
        and data.get("scope") == "supply_components"
        and data.get("contract_registry_number") == "54716016979250033980000"
        and data.get("contract_registered_price_rub") == "3490560.00"
        and data.get("pq_equipment_only_contract_rub") == "3490560.00"
        and data.get("quantity") == 12
        and data.get("unit_price_rub") == "290880.00"
        and data.get("registered_signed_contract_verified") is True
        and data.get("contract_execution_status_verified") == "Исполнение"
        and proof.get("signed_supplier_identity") == "unverified"
        and proof.get("paid_amount") == "unverified"
        and [x.get("sha256") for x in sources] == [
            "b3571212f38a646f3686d30974ce3a4fd6df904e2a5b22a1cd51c3b9363ed0c6",
            "72a8d234dbaab2a78f64297643a986d5a76dfd6882a7799dd7aa9805a4c414c6",
            "ecda30473b4c6fef92b459ea4b41e12af3f2ac34d997bef118ddc35525408463",
            "9f2fcb5412e2b45f5647082fa227fe50703b171d0a40af7047a635805028c0c1",
            "e52ec01d1e69ac64b4b1e04cd36a8f3b7502d5788a57c61fce27c8f1f2c06506",
        ]
    )


def source_bound_filter_south_signed_note(data, metadata):
    if not verified_filter_south_signed_contract(data, metadata):
        return None
    return (
        "ЕИС 223-ФЗ №32515029641: комиссия 19.08.2025 рекомендовала "
        "заключить договор с допущенным участником ООО «ЭСК ЮГ» "
        "на 3 490 560 руб. Реестр №54716016979250033980000 "
        "подтверждает договор №123 от 01.09.2025 на ту же сумму. "
        "Предмет: 12 конденсаторов КЭПФ-12-450-2 УХЛ1 по 290 880 руб.; "
        "сумма целиком относится к компонентам фильтра, не к полной "
        "системе PQ 6–35 кВ. Статус реестра «Исполнение» — "
        "не подтверждение завершения или оплаты. Личность подписавшего "
        "поставщика и факт платежа отдельно не подтверждены."
    )


def source_bound_bidzaar_306644_note(data, metadata):
    """Supersede stale pre-download note only with SHA-bound technical evidence."""
    proof = (metadata or {}).get("bidzaar_306644_p2") or {}
    expected = "28c970162cc7b36cff91df3b64ea4168c5717cc43554aea162440e6d10272516"
    if (data.get("canonical_id") != "commercial:306-644:lot35"
            or data.get("voltage_kv") != "6"
            or data.get("power") != "900 кВАр на каждую из 2 УКРМ"
            or data.get("quantity") != 1 or data.get("quantity_unit") != "усл.ед"
            or proof.get("source_sha256") != expected
            or proof.get("customer_provided_equipment") is not True
            or proof.get("not_an_equipment_sale") is not True
            or not any(e.get("sha256") == expected for e in data.get("evidence", []))):
        return None
    return (
        "ТЗ Bidzaar №306-644, SHA-256 " + expected + ": установка и ПНР двух "
        "УКРМ 6 кВ по 900 кВАр каждая на площадке ООО Сибстекло. "
        "Оборудование предоставляет заказчик; предмет запроса — монтаж, "
        "подключение и ПНР, а не продажа двух новых УКРМ. "
        "1 усл.ед — объём работ, не число физических установок. "
        "Проект договора не подписан, цена и исполнитель не установлены."
    )



def source_bound_bidzaar_351062_note(data, metadata):
    """Replace stale pre-download note only when both original documents are SHA-bound."""
    proof = (metadata or {}).get("bidzaar_351062_p2") or {}
    voltage = (metadata or {}).get("bidzaar_351062_voltage") or {}
    power_sha = "e53a74ef8a4fda14aedce7254488013187aba3bba7780b5a9c6443e4d0caacaf"
    voltage_sha = "e7927732264deb30813bcf967740763cfb032f5710ca78156f76646f8cc0d831"
    if (data.get("canonical_id") != "commercial:351-062:lot1"
            or data.get("quantity") != 2 or data.get("equipment_voltage_kv") != "6.3"
            or data.get("power") != "3000 кВАр (по опросному листу; не умножать на 2)"
            or proof.get("original_sha256") != power_sha
            or voltage.get("original_sha256") != voltage_sha
            or not all(any(e.get("sha256") == sha for e in data.get("evidence", []))
                       for sha in (power_sha, voltage_sha))):
        return None
    return (
        "Bidzaar №351-062: получены SHA-проверенные оригиналы DOC и DOCX. "
        "Опросный лист указывает УКРМ 6,3 кВ, 3000 кВАр; заявлено 2 установки, "
        "но суммарная мощность двух изделий отдельно не подтверждена. "
        "Это анализ цен/мониторинг рынка, а не доказанный подписанный договор. "
        "Победитель, цена договора, факт поставки и оплаты не установлены."
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


def verified_tyazhinskaya_20261101(data, metadata):
    proof = (metadata or {}).get("eis_tyazhinskaya_20261101_registered_contract") or {}
    sources = proof.get("sources") or []
    expected = (
        "d449da956df043fd0660a2df91b0ba8f5a314a58a33707c7e01fb4d1b30de75e",
        "4460e5d597e28260c16b0281cf445c8e6e742df6a3ff7ca8638174bd6765764a",
    )
    return (
        data.get("canonical_id") == "223fz:32615937898:lot1"
        and data.get("scope") == "design_and_survey_only"
        and data.get("market_scope") == "adjacent_110kv_reactive_compensation_design_not_equipment_sale"
        and data.get("contract_registry_number") == "67728589190260001030000"
        and data.get("contract_number") == "СП-14.4200.4613.25/1"
        and data.get("contract_signed_date") == "2026-06-10"
        and data.get("contract_registered_price_rub") == "3050000.00"
        and data.get("registered_signed_contract_verified") is True
        and data.get("supplier_verified") is False
        and data.get("paid_verified") is False
        and proof.get("payment_verified") is False
        and proof.get("supplier_verified") is False
        and len(sources) == len(expected)
        and all(source.get("sha256") == sha
                for source, sha in zip(sources, expected, strict=True))
        and all(any(e.get("sha256") == sha and e.get("url") == source.get("url")
                    for e in data.get("evidence", []))
                for source, sha in zip(sources, expected, strict=True))
    )


def source_bound_tyazhinskaya_20261101_note(data, metadata):
    if not verified_tyazhinskaya_20261101(data, metadata):
        return None
    return (
        "Первичный реестр ЕИС: договор №СП-14.4200.4613.25/1 "
        "от 10.06.2026 на 3 050 000,00 руб. за проектирование и "
        "инженерные изыскания ПС Тяжинская (БСК-110 → СКРМ 52 Мвар). "
        "Это НЕ продажа оборудования 6–35 кВ. Подписавший подрядчик, "
        "фактическая оплата и цена отдельного PQ-оборудования не подтверждены."
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


def verified_eis_contract_item(data, metadata):
    proof = (metadata or {}).get("eis_20261101_contract_item_enrichment") or {}
    sources = proof.get("sources") or []
    return (
        data.get("canonical_id") == "223fz:32616266007:lot1"
        and data.get("contract_registry_number") == "54716016979260041190000"
        and data.get("contract_item_model") == "КЭПФ-12-450-2 УХЛ1"
        and data.get("contract_item_quantity") == 5
        and data.get("contract_item_unit_price_rub") == "132492.00"
        and data.get("contract_item_country_of_origin") == "Республика Казахстан"
        and data.get("contract_item_okpd2") == "27.90.52.000"
        and data.get("signed_supplier_verified") is False
        and data.get("paid_verified") is False
        and len(sources) == 2
        and sources[0].get("sha256") == "a2865ba18ce0e67bcb45d8bf6054e1dbe13e71a15fb78287ce6cdcf273a97f74"
        and sources[1].get("sha256") == "08b09706b512f497b94941b5de857d0aabbda3eac9f1df64b4c8bd0d4e8b375c"
    )


def source_bound_eis_contract_item_note(data, metadata):
    if not verified_eis_contract_item(data, metadata):
        return None
    return (
        "Официальный реестр ЕИС, договор №1605245 от 14.10.2026: "
        "5 конденсаторов КЭПФ-12-450-2 УХЛ1, 132 492 руб./шт., "
        "всего 662 460 руб.; страна происхождения — Казахстан. "
        "В ТЗ указан QBANK-A CHDB-142 или эквивалент, 8,3 кВ, 592 квар. "
        "Эквивалентность и номинальные параметры фактически поставленного "
        "изделия не подтверждены. Это компоненты БСК для ПС 500 кВ, "
        "не поставка полноценной системы PQ 6–35 кВ. "
        "Личность подписавшего поставщика и оплата не установлены."
    )


def source_bound_eis_contract_item_sources(data, metadata):
    if not verified_eis_contract_item(data, metadata):
        return []
    return [
        {"url": x["url"], "sha256": x["sha256"],
         "source_tier": "first_party_eis_registered_contract_subject"}
        for x in metadata["eis_20261101_contract_item_enrichment"]["sources"]
    ]


def verified_evraz_dual(data, metadata):
    """Two independent EIS contracts on one mixed repair lot; not PQ sales."""
    proof = (metadata or {}).get("evraz_dual_contract_20261101") or {}
    entries = data.get("contract_registry_entries") or []
    sources = proof.get("sources") or []
    return (data.get("canonical_id") == "223fz:32413195287:lot1"
            and data.get("buyer_inn") == "4217084532"
            and data.get("registered_signed_contract_verified") is True
            and len(entries) == 2 and len(sources) == 4
            and [e.get("registry_number") for e in entries] == [
                "54217084532240000450000", "54217084532240000460000"]
            and [e.get("registered_price_rub") for e in entries] == [
                "1043734.03", "13090401.45"]
            and [s.get("sha256") for s in sources] == [
                "d8db0210aa94eaef7102c4384ec188d82468a736647369daad0a253c7e5e7db4",
                "b5c6cc09f7b2dec47682a5d63c4445d51762db3da3f74c2d31b9aa69efa7b0a2",
                "926bbce4fd20cb0d264f42cd25326063131ffb73997d45706097a2953f752964",
                "c968b9971c26b45280c5839eafb74de45487fee9abd08e5132a3a84880aedf67"]
            and proof.get("supplier_verified") is False
            and proof.get("paid_verified") is False
            and proof.get("pq_equipment_allocation_verified") is False)


def evraz_contract_numbers(data, metadata):
    if verified_evraz_dual(data, metadata):
        return "; ".join(e["registry_number"] for e in data["contract_registry_entries"])
    return None


def evraz_sources(data, metadata):
    if verified_evraz_dual(data, metadata):
        return [{"url": s["url"], "sha256": s["sha256"],
                 "source_tier": "first_party_eis_registered_contract"}
                for s in metadata["evraz_dual_contract_20261101"]["sources"]]
    return []


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
            urls.append({"url":u,"tier":clean(e.get("source_tier") or e.get("tier"),120),
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
            "buyer_inn":clean(customer.get("inn") or (d.get("buyer_inn") if verified_evraz_dual(d,r.get("metadata")) else None) or source_bound_buyer_inn(d,r.get("metadata")) or ("4716016979" if verified_lopcha_p0(d,r.get("metadata")) else None),24),
            "project":clean(d.get("project"),500),
            "description":clean(d.get("description"),2200),
            "family":clean(d.get("family"),120),
            "scope":clean(d.get("scope"),140),
            "platform":clean(d.get("platform"),180),
            "nmck":clean(d.get("nmck_rub"),50),
            "price_kind":clean(d.get("reported_price_kind"),140),
            "contract_price":clean(val(d,"contract_registered_price_rub",
                "verified_equipment_supply_contract_price_rub","reported_contract_total_rub"),50),
            "contract_no":clean(evraz_contract_numbers(d,r.get("metadata")) or val(d,"contract_number","contract_registry_number","linked_contract_registry_number"),100),
            "contract_registry_number":clean(evraz_contract_numbers(d,r.get("metadata")) or val(d,"contract_registry_number","linked_contract_registry_number"),100),
            "equipment_only_price":clean(val(d,"pq_equipment_only_contract_rub",
                "verified_equipment_price_as_of","pq_equipment_portion_rub"),60),
            "paid_amount":clean(val(d,"paid_amount_rub","actual_payment_rub","paid_rub"),60),
            "contract_date":clean(("2024-03-11" if verified_evraz_dual(d,r.get("metadata")) else None) or val(d,"contract_signed_date","contract_date","contract_register_date","reported_contract_date"),30),
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
            "status":clean("official_registered_filter_components_contract_supplier_unverified" if verified_filter_south_signed_contract(d,r.get("metadata")) else ("official_completed_filter_capacitor_contract_supplier_unverified" if verified_filter_signed_contract(d,r.get("metadata")) else ("official_registered_ukrm_supply_contract_supplier_unverified" if verified_bashkirenergo_contract(d,r.get("metadata")) else ("official_registered_contract_supplier_unverified" if verified_meleuz_contract(d,r.get("metadata")) else ("official_registered_design_contract_supplier_unverified" if verified_tyazhinskaya_contract(d,r.get("metadata")) else ("RAD_official_failed_single_application_committee_recommended_contract" if verified_rad_commission(d,r.get("metadata")) else d.get("status")))))),200),
            "market_scope":clean("adjacent_500kv_substation_12kv_filter_capacitor_components_not_full_pq_system" if verified_filter_signed_contract(d,r.get("metadata")) else ("high_voltage_network_requirement_up_to_6p3kv_not_nameplate" if verified_meleuz_contract(d,r.get("metadata")) else d.get("market_scope")),220),
            "notes":clean(source_bound_commission_note(d,r.get("metadata")) or (d.get("contract_status_note") if verified_evraz_dual(d,r.get("metadata")) else None) or source_bound_eis_contract_item_note(d,r.get("metadata")) or source_bound_filter_south_signed_note(d,r.get("metadata")) or source_bound_filter_signed_note(d,r.get("metadata")) or source_bound_bidzaar_306644_note(d,r.get("metadata")) or source_bound_bidzaar_351062_note(d,r.get("metadata")) or source_bound_bashkirenergo_note(d,r.get("metadata")) or source_bound_tyazhinskaya_note(d,r.get("metadata")) or source_bound_meleuz_note(d,r.get("metadata")) or source_bound_rad_note(d,r.get("metadata")) or d.get("notes"),2000),
            "review":r["review"],
            "source_urls":safe_urls(evraz_sources(d,r.get("metadata")) + source_bound_eis_contract_item_sources(d,r.get("metadata")) + (d.get("evidence") or []) + source_bound_rad_sources(d,r.get("metadata")) + source_bound_lopcha_sources(d,r.get("metadata")) + source_bound_ntc_vanino_sources(d,r.get("metadata"))),
        })
        if verified_tyazhinskaya_20261101(d, r.get("metadata")):
            out[-1]["status"] = "official_registered_design_contract_supplier_unverified"
            out[-1]["notes"] = source_bound_tyazhinskaya_20261101_note(d, r.get("metadata"))
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
