"""Independently verify 196 original EIS HTMLs and export all 298 DB comparisons.

Only reads source artifacts; writes new private audit reports; no database access.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import io
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.diagnostics.audit_eis_midnight_deadlines import (
    _read_snapshot,
    _unique_notice_url,
    extract_exact_eis_deadline,
)

MSK = ZoneInfo("Europe/Moscow")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def write_once(path: Path, raw: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as out:
        out.write(raw)
        out.flush()
        os.fsync(out.fileno())


def summarize(root: Path, snapshot_sha: str) -> dict:
    if root.is_symlink() or not root.is_dir() or root.stat().st_mode & 0o077:
        raise ValueError("unsafe report root")
    _, groups = _read_snapshot(root / "snapshot.json", snapshot_sha)
    receipts = {}
    for path in (root / "receipts").glob("*.json"):
        if path.is_symlink():
            raise ValueError("symlink receipt")
        receipts[path.stem] = json.loads(path.read_text())
    if len(receipts) != 196 or set(receipts) != set(groups):
        raise ValueError("missing official source receipts")
    first_failures = list((root / "first-pass-unverified").glob("*.json"))
    if len(first_failures) != 5:
        raise ValueError("missing 5 first-pass failure receipts")
    zones = collections.Counter()
    for registry, evidence in receipts.items():
        raw_path = root / "html" / (registry + ".html")
        if raw_path.is_symlink() or not raw_path.is_file():
            raise ValueError("missing official HTML")
        raw = raw_path.read_bytes()
        parsed = extract_exact_eis_deadline(raw.decode("utf8", "replace"), registry)
        if (evidence["status"] != "official_exact_verified"
                or evidence["source_html_sha256"] != sha(raw)
                or evidence["source_html_bytes"] != len(raw)
                or evidence["row_count"] != len(groups[registry])
                or not all(evidence.get(k) == v for k, v in parsed.items())
                or set(evidence["database_row_ids"]) != {r["id"] for r in groups[registry]}):
            raise ValueError("original HTML or source receipt changed")
        zones[evidence["official_timezone"]] += 1

    now = datetime.now(UTC)
    all_rows = []
    for registry, rows in groups.items():
        evidence = receipts[registry]
        actual = datetime.fromisoformat(evidence["official_utc"])
        for row in rows:
            _unique_notice_url(row["source_url"], registry)
            stored = datetime.fromisoformat(row["deadline_at"])
            if actual == stored:
                category = "EXACT_MATCH"
            elif actual.astimezone(MSK).date() == stored.astimezone(MSK).date():
                category = "SAME_MSK_DATE_WRONG_CLOCK"
            else:
                category = "DIFFERENT_MSK_DATE"
            all_rows.append({
                "registry_number": registry,
                "record_id": row["id"],
                "run_id": row["run_id"],
                "status": row["status"],
                "title": row["title"],
                "stored_msk": stored.astimezone(MSK).strftime("%Y-%m-%d %H:%M"),
                "official_msk": actual.astimezone(MSK).strftime("%Y-%m-%d %H:%M"),
                "official_timezone": evidence["official_timezone"],
                "stored_utc": stored.isoformat(),
                "official_utc": actual.isoformat(),
                "shift_hours": round((actual - stored).total_seconds() / 3600, 4),
                "classification": category,
                "deadline_in_future": actual > now,
                "source_url": row["source_url"],
                "source_sha256": evidence["source_html_sha256"],
                "source_observed_utc": evidence.get(
                    "recovered_at_utc", evidence["audited_at_utc"]
                ),
            })
    if len(all_rows) != 298 or len({r["record_id"] for r in all_rows}) != 298:
        raise ValueError("the 298 original DB identities did not reconcile")
    all_rows.sort(key=lambda x: (x["registry_number"], x["run_id"], x["record_id"]))
    cls = collections.Counter(x["classification"] for x in all_rows)
    dirs = collections.Counter(
        "EARLIER" if x["shift_hours"] < 0 else
        "LATER" if x["shift_hours"] > 0 else "SAME" for x in all_rows
    )
    if cls != {
        "EXACT_MATCH": 3, "SAME_MSK_DATE_WRONG_CLOCK": 288,
        "DIFFERENT_MSK_DATE": 7,
    } or dirs != {"EARLIER": 2, "LATER": 293, "SAME": 3}:
        raise ValueError("source comparison totals unexpectedly changed")

    columns = list(all_rows[0])
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    for row in all_rows:
        item = dict(row)
        if item["title"][:1] in "=+-@":
            item["title"] = "'" + item["title"]
        writer.writerow(item)
    csv_bytes = output.getvalue().encode("utf-8")
    write_once(root / "EIS_298_ALL_VERIFIED.csv", csv_bytes)
    manager = [r for r in all_rows if r["status"] == "MANAGER_READY"]
    upcoming = sorted(
        (r for r in manager if r["deadline_in_future"]),
        key=lambda x: (x["official_utc"], x["registry_number"]),
    )
    summary = {
        "audited_at_utc": now.isoformat(),
        "production_snapshot_sha256": snapshot_sha,
        "rows": len(all_rows),
        "unique_eis_notices": len(receipts),
        "original_html_reverified": 196,
        "unresolved": 0,
        "first_pass_recovered": len(first_failures),
        "categories": dict(cls),
        "official_vs_stored": dict(dirs),
        "manager_ready": len(manager),
        "manager_ready_future": len(upcoming),
        "all_future_rows": sum(r["deadline_in_future"] for r in all_rows),
        "official_source_timezones": dict(zones),
        "csv_sha256": sha(csv_bytes),
        "csv_size_bytes": len(csv_bytes),
        "production_database_modified": False,
        "submissions_sent": False,
    }
    md = [
        "# Полный аудит сроков 298 записей ЕИС — 23 ноября 2026",
        "",
        f"Снимок реальной рабочей БД, 298 строк, 196 уникальных извещений; "
        f"снято в режиме REPEATABLE READ READ ONLY. SHA снимка: {snapshot_sha}. "
        "Повторно проверены все 196 исходных HTML ЕИС, их SHA-256, "
        "номера извещений и квитанции сохранения.",
        "",
        "**Итоги сравнения с текущей официальной редакцией:** "
        "**288** — та же московская дата, но отличается время; "
        "**7** — отличается московская календарная дата; "
        "**3** — точное совпадение; **0** — не проверено. "
        "По сравнению с БД 293 официальных срока позже, 2 раньше, 3 совпадают.",
        "",
        f"Состояние MANAGER_READY: {len(manager)} записей, из них "
        f"{len(upcoming)} с будущим сроком по ЕИС. "
        f"Всего записей с будущим официальным сроком: {summary['all_future_rows']}.",
        "",
        "**Ограничение:** сверка относится к текущему официальному извещению, "
        "не к каждой его исторической редакции. Часть сроков могла измениться "
        "после первоначального импорта. Не выполнено ни одного UPDATE БД, "
        "автоматической коррекции статусов или подачи заявок.",
        "",
        "## Особо опасные расхождения — ЕИС раньше БД",
        "",
        "| Извещение | Статус | В БД, МСК | В ЕИС, МСК | Сдвиг |",
        "|---|---|---|---|---|",
    ]
    for r in [x for x in all_rows if x["shift_hours"] < 0]:
        md.append(f"| [№{r['registry_number']}]({r['source_url']}) | "
                  f"{r['status']} | {r['stored_msk']} | "
                  f"{r['official_msk']} | {r['shift_hours']:+g} ч |")
    md.extend([
        "", "## Отличается календарная дата по Москве", "",
        "| Извещение | Статус | БД | ЕИС | Пояс в ЕИС |",
        "|---|---|---|---|---|",
    ])
    for r in [x for x in all_rows if x["classification"] == "DIFFERENT_MSK_DATE"]:
        md.append(f"| [№{r['registry_number']}]({r['source_url']}) | "
                  f"{r['status']} | {r['stored_msk']} | "
                  f"{r['official_msk']} | {r['official_timezone']} |")
    md.extend(["", "## Подтверждённая точная полночь — не исправлять", ""])
    for r in [x for x in all_rows if x["classification"] == "EXACT_MATCH"]:
        md.append(f"- [№{r['registry_number']}]({r['source_url']}) — "
                  f"{r['status']}: {r['official_msk']} МСК.")
    md.extend([
        "", "## Ближайшие MANAGER_READY с будущими официальными сроками", "",
        "| Извещение | ЕИС, МСК | БД, МСК | Сравнение |",
        "|---|---|---|---|",
    ])
    for r in upcoming[:20]:
        md.append(f"| [№{r['registry_number']}]({r['source_url']}) | "
                  f"{r['official_msk']} | {r['stored_msk']} | "
                  f"{r['classification']} |")
    md.extend([
        "", "## Метод проверки", "",
        "- 298 строк прочитаны из подтверждённой production PostgreSQL "
        "в одной транзакции REPEATABLE READ READ ONLY.",
        "- Выполнено по одному публичному HTTPS GET на уникальный номер "
        "ЕИС (ea20, zk20, ok20) с проверкой исходного URL и номера. "
        "Дата и точное время извлечены из поля "
        "«Дата и время окончания срока подачи заявок» вместе с МСК±N.",
        "- Первая попытка: 191/196, оставшиеся 5 (4 больших HTML, "
        "1 временный timeout) успешно повторно проверены; "
        "исходные неудачные квитанции сохранены отдельно.",
        f"- Все 298 построчных сверок: EIS_298_ALL_VERIFIED.csv; "
        f"SHA-256 CSV: {summary['csv_sha256']}. "
        "196 HTML-оригиналов и квитанций хранятся приватно на Mac mini.",
        "",
        "## Региональные пояса 196 исходных извещений",
        "",
    ])
    md.extend(f"- {zone}: {count}" for zone, count in sorted(zones.items()))
    md_bytes = ("\n".join(md) + "\n").encode()
    write_once(root / "EIS_298_REPORT.md", md_bytes)
    summary["report_sha256"] = sha(md_bytes)
    write_once(
        root / "EIS_298_SUMMARY.json",
        (json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(),
    )
    return summary


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", required=True, type=Path)
    p.add_argument("--snapshot-sha256", required=True)
    args = p.parse_args()
    print(json.dumps(summarize(args.root, args.snapshot_sha256), ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())
