"""Fail-closed current getDocsIP XML comparison, with source-verified replacement files."""
from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

from scripts.acceptance.audit_r5_official_sources import audit_archive, local_name
from scripts.acceptance.check_r4_live_eis_cards import compare_deadline


def notice_attachments(zip_path: Path, number: str, version: int) -> dict[str, dict]:
    matches = []
    with zipfile.ZipFile(zip_path) as archive:
        for filename in archive.namelist():
            if not filename.lower().endswith(".xml"):
                continue
            root = ET.fromstring(archive.read(filename))
            for node in root.iter():
                if not local_name(node.tag).startswith("epNotification"):
                    continue
                versions = [(x.text or "").strip() for x in node if local_name(x.tag) == "versionNumber"]
                identities = {(x.text or "").strip() for x in node.iter()
                              if local_name(x.tag) == "purchaseNumber"}
                if versions != [str(version)] or number not in identities:
                    continue
                items = []
                for item in node.iter():
                    if local_name(item.tag) == "attachmentInfo":
                        entry = {local_name(c.tag): (c.text or "").strip() for c in item}
                        if entry.get("publishedContentId"):
                            items.append(entry)
                matches.append(items)
    if len(matches) != 1 or len({v["publishedContentId"] for v in matches[0]}) != len(matches[0]):
        raise ValueError("Official original attachment identities ambiguous")
    return {v["publishedContentId"]: v for v in matches[0]}


def same_deadline(old: str | None, new: str | None) -> bool | None:
    if not old or not new:
        return None
    a, b = datetime.fromisoformat(old), datetime.fromisoformat(new)
    if a.tzinfo is None or b.tzinfo is None:
        return None
    return a.astimezone(UTC) == b.astimezone(UTC)


def verified_current_sources(
    archived: dict, soap_receipt: list[dict], html: dict,
    fresh_root: Path, old_root: Path, binary_receipt: list[dict],
    binary_dir: Path,
) -> dict:
    selected = archived["competitive_notices"]
    if len(selected) != 20 or len(soap_receipt) != 20:
        raise ValueError("Require exactly twenty EIS original notices and current XML receipts")
    if archived["selected_original_notice_attachment_coverage"]["source_shas_attested"] != 96:
        raise ValueError("Official baseline source coverage incomplete")
    old = {x["registry_number"]: x for x in selected}
    http = {x["registry_number"]: x for x in html["cases"]}
    if len(old) != 20 or len(http) != 20 or len({x["registry_number"] for x in soap_receipt}) != 20:
        raise ValueError("Duplicate/missing official procurement identities")
    new_receipt = {r["source_uid"]: r for r in binary_receipt}
    if len(new_receipt) != len(binary_receipt):
        raise ValueError("Duplicate replacement binary")
    request_times = [datetime.fromisoformat(r["requested_at_utc"]) for r in soap_receipt]
    if any(d.tzinfo is None for d in request_times):
        raise ValueError("SOAP source timestamps must be timezone-aware")
    checked_at = max(request_times).astimezone(UTC)
    cases = []
    for receipt in soap_receipt:
        n = receipt["registry_number"]
        historical = old[n]
        if receipt["status"] != "OFFICIAL_SOAP_ZIP_XML_AT_REQUEST":
            raise ValueError("Latest official getDocsIP XML not verified")
        file = fresh_root / n / "documentation-archive.zip"
        original = audit_archive(file, n)
        current = original["highest"]
        if (
            original["zip_sha256"] != receipt["source_zip_sha256"]
            or current["xml_sha256"] != receipt["latest_xml_sha256"]
            or current["version"] != receipt["highest_version"]
            or current["endDT"] != receipt["latest_endDT"]
            or current["notice_type"] != historical["notice_type"]
            or current["version"] < historical["archived_version"]
            or current["endDT_ambiguity"]
        ):
            raise ValueError("Current official ZIP/XML has changed since private receipt")
        online = http[n]
        if online["source_status"] == "OFFICIAL_CARD_STAGE_AT_CAPTURE_TIME":
            if compare_deadline(online["displayed_deadline"], current["endDT"]) != "MATCH":
                raise ValueError("Independent official HTML/SOAP bid deadlines disagree")
            stage = online["displayed_stage"]
        else:
            stage = "UNKNOWN_HTML_UNAVAILABLE"
        upgraded = current["version"] > historical["archived_version"]
        xml_diff = current["xml_sha256"] != historical["original_xml_sha256"]
        if upgraded != xml_diff:
            raise ValueError("Unexpected official XML drift without notice version")
        case = {
            "registry_number": n,
            "archived_version": historical["archived_version"],
            "current_official_xml_version": current["version"],
            "archived_endDT": historical["archived_submission_end"],
            "current_official_xml_endDT": current["endDT"],
            "deadline_changed": same_deadline(historical["archived_submission_end"], current["endDT"]) is False,
            "deadline_after_source_check": (
                datetime.fromisoformat(current["endDT"]).astimezone(UTC) > checked_at
                if current["endDT"] else None
            ),
            "verified_soap_at_utc": receipt["requested_at_utc"],
            "version_changed": upgraded,
            "same_source_xml": not xml_diff,
            "same_complete_zip_bytes": original["zip_sha256"] == historical["original_zip_sha256"],
            "latest_xml_sha256": current["xml_sha256"],
            "latest_zip_sha256": original["zip_sha256"],
            "html_stage": stage,
            "all_current_attachments_legally_reviewed": False,
            "human_legal_signed": False,
            "bid_ready": False,
        }
        if upgraded:
            prev = notice_attachments(
                old_root / n / "documentation-archive.zip", n, historical["archived_version"]
            )
            new = notice_attachments(file, n, current["version"])
            replaced = set(new) - set(prev)
            retired = set(prev) - set(new)
            if len(replaced) != len(retired) or replaced != set(new_receipt):
                raise ValueError("Latest official replacement attachments not fully recovered")
            evidence = []
            for uid in replaced:
                item, proof = new[uid], new_receipt[uid]
                suffix = Path(item["fileName"]).suffix.lower()
                raw = (binary_dir / (uid + suffix)).read_bytes()
                if (
                    proof["status"] != "FIRST_PARTY_BINARY_VERIFIED"
                    or proof["file_name"] != item["fileName"]
                    or proof["file_size"] != len(raw) or int(item["fileSize"]) != len(raw)
                    or proof["sha256"] != hashlib.sha256(raw).hexdigest()
                ):
                    raise ValueError("New EIS original binary SHA/size/identity mismatch")
                evidence.append({
                    "filename": item["fileName"],
                    "size_bytes": len(raw),
                    "sha256": proof["sha256"],
                    "binary_verified": True,
                    "full_legal_scope_review_signed": False,
                })
            case["new_replaced_attachments"] = sorted(evidence, key=lambda x: x["filename"])
            case["unchanged_attachment_refs"] = len(set(new) & set(prev))
            case["old_semantic_review_is_stale"] = True
        cases.append(case)
    return {
        "source": "OFFICIAL_GETDOCSIP_READONLY_TLS_FIRST_PARTY_ZIP_XML",
        "observed_date": "2026-10-14",
        "checked_at_utc": checked_at.isoformat(timespec="seconds"),
        "after_check_future_deadlines": sum(c["deadline_after_source_check"] is True for c in cases),
        "verified_official_xml_cases": len(cases),
        "official_html_stage_attested": html["official_card_attested"],
        "changed_xml_versions": [x["registry_number"] for x in cases if x["version_changed"]],
        "deadlines_changed": sum(c["deadline_changed"] for c in cases),
        "full_zip_byte_drift": sum(not c["same_complete_zip_bytes"] for c in cases),
        "signed_expert_reviews": 0,
        "bid_ready": False,
        "cases": cases,
        "scope_note": (
            "SOAP XML is latest in requested ZIP, not signed legal gold. "
            "HTML may be unavailable, and updated attachments may need "
            "fresh technical and legal analysis even when SHA-verified."
        ),
    }


def _human_deadline(value: str | None) -> str:
    if not value:
        return "UNKNOWN"
    d = datetime.fromisoformat(value)
    if d.tzinfo is None:
        return "UNKNOWN"
    offset = int(d.utcoffset().total_seconds() // 3600) - 3
    zone = "МСК" if offset == 0 else f"МСК{offset:+d}"
    return d.strftime("%d.%m.%Y %H:%M") + f" ({zone})"


def readable_freshness(audit: dict) -> str:
    lines = [
        "# Tender Agent — повторная проверка 20 извещений ЕИС",
        "",
        (
            "**Дата:** 14 октября 2026 года. Источник: официальный getDocsIP, "
            "повторно проверенные ZIP и исходные XML."
        ),
        "",
        (
            f"**Проверено:** {audit['verified_official_xml_cases']}/20 текущих SOAP-архивов. "
            f"Новые редакции XML: {len(audit['changed_xml_versions'])}. "
            f"Карточки HTML с подтверждённым этапом: "
            f"{audit['official_html_stage_attested']}/20. "
            f"Срок ещё не наступил в {audit['after_check_future_deadlines']} XML "
            "на момент проверки (это не доказывает приём заявок)."
        ),
        "",
        (
            "Текущие сроки относятся к последней версии XML в свежем официальном ZIP. "
            "Они не подтверждают открытый приём заявок на ЭТП. "
            "Если HTML ЕИС не отвечал, этап остаётся UNKNOWN."
        ),
        "",
        "| ЕИС | Редакция: архив → свежая | Срок по свежему XML | Изменение | HTML-этап |",
        "|---|---|---|---|---|",
    ]
    for c in audit["cases"]:
        change = "Новая редакция, повторить анализ" if c["version_changed"] else "XML без изменения"
        lines.append(
            f"| {c['registry_number']} | {c['archived_version']} → "
            f"{c['current_official_xml_version']} | "
            f"{_human_deadline(c['current_official_xml_endDT'])} | {change} | "
            f"{c['html_stage']} |"
        )
    for c in audit["cases"]:
        if not c["version_changed"]:
            continue
        lines.extend([
            "",
            f"## Новая редакция: {c['registry_number']}",
            "",
            (
                f"Версия {c['archived_version']} заменена на "
                f"{c['current_official_xml_version']}. "
                f"Срок: {_human_deadline(c['archived_endDT'])} → "
                f"{_human_deadline(c['current_official_xml_endDT'])}. "
                f"Осталось прежних вложений: {c['unchanged_attachment_refs']}; "
                f"появилось заменённых: {len(c['new_replaced_attachments'])}."
            ),
            "",
            "| Новый официальный файл | Размер, байт | SHA-256 |",
            "|---|---:|---|",
        ])
        for item in c["new_replaced_attachments"]:
            lines.append(
                f"| {item['filename']} | {item['size_bytes']} | {item['sha256']} |"
            )
        lines.extend([
            "",
            (
                "**Нужно повторно оценить содержание изменённых договора, ТЗ и "
                "приложений.** Побайтная проверка оригиналов сама по себе "
                "не подтверждает правовую применимость условий."
            ),
        ])
    lines.extend([
        "",
        "## Обязательные ограничения",
        "",
        (
            "Получение ZIP и проверка XML не равны подтверждению фактического "
            "этапа подачи, возможности участия и соответствия исполнителя. "
            "Предыдущие цитаты по изменённым приложениям нельзя "
            "автоматически переносить в новый договор. "
            "**Подписано экспертных заключений: 0/20. bid_ready=false.**"
        ),
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    import argparse

    p = argparse.ArgumentParser()
    for key in (
        "audit", "soap-receipt", "html-snapshot", "fresh-root",
        "historic-root", "binary-receipt", "binary-dir", "output-json", "output-md",
    ):
        p.add_argument("--" + key, type=Path, required=True)
    args = p.parse_args()
    result = verified_current_sources(
        archived=json.loads(args.audit.read_text()),
        soap_receipt=json.loads(args.soap_receipt.read_text()),
        html=json.loads(args.html_snapshot.read_text()),
        fresh_root=args.fresh_root,
        old_root=args.historic_root,
        binary_receipt=json.loads(args.binary_receipt.read_text()),
        binary_dir=args.binary_dir,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    args.output_md.write_text(readable_freshness(result))
    print({
        "current_xml": result["verified_official_xml_cases"],
        "new_editions": result["changed_xml_versions"],
        "updated_deadlines": result["deadlines_changed"],
        "new_binary_attestations": sum(
            len(x.get("new_replaced_attachments", [])) for x in result["cases"]
        ),
    })


if __name__ == "__main__":
    main()
