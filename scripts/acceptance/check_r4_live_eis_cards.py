"""Read-only, TLS-verified official EIS HTML capture. HTML is NOT current XML proof."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import subprocess
import tempfile
import time
from collections import Counter
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BASE = "https://zakupki.gov.ru"
ROUTES = {
    "COMPETITIVE_ELECTRONIC_AUCTION": "ea20",
    "COMPETITIVE_ELECTRONIC_QUOTATIONS": "zk20",
    "COMPETITIVE_OPEN_ELECTRONIC_COMPETITION": "ok20",
}
DATE = re.compile(r"(\d{2}\.\d{2}\.\d{4})\s+(\d{2}:\d{2})\s*\((МСК(?:[+-]\d+)?)\)")
HEADER = re.compile(r'<span\s+class="cardMainInfo__state\s+distancedText"[^>]*>(.*?)</span>', re.DOTALL)
BODY = re.compile(r'<span\s+class="section__title">\s*Этап закупки\s*</span>\s*<span\s+class="section__info">(.*?)</span>', re.DOTALL)
END = re.compile(r'<span\s+class="section__title">\s*Дата и время окончания срока подачи заявок\s*</span>\s*<span\s+class="section__info">(.*?)</section>', re.DOTALL)


def _plain(t: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", t)).split())


def official_url(number: str, method: str) -> str:
    if re.fullmatch(r"\d{19}", number) is None:
        raise ValueError("Invalid original EIS number")
    return f"{BASE}/epz/order/notice/{ROUTES[method]}/view/common-info.html?regNumber={number}"


def parse_official_card(raw: bytes, number: str) -> tuple[str, str]:
    if not 1000 < len(raw) < 1_400_000:
        raise ValueError("Invalid HTML content length")
    page = raw.decode("utf8", "strict")
    if "Сведения закупки" not in page or not re.search(rf"№\s*{number}\b", page):
        raise ValueError("No confirmed official notice identity")
    head, body = HEADER.findall(page), BODY.findall(page)
    if len(head) != 1 or len(body) != 1 or not _plain(head[0]) or _plain(head[0]) != _plain(body[0]):
        raise ValueError("Official stage missing, ambiguous or inconsistent")
    deadline = END.findall(page)
    found = DATE.search(_plain(deadline[0])) if len(deadline) == 1 else None
    display = f"{found.group(1)} {found.group(2)} ({found.group(3)})" if found else ""
    return _plain(head[0]), display


def compare_deadline(display: str, historical: str | None) -> str:
    m = DATE.fullmatch(display)
    if not m or not historical:
        return "UNKNOWN"
    suffix = m.group(3).removeprefix("МСК")
    hour_offset = 3 + (int(suffix) if suffix else 0)
    current = datetime.strptime(f"{m.group(1)} {m.group(2)}", "%d.%m.%Y %H:%M").replace(
        tzinfo=timezone(timedelta(hours=hour_offset))
    )
    archived = datetime.fromisoformat(historical)
    if archived.tzinfo is None:
        return "UNKNOWN"
    return "MATCH" if current == archived else "DIFF_REQUIRES_REVIEW"


def valid_final_url(actual: str, expected: str) -> bool:
    a, b = urlparse(actual), urlparse(expected)
    return a.scheme == "https" and a.hostname == "zakupki.gov.ru" and a.path == b.path and parse_qs(a.query) == parse_qs(b.query) and not a.username and not a.password and not a.fragment


def fetch_official_card(url: str, destination: Path, retries: int = 3) -> dict:
    destination.parent.mkdir(parents=True, exist_ok=True)
    error = "UNVERIFIED"
    for attempt in range(1, retries + 1):
        with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=".html-", delete=False) as f:
            temp = Path(f.name)
        try:
            proc = subprocess.run([
                "/usr/bin/curl", "--silent", "--show-error", "--location",
                "--max-redirs", "3", "--proto", "=https", "--proto-redir", "=https",
                "--connect-timeout", "8", "--max-time", "24", "--max-filesize", "1400000",
                "--output", str(temp),
                "--write-out", "%{http_code}\t%{ssl_verify_result}\t%{url_effective}", url,
            ], capture_output=True, text=True, timeout=30, check=False)
            values = proc.stdout.strip().split("\t")
            if proc.returncode == 0 and len(values) == 3 and values[0] == "200" and values[1] == "0" and valid_final_url(values[2], url) and 1000 < temp.stat().st_size < 1_400_000:
                temp.replace(destination)
                return {"ok": True, "attempts": attempt}
            error = "HTTP_" + values[0] if values and values[0].isdigit() else "TRANSPORT_FAILURE"
        except (OSError, subprocess.TimeoutExpired):
            error = "TRANSPORT_FAILURE"
        finally:
            temp.unlink(missing_ok=True)
        if attempt < retries:
            time.sleep(0.4)
    return {"ok": False, "attempts": retries, "failure": error}


def collect_live_snapshot(audit: dict, previous_receipt: dict, private_dir: Path, *, fetcher=fetch_official_card) -> dict:
    notices = audit["competitive_notices"]
    coverage = audit["selected_original_notice_attachment_coverage"]
    if len(notices) != 20 or len({n["registry_number"] for n in notices}) != 20 or coverage["source_shas_attested"] != 96:
        raise ValueError("20 distinct first-party source-attested notices are required")
    older = {c["reg_number"]: c for c in previous_receipt["cases"]}
    if len(older) != 20:
        raise ValueError("Previous 20-card official EIS receipt incomplete")
    records = []
    for notice in notices:
        number = notice["registry_number"]
        url = official_url(number, notice["method"])
        prior = older.get(number)
        if prior is None or prior["request_url_path"] != urlparse(url).path:
            raise ValueError("Previous first-party EIS route differs from notice type")
        stamp = datetime.now(UTC).isoformat(timespec="seconds")
        private_file = private_dir / f"{number}-official-curl.html"
        result = fetcher(url, private_file)
        row = {
            "registry_number": number,
            "official_url": url,
            "captured_at_utc": stamp,
            "source_status": "UNKNOWN",
            "archived_submission_end": notice.get("archived_submission_end"),
            "prior_oct12_status": prior["official_stage"],
            "tries": result["attempts"],
            "current_xml_revision_attested": False,
            "current_attachment_editions_attested": False,
            "human_legal_signed": False,
            "bid_ready": False,
        }
        if result["ok"]:
            try:
                raw = private_file.read_bytes()
                stage, deadline = parse_official_card(raw, number)
            except (ValueError, UnicodeError):
                private_file.unlink(missing_ok=True)
                row["source_failure"] = "UNVERIFIED_CARD_CONTENT"
            else:
                row.update({
                    "source_status": "OFFICIAL_CARD_STAGE_AT_CAPTURE_TIME",
                    "displayed_stage": stage,
                    "displayed_deadline": deadline or "UNKNOWN",
                    "deadline_vs_archived_xml": compare_deadline(deadline, notice.get("archived_submission_end")),
                    "stage_changed_since_oct12": stage != prior["official_stage"],
                    "html_sha256": hashlib.sha256(raw).hexdigest(),
                    "html_bytes": len(raw),
                })
        else:
            row["source_failure"] = result["failure"]
        records.append(row)
    good = [c for c in records if c["source_status"] == "OFFICIAL_CARD_STAGE_AT_CAPTURE_TIME"]
    return {
        "source": "PUBLIC_EIS_LIVE_OFFICIAL_CARD_HTTPS_WITH_TLS",
        "captured_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "baseline_date": "2026-10-12",
        "notice_count": len(records),
        "official_card_attested": len(good),
        "unverified_or_unavailable": 20-len(good),
        "stage_counts": dict(sorted(Counter(x["displayed_stage"] for x in good).items())),
        "live_xml_version_attested": 0,
        "live_attachment_editions_attested": 0,
        "human_legal_signed": 0,
        "bid_ready": False,
        "cases": records,
        "limits": (
            "Official display is a snapshot only, not latest XML edition or ETP "
            "bid acceptance. HTTP errors remain UNKNOWN and do not imply cancellation. "
            "Current source attachments, legal eligibility and human GO remain unverified."
        ),
    }


def readable_report(snapshot: dict) -> str:
    lines = [
        "# Актуальный этап ЕИС — проверка 20 конкурентных закупок",
        "",
        f"**Момент проверки:** {snapshot['captured_at_utc']} UTC.",
        "",
        (
            f"Официальные HTML-карточки: **{snapshot['official_card_attested']}/20** "
            f"подтверждены. Не подтверждены: **{snapshot['unverified_or_unavailable']}**."
        ),
        "",
        (
            "Этап и срок — только отображаемое состояние первой стороны на момент HTTPS-запроса. "
            "Это не подтверждение актуальной версии XML, новых приложений, фактической "
            "возможности подачи на ЭТП или юридической допустимости участия."
        ),
        "",
        "| Закупка ЕИС | Отображаемый этап | Срок подачи по карточке | Срок против архивного XML |",
        "|---|---|---|---|",
    ]
    for c in snapshot["cases"]:
        stage = c.get("displayed_stage", "UNKNOWN — карточка не подтверждена")
        deadline = c.get("displayed_deadline", "UNKNOWN")
        diff = c.get("deadline_vs_archived_xml", "UNKNOWN")
        lines.append(f"| [{c['registry_number']}]({c['official_url']}) | {stage} | {deadline} | {diff} |")
    lines.extend([
        "",
        "## Граница подтверждения",
        "",
        (
            "Ошибки HTTP 404 и временная недоступность **не** означают отмену закупки. "
            "Для решения об участии нужны актуальная редакция всех документов "
            "ЕИС, независимая юридическая экспертиза и согласование владельца. "
            "**Экспертная приёмка: 0/20; bid_ready=false.**"
        ),
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--audit", type=Path, required=True)
    p.add_argument("--previous", type=Path, required=True)
    p.add_argument("--private", type=Path, required=True)
    p.add_argument("--json", type=Path, required=True)
    p.add_argument("--markdown", type=Path, required=True)
    args = p.parse_args()
    snapshot = collect_live_snapshot(
        json.loads(args.audit.read_text("utf8")),
        json.loads(args.previous.read_text("utf8")),
        args.private,
    )
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    args.markdown.write_text(readable_report(snapshot), encoding="utf8")
    print(json.dumps({
        "verified": snapshot["official_card_attested"],
        "unknown": snapshot["unverified_or_unavailable"],
        "stages": snapshot["stage_counts"],
        "live_xml_verified": snapshot["live_xml_version_attested"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
