"""Non-decisional, source-attested comparison of archival contract/TZ/application wording.

Only exact first-party quotations from 4 preselected historically competitive
notices. A contrast in wording is NOT a legal contradiction or GO/no-GO.
Full legal review of other clauses and live EIS editions is still required.
"""
from __future__ import annotations

import hashlib
import re

_LOCATOR = re.compile(r"PARAGRAPH-\d+|TABLE-\d+ ROW-\d+ CELL-\d+")


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf8")).hexdigest()


# Fixed quotations and exact archive attachment names independently checked
# against the official SHA-attested original text. No licensed party is inferred.
_CROSS_DOCUMENT_CASES = (
    {
        "registry_number": "0349100009326000005",
        "topic": "Телематическая лицензия: исполнитель либо соисполнитель",
        "question": (
            "В ТЗ допускается лицензия у исполнителя и/или соисполнителя; "
            "контракт и требования к заявке называют исполнителя. "
            "Проверить применимость к участнику и допустимость соисполнителя."
        ),
        "sources": (
            ("Приложение 5_ Проект Контракта.docx",
             "Исполнитель должен иметь лицензию на телематические услуги связи"),
            (("Приложение  2_Описание обьекта закупки. Техническое задание. "
              "Сверенное - Актуальное 18.10.2024.doc"),
             "Наличие у Исполнителя (и/или соисполнителя) лицензии на телематические услуги связи"),
            ("Приложение  3_ Требования к содержанию, составу заявки и инструкцию по ее заполнению..docx",
             "наличие у Исполнителя лицензии на оказание телематических услуг связи является обязательным требованием"),
        ),
    },
    {
        "registry_number": "0895100000126000897",
        "topic": "ФСТЭК и ФСБ: участник заявки и подрядчик/соисполнитель",
        "question": (
            "В требованиях к заявке лицензии ФСТЭК и ФСБ названы для участника; "
            "в контракте фигурируют подрядчик, субподрядчик, соисполнитель. "
            "Проверить законность и субъект каждого требования."
        ),
        "sources": (
            ("4 Требования к содержанию, составу заявки ОАЭФ-098.docx",
             "Участник закупки должен иметь лицензии:"),
            ("4 Требования к содержанию, составу заявки ОАЭФ-098.docx",
             "Лицензия ФСТЭК России на деятельность по технической защите конфиденциальной информации"),
            ("4 Требования к содержанию, составу заявки ОАЭФ-098.docx",
             "Лицензия ФСБ России на деятельность по разработке"),
            ("2 Проект контракта ОАЭФ-098.docx",
             "Подрядчик (субподрядчик, соисполнитель) - обязуется иметь следующие действующие лицензии:"),
        ),
    },
    {
        "registry_number": "0148200000526000028",
        "topic": "Права SiteSoft.Platform и отдельная лицензия ФСТЭК",
        "question": (
            "ТЗ фиксирует платформу заказчика. Документ о заявке отдельно "
            "перечисляет варианты подтверждения прав на неё и лицензию ФСТЭК. "
            "Нужно проверить объём допустимых прав и точную обязанность участника."
        ),
        "sources": (
            ("3_Описание объекта закупки.docx",
             "Сайт реализован на системе управления Сайтом SiteSoft.Platform"),
            ("4_Требования к содержанию, составу заявки.docx",
             "лицензионный договор с правообладателем ПО «SiteSoft.Platform»"),
            ("4_Требования к содержанию, составу заявки.docx",
             "сублицензионный договор с лицом, с которым правообладатель ПО «SiteSoft.Platform»"),
            ("4_Требования к содержанию, составу заявки.docx",
             "в составе заявки Исполнитель должен предоставить копию действующей лицензии"),
        ),
    },
    {
        "registry_number": "0372200172326000015",
        "topic": "Права на будущий сайт и права участника на результаты",
        "question": (
            "В контракте установлено соблюдение чужих исключительных прав, "
            "ТЗ предусматривает передачу прав на создаваемый сайт, а "
            "требования к заявке описывают владение правами участником. "
            "Не считать эти три формулировки тождественными."
        ),
        "sources": (
            ("Приложение_1_Проект_контракта.doc",
             "Обеспечить соблюдение всех исключительных прав на все результаты интеллектуальной деятельности"),
            ("Приложение_3_Описание_объекта_закупки_сайт.docx",
             "Исполнитель передает Заказчику исключительные права на созданный сайт"),
            ("приложение_4_Требования_к_содержанию,_составу_заявки_и_инструкция_по_заполнению.docx",
             "Обладание участником закупки исключительными правами на результаты интеллектуальной деятельности"),
        ),
    },
)


def verify_archival_scope_contrasts(
    verified_texts: dict[tuple[str, str], list[str]],
    expected: dict[tuple[str, str], dict],
) -> dict:
    """Fail closed on any original mismatch, missing quotation or ambiguous source."""
    attachments: dict[tuple[str, str], tuple[str, list[str], dict]] = {}
    for (number, binary_sha), texts in verified_texts.items():
        doc = expected[(number, binary_sha)]
        name = doc["original_filename"]
        key = number, name
        if key in attachments:
            raise ValueError("ambiguous identical source attachment filename")
        attachments[key] = binary_sha, texts, doc

    cases = []
    for spec in _CROSS_DOCUMENT_CASES:
        number = spec["registry_number"]
        sourced = []
        for original_filename, quote in spec["sources"]:
            key = number, original_filename
            if key not in attachments:
                raise ValueError("archival cross-document source not found")
            sha, texts, doc = attachments[key]
            matches = [
                (part, text, text.index(quote)) for part, text in enumerate(texts, 1)
                if text.count(quote) == 1
            ]
            if len(matches) != 1:
                raise ValueError("archival cross-document wording missing or ambiguous")
            part, content, position = matches[0]
            anchors = list(_LOCATOR.finditer(content, 0, position))
            source_locator = (
                anchors[-1].group(0) if anchors
                else f"Строка {content.count(chr(10), 0, position) + 1}"
            )
            sourced.append({
                "original_filename": original_filename,
                "original_binary_sha256": sha,
                "original_notice_source_method": doc["source_proof"],
                "text_part": part,
                "source_text_sha256": _sha(content),
                "source_locator": source_locator,
                "literal_start": position,
                "exact_archival_quote": quote,
                "quote_sha256": _sha(quote),
                "source_role_requires_expert_review": True,
                "legal_duty_confirmed": False,
            })
        if len({item["original_filename"] for item in sourced}) < 2:
            raise ValueError("cross-document contrast needs multiple independent originals")
        cases.append({
            "registry_number": number,
            "topic": spec["topic"],
            "scope_question": spec["question"],
            "independent_original_documents": len({
                item["original_filename"] for item in sourced
            }),
            "archival_source_excerpts": sourced,
            "scope_difference_status": "POTENTIAL_SCOPE_DIFFERENCE_EXPERT_REVIEW_REQUIRED",
            "expert_signed": False,
            "live_eis_edition_verified": False,
            "bid_ready": False,
        })
    return {
        "scope": "FOUR_ARCHIVED_SOURCE_ATTESTED_CROSS_DOCUMENT_WORDING_COMPARISONS",
        "case_count": len(cases),
        "cases": cases,
        "human_signed_legal_interpretations": 0,
        "current_eis_revision_attested": False,
        "bid_ready": False,
        "limitations": (
            "Exact quotes from separate original attachments illustrate textual "
            "scope differences, not proven legal conflicts. Cross-document context "
            "does not establish procurement legality, current EIS revisions, "
            "required participant qualifications or eligibility for tender."
        ),
    }
