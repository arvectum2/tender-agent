"""Source-bound reference case: signed/paid supplier and OEM remain unverified."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

OUT=Path("data/market_intelligence/power_quality/exemplars/reto_32616181358_20261031.v1.json")
SQL="SELECT d.data::text FROM dp_resources r JOIN dp_records d USING(resource_id) WHERE r.collection_id='arvectum-market-pq-6-35kv' AND r.external_id='223fz:32616181358:lot1'"
SOURCES={
 "TZ":{"label":"Оригинальное ТЗ КЭПФ_186, 7 стр.","grade":"A",
   "url":"https://tender.lot-online.ru/etp/downloadppf?uuid=dbfile19718u80000punsoc08chcr834",
   "sha":"9ceb44be68abcf07729cb9045b1a3ce7b54456810c93c9a32885781d3a578032"},
 "PROTOCOL":{"label":"Оригинал протокола комиссии 186-2, 3 стр.","grade":"A",
   "url":"https://tender.lot-online.ru/etp/downloadppf?uuid=dbfile19718u80000pvkg89is0k0tsd4",
   "sha":"92874d098feb7dc6c283bd7b66c5218e11e472f27eddffc75edd6613fb5b21ef"},
 "ETP":{"label":"Официальная карточка Lot-online RAD260032779","grade":"B",
   "url":"https://tender.lot-online.ru/etp/app/LotCard/page?LotCard.lotEntity=LT%3Acorebo19718u80000pudvaupvhqhhca4",
   "sha":"6c770a82a2093fe09e9152e208bccced7e452bf4a5545200dbd9a16fb3cdf453"},
 "EIS":{"label":"Исторический реестр договора ЕИС, 31.10 HTTP404","grade":"archived_A_unavailable_today",
   "url":"https://zakupki.gov.ru/epz/contractfz223/card/contract-info.html?reestrNumber=57724646338260000460000",
   "sha":"94170a4d9314d78307300f410c2e71fc3ee8ab4a3c9ea86633e48d1809b390aa"},
 "ITEMS":{"label":"Исторические позиции договора ЕИС, 31.10 HTTP404","grade":"archived_A_unavailable_today",
   "url":"https://zakupki.gov.ru/epz/contractfz223/card/contract-subject.html?reestrNumber=57724646338260000460000",
   "sha":"76d050d1fd3f65a6a5eb2f58358fa376b5cc280abe6ff1207122698d73c5f6cf"},
 "XLSX":{"label":"Шаблон предложения поставки ТМЦ","grade":"A",
   "url":"https://tender.lot-online.ru/etp/downloadppf?uuid=dbfile19718u80000punsoc1paupdotk",
   "sha":"547d1bb48ef8525148dc3a07344d5c6806a21b4b6fbf1e9a413e6ee8d08e36b9"}
}
def read_live():
    p=subprocess.run(["docker","exec","-i","arvectum-postgres","sh","-c",
        'psql -X -A -t -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d arvectum_data'],
        input=SQL,text=True,capture_output=True,timeout=20,check=True)
    return json.loads(next(s for s in p.stdout.splitlines() if s.startswith("{")))
def build():
    d=read_live()
    ex=d["mi013_source_enrichments"]["v39"]["verified_primary"]
    assert d["canonical_id"]=="223fz:32616181358:lot1"
    assert ex["original_pdf"]["sha256"]==SOURCES["PROTOCOL"]["sha"]
    out={
      "schema":"arvectum-reference-procurement/1","as_of":"2026-10-31",
      "case_id":d["canonical_id"],"snapshot_live_db_original":True,
      "buyer":d["customer"]["name"],"buyer_inn":d["customer"]["inn"],
      "organizer":d["organizer"]["name"],"beneficiary":None,
      "location":"Москва, Старокаширское шоссе, 4А",
      "procedure":d["procedure_id"],"etp_id":"RAD260032779","lot_no":1,
      "regime":"223-ФЗ","method":"Запрос котировок в электронной форме",
      "subject":"Поставка конденсаторов косинусных КЭПФ для БСК",
      "publication":"2026-07-06","revision":"2026-07-14","deadline":"2026-07-20 11:00 МСК",
      "protocol_date":"2026-08-03","protocol_published":"2026-08-05",
      "protocol_number":"186-2","contract_date_archive":"2026-08-19",
      "contract_number_archive":"060-26-Р",
      "registry_number":d["contract_registry_number"],
      "contract_term_end":"2026-12-31",
      "scope":"Компоненты БСК, НЕ завершённая установка STATCOM/SVG",
      "nmck_rub":3078500,"vat_on_initial_percent":22,
      "nmck_without_vat_rub":2523360.66,"nmck_vat_rub":555139.34,
      "winning_bid_rub":3050000,"contract_total_archived_rub":3050000,
      "discount_rub":28500,"discount_percent":round(28500/3078500*100,2),
      "physical_delivery_verified":False,"payment_verified":False,
      "signed_supplier_verified":False,"signed_supplier":None,
      "oem_verified":False,"oem":None,
      "manufacturer_registered_country_archive":"Республика Казахстан",
      "manufactured_country_verified":False,"contract_registry_live_accessible":False,
      "participation":ex["participants"],
      "bids_received":3,"bids_admitted":2,"bids_rejected":1,
      "winner":d["commission_winner_name"],"winner_inn":d["commission_winner_inn"],
      "source_provenance":SOURCES,
      "evidence_notes":"Поля договора — исторический архив ЕИС, страницы сегодня 404. Итоговый протокол и ТЗ получены первично; не приписывать победителю статус подписавшего поставщика.",
    }
    out["hardware"]={
      "technology":"КЭПФ: компоненты батареи статических конденсаторов",
      "voltage_kv":12,"frequency_hz":50,"units_total":10,
      "power_total_kvar":5250,
      "items":[
        {"model":"КЭПФ-12-450-2УХЛ1","qty":5,"power_each_kvar":450,
         "current_a":37.5,"capacitance_uf":9.95,"dimensions_mm":"345×178×700",
         "nmc_unit_inc_vat_rub":294500,"archived_contract_unit_rub":292000},
        {"model":"КЭПФ-12-600-2УХЛ1","qty":5,"power_each_kvar":600,
         "current_a":50.0,"capacitance_uf":13.26,"dimensions_mm":"380×200×950",
         "nmc_unit_inc_vat_rub":321200,"archived_contract_unit_rub":318000}],
      "replacement":"Позиция КЭПФ-12-450 — замена CHDB-992 ABB по письму покупателя",
      "requirements":["Новые изделия, не восстановленные",
        "Не менее 12 мес. гарантии с даты поставки",
        "МЭК 60871-4: внутренние плавкие предохранители",
        "Встроенные разрядные резисторы, экологически безопасная пропиточная жидкость",
        "Требуется положительная аттестация ПАО «Россети» и подтверждающие документы",
        "Изделия одной даты изготовления, не старше 3 месяцев на момент поставки"],
      "delivery_due":"80 календарных дней после подписания договора; досрочная поставка допустима",
      "delivery_place":"Склад заказчика, г. Москва, Старокаширское ш., 4А",
      "payment_terms":"30 раб. дней после приёмки либо 7 раб. дней для победителя-МСП; в итоговом протоколе указано 7 раб. дней",
      "price_scope":"НМЦ включает доставку, страхование, пошлины, налоги и иные расходы",
      "source_codes":["TZ","PROTOCOL","ITEMS"] }
    out["bid_rejection"]={
      "company":"ООО «Серпуховский конденсаторный завод «КВАР»",
      "inn":"5043061102","offer_rub":1960906,
      "reason1":"Отсутствует справка ФНС КНД 1120101",
      "reason2":"В предложении на КЭПФ-12-600 ток 37,5 А, требуется 50 А",
      "conclusion":"Отклонённая цена не считается победившей ставкой, договором или продажей",
      "source_codes":["PROTOCOL"] }
    out["missing_and_conflicts"]=[
      "Подписавший договор поставщик и его ИНН не раскрыты доступной публичной карточкой",
      "Фактический OEM неизвестен; страна регистрации изготовителя (Казахстан) не подтверждает страну производства",
      "Подписанный текст договора и товарные накладные не получены",
      "Фактическая отгрузка, приёмка и оплата не подтверждены",
      "Текущий статус ЕИС не перепроверен — публичный URL возвращает HTTP 404",
      "НДС исторической записи договора не перепроверен отдельно (НДС 22% подтверждён в протоколе и ТЗ)" ]
    assert out["nmck_rub"]==sum(i["qty"]*i["nmc_unit_inc_vat_rub"] for i in out["hardware"]["items"])
    assert out["contract_total_archived_rub"]==sum(i["qty"]*i["archived_contract_unit_rub"] for i in out["hardware"]["items"])
    assert out["hardware"]["power_total_kvar"]==sum(i["qty"]*i["power_each_kvar"] for i in out["hardware"]["items"])
    def field(label,value,grade,sources,remark=""):
        return {"field":label,"value":value,"status":grade,
                "source_ids":sources,"note":remark}
    ev=[
      field("canonical_id",out["case_id"],"verified",["ETP"]),
      field("procedure",out["procedure"],"verified",["ETP"]),
      field("etp_id",out["etp_id"],"verified",["ETP"]),
      field("lot_no",out["lot_no"],"verified",["ETP"]),
      field("regime",out["regime"],"verified",["ETP"]),
      field("purchase_method",out["method"],"verified",["ETP"]),
      field("buyer",out["buyer"],"verified",["PROTOCOL"]),
      field("buyer_inn",out["buyer_inn"],"verified",["PROTOCOL"]),
      field("organizer",out["organizer"],"verified",["ETP"]),
      field("beneficiary",None,"not_verified",[]),
      field("delivery_address",out["location"],"verified",["TZ"]),
      field("subject",out["subject"],"verified",["TZ","PROTOCOL"]),
      field("publication_date",out["publication"],"verified",["ETP"]),
      field("revision_date",out["revision"],"verified",["ETP"]),
      field("deadline",out["deadline"],"verified",["ETP"]),
      field("protocol_date",out["protocol_date"],"verified",["PROTOCOL"]),
      field("protocol_published",out["protocol_published"],"verified",["ETP"]),
      field("protocol_number",out["protocol_number"],"verified",["PROTOCOL"]),
      field("component_voltage_kv",12,"verified",["TZ"]),
      field("model_450_quantity",5,"verified",["TZ"]),
      field("model_600_quantity",5,"verified",["TZ"]),
      field("total_nameplate_kvar",5250,"derived_verified",["TZ"]),
      field("model_450_current_a",37.5,"verified",["TZ"]),
      field("model_600_current_a",50,"verified",["TZ"]),
      field("frequency_hz",50,"verified",["TZ"]),
      field("warranty_months_min",12,"verified",["TZ"]),
      field("safety_and_approval","IEC 60871-4; аттестация Россетей","verified",["TZ"]),
      field("initial_price_rub",out["nmck_rub"],"verified",["TZ","PROTOCOL"]),
      field("vat_initial_percent",22,"verified",["TZ","PROTOCOL"]),
      field("winner_offer_rub",out["winning_bid_rub"],"verified",["PROTOCOL"]),
      field("competing_bids",3,"verified",["PROTOCOL"]),
      field("commission_winner",out["winner"],"verified",["PROTOCOL"]),
      field("commission_winner_inn",out["winner_inn"],"verified",["PROTOCOL"]),
      field("rank2","ООО «ТО-СТРОЙМОНТАЖ» · 3 078 500 ₽","verified",["PROTOCOL"]),
      field("rejected_bid","КВАР · 1 960 906 ₽","verified",["PROTOCOL"]),
      field("rejection_reason",out["bid_rejection"]["reason2"],"verified",["PROTOCOL"]),
      field("contract_registry_number",out["registry_number"],"archived_primary",["EIS"]),
      field("registered_contract_amount_rub",out["contract_total_archived_rub"],"archived_primary",["EIS"]),
      field("contract_internal_number",out["contract_number_archive"],"archived_primary",["EIS"]),
      field("contract_date",out["contract_date_archive"],"archived_primary",["EIS"]),
      field("historical_contract_item_prices",out["hardware"]["items"][0]["archived_contract_unit_rub"],"archived_primary",["ITEMS"]),
      field("signed_supplier_name",None,"not_verified",[]),
      field("signed_supplier_inn",None,"not_verified",[]),
      field("manufacturer_oem",None,"not_verified",[]),
      field("country_manufactured",None,"not_verified",[]),
      field("registered_manufacturer_country","Республика Казахстан","archived_primary",["EIS"]),
      field("physical_delivery",None,"not_verified",[]),
      field("acceptance_certificate",None,"not_verified",[]),
      field("actual_payment_rub",None,"not_verified",[]),
      field("epc_contractor",None,"not_applicable",[],"Не предмет договора: поставка компонентов"),
      field("design_contractor",None,"not_verified",[]),
      field("contract_vat_basis",None,"not_verified",[]),
    ]
    out["field_evidence"]=ev
    assert len({q["field"] for q in ev})==len(ev)
    for q in ev:
        assert all(z in SOURCES for z in q["source_ids"])
    out["reference_template_status"]="working_exemplar_complete_fields_not_all_independently_verified"
    return out

if __name__=="__main__":
    OUT.parent.mkdir(parents=True,exist_ok=True)
    r=build()
    OUT.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print("CREATED",OUT,"bytes",OUT.stat().st_size)
