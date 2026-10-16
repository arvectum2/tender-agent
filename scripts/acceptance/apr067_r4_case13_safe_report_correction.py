"""Publish an append-only, no-LLM correction of one archived EIS case 13.

Never rewrites the source model's original report, metadata or LLM trace.
Fails closed if real saved EIS source evidence and frozen hashes disagree.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from src.modules.tender_operator_agent_demo.operator_eis_report_citations import (
    append_official_eis_citations,
)
from src.modules.tender_operator_agent_demo.operator_report_revision import (
    published_report_path,
    verified_revision,
)
from src.modules.tender_operator_agent_demo.operator_workspace_evidence import (
    get_operator_source_evidence,
)

REGISTRY = "0349100009326000005"
RUN = "toa-run-20261015214554-288eac"
ORIGINAL_HTML = "20ee85843d42f47acab1dbced2c318aedc06aa8c431040bad6a47afcbfde80d3"
ORIGINAL_JSON = "a77874d7aa367172ca31990e1b815b68a3d1bbe226ce42cae15e67a69680ae2a"
ORIGINAL_META = "f1979a0271ea0201934e40903606d983426f3b55b95dafb939dd57c4c0dd8725"
REVIEW = (
    "АРХИВ ЕИС: текущая редакция закупки и срок подачи не подтверждены. "
    "Нельзя принимать решение об участии без актуального ЕИС, "
    "изучения ТЗ, договора, собственной себестоимости и ресурсов."
)
LIMIT = (
    "Структурированные объёмы услуг, часы, единичные расценки и "
    "обязательные ресурсы исполнителя не подтверждены. "
    "Нельзя считать режим поддержки 24/7 объёмом учебной программы."
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def publish(stage: Path) -> dict:
    output = stage / "runs" / RUN / "output"
    input_dir = stage / "runs" / RUN / "input"
    meta_path = stage / "runs" / RUN / "metadata.json"
    assert output.is_dir() and input_dir.is_dir()
    assert sha(output / "report.html") == ORIGINAL_HTML
    assert sha(output / "report.json") == ORIGINAL_JSON
    assert sha(meta_path) == ORIGINAL_META
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["procurement_id"] == REGISTRY and meta["run_id"] == RUN
    assert meta["ai_runtime_provenance"]["llm_calls_count"] == 4
    assert not meta["ai_runtime_provenance"].get("fallback_reason")
    receipt = json.loads((stage / "output" / "offline_archived_source_receipt.json").read_text())
    assert receipt["run_id"] == RUN and receipt["registry_number"] == REGISTRY
    assert len(receipt["all_input_sha256"]) == 9
    original_files = []
    names = set()
    for original in receipt["all_input_sha256"]:
        name, expected = original["stored_name"], original["sha256"]
        rel = Path(name)
        assert name not in names and not rel.is_absolute() and ".." not in rel.parts
        assert len(rel.parts) == 1 or (len(rel.parts) == 2 and rel.parts[0] == "extracted")
        names.add(name)
        p = input_dir / rel
        assert p.resolve().is_relative_to(input_dir.resolve())
        assert p.is_file() and not p.is_symlink() and sha(p) == expected
        original_files.append({"stored_name": name, "sha256": expected})
    proof_path = stage / "output" / "source_only_service_scope_reprojection_v2.json"
    projection = json.loads(proof_path.read_text(encoding="utf-8"))
    assert (projection["registry_number"] == REGISTRY
            and projection["run_id"] == RUN
            and projection["original_report_html_sha256"] == ORIGINAL_HTML
            and projection["original_report_unchanged"] is True
            and projection["original_source_docs_read"] == 9
            and projection["new_real_model_invocations"] == 0
            and projection["new_domain_profile"] == "general_services")
    if (output / "report-revision.json").exists():
        old = verified_revision(output, RUN)
        assert old is not None
        return old

    evidence = get_operator_source_evidence(RUN)
    assert evidence["source_selection"] == "single_registry_matched_xml"
    facts = evidence["facts"]
    assert {"procurement_title", "application_deadline", "nmck"} <= set(facts)
    for name in ("procurement_title", "application_deadline", "nmck"):
        f = facts[name]
        assert f["status"] == "KNOWN" and len(f.get("evidence", [])) == 1
        assert f["evidence"][0]["source_ref"].startswith("eis-xml:")
    subject = facts["procurement_title"]["value"]
    deadline = facts["application_deadline"]["value"]
    nmck = facts["nmck"]["value"]
    assert "поддержке и размещению сайта" in str(subject)
    assert deadline == "2026-03-02T07:00:00+03:00"
    assert abs(float(nmck) - 130000) < 0.01

    original_document_names = [x["original_name"] for x in meta["files"]]
    assert len(original_document_names) == 9
    contract = [x for x in meta["files"] if x["document_kind"] == "contract_draft"]
    assert len(contract) == 1
    checks = [
        REVIEW, LIMIT,
        "Изучить оригинальный проект контракта: условия оплаты, приёмки, ответственности и обеспечения.",
        "Сверить объём и условия сопровождения сайта в ТЗ и расчёте НМЦК с исходниками.",
        "Подтвердить реальные квалификации, ресурсы и собственную себестоимость только по документам и профилю исполнителя.",
    ]
    summary = [
        f"Оригинальный предмет XML ЕИС: {subject}.",
        f"НМЦК архивного извещения: {float(nmck):,.2f} RUB. Дедлайн: {deadline}.",
        "Оригинальные документы: 9/9 проверенных файлов; проект контракта обнаружен.",
        LIMIT, REVIEW,
    ]
    sections = [
        {"title": "Подтверждённые факты из XML ЕИС", "kind": "bullets", "items": summary[:2]},
        {"title": "Оригинальный комплект документов", "kind": "bullets",
         "items": [f"Сохранено и сверено {len(original_files)}/9 файлов, включая исходный проект контракта."]
         + original_document_names},
        {"title": "Неизвестное и ручная проверка", "kind": "bullets", "items": checks},
        {"title": "История исправления", "kind": "bullets", "items": [
            "Это новая source-only версия старого отчёта, а не новый запуск Gemma.",
            "Исходные report.json, report.html, metadata.json и модельный след оставлены без изменений.",
            f"SHA исходного HTML-отчёта: {ORIGINAL_HTML}.",
            "Специфические объёмы/требования не признаны подтверждёнными.",
        ]},
    ]
    markdown = (
        f"# Исправленная архивная версия отчёта — закупка {REGISTRY}\n\n"
        + "\n\n".join(f"## {s['title']}\n" + "\n".join("- " + line for line in s["items"]) for s in sections)
        + "\n\n**Решение: только ручная проверка; разрешение на подачу заявки не выдаётся.**\n"
    )
    corrected = {
        "run_id": RUN, "report_title": "Исправленный отчёт по оригиналам ЕИС — архивная редакция",
        "generated_at": datetime.now(UTC).isoformat(),
        "recommendation": "manual_review_required", "recommendation_label": "Требуется ручная проверка",
        "executive_summary": summary, "manual_checks": checks,
        "sections": sections, "report_markdown": markdown,
        "decision_core": {
            "contract_version": "append-only-source-correction-v1",
            "procurement_regime": "archived_eis_44_fz",
            "decision": {
                "status": "NEEDS_REVIEW", "confidence": "low",
                "rationale": [LIMIT, REVIEW],
                "human_control_required": True, "external_action_allowed": False,
            },
            "facts": {k: {"status": "KNOWN", "value": f["value"], "evidence": f["evidence"]}
                      for k, f in facts.items() if k in ("procurement_title", "application_deadline", "nmck")},
            "historical_decision_not_authoritative": True,
            "current_eis_revision_status": "UNKNOWN",
            "new_model_inference_calls": 0,
        },
    }
    document = (
        '<!doctype html><html lang="ru"><head><meta charset="utf-8">'
        '<title>Исправленный архивный отчёт ЕИС</title></head><body><main>'
        "<h1>Исправленная исходно подтверждённая версия</h1>"
        '<p>Новая версия без повторного запуска LLM; исходный отчёт сохранён неизменным.</p>'
        + "".join(
            "<section><h2>" + html.escape(s["title"]) + "</h2><ul>"
            + "".join("<li>" + html.escape(item) + "</li>" for item in s["items"])
            + "</ul></section>" for s in sections
        )
        + "<p><strong>Требуется ручная проверка. Архивное извещение не разрешает участие.</strong></p>"
        + "</main></body></html>"
    )
    revision_dir = output / "report-revisions" / "source-correction-v1"
    assert not revision_dir.exists(), "never overwrite a prior revision"
    revision_dir.mkdir(parents=True)
    json_path = revision_dir / "report.json"
    html_path = revision_dir / "report.html"
    json_path.write_text(json.dumps(corrected, ensure_ascii=False, indent=2) + "\n")
    html_path.write_text(document, encoding="utf-8")
    cited = append_official_eis_citations(report_path=html_path, run_id=RUN, metadata=meta)
    assert cited == 3 and html_path.read_text().count("eis-xml:") >= 3
    manifest = {
        "revision": "source-correction-v1", "run_id": RUN, "registry_number": REGISTRY,
        "original_report_json_sha256": ORIGINAL_JSON, "original_report_html_sha256": ORIGINAL_HTML,
        "original_metadata_sha256": ORIGINAL_META, "original_source_files": original_files,
        "revision_report_json_sha256": sha(json_path),
        "revision_report_html_sha256": sha(html_path),
        "real_model_calls_original": 4, "real_model_calls_new": 0,
        "original_source_eis_xml_citations": cited,
        "semantic_status": "corrected_historical_source_only_needs_review",
    }
    pointer = output / "report-revision.json"
    with tempfile.NamedTemporaryFile("w", dir=output, prefix=".report-revision-", delete=False) as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
        tmp = Path(fh.name)
    os.replace(tmp, pointer)
    assert verified_revision(output, RUN) == manifest
    assert published_report_path(output, RUN, "html") == html_path
    assert sha(output / "report.html") == ORIGINAL_HTML and sha(output / "report.json") == ORIGINAL_JSON
    assert meta["ai_runtime_provenance"]["llm_calls_count"] == 4
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(publish(args.stage), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
