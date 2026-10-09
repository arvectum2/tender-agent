"""Product-only evidence presentation adapter for EIS operator reports.

Keeps frozen R7 producer bytes, raw requirements and the Data Platform document
extraction contract separate. Adds only source-bound facts already verified
against a registry-matched original EIS XML during intake. No untrusted missing
field is inferred from heuristic document headings.
"""

from __future__ import annotations

from typing import Any

from src.modules.tender_operator_agent_demo.report_model import (
    _verified_notice_fact_projection,
)
from src.modules.tender_operator_agent_demo.schemas import (
    DemoDetailSection,
    DemoStep,
)

_EIS_SOURCE = "zakupki_gov_ru_getdocs_ip"
_TITLES = (
    ("procurement_title", "Предмет закупки"),
    ("application_deadline", "Окончание подачи заявок"),
    ("nmck", "НМЦК"),
)


def _facts_for_report(metadata: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Never promote a free-form document snippet as EIS-verified."""
    if metadata.get("procurement_source") != _EIS_SOURCE:
        return {}
    proof = metadata.get("_verified_notice_facts")
    if not isinstance(proof, dict):
        return {}
    file_id = proof.get("file_id")
    filename = proof.get("document")
    # The cited file must be among this run's preserved originals.
    files = metadata.get("files")
    if not isinstance(files, list) or not any(
        isinstance(file, dict)
        and file.get("file_id") == file_id
        and (file.get("display_name") or file.get("original_name")) == filename
        and str(file.get("extension") or "").lower() == ".xml"
        for file in files
    ):
        return {}
    procurement = metadata.get("procurement")
    procurement = procurement if isinstance(procurement, dict) else {}
    registry = metadata.get("procurement_id") or procurement.get("procurement_number")
    model = {
        "procurement_number": registry,
        "_verified_notice_facts": proof,
    }
    return _verified_notice_fact_projection(model)


def add_verified_notice_to_report_steps(
    metadata: dict[str, Any], steps: list[DemoStep],
) -> list[DemoStep]:
    """Add a traceable official passport before unverified heuristic prose.

    Only the EIS documentation run is changed; generic and frozen runs retain
    their existing compatibility-step shapes and stable ordering.
    """
    facts = _facts_for_report(metadata)
    if not facts:
        return steps
    entries: list[str] = []
    for key, title in _TITLES:
        fact = facts.get(key, {})
        if fact.get("status") != "KNOWN" or not fact.get("evidence"):
            continue
        locator = fact["evidence"][0]
        entries.append(
            f"{title}: {fact['value']} "
            f"[{locator['source_ref']}; {locator['document']}; {locator['locator']}]"
        )
    if not entries:
        return steps
    amended = []
    for step in steps:
        if step.key != "requirements":
            amended.append(step)
            continue
        # The legacy heuristic sometimes reports a section heading as the
        # procurement subject. Preserve other requirements but not that claim.
        existing = [
            item for item in step.findings
            if not (facts.get("procurement_title", {}).get("status") == "KNOWN"
                    and item.strip().lower().startswith("предмет закупки:"))
        ]
        official_subject_known = facts.get("procurement_title", {}).get("status") == "KNOWN"
        prior_sections = [
            section.model_copy(
                update={
                    "items": [
                        item
                        for item in section.items
                        if not (
                            official_subject_known
                            and item.strip().lower().startswith("предмет закупки:")
                        )
                    ]
                }
            )
            for section in step.result_sections
        ]
        sections = [
            DemoDetailSection(
                title="Официальные факты из исходного XML ЕИС",
                kind="bullets",
                items=entries,
            ),
            *prior_sections,
        ]
        amended.append(
            step.model_copy(
                update={
                    "result_summary": (
                        "Проверены официальные сведения из XML ЕИС; "
                        "остальные выводы требуют сверки с документами."
                    ),
                    "findings": [*entries, *existing],
                    "result_sections": sections,
                }
            )
        )
    return amended
