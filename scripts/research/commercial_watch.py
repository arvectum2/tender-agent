"""Source-bound read-only commercial watch: verified GEH delta + dated SIBUR public snapshot.

No network, database, subprocess, connector credentials, or local writes.
A public-list observation is NOT proof of live eligibility, current stage or award.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

MOSCOW = timezone(timedelta(hours=3))
SHA = re.compile(r"^[0-9a-f]{64}$")
SOURCE_HOSTS = {"etpgpb.ru", "www.sibur.ru", "sibur.ru"}
MONTHS_RU = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
    "мая": 5, "июня": 6, "июля": 7, "августа": 8,
    "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}
# Narrow, business-relevant evidence, NOT LLM judgement of eligibility.
MATCHES = (
    ("АСУ ТП / автоматизация", 100, re.compile(
        r"асу\s*тп|асутп|автоматизац|систем[аы] управления производством|диспетчер", re.IGNORECASE)),
    ("ПНР / электромонтаж", 95, re.compile(
        r"пусконалад|\bпнр\b|\bппнр\b|электромонтаж", re.IGNORECASE)),
    ("Электротехника / приводы", 90, re.compile(
        r"электродвигател|электропривод|электрооборудован|электротехнич|"
        r"трансформатор|релейн|рза\b|частотн|тиристор|"
        r"\bктп\b|коммутац", re.IGNORECASE)),
    ("КИПиА / измерение", 87, re.compile(
        r"\bкип\b|кипи[а-я]?|расходомер|датчик|сенсор|"
        r"метролог|анализатор|вибропреобразоват", re.IGNORECASE)),
    ("Инженерные работы", 68, re.compile(
        r"проектно.изыскательск|проектирован|техническ[а-я ]*перевооруж|"
        r"модернизац", re.IGNORECASE)),
)
MAX_INPUT_BYTES = 5_000_000
MAX_PAGE_BYTES = 4_000_000


class EvidenceRejected(ValueError):
    """Cannot safely turn unverified snapshots into business recommendations."""


def _read_json(path: Path, *, max_bytes: int = MAX_INPUT_BYTES):
    if not path.is_file() or path.stat().st_size > max_bytes:
        raise EvidenceRejected(f"missing or oversized evidence: {path.name}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise EvidenceRejected(f"invalid evidence JSON: {path.name}") from exc


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(131072), b""):
            h.update(block)
    return h.hexdigest()


def _verified_sha(value: str) -> bool:
    return isinstance(value, str) and SHA.fullmatch(value) is not None


def _first_party_url(raw: str, *, provider: str) -> str:
    if not isinstance(raw, str):
        raise EvidenceRejected("missing first-party source URL")
    u = urlsplit(raw)
    required = {"geh": "etpgpb.ru", "sibur": "www.sibur.ru"}[provider]
    if (u.scheme != "https" or u.hostname != required or u.username or u.password
            or u.port is not None or not u.path.startswith(
                "/procedures/" if provider == "geh" else "/ru/procurement/buy/"
            )):
        raise EvidenceRejected("non-first-party or non-procurement URL")
    return raw


def _time(raw: str) -> datetime:
    if not isinstance(raw, str):
        raise EvidenceRejected("missing timestamp")
    try:
        value = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise EvidenceRejected("invalid timestamp") from exc
    if value.tzinfo is None:
        raise EvidenceRejected("timestamp missing timezone")
    return value.astimezone(UTC)


def _geh_deadline(raw: str) -> datetime:
    if not isinstance(raw, str):
        raise EvidenceRejected("GEH deadline missing")
    match = re.fullmatch(r"(\d{1,2}) (\S+) (\d{4}), (\d{2}):(\d{2}) Z", raw.strip())
    if not match:
        raise EvidenceRejected("GEH deadline format unverified")
    day, month, year, hour, minute = match.groups()
    if month not in MONTHS_RU:
        raise EvidenceRejected("GEH month not recognized")
    try:
        return datetime(
            int(year), MONTHS_RU[month], int(day), int(hour), int(minute), tzinfo=UTC
        )
    except ValueError as exc:
        raise EvidenceRejected("GEH deadline invalid") from exc


def _sibur_deadline(raw: str) -> datetime:
    try:
        return datetime.strptime(raw, "%Y-%m-%d %H:%M").replace(tzinfo=MOSCOW).astimezone(UTC)
    except (ValueError, TypeError) as exc:
        raise EvidenceRejected("SIBUR deadline unverified") from exc


def _classify(title: str, category: str) -> tuple[str, int] | None:
    if not isinstance(title, str) or len(title) > 1000:
        raise EvidenceRejected("invalid procurement title")
    haystack = title + " " + (category if isinstance(category, str) else "")
    choices = [(name, score) for name, score, pattern in MATCHES if pattern.search(haystack)]
    return max(choices, key=lambda x: x[1]) if choices else None


def _item(
    source: str, row: dict, deadline: datetime, observed: datetime,
    as_of: datetime, *, is_new: bool, freshness: str, category: str,
) -> dict | None:
    if deadline <= as_of:
        return None
    title = row.get("title")
    fit = _classify(title, category)
    if fit is None:
        return None
    if not isinstance(row.get("external_id"), str) or not row["external_id"]:
        raise EvidenceRejected("missing source identity")
    if not _verified_sha(row.get("source_sha256")):
        raise EvidenceRejected("missing original page SHA")
    url = _first_party_url(row.get("detail_url") if source == "GEH" else row.get("source_url"),
                           provider="geh" if source == "GEH" else "sibur")
    if observed > as_of + timedelta(minutes=5):
        raise EvidenceRejected("snapshot observation in the future")
    kind = ("MARKET_RESEARCH_ONLY" if row["external_id"].startswith("price_request:")
            else "PUBLIC_LIST_CARD_RECHECK" if source == "GEH"
            else "STALE_SIBUR_SNAPSHOT_RECHECK")
    hours = (deadline - as_of).total_seconds() / 3600
    score = min(100, fit[1] + (7 if hours <= 48 else 0) + (3 if is_new else 0))
    return {
        "source": source,
        "external_id": row["external_id"],
        "title": title,
        "buyer_as_published": row.get("customers_raw") if source == "GEH" else row.get("organizer"),
        "organizer_as_published": row.get("organizer_raw") if source == "GEH" else None,
        "topic": fit[0],
        "priority_score": score,
        "deadline_utc": deadline.isoformat(),
        "observed_at_utc": observed.isoformat(),
        "first_party_source_url": url,
        "source_sha256": row["source_sha256"],
        "novelty": "new_verified_ingest" if is_new else "previous_observation",
        "evidence_status": kind,
        "freshness": freshness,
        "next_action": (
            "Проверить предмет, требования и статус в карточке запроса цен; не считать тендером"
            if kind == "MARKET_RESEARCH_ONLY" else
            "Повторно проверить текущий статус и срок в официальном источнике; не утверждать право участия"
        ),
    }


def _geh(snapshot: Path, as_of: datetime) -> tuple[list[dict], dict]:
    capture = _read_json(snapshot / "capture-status.json")
    state = _read_json(snapshot / "guarded-ingest" / "state.json")
    receipts = _read_json(snapshot / "gpb-geh-section-receipts.json")
    plan_path = snapshot / "verified-active-plan.json"
    plan = _read_json(plan_path)
    new_path = snapshot / "guarded-ingest" / "new-only.json"
    new_payload = _read_json(new_path)
    if (not isinstance(receipts, list) or not isinstance(plan, list)
            or not isinstance(new_payload, dict)
            or not isinstance(new_payload.get("accepted"), list)):
        raise EvidenceRejected("invalid GEH source structure")
    n = capture.get("expected_pages")
    if (capture.get("complete") is not True or not isinstance(n, int) or not 1 <= n <= 25
            or capture.get("verified_pages") != n or len(receipts) != n):
        raise EvidenceRejected("GEH source pagination incomplete")
    pages = set()
    source_hashes = set()
    for receipt in receipts:
        if not isinstance(receipt, dict):
            raise EvidenceRejected("invalid GEH page receipt")
        page = receipt.get("current_page")
        name = receipt.get("name")
        expected_sha = receipt.get("sha256")
        if (not isinstance(page, int) or page in pages or page not in range(1, n + 1)
                or receipt.get("advertised_last_page") != n or
                name != f"geh_active_p{page}" or not _verified_sha(expected_sha)):
            raise EvidenceRejected("invalid GEH receipt identity")
        html_path = snapshot / f"{name}.html"
        if (not html_path.is_file() or html_path.stat().st_size > MAX_PAGE_BYTES
                or _sha(html_path) != expected_sha):
            raise EvidenceRejected("GEH original HTML hash mismatch")
        pages.add(page)
        source_hashes.add(expected_sha)
    if len(pages) != n:
        raise EvidenceRejected("GEH page receipt missing")
    if (state.get("status") != "completed" or state.get("stage") != "verified"
            or state.get("inflight") is not False or
            state.get("old_rows_unchanged") is not True or
            state.get("replay_inserted") != 0 or
            not _verified_sha(state.get("plan_sha256")) or
            _sha(plan_path) != state["plan_sha256"] or
            not _verified_sha(state.get("source_input_sha256")) or
            _sha(new_path) != state["source_input_sha256"]):
        raise EvidenceRejected("GEH immutable ingest/replay proof invalid")
    newly = new_payload["accepted"]
    if (not isinstance(state.get("new"), int) or state["new"] < 0
            or len(newly) != state["new"] or
            state.get("inserted") != state["new"] or
            state.get("after") != state.get("before", -1) + state["new"] or
            state.get("valid") != len(plan)):
        raise EvidenceRejected("GEH inserted-count or immutable-history mismatch")
    originals = {}
    for entry in plan:
        if not isinstance(entry, dict) or not isinstance(entry.get("observation"), dict):
            raise EvidenceRejected("GEH plan row invalid")
        row = entry["observation"]
        if (row.get("source") != "etp_gpb" or
                row.get("verification") != "PUBLIC_LIST_OBSERVATION_ONLY" or
                row.get("source_sha256") not in source_hashes):
            raise EvidenceRejected("unverifiable GEH source row")
        rid = row.get("external_id")
        if rid in originals or not isinstance(rid, str) or not rid.startswith(("etp:", "price_request:")):
            raise EvidenceRejected("GEH duplicate or unknown identity")
        originals[rid] = entry
    found = set()
    candidates = []
    for entry in newly:
        if not isinstance(entry, dict) or not isinstance(entry.get("observation"), dict):
            raise EvidenceRejected("GEH newly imported row invalid")
        row = entry["observation"]
        rid = row.get("external_id")
        if rid in found or rid not in originals or entry != originals[rid]:
            raise EvidenceRejected("GEH newly inserted source cannot be matched to plan")
        found.add(rid)
        observed = _time(entry["observed_at"])
        candidate = _item(
            "GEH", row, _geh_deadline(row.get("deadline_raw")), observed, as_of,
            is_new=True, freshness="same_day" if as_of - observed <= timedelta(days=1) else "old_snapshot",
            category="",
        )
        if candidate is not None:
            candidates.append(candidate)
    return candidates, {"pages": n, "captured": len(plan) + state.get("review", 0),
                        "accepted": len(plan), "review": state.get("review"),
                        "actually_inserted": len(newly), "matching_unexpired": len(candidates),
                        "capture_status": "verified_hash_and_database_replay"}


def _sibur(watch: Path, as_of: datetime) -> tuple[list[dict], dict]:
    data = _read_json(watch)
    if not isinstance(data, dict) or not isinstance(data.get("rows"), list):
        raise EvidenceRejected("SIBUR watch structure invalid")
    if not _verified_sha(data.get("snapshot_receipts_sha256")):
        raise EvidenceRejected("SIBUR snapshot receipts SHA missing")
    observed = _time(data.get("as_of"))
    if observed > as_of + timedelta(minutes=5):
        raise EvidenceRejected("future SIBUR observation")
    stale = as_of - observed > timedelta(hours=48)
    seen = set()
    candidates = []
    expired = 0
    for entry in data["rows"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("observation"), dict):
            raise EvidenceRejected("SIBUR watch row malformed")
        row = entry["observation"]
        rid = row.get("external_id")
        if not isinstance(rid, str) or not rid or rid in seen or rid != entry.get("procedure_id"):
            raise EvidenceRejected("SIBUR duplicate or unstable identity")
        seen.add(rid)
        if (row.get("verification") != "PUBLIC_SNAPSHOT_ONLY"
                or row.get("source") != "sibur_public"):
            raise EvidenceRejected("SIBUR status unsupported by source")
        deadline = _sibur_deadline(entry.get("deadline_msk"))
        if deadline <= as_of:
            expired += 1
        item = _item(
            "SIBUR", row, deadline, observed, as_of, is_new=False,
            freshness="older_than_48h_requires_refresh" if stale else "recent_public_snapshot_only",
            category=row.get("category") or "",
        )
        if item is not None:
            item["commercial_kind_from_prior_review"] = entry.get("commercial_kind")
            item["previous_priority"] = entry.get("priority")
            candidates.append(item)
    return candidates, {"snapshot_at_utc": observed.isoformat(), "source_rows": len(seen),
                        "expired_observed_deadlines": expired,
                        "freshness": "stale" if stale else "recent",
                        "unexpired_relevant_requires_live_recheck": len(candidates)}


def compile_watch(geh_snapshot: Path, sibur_watch: Path, as_of: datetime,
                  *, limit_per_source: int = 10) -> dict:
    if as_of.tzinfo is None or not 1 <= limit_per_source <= 30:
        raise EvidenceRejected("invalid observation cutoff or report size")
    as_of = as_of.astimezone(UTC)
    geh, geh_summary = _geh(geh_snapshot, as_of)
    sibur, sibur_summary = _sibur(sibur_watch, as_of)
    order = lambda c: (-c["priority_score"], c["deadline_utc"], c["external_id"])
    return {
        "schema": "arvectum_commercial_watch_v1",
        "generated_for_utc": as_of.isoformat(),
        "scope": "read_only_first_party_observations_not_live_eligibility",
        "production_database_modified": False,
        "submissions_sent": False,
        "sibur": {"summary": sibur_summary, "candidates": sorted(sibur, key=order)[:limit_per_source]},
        "geh": {"summary": geh_summary, "candidates": sorted(geh, key=order)[:limit_per_source]},
    }


def render_markdown(data: dict) -> str:
    lines = [
        "# Коммерческая подборка Arvectum: СИБУР и ГЭХ",
        f"Срез: {data['generated_for_utc']} (UTC). Только проверенные сохранённые публичные наблюдения; **не подтверждён доступ к участию**.",
        "",
    ]
    for source in ("geh", "sibur"):
        part = data[source]
        summary = part["summary"]
        lines += [
            f"## {source.upper()}",
            "Источник/состояние: " + ", ".join(f"{k}={v}" for k, v in summary.items()),
            "",
        ]
        for i, c in enumerate(part["candidates"], 1):
            title = c["title"].replace("\n", " ").replace("]", r"\]")
            buyer = (c["buyer_as_published"] or "не подтверждён").replace("\n", " ")
            lines.extend([
                f"{i}. **[{title}]({c['first_party_source_url']})** — {c['external_id']}",
                (f"   Заказчик по публикации: {buyer}. Направление: {c['topic']}. "
                 f"Дедлайн по наблюдению: {c['deadline_utc']} (UTC). "
                 f"Приоритет: {c['priority_score']}/100."),
                (f"   Доказательства: {c['novelty']}, {c['freshness']}, {c['evidence_status']}; "
                 f"SHA страницы: {c['source_sha256'][:12]}…. Действие: {c['next_action']}"),
            ])
        if not part["candidates"]:
            lines.append("Нет подтверждённых по этому срезу релевантных процедур с будущим дедлайном.")
        lines.append("")
    lines.append(
        "**Ограничение:** статус публичного списка не равен статусу официальной карточки, "
        "подтверждённому допуску или текущему состоянию закрытой SAP SRM. "
        "Запрос цен — не тендер; прошлые сроки исключены."
    )
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--geh-snapshot", type=Path, required=True)
    p.add_argument("--sibur-watch", type=Path, required=True)
    p.add_argument("--as-of", default=datetime.now(UTC).isoformat())
    p.add_argument("--limit-per-source", type=int, default=10)
    p.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = p.parse_args()
    try:
        value = compile_watch(args.geh_snapshot, args.sibur_watch, _time(args.as_of),
                              limit_per_source=args.limit_per_source)
    except EvidenceRejected as exc:
        p.exit(2, f"Evidence rejected: {exc}\n")
    if args.format == "json":
        print(json.dumps(value, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(value))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
