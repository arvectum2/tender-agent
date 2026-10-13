"""Create a read-only, local APR-06 human-review queue from existing source hints.

This tool NEVER generates human decisions, hashes, official source confirmations
or acceptance observations. Its only output is private review navigation HTML.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
from pathlib import Path
from urllib.parse import quote, urlsplit

NOTICE = re.compile(r"(?:[0-9]{11}|[0-9]{19})\Z")
RUN_ID = re.compile(r"toa-run-[0-9]{14}-[a-z0-9]{6,16}\Z")


def _read_cases(path: Path, *, key: str) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get(key), list):
        raise TypeError(f"Invalid APR06 input object: {path.name}")
    cases = data[key]
    if not all(isinstance(case, dict) for case in cases):
        raise ValueError("Every case must be an object")
    return cases


def _loopback_base_url(raw: str) -> str:
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Review links must target an explicit localhost HTTP port") from exc
    if (
        parsed.scheme != "http" or parsed.hostname != "127.0.0.1"
        or parsed.username or parsed.password or parsed.query or parsed.fragment
        or parsed.path not in ("", "/")
        or port is None or port < 1024
    ):
        raise ValueError("Review links must target an explicit localhost HTTP port")
    return f"http://127.0.0.1:{parsed.port}"


def build_queue(manifest: dict, machine_prefill: dict, *, base_url: str) -> tuple[list[dict], dict]:
    base = _loopback_base_url(base_url)
    cases = manifest.get("cases")
    reports = machine_prefill.get("cases")
    if not isinstance(cases, list) or not isinstance(reports, list):
        raise TypeError("APR06 manifest and prefill must both contain cases lists")
    seen: set[str] = set()
    report_by_notice: dict[str, dict] = {}
    for item in reports:
        if not isinstance(item, dict):
            raise TypeError("Machine report must be an object")
        notice = item.get("notice")
        run_id = item.get("run_id")
        if not isinstance(notice, str) or not NOTICE.fullmatch(notice):
            raise ValueError("Invalid machine report procurement ID")
        if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
            raise ValueError("Invalid saved run ID")
        if notice in report_by_notice:
            raise ValueError("Duplicate machine report procurement number")
        report_by_notice[notice] = item

    queue = []
    for case in cases:
        if not isinstance(case, dict):
            raise TypeError("Manifest case must be an object")
        notice = case.get("reg_number")
        if not isinstance(notice, str) or not NOTICE.fullmatch(notice) or notice in seen:
            raise ValueError("Invalid or duplicate manifest procurement number")
        seen.add(notice)
        match = report_by_notice.get(notice)
        text_files = match.get("source_text_available") if match else None
        files = match.get("source_files") if match else None
        full_text = (
            isinstance(files, int) and not isinstance(files, bool)
            and isinstance(text_files, int) and not isinstance(text_files, bool)
            and files > 0 and text_files == files
        )
        status = (
            "MACHINE_REPORT_AVAILABLE_UNVERIFIED" if full_text
            else "PARTIAL_SOURCE_TEXT" if match else "SOURCE_DOCUMENTS_REQUIRED"
        )
        row = {
            "reg_number": notice,
            "law": str(case.get("law") or "UNKNOWN"),
            "subject": str(case.get("subject") or "Без темы"),
            "machine_status": status,
            "machine_hint": str(match.get("machine_decision") or "UNKNOWN") if match else "NOT_ANALYZED",
            "text_coverage": f"{text_files}/{files}" if match else "не проверено",
            "private_report": (
                base + "/demo/tender-agent/runs/" + quote(match["run_id"]) + "/report"
                if match else None
            ),
            # Never infer EIS revision, file digests, reviewer or decision.
            "official_eis_revision": None,
            "official_document_sha256": None,
            "human_reviewer_id": None,
            "human_decision": None,
            "human_evidence_ref": None,
            "human_reviewed": False,
        }
        queue.append(row)
    extra = set(report_by_notice) - seen
    if extra:
        raise ValueError("Machine reports refer to cases absent from manifest")
    queue.sort(key=lambda x: (
        0 if x["machine_status"] == "PARTIAL_SOURCE_TEXT" else 1
        if x["machine_hint"] == "NO_GO" else 2
        if x["private_report"] else 3,
        x["reg_number"],
    ))
    return queue, {
        "candidate_total": len(queue),
        "machine_reports": sum(bool(row["private_report"]) for row in queue),
        "human_reviewed": 0,
        "source_incomplete": sum(row["machine_status"] != "MACHINE_REPORT_AVAILABLE_UNVERIFIED" for row in queue),
        "commercial_acceptance": "BLOCKED_HUMAN_EVIDENCE_REQUIRED",
    }


def render_html(queue: list[dict], summary: dict) -> str:
    def esc(value: object) -> str:
        return html.escape(str(value), quote=True)

    rows = []
    for item in queue:
        action = (
            f'<a href="{esc(item["private_report"])}" target="_blank" rel="noopener noreferrer">Защищённый отчёт</a>'
            if item["private_report"] else "Сначала получить документы"
        )
        rows.append(
            '<tr>'
            f'<td><code>{esc(item["reg_number"])}</code></td>'
            f'<td>{esc(item["law"])}</td>'
            f'<td>{esc(item["subject"])}</td>'
            f'<td>{esc(item["machine_status"])}</td>'
            f'<td>{esc(item["machine_hint"])} <small>машинная гипотеза, НЕ решение</small></td>'
            f'<td>{esc(item["text_coverage"])}</td>'
            f'<td>{action}</td>'
            '<td>Проверяющий не назначен; источник и редакция НЕ подтверждены</td>'
            '</tr>'
        )
    return """<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>APR-06 · Очередь независимой проверки</title>
<style>
:root{color-scheme:light;font-family:system-ui,-apple-system,sans-serif;background:#f5f6f8;color:#1d2630}
body{max-width:1500px;margin:3rem auto;padding:0 1.5rem} h1{font-size:1.7rem}
aside{border-left:5px solid #b35b11;background:#fff5e9;padding:1.1rem;margin:1.3rem 0}
.stats{display:flex;gap:1rem;flex-wrap:wrap}.stats div{padding:1rem;background:#fff;border:1px solid #dadde4;border-radius:9px}
table{width:100%;border-collapse:collapse;background:white;font-size:.9rem}
th{text-align:left;background:#dfe5ee}th,td{padding:.7rem;border-bottom:1px solid #d9dde3;vertical-align:top}
tr:hover{background:#f3f8fb}td code{font-size:.85rem}
td small{display:block;color:#8c4d19} a{color:#0a6173}
footer{margin:2rem 0;color:#445161} p{line-height:1.55}
</style></head><body>
<h1>APR-06 — очередь независимой проверки закупок</h1>
<aside><strong>НЕ ПРИНЯТО. НЕ РЕШЕНИЕ ОБ УЧАСТИИ.</strong>
Это предварительная очередь из уже имеющихся материалов. Машинные NO_GO/NEEDS_REVIEW — гипотезы, не подтверждённые человеком.
Никаких человеческих оценок, действующей редакции ЕИС, SHA-256 официального комплекта и экспертного GO не создано.
Ссылки открываются только в приватном Operator Workspace на Mac mini при законной авторизации.</aside>
<div class="stats">
<div>Кандидатов: <strong>__TOTAL__</strong></div>
<div>Машинных отчётов: <strong>__REPORTS__</strong></div>
<div>Неполные источники: <strong>__INCOMPLETE__</strong></div>
<div>Проверено человеком: <strong>0</strong></div>
</div>
<h2>Порядок независимой работы</h2>
<p>Для каждой закупки: проверить идентификатор, 44/223-ФЗ, актуальную официальную редакцию, статус и все приложения;
сверить цитаты с оригиналами и хешами файлов; зафиксировать reviewer ID, фактическое время работы,
доказательства и реальное GO/NO_GO/DEFER. При пропуске документа — DEFER до восполнения.
После этого сохранить атрибутируемое наблюдение строго по <code>docs/acceptance/APR06_PROTOCOL.md</code>.
Этот HTML ничего не отправляет, не подписывает, не голосует и не сохраняет решения.</p>
<table><thead><tr><th>Номер</th><th>Закон</th><th>Предмет</th><th>Состояние источников</th><th>Машинная версия</th><th>Текст</th><th>Отчёт</th><th>Требуется от человека</th></tr></thead>
<tbody>__ROWS__</tbody></table>
<footer>Источник: кандидаты APR-06 и машинные результаты. Дата их предварительных данных — 9 октября 2026.
Они могут быть устаревшими. Текущую редакцию и сроки проверять непосредственно перед оценкой.</footer>
</body></html>""".replace("__TOTAL__", esc(summary["candidate_total"])).replace(
        "__REPORTS__", esc(summary["machine_reports"])
    ).replace("__INCOMPLETE__", esc(summary["source_incomplete"])).replace("__ROWS__", "".join(rows))


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline private APR06 reviewer navigation packet")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--prefill", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--local-base", default="http://127.0.0.1:18083")
    args = parser.parse_args()
    cases = _read_cases(args.manifest, key="cases")
    prefill = _read_cases(args.prefill, key="cases")
    queue, summary = build_queue({"cases": cases}, {"cases": prefill}, base_url=args.local_base)
    rendered = render_html(queue, summary)
    args.output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        output.write(rendered)
    print(json.dumps({"output": str(args.output), **summary}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
