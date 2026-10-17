"""Add a source-reverified EIS evidence panel to a legacy operator HTML report.

Product-only, official-EIS-only projection AFTER the frozen R7 producer.
Never promote arbitrary saved model text or metadata source labels as proof.
"""
from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

_FIELDS = (
    ("procurement_title", "Предмет закупки"),
    ("application_deadline", "Окончание подачи заявок"),
    ("nmck", "НМЦК"),
)
_PANEL_ID = 'id="official-eis-citations"'


def append_official_eis_citations(
    *, report_path: Path, run_id: str, metadata: dict[str, Any]
) -> int:
    """Return count of cited, original-XML-verified facts actually rendered."""
    if metadata.get("procurement_source") != "zakupki_gov_ru_getdocs_ip":
        return 0

    from src.modules.tender_operator_agent_demo.operator_workspace_evidence import (
        get_operator_source_evidence,
    )

    # Source evidence re-reads the saved, registry-matched, unique XML bytes.
    proof = get_operator_source_evidence(run_id)
    if proof.get("source_selection") not in {
        "single_registry_matched_xml",
        "pinned_latest_archived_notice_revision",
    }:
        return 0
    rows: list[str] = []
    facts = proof.get("facts")
    if not isinstance(facts, dict):
        return 0
    for field, label in _FIELDS:
        item = facts.get(field)
        if not isinstance(item, dict) or item.get("status") != "KNOWN":
            continue
        evidence = item.get("evidence")
        if not isinstance(evidence, list) or len(evidence) != 1:
            continue
        entry = evidence[0]
        if not isinstance(entry, dict) or not all(
            isinstance(entry.get(k), str) and entry[k] for k in (
                "source_ref", "document", "locator", "excerpt"
            )
        ):
            continue
        if not str(entry["source_ref"]).startswith("eis-xml:"):
            continue
        escaped = {k: html.escape(str(entry[k]), quote=True) for k in (
            "source_ref", "document", "locator", "excerpt"
        )}
        value = html.escape(str(item["value"]), quote=True)
        rows.append(
            "<li><strong>"
            + html.escape(label, quote=True)
            + ": "
            + value
            + "</strong><p>Оригинал: "
            + escaped["document"]
            + "; "
            + escaped["locator"]
            + "; "
            + escaped["source_ref"]
            + "</p><blockquote>"
            + escaped["excerpt"]
            + "</blockquote></li>"
        )

    if not rows or not report_path.is_file():
        return 0
    current = report_path.read_text(encoding="utf-8")
    if _PANEL_ID in current or "</main>" not in current:
        return 0
    subject = facts.get("procurement_title")
    if isinstance(subject, dict) and subject.get("status") == "KNOWN" and subject.get("value"):
        official_subject = str(subject["value"]).strip()

        def correct_subject(match: re.Match[str]) -> str:
            # The old heuristic can mistake a TЗ heading for the subject.
            # Only a byte-verified unique original XML may correct it.
            candidate = html.unescape(match.group(1)).strip()
            if candidate.casefold() == official_subject.casefold():
                return match.group(0)
            return (
                "<li>Предмет закупки (XML ЕИС): "
                + html.escape(official_subject, quote=True)
                + "</li>"
            )

        current = re.sub(
            r"<li>Предмет закупки:\s*([^<]*)</li>",
            correct_subject,
            current,
            flags=re.IGNORECASE,
        )
    section = (
        '<section id="official-eis-citations"><h2>Цитаты из оригинального XML ЕИС</h2>'
        '<p>Факты сверены с сохранённым XML соответствующего номера закупки. '
        'Это архивная редакция: актуальность сроков и условий проверяется отдельно.</p>'
        "<ul>"
        + "".join(rows)
        + "</ul></section>"
    )
    report_path.write_text(current.replace("</main>", section + "</main>", 1), encoding="utf-8")
    return len(rows)
