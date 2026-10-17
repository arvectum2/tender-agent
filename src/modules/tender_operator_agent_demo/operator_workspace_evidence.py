"""Source-verified operator facts from the original, registry-matched EIS notice XML.

APR-03B: do not equate a generic source label with an attributable citation.
Only actual values read from the preserved notice file may become KNOWN.
"""
from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

from src.modules.tender_operator_agent_demo.eis_fact_values import (
    EIS_NOTICE_FACT_TAGS,
    verified_eis_fact_value,
)
from src.modules.tender_operator_agent_demo.upload_service import (
    get_demo_run_input_dir,
    load_demo_run_metadata,
)

_FIELDS = dict(EIS_NOTICE_FACT_TAGS)
_MAX_XML_BYTES = 5 * 1024 * 1024
_NUMBER = re.compile(r"\d{19}\Z")

# Official 44-FZ getDocsIP archives legitimately contain protocols, placement
# results and proposal outcomes alongside the notice. They may repeat the same
# purchaseNumber but MUST NOT be counted as alternative notice revisions.
_SUPPORTED_44FZ_NOTICE_TYPES = frozenset({
    "epNotificationEF2020",
    "epNotificationEZK2020",
    "epNotificationEOK2020",
})


def _is_notice_xml(root: ET.Element) -> bool:
    """Select the notice by its top-level EIS document type, not its number alone."""
    if _tag(root) == "notice":
        # Narrow legacy fixture of the read-only parser: still validated by
        # registry, field uniqueness and source file identification.
        return True
    if _tag(root) != "export":
        return False
    children = list(root)
    return len(children) == 1 and _tag(children[0]) in _SUPPORTED_44FZ_NOTICE_TYPES



def _tag(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _values(root: ET.Element, tag: str) -> list[str]:
    return list(dict.fromkeys(
        (element.text or "").strip()
        for element in root.iter()
        if _tag(element) == tag and (element.text or "").strip()
    ))


def _unknown() -> dict[str, Any]:
    return {"status": "UNKNOWN", "value": None, "evidence": []}


def _matching_notice_xml_candidates(run_id: str, metadata: dict[str, Any]) -> list[tuple[ET.Element, dict[str, Any]]]:
    # All paths are obtained from the existing run directory; never from an HTTP parameter.
    directory = get_demo_run_input_dir(run_id).resolve()
    matches: list[tuple[ET.Element, dict[str, Any]]] = []
    for item in metadata.get("files") or []:
        if not isinstance(item, dict) or str(item.get("extension") or "").lower() != ".xml":
            continue
        stored = str(item.get("stored_name") or "")
        if not stored:
            continue
        path = (directory / stored).resolve()
        if not path.is_relative_to(directory) or not path.is_file():
            continue
        if path.stat().st_size > _MAX_XML_BYTES:
            continue
        raw = path.read_bytes()
        if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
            continue
        try:
            parsed = ET.fromstring(raw)
        except ET.ParseError:
            continue
        if not _is_notice_xml(parsed):
            # e.g. epProtocolEZK2020Final / fcsPlacementResult, not a second
            # version of epNotificationEZK2020 with the same registry number.
            continue
        matches.append((parsed, item))
    number = str(
        metadata.get("procurement_notice_number")
        or metadata.get("procurement_id")
        or ""
    ).strip()
    if not _NUMBER.fullmatch(number):
        return []
    valid = [
        (xml, item) for xml, item in matches
        if [n for n in _values(xml, "purchaseNumber") if _NUMBER.fullmatch(n)] == [number]
    ]
    return valid

def _pinned_archived_notice_revision(
    run_id: str, metadata: dict[str, Any],
    candidates: list[tuple[ET.Element, dict[str, Any]]],
) -> tuple[ET.Element, dict[str, Any], int] | None:
    """Select the single HIGHEST ARCHIVED notice, only if the original ZIP proves it.

    The SHA/edition are rederived from a locally saved official getDocsIP ZIP,
    never supplied by an LLM or the report. Multiple latest-edition notice
    members, missing original ZIP or changed saved XML remain UNKNOWN.
    Historical source facts do NOT prove the live/current EIS edition.
    """
    if not candidates:
        return None
    recorded = metadata.get("official_eis_procedure")
    if not isinstance(recorded, dict) or recorded.get("status") != "ATTESTED_COMPETITIVE":
        return None
    number = metadata.get("procurement_id")
    filename = metadata.get("archive_stored_name")
    if (not isinstance(number, str) or not _NUMBER.fullmatch(number)
            or not isinstance(filename, str) or filename != Path(filename).name
            or not filename.endswith(".zip")):
        return None
    input_dir = get_demo_run_input_dir(run_id)
    archive_file = input_dir / filename
    if archive_file.is_symlink() or not archive_file.is_file():
        return None

    from src.modules.tender_operator_agent_demo.eis_official_procedure import (
        classify_official_eis_archive,
    )

    original = classify_official_eis_archive(archive_file, number)
    bound = ("status", "archive_sha256", "notice_xml_sha256",
             "source_purchase_number", "source_version", "notice_type")
    if (original.get("status") != "ATTESTED_COMPETITIVE"
            or any(original.get(key) != recorded.get(key) for key in bound)
            or type(original.get("source_version")) is not int):
        return None

    version = original["source_version"]
    chosen_filename = re.compile(
        r"epNotification(?:EF2020|EZK2020|EOK2020)_"
        + re.escape(number) + "_" + str(version) + r"_[A-Fa-f0-9]{32}\.xml\Z"
    )
    try:
        with zipfile.ZipFile(archive_file) as zipped:
            members = [i for i in zipped.infolist()
                       if chosen_filename.fullmatch(i.filename) and not i.is_dir()]
            if len(members) != 1 or members[0].file_size > _MAX_XML_BYTES:
                return None
            source_bytes = zipped.read(members[0])
        if hashlib.sha256(source_bytes).hexdigest() != original["notice_xml_sha256"]:
            return None
        selected = []
        for root, item in candidates:
            if item.get("original_name") != members[0].filename:
                continue
            stored = item.get("stored_name")
            if not isinstance(stored, str):
                continue
            from src.modules.tender_operator_agent_demo.operator_stored_file_paths import (
                checked_original_input_path,
            )
            path = checked_original_input_path(input_dir, stored)
            if hashlib.sha256(path.read_bytes()).hexdigest() == original["notice_xml_sha256"]:
                selected.append((root, item))
        if len(selected) != 1:
            return None
        return (*selected[0], version)
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile):
        return None


def _notice_xml(run_id: str, metadata: dict[str, Any]) -> tuple[ET.Element, dict[str, Any]] | None:
    """Compatibility entrypoint: never guess which competing XML is current."""
    candidates = _matching_notice_xml_candidates(run_id, metadata)
    return candidates[0] if len(candidates) == 1 else None


def _verified_fact(root: ET.Element, item: dict[str, Any], key: str) -> dict[str, Any]:
    tag = _FIELDS[key]
    values = _values(root, tag)
    if len(values) != 1:
        return _unknown()
    excerpt = values[0]
    value = verified_eis_fact_value(key, excerpt)
    if value is None:
        return _unknown()
    filename = Path(str(item.get("display_name") or item.get("original_name") or "")).name
    file_id = str(item.get("file_id") or "").strip()
    if not filename or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", file_id):
        return _unknown()
    return {
        "status": "KNOWN",
        "value": value,
        "evidence": [{
            "source_ref": "eis-xml:" + file_id + ":" + tag,
            "document": filename,
            "locator": "XML:" + tag,
            "excerpt": excerpt,
            "file_id": file_id,
        }],
    }


def get_operator_source_evidence(run_id: str) -> dict[str, Any]:
    metadata = load_demo_run_metadata(run_id)
    # The operator source layer is never permitted to present demo/manual files
    # as official EIS evidence, or to silently promote 223-FZ as supported.
    source = str(metadata.get("procurement_source") or "")
    facts = {field: _unknown() for field in _FIELDS}
    warnings: list[str] = []
    source_selection = "unsupported_source"
    source_candidate_count = 0
    if source != "zakupki_gov_ru_getdocs_ip":
        warnings.append("Нет подтверждённого исходного извещения XML ЕИС 44-ФЗ для этого запуска.")
    else:
        candidates = _matching_notice_xml_candidates(run_id, metadata)
        source_candidate_count = len(candidates)
        # When the saved run has an attested original ZIP, even a single
        # surviving XML candidate MUST match its selected archived edition.
        # Otherwise corrupting/removing the newest XML could silently promote
        # an obsolete v1 (while the true original ZIP contains v4).
        official = metadata.get("official_eis_procedure")
        has_pinned_archive = (
            isinstance(official, dict)
            and official.get("status") == "ATTESTED_COMPETITIVE"
            and isinstance(metadata.get("archive_stored_name"), str)
        )
        pinned_revision = (
            _pinned_archived_notice_revision(run_id, metadata, candidates)
            if has_pinned_archive else None
        )
        if has_pinned_archive and pinned_revision is None:
            source_selection = "archived_notice_source_hash_mismatch"
            warnings.append(
                "Сохранённый XML не совпадает с выбранной архивной редакцией "
                "оригинального ZIP ЕИС; поля остаются UNKNOWN."
            )
        elif pinned_revision is not None:
            xml, item, selected_version = pinned_revision
            source_selection = "pinned_latest_archived_notice_revision"
            for field in facts:
                facts[field] = _verified_fact(xml, item, field)
            warnings.append(
                f"Выбрана редакция № {selected_version} из сохранённого оригинального ZIP ЕИС. "
                "Текущая опубликованная редакция и возможность участия НЕ подтверждены."
            )
        elif len(candidates) > 1:
            source_selection = "ambiguous_notice_revisions"
            warnings.append(
                "Найдено несколько оригинальных XML для одного номера ЕИС; "
                "уникальная архивная редакция не доказана оригинальным ZIP. Поля UNKNOWN."
            )
        elif not candidates:
            source_selection = "no_unique_registry_matched_xml"
            warnings.append(
                "Нет единственного исходного XML с подтверждённым номером ЕИС; "
                "проверьте наличие и редакцию извещения."
            )
        else:
            source_selection = "single_registry_matched_xml"
            xml, item = candidates[0]
            for field in facts:
                facts[field] = _verified_fact(xml, item, field)
            if any(value["status"] != "KNOWN" for value in facts.values()):
                warnings.append("Часть полей XML неоднозначна или отсутствует; требуется проверка.")

    # A separately timestamped, source-rechecked archive observation is not
    # a live EIS legal status and must never upgrade GO or archived XML facts.
    source_revalidation = None
    if source == "zakupki_gov_ru_getdocs_ip":
        from src.modules.tender_operator_agent_demo.eis_archived_source_integrity import (
            verified_saved_observation,
        )
        source_revalidation = verified_saved_observation(run_id)

    from src.modules.tender_operator_agent_demo.eis_archived_deadline_status import (
        archived_notice_deadline_observation,
    )
    submission_cutoff = archived_notice_deadline_observation(
        facts["application_deadline"]
        if source == "zakupki_gov_ru_getdocs_ip"
        and source_selection == "pinned_latest_archived_notice_revision"
        else None
    )

    # Do not use the old report's claimed status to prove the content of EIS XML.
    return {
        "contract_version": "operator-eis-source-evidence-v1",
        "run_id": run_id,
        "registry_number": metadata.get("procurement_notice_number") or metadata.get("procurement_id"),
        "source": source,
        "source_selection": source_selection,
        "source_candidate_count": source_candidate_count,
        "source_revalidation": source_revalidation,
        "archived_submission_deadline_status": submission_cutoff,
        "facts": facts,
        "warnings": warnings,
        "human_control_required": True,
        "external_action_allowed": False,
    }
