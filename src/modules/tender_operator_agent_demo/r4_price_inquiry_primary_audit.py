"""Independent original-source expert audit of three EIS price enquiries.

The previous R4 'no_data' refers ONLY to competitive getDocsIP transport,
not absence of official price-inquiry cards, records or their attachments.
Read-only replay of PINNED original EIS HTML receipts and 2026-10-14 official
attachment bytes; never construct a competitive bid or trust the model.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

_PRICE_PRIMARY_PIN = "b1f1a430821a63439adfac6576ef493acf9d43f9ca5e062c2d32a87468e002f0"
_ATTACHMENT_RECEIPT_PIN = "45dde4e4687700fa73182b2ee37cb3e53b4f0a7de15addfada8afff0a05129ff"
_CASES = {
    "0148300050426000047": {
        "title": "Оказание услуг по сопровождению и модернизации сайта",
        "customer": "АДМИНИСТРАЦИЯ МУНИЦИПАЛЬНОГО ОБРАЗОВАНИЯ ГОРОДСКОЙ ОКРУГ ЛОСИНО-ПЕТРОВСКИЙ",
        "published": "14.09.2026",
        "pricing_deadline": "15.09.2026 16:10",
        "official_page_status": "Завершен",
        "attachment_count": 1,
        "source_citation_labels": ["Описание объекта закупки сайт"],
        "scope": "Модернизация нескольких сайтов администрации, адаптация страниц, производительность и права на результат.",
        "material_risks": [
            "В приложенном задании на работы 2026 года указан срок действия договора до 31 декабря 2025 года — требуется исправленное условие.",
            "Объём включает три сайта, права на результаты работ и длительное сопровождение; нельзя оценивать только главную страницу.",
            "В ТЗ предусмотрено продление лицензии «1С-Битрикс» на три года, что требует отдельного расчёта внешних расходов.",
            "В официальной карточке указан заказчик Московской области; регион «Мордовия» во вторичном каталоге не подтверждается первоисточником.",
        ],
        "proofs_in_extracts": [
            ("0148300050426000047-1.extracted-private.txt", "до «31» декабря 2025 года"),
            ("0148300050426000047-1.extracted-private.txt", "https://sd.lospet.ru/"),
            ("0148300050426000047-1.extracted-private.txt", "https://ksp.lospet.ru/"),
            ("0148300050426000047-1.extracted-private.txt", "должна быть продлена на 3 года"),
        ],
    },
    "0318200087026000163": {
        "title": "Оказание услуги по модернизации интернет-сайта www.gbukkmsk.ru",
        "customer": 'ГОСУДАРСТВЕННОЕ БЮДЖЕТНОЕ УЧРЕЖДЕНИЕ КРАСНОДАРСКОГО КРАЯ "ГОРОД СПОРТА"',
        "published": "18.06.2026",
        "pricing_deadline": "18.06.2026 12:30",
        "official_page_status": "Завершен",
        "attachment_count": 2,
        "source_citation_labels": ["ОБРАЗЕЦ ОТВЕТА НА ЗАПРОС ЦЕН без 1875", "Сайт ООЗ — копия"],
        "scope": "Модернизация сайта с переносом контента, адаптивной вёрсткой, новой административной панелью и базовой поисковой оптимизацией.",
        "material_risks": [
            "На перенос контента, переработку интерфейса, административную панель и другие работы отведено всего пять календарных дней с даты заключения договора.",
            "В техническом задании предусмотрена фотосъёмка руководства; оплата — после приёмки в течение семи рабочих дней.",
            "Заказчик находится в Краснодарском крае, а работы выполняются по месту нахождения исполнителя. Нельзя полагаться на ошибочную географическую привязку агрегаторов.",
        ],
        "proofs_in_extracts": [
            ("0318200087026000163-2.extracted-private.txt", "в течение 5 календарных дней с даты подписания Контракта"),
            ("0318200087026000163-2.extracted-private.txt", "в течение 7 рабочих дней"),
            ("0318200087026000163-2.extracted-private.txt", "организация фотосъемки"),
        ],
    },
    "0348100024426000052": {
        "title": "Выполнение работ по развитию и модернизации платформы управления типовым сайтом Государственного казенного учреждения «Центр занятости населения Московской области»",
        "customer": 'ГОСУДАРСТВЕННОЕ КАЗЕННОЕ УЧРЕЖДЕНИЕ МОСКОВСКОЙ ОБЛАСТИ "ЦЕНТР ЗАНЯТОСТИ НАСЕЛЕНИЯ МОСКОВСКОЙ ОБЛАСТИ"',
        "published": "23.09.2026",
        "pricing_deadline": "24.09.2026 16:00",
        "official_page_status": "Завершен",
        "attachment_count": 1,
        "source_citation_labels": ["ООЗ ДОРАБОТКА САЙТА"],
        "scope": "Развитие существующей платформы сайта по подробному техническому заданию; работа внутри используемой архитектуры, включая отдельные модули и взаимодействия.",
        "material_risks": [
            "Приложение — PDF на 83 физические страницы, а не краткое описание трёх доработок; необходимо оценивать полный объём.",
            "Задание требует работы без изменения существующей технологической архитектуры; срок окончания указан до 15 декабря 2026 года.",
            "Формулировки ТЗ затрагивают сопровождение и взаимодействие с действующими модулями платформы; трудоёмкость нельзя оценивать только по трём позициям краткой карточки.",
        ],
        "proofs_in_extracts": [
            ("0348100024426000052-1.extracted-private.txt", "15 декабря 2026 года включительно"),
            ("0348100024426000052-1.extracted-private.txt", "исключительно в рамках существующей технологической архитектуры"),
        ],
    },
}
_BINARY_RECEIPTS = {
    "0148300050426000047-1.docx": ("ef06c6624e2493504348ce66f73f618d8770f0a7d9540c94a5cffea4db6f99cb", 34578),
    "0318200087026000163-1.doc": ("3533cfcc0c8a8c3fc23e204da992c4047707ef7964a515c26c7c8a839d00ec2f", 37888),
    "0318200087026000163-2.docx": ("08ca3ba6a845d27c08c1da8b489d97adcca5ed9948aa7e0335ef5af4113974e5", 25026),
    "0348100024426000052-1.pdf": ("830a4517c8a6b27b4c0759e20b4e80aed398c5ba6514d7cdeda0f10ea2320169", 1203863),
}


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _official_urls(number: str) -> dict[str, str]:
    base="https://zakupki.gov.ru/epz/pricereq/"
    return {
        "search":base+"search/results.html?searchString="+number,
        "card":base+"card/common-info.html?reestrNumber="+number,
        "docs":base+"card/docs.html?reestrNumber="+number,
    }


def _safe_verified_record(root: Path, receipt: dict[str, Any], number: str) -> dict[str, Any]:
    record = next((r for r in receipt["results"] if r["reg_number"] == number), None)
    if not record or not record.get("category_attested_by_first_party"):
        raise ValueError("official source record not independently attested")
    for key, url in _official_urls(number).items():
        recorded = record["pages"][key]
        if recorded["url"] != url or recorded["http_status"] != 200:
            raise ValueError("original EIS price inquiry card identity/status conflict")
        for extension, field in (("html","html_sha256"),("txt","text_sha256")):
            raw=(root/f"{number}-{key}.{extension}").read_bytes()
            if _sha(raw)!=recorded[field]:
                raise ValueError("official EIS original card/content digest mismatch")
        text=(root/f"{number}-{key}.txt").read_text(encoding="utf8")
        if number not in text or "Запрос" not in text:
            raise ValueError("EIS price inquiry original identity not in page")
    card=(root/f"{number}-card.txt").read_text(encoding="utf8")
    facts=_CASES[number]
    for key in ("title","customer","published","pricing_deadline","official_page_status"):
        if facts[key] not in card:
            raise ValueError(f"official EIS card does not support {key}")
    documents_html=(root/f"{number}-docs.html").read_text(encoding="utf8")
    linked_urls=list(dict.fromkeys(re.findall(
        r"https://zakupki[.]gov[.]ru/44fz/filestore/public/1[.]0/download/pricereq/file[.]html[?]uid=[A-F0-9]{32}",
        documents_html,
    )))
    if len(linked_urls)!=facts["attachment_count"]:
        raise ValueError("EIS original attachment inventory differs from cited filing")
    for name in facts["source_citation_labels"]:
        if name not in (root/f"{number}-docs.txt").read_text(encoding="utf8"):
            raise ValueError("original file name not cited by EIS documents tab")
    return {"primary_original_card_sha256":record["pages"]["card"]["html_sha256"],
            "primary_original_docs_sha256":record["pages"]["docs"]["html_sha256"],
            "card_url":record["pages"]["card"]["url"],
            "attachment_inventory_count":len(linked_urls)}


def reconcile_price_inquiry_originals(
    matrix: dict[str, Any], official_root: Path,
) -> dict[str, Any]:
    """Upgrade 3 SOAP archive gaps to original EIS enquiry evidence, not GO."""
    receipts=(official_root/"first-party-registry-receipt.json").read_bytes()
    attachment_root=official_root/"official-attachments-private-20261014"
    attachment_receipts=(attachment_root/"manifest-private.json").read_bytes()
    if _sha(receipts)!=_PRICE_PRIMARY_PIN or _sha(attachment_receipts)!=_ATTACHMENT_RECEIPT_PIN:
        raise ValueError("independent primary source proof differs from pinned receipt")
    receipt=json.loads(receipts)
    manifest=json.loads(attachment_receipts)
    if len(receipt.get("results",[]))!=3 or {r["reg_number"] for r in receipt["results"]}!=set(_CASES):
        raise ValueError("official price request registry original set incomplete/duplicated")
    if len(manifest)!=4 or {x["local_file"] for x in manifest}!=set(_BINARY_RECEIPTS):
        raise ValueError("original price inquiry attachment inventory incomplete or duplicated")
    by_id={}
    for att in manifest:
        name=att["local_file"]
        expected_sha,expected_size=_BINARY_RECEIPTS[name]
        if (att["status"]!="DOWNLOADED_ORIGINAL" or att["http_status"]!=200
                or att["sha256"]!=expected_sha or att["bytes"]!=expected_size):
            raise ValueError("official downloaded original attachment receipt differs")
        raw=(attachment_root/name).read_bytes()
        if _sha(raw)!=expected_sha or len(raw)!=expected_size:
            raise ValueError("attachment bytes do not match official download receipt")
        by_id.setdefault(att["registry_number"],[]).append(att)
    cases=list(matrix.get("cases") or [])
    if len(cases)!=20 or len({c.get("reg_number") for c in cases})!=20:
        raise ValueError("R4 case collection does not match canonical twenty")
    import copy
    out=copy.deepcopy(matrix)
    audited={}
    for number,facts in _CASES.items():
        proof=_safe_verified_record(official_root,receipt,number)
        row=next((c for c in out["cases"] if c["reg_number"]==number),None)
        if not row or row["official_archive_status"]!="NO_DATA" or row["source_case_file_count"]!=0:
            raise ValueError("original SOAP archive absence is not recorded for price enquiry")
        att=by_id.get(number,[])
        if len(att)!=facts["attachment_count"]:
            raise ValueError("downloaded original file inventory mismatch")
        for fn,phrase in facts["proofs_in_extracts"]:
            text=(attachment_root/fn).read_text(encoding="utf8")
            if re.sub(r"\s+", " ", phrase).strip() not in re.sub(r"\s+", " ", text).strip():
                raise ValueError("critical technical requirement not supported by original")
        row["verified_primary_record_type"]="EIS_PRICE_INFORMATION_REQUEST"
        row["customer_source_status"]="Запрос ценовой информации найден в ЕИС, документы доступны"
        row["customer_procedure_status"]="Сбор ценовой информации завершён"
        row["customer_competition_status"]="Это не конкурсная процедура подачи заявки"
        row["official_record_url"]=proof["card_url"]
        row["official_document_count"]=len(att)
        row["client_title"]=facts["title"]
        row["client_customer"]=facts["customer"]
        row["client_published_date"]=facts["published"]
        row["client_price_response_deadline"]=facts["pricing_deadline"]
        row["client_maximum_contract_price"]=None
        row["client_scope"]=facts["scope"]
        row["client_material_risks"]=list(facts["material_risks"])
        row["human_source_review"]="NOT_VERIFIED"
        row["expert_gold"]=False
        row["latest_official_notice_attested"]=False
        row["bid_ready"]=False
        row["blockers"]=[b for b in row["blockers"] if b!="OFFICIAL_ARCHIVE_NO_DATA_NOT_NONEXISTENCE"]
        row["blockers"].extend(["MARKET_PRICE_INFORMATION_ONLY_NO_COMPETITIVE_BID",
                                "LEGAL_SCOPE_AND_CONTRACT_REVIEW_NOT_SIGNED"])
        row["blockers"]=sorted(set(row["blockers"]))
        audited[number]={"official_source_card_sha256":proof["primary_original_card_sha256"],
                         "official_attachment_count":len(att),
                         "source_original_binary_sha256":[x["sha256"] for x in att],
                         "source_access_date":"2026-10-14",
                         "original_html_snapshot_date":"2026-10-12",
                         "not_a_competitive_bid":True}
    out["original_price_inquiries"]=audited
    out["summary"]["original_price_inquiry_cards_confirmed"]=len(audited)
    out["summary"]["price_inquiry_original_attachments_retrieved"]=4
    out["summary"]["cases_with_original_source_evidence"]=out["summary"]["archived_official_zip"]+len(audited)
    out["summary"]["competitive_archived_cases_not_currently_attested"]=out["summary"]["archived_official_zip"]
    out["summary"]["human_gold_reviews_completed"]=0
    out["summary"]["arv001_releases"]=0
    out["source_matrix_sha256"]=_sha(json.dumps(out["cases"],ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf8"))
    out["scope"]="20_ARCHIVED_R4_CASES_PLUS_THREE_OFFICIAL_NONCOMPETITIVE_PRICE_INQUIRIES_NO_LIVE_GO"
    out["human_gold_attested"]=False
    out["bid_ready"]=False
    return out


def client_expert_source_report(matrix: dict[str,Any]) -> str:
    """Only client-ready Russian report. Machine diagnostics are separate."""
    cases=matrix["cases"]
    out=[
        "# Независимая проверка источников по 20 процедурам",
        "",
        ("Проверены ранее сохранённые официальные сведения о закупках и запросах цен, а также доступные приложения. "
         "Выводы относятся к проверенным редакциям документов; перед коммерческим решением необходима сверка актуальной публикации."),
        "",
        "## Общий вывод",
        "",
        ("По 17 процедурам доступны исторические архивы извещений. Ещё три записи — запросы ценовой информации для исследования рынка, "
         "а не конкурсы на заключение договора. Официальные карточки и четыре приложения к ним получены и изучены."),
        ("В трёх исторических извещениях отмечены более поздние редакции, а по двум сохранённым аналитическим отчётам "
         "выявлены расхождения дат подачи заявок (0158300034526000388 и 0348100024426000039). "
         "Использовать прежние сроки без повторной проверки нельзя."),
        "Ни одна из 20 процедур не получила подтверждения права на участие или подписанного экспертного заключения.",
        "",
        "## Три отдельно проверенных запроса ценовой информации",
        "",
    ]
    for c in cases:
        if c.get("verified_primary_record_type")!="EIS_PRICE_INFORMATION_REQUEST":
            continue
        out.extend([
            f"### {c['reg_number']} — {c['client_title']}",
            "",
            f"**Заказчик:** {c['client_customer']}.",
            (f"**Цель публикации:** сбор ценовой информации для исследования рынка; сбор завершён. "
             f"**Срок ответа:** {c['client_price_response_deadline']}."),
            f"**Документы:** {c['official_document_count']} приложения получены с официального сайта.",
            f"**Объём:** {c['client_scope']}",
            "**Существенные замечания эксперта:**",
            *[f"- {v}" for v in c["client_material_risks"]],
            f"**Первоисточник:** {c['official_record_url']}",
            "**Вывод:** это не объявление конкурентных торгов; подготовка конкурсной заявки по этой карточке не предусмотрена.",
            "",
        ])
    out.extend([
        "## Что требуется перед решением об участии",
        "",
        ("Для остальных 17 процедур необходимо проверить последнюю опубликованную редакцию извещения и все приложенные условия, "
         "особенно ограничения допуска, сроки, проект договора, стоимость исполнения, гарантии и ответственность."),
        "Три ранее выявленные устаревшие архивные редакции и два несовпадения сроков требуют отдельного исправления.",
        "Заключения независимых экспертов пока не получены; автоматическое решение об участии недопустимо.",
        "",
    ])
    report="\n".join(out)
    for banned in ("no_data","getDocsIP","HTTP 409","SOURCE_UNAVAILABLE","Traceback","JSONDecodeError","UNKNOWN/DEFER","SHA256","status_code"):
        if banned in report:
            raise ValueError("customer report contains machine-only diagnostic")
    return report
