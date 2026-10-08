"""Bounded source-observation bridge from RI223 XML to existing tender analysis.

This deliberately does NOT synthesize GO/NO-GO, legal effectiveness, eligibility,
or source-grounded textual answers. XML SHA + member + XPath are separate from
Data Platform chunk citations and must be presented as such.
"""

from __future__ import annotations

import re
from typing import Any

_SHA256 = re.compile(r"[0-9a-f]{64}", re.ASCII)
_MAX_REVISIONS = 32
_MAX_LOTS = 50
_MAX_POSITIONS_PER_LOT = 100
_MAX_EXPLANATIONS = 64
_MAX_TEXT = 1200


def _bounded(value: object) -> str | None:
    if not isinstance(value, (str, int, float)):
        return None
    result = " ".join(str(value).split())
    return result[:_MAX_TEXT] if result else None


def _provenance(raw: object) -> dict[str, str] | None:
    if not isinstance(raw, dict):
        return None
    if raw.get("regime") != "223fz" or raw.get("source") != "RI223_getDocsIP":
        return None
    xml_hash = raw.get("xml_sha256")
    archive_hash = raw.get("archive_sha256")
    member = raw.get("xml_member")
    xpath = raw.get("xpath")
    if not (
        isinstance(xml_hash, str)
        and _SHA256.fullmatch(xml_hash)
        and isinstance(archive_hash, str)
        and _SHA256.fullmatch(archive_hash)
        and isinstance(member, str)
        and member.lower().endswith(".xml")
        and 0 < len(member) <= 256
        and isinstance(xpath, str)
        and xpath.startswith("/")
        and 0 < len(xpath) <= 512
    ):
        return None
    return {
        "source": "RI223_getDocsIP",
        "xml_member": member,
        "xml_sha256": xml_hash,
        "archive_sha256": archive_hash,
        "xpath": xpath,
    }


def _observation(
    kind: str,
    data: dict[str, object],
    provenance: object,
) -> dict[str, Any] | None:
    evidence = _provenance(provenance)
    if evidence is None:
        return None
    return {
        "kind": kind,
        "fields": {
            key: val for key, raw in data.items() if (val := _bounded(raw)) is not None
        },
        "evidence": evidence,
        "interpretation": "XML_SOURCE_OBSERVATION_ONLY",
    }


def project_ri223_source_facts(
    law_type: str | None,
    raw_payload: object,
) -> list[dict[str, Any]]:
    """Return only individually source-cited facts; omit unverified fields.

    This complements, but never replaces, Data Platform document citations.
    Unsupported or unverified payload cannot become apparent 'facts'.
    """
    if law_type != "223fz" or not isinstance(raw_payload, dict):
        return []
    payload = raw_payload
    if payload.get("source_subsystem") != "RI223":
        nested = payload.get("soap_raw_payload")
        if not isinstance(nested, dict):
            return []
        payload = nested
    if (
        payload.get("source_regime") != "223fz"
        or payload.get("source_subsystem") != "RI223"
    ):
        return []
    archive_sha256 = payload.get("archive_sha256")
    if not isinstance(archive_sha256, str) or not _SHA256.fullmatch(archive_sha256):
        return []

    output: list[dict[str, Any]] = []
    history = payload.get("notice_versions")
    if isinstance(history, list):
        for item in history[:_MAX_REVISIONS]:
            if not isinstance(item, dict):
                continue
            observation = _observation(
                "notice_revision",
                {
                    "source_version": item.get("source_version"),
                    "publication_datetime": item.get("publication_datetime"),
                    "modification_datetime": item.get("modification_datetime"),
                    "submission_close_datetime": item.get("submission_close_datetime"),
                    "modification_description": item.get("modification_description"),
                    "lot_count": item.get("lot_count"),
                    "source_status_code": item.get("source_status_code"),
                },
                item.get("evidence"),
            )
            if observation:
                output.append(observation)

    lots = payload.get("lots")
    if isinstance(lots, list):
        for lot in lots[:_MAX_LOTS]:
            if not isinstance(lot, dict):
                continue
            observation = _observation(
                "lot",
                {
                    "ordinal_number": lot.get("ordinal_number"),
                    "subject": lot.get("subject"),
                    "initial_sum": lot.get("initial_sum"),
                    "currency_code": lot.get("currency_code"),
                    "position_count": (
                        len(lot["positions"])
                        if isinstance(lot.get("positions"), list)
                        else None
                    ),
                },
                lot.get("evidence"),
            )
            if observation:
                output.append(observation)
            positions = lot.get("positions")
            if not isinstance(positions, list):
                continue
            for position in positions[:_MAX_POSITIONS_PER_LOT]:
                if not isinstance(position, dict):
                    continue
                position_observation = _observation(
                    "lot_position",
                    {
                        "lot_ordinal_number": lot.get("ordinal_number"),
                        "ordinal_number": position.get("ordinal_number"),
                        "okpd2_code": position.get("okpd2_code"),
                        "okpd2_name": position.get("okpd2_name"),
                        "quantity": position.get("quantity"),
                        "unit_code": position.get("unit_code"),
                        "unit_name": position.get("unit_name"),
                    },
                    position.get("evidence"),
                )
                if position_observation:
                    output.append(position_observation)

    explanations = payload.get("explanations")
    if isinstance(explanations, list):
        for explanation in explanations[:_MAX_EXPLANATIONS]:
            if not isinstance(explanation, dict):
                continue
            observation = _observation(
                "explanation",
                {
                    "source_guid": explanation.get("source_guid"),
                    "request_date": explanation.get("request_date"),
                    "publish_date": explanation.get("publish_date"),
                    "request_subject_info": explanation.get("request_subject_info"),
                    "source_description": explanation.get("source_description"),
                    "source_status_code": explanation.get("source_status_code"),
                    "source_lot_binding": "UNKNOWN",
                },
                explanation.get("evidence"),
            )
            if observation:
                output.append(observation)
    return [
        record
        for record in output
        if record["evidence"]["archive_sha256"] == archive_sha256
    ]


_LABELS = {
    "notice_revision": "Версия извещения (наблюдаемая)",
    "lot": "Лот",
    "lot_position": "Позиция лота",
    "explanation": "Разъяснение (источник)",
}

_FIELD_LABELS = {
    "source_version": "версия",
    "publication_datetime": "публикация",
    "modification_datetime": "изменение",
    "submission_close_datetime": "срок подачи",
    "modification_description": "описание изменения",
    "lot_count": "лотов",
    "source_status_code": "код источника",
    "ordinal_number": "номер",
    "lot_ordinal_number": "лот",
    "subject": "предмет",
    "initial_sum": "начальная сумма лота",
    "currency_code": "валюта",
    "position_count": "позиций",
    "okpd2_code": "ОКПД2",
    "okpd2_name": "наименование ОКПД2",
    "quantity": "количество",
    "unit_code": "код единицы",
    "unit_name": "единица",
    "source_guid": "GUID",
    "request_date": "дата запроса",
    "publish_date": "дата публикации",
    "request_subject_info": "вопрос",
    "source_description": "описание",
    "source_lot_binding": "привязка к лоту",
}


def render_ri223_source_facts(facts: list[dict[str, Any]]) -> list[str]:
    if not facts:
        return []
    lines = [
        "## Структурированные наблюдения ЕИС (223-ФЗ)",
        "",
        (
            "Это поля исходных RI223 XML с технической привязкой к источнику, "
            "а не вывод LLM, проверка действующей редакции или правовая экспертиза."
        ),
        (
            "Описания версий, вопросы и суммы относятся только к своим источникам/лотам. "
            "Совокупная цена многолотовой закупки и юридический статус не выводятся."
        ),
        "",
    ]
    for observation in facts:
        fields = observation["fields"]
        evidence = observation["evidence"]
        kind = observation["kind"]
        lines.append(
            "**"
            + _LABELS.get(kind, "Поле ЕИС")
            + ":** "
            + "; ".join(
                _FIELD_LABELS.get(k, k) + " — " + str(v) for k, v in fields.items()
            )
        )
        lines.append(
            "Источник XML: "
            + evidence["xml_member"]
            + "; SHA-256: "
            + evidence["xml_sha256"]
            + "; XPath: "
            + evidence["xpath"]
        )
        lines.append("")
    return lines
