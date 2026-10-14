"""Verifiable clause leads from newly recovered original EIS contract attachments.

This is a conservative literal locator audit, not a full semantic or
legal eligibility assessment. Private originals never travel to GitHub.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

RECEIPT_SHA256 = "e2f86213e48a1fdf7fa146be22de77e3add59ed6d94b62713975963a2a5adfe8"

# An exact source document, text location, and clause substring is required.
# Categories describe QUESTIONS for legal/technical review, never bid blockers.
LEADS = (
    ("0148200000526000028", "attachment-04", "лицензионный договор с правообладателем ПО «SiteSoft.Platform»",
     "Права на используемую платформу", "Допуск / подтверждение прав"),
    ("0349100009326000005", "attachment-03", "лицензии на телематические услуги связи",
     "Телекоммуникационная лицензия", "Соответствие исполнителя / соисполнителя"),
    ("0349100009326000005", "attachment-03", "государственной аккредитации Министерством цифрового развития",
     "Государственная аккредитация", "Соответствие исполнителя"),
    ("0360600005326000018", "attachment-02", "в течение 60 (шестидесяти) календарных дней",
     "Срок выполнения работ", "Планирование исполнения"),
    ("0149200002326001555", "attachment-02", "списке уязвимостей банка данных угроз безопасности информации ФСТЭК России",
     "Контроль уязвимостей", "Информационная безопасность"),
    ("0149200002326001555", "attachment-02", "передает заказчику указанные права посредством заключения лицензионного договора",
     "Передача прав на результаты", "Интеллектуальные права"),
    ("0895100000126000897", "attachment-02", "мер по обеспечению безопасности персональных данных",
     "Меры защиты персональных данных", "Информационная безопасность"),
    ("0895100000126000897", "attachment-02", "включая стоимость исключительного права на результаты Работ",
     "Стоимость исключительных прав", "Экономика исполнения / интеллектуальные права"),
    ("0127100008626000013", "attachment-02", "ОБЕСПЕЧЕНИЕ ИСПОЛНЕНИЯ КОНТРАКТА",
     "Обеспечение исполнения", "Финансовые условия"),
    ("0127100008626000013", "attachment-02", "ПОРЯДОК СДАЧИ И ПРИЕМКИ УСЛУГ",
     "Приёмка результатов", "Исполнение и приёмка"),
    ("0348100024426000039", "attachment-05", "в ПИК ЕАСУЗ обрабатываются исключительно общедоступные персональные данные",
     "Обработка персональных данных в системе", "Информационная безопасность"),
    ("0348100024426000039", "attachment-05", "использование для подписания электронных документов КЭП средств криптографической защиты информации",
     "Подписание в системе документооборота", "Исполнение / электронный документооборот"),
)


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def verify_material_clause_leads(private_folder: Path) -> dict:
    receipt = private_folder / "text-extraction-private-receipt.json"
    raw = receipt.read_bytes()
    if _hash(raw) != RECEIPT_SHA256:
        raise ValueError("source text manifest differs from pinned private original audit")
    rows = json.loads(raw)
    if len(rows) != 25:
        raise ValueError("not all twenty-five freshly recovered texts available")
    index = {}
    for record in rows:
        number = record["registry_number"]
        filename = record["text_private_file"]
        if (not re.fullmatch(r"\d{19}", number)
                or not filename.startswith("attachment-")
                or Path(filename).name != filename
                or record["text_status"] != "TEXT_EXTRACTED"):
            raise ValueError("invalid retrieved official document text receipt")
        path = private_folder / number / filename
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(private_folder.resolve()):
            raise ValueError("untrusted saved original text location")
        content = path.read_bytes()
        if (_hash(content) != record["text_sha256"]
                or len(content.decode("utf8")) != record["text_chars"]
                or not re.fullmatch("[a-f0-9]{64}", record["origin_sha256"])):
            raise ValueError("original binary/normalized text receipt mismatch")
        key = number, filename.split(".")[0]
        if key in index:
            raise ValueError("duplicate original procurement attachment slot")
        index[key] = (record, content.decode("utf8"))
    if len(index) != 25:
        raise ValueError("some original attachment texts are missing")
    results = []
    for n, slot, needle, title, question in LEADS:
        evidence = index.get((n, slot))
        if evidence is None:
            raise ValueError("source clause references wrong original procurement/attachment")
        meta, content = evidence
        count = content.count(needle)
        if count < 1:
            raise ValueError("original contract clause missing from pinned text")
        offset = content.find(needle)
        paragraph = re.findall(r"PARAGRAPH-\d+|TABLE-\d+ ROW-\d+ CELL-\d+", content[:offset])
        anchor = paragraph[-1] if paragraph else f"Строка {content.count(chr(10), 0, offset) + 1}"
        results.append({
            "registry_number": n,
            "original_document_name": meta["source_name"],
            "original_binary_sha256": meta["origin_sha256"],
            "normalized_text_sha256": meta["text_sha256"],
            "evidence_locator": anchor,
            "character_offset": offset,
            "literal_occurrences_in_same_original": count,
            "literal_quote": needle,
            "literal_quote_sha256": _hash(needle.encode("utf8")),
            "review_subject": title,
            "question_category": question,
            "interpretation_status": "REQUIRES_INDEPENDENT_LEGAL_TECHNICAL_REVIEW",
            "human_signed": False,
            "bid_ready": False,
        })
    cases = Counter(x["registry_number"] for x in results)
    if len(results) != 12 or len(cases) != 7:
        raise ValueError("known selected original material conditions not all located")
    return {
        "scope": "PRIVATE_OFFICIAL_EXTRACT_25_EARLY_SEMANTIC_LEADS_NOT_ALL_96",
        "source_original_attachments_with_text": len(index),
        "archived_original_total": 96,
        "independently_located_clause_leads": len(results),
        "procurements_with_early_clause_leads": len(cases),
        "procurements_without_this_manual_clause_sampling": 20-len(cases),
        "full_contract_semantic_reviews_signed": 0,
        "current_eis_revision_attested": False,
        "bid_ready": False,
        "leads": results,
    }


def validate_clause_leads_against_official_attachments(
    leads: dict, official_coverage: dict,
) -> dict:
    """Tie each extracted clause back to the exact selected EIS notice binary.

    A saved normalized text digest alone is never an original source proof.
    """
    if official_coverage.get("source_shas_attested") != 96:
        raise ValueError("incomplete official selected-archive attachment inventory")
    by_procurement = {
        item["registry_number"]: item for item in official_coverage.get("cases", [])
    }
    if len(by_procurement) != 20:
        raise ValueError("procurement archive source inventory incomplete")
    checked = 0
    for entry in leads.get("leads", []):
        case = by_procurement.get(entry["registry_number"])
        if not case:
            raise ValueError("original clause belongs to unverified procurement")
        source = [
            doc for doc in case["documents"]
            if doc["original_filename"] == entry["original_document_name"]
            and doc["original_document_sha256"] == entry["original_binary_sha256"]
        ]
        if len(source) != 1:
            raise ValueError("quoted original contract not attested in chosen EIS notice")
        if not entry.get("literal_quote") or entry["human_signed"] is not False:
            raise ValueError("invalid or human-approved material finding")
        checked += 1
    if checked != 12:
        raise ValueError("partial source clause provenance cannot be promoted")
    return {
        "original_binary_sha_and_notice_edition_links_verified": checked,
        "human_legal_approvals": 0,
        "bid_ready": False,
    }
