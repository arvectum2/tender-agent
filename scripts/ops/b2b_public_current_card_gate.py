"""Fail-closed current *displayed card* vs archived official sources.

This script never authenticates, downloads private documents or submits an ETP bid.
HTTP 404/403 and missing stage stay UNKNOWN, not "open".
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from scripts.acceptance.check_r4_live_eis_cards import (
    compare_deadline,
    official_url,
    parse_official_card,
)

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "docs" / "roadmap"
OLD = SRC / "b2b_44fz_official_printform_observations_2026-10-17.json"
EIS = SRC / "b2b_oct18_three_new_eis_originals.json"
B2B = SRC / "b2b_oct18_b2bcenter_4643484_firstparty.json"
METHODS = {
    "epNotificationEOK2020": "COMPETITIVE_OPEN_ELECTRONIC_COMPETITION",
    "epNotificationEZK2020": "COMPETITIVE_ELECTRONIC_QUOTATIONS",
    "epNotificationEF2020": "COMPETITIVE_ELECTRONIC_AUCTION",
}
MAX_BYTES = 1_400_000
KIND = ("live-common-info", "printform")
OFFICIAL = "https://zakupki.gov.ru/epz/order/notice/printForm/view.html?regNumber="
OFFICIAL_HOME = "https://zakupki.gov.ru/epz/main/public/home.html"
NUMBER = re.compile(r"\d{19}\Z")


class PublicStageError(ValueError):
    """No defensible first-party displayed-stage observation."""


class _Visible(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.skip: list[str] = []
        self.values: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"style", "script", "noscript", "svg"}:
            self.skip.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if self.skip and tag == self.skip[-1]:
            self.skip.pop()

    def handle_data(self, data: str) -> None:
        if not self.skip and data.strip():
            self.values.append(" ".join(data.split()))


def _visible(raw: bytes) -> list[str]:
    if not 1200 < len(raw) < MAX_BYTES:
        raise PublicStageError("source body invalid/too short/too long")
    page = _Visible()
    page.feed(raw.decode("utf8", errors="strict"))
    return page.values


def _safe_url(requested: str, actual: str) -> bool:
    req, out = urlsplit(requested), urlsplit(actual)
    return (
        req.scheme == out.scheme == "https"
        and req.netloc == out.netloc
        and req.path == out.path
        and parse_qs(req.query) == parse_qs(out.query)
        and not out.fragment
        and not out.username
        and not out.password
    )


def _read_public(url: str) -> dict:
    """Bounded TLS curl; original HTML is ephemeral, record HTTP outcome only."""
    with tempfile.TemporaryDirectory(prefix="ta-public-status-") as tmp:
        filename = Path(tmp) / "source"
        attempt = subprocess.run(
            [
                "/usr/bin/curl", "--silent", "--show-error", "--location",
                "--max-redirs", "1", "--proto", "=https", "--proto-redir", "=https",
                "--connect-timeout", "8", "--max-time", "20",
                "--max-filesize", str(MAX_BYTES), "--output", str(filename),
                "--write-out", "%{http_code}\t%{ssl_verify_result}\t%{url_effective}",
                url,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=25,
        )
        status = attempt.stdout.strip().split("\t")
        if len(status) != 3:
            return {"http_state": "TRANSPORT_UNAVAILABLE", "raw": None}
        http, ssl, actual = status
        if ssl != "0" or not _safe_url(url, actual):
            return {"http_state": "TLS_OR_REDIRECT_UNVERIFIED", "raw": None}
        if attempt.returncode != 0 or http != "200":
            return {"http_state": "HTTP_" + http if http.isdigit() else "TRANSPORT_UNAVAILABLE", "raw": None}
        if not filename.is_file() or not 1200 < filename.stat().st_size <= MAX_BYTES:
            return {"http_state": "INVALID_BODY", "raw": None}
        return {"http_state": "HTTP_200", "raw": filename.read_bytes()}


def dedupe_new_ids(current: dict, baseline: dict) -> dict:
    original = current["records"]
    identifiers = [r.get("number") for r in original]
    if (len(identifiers) != 3 or len(set(identifiers)) != 3
            or any(not isinstance(n, str) or not NUMBER.fullmatch(n) for n in identifiers)
            or any(r.get("archival_evidence") != "SHA_VERIFIED_NOTICE" for r in original)):
        raise PublicStageError("untrusted original fixed three procurement numbers")
    historical = {r.get("number") for r in baseline.get("items", [])}
    if "0163200000326005243" not in historical:
        raise PublicStageError("official 17 October prior record missing")
    already = sorted(set(identifiers) & historical)
    new = sorted(set(identifiers) - historical)
    if already != ["0163200000326005243"] or len(new) != 2:
        raise PublicStageError("wrong historic dedupe / inflation risk")
    return {
        "eis_originals_refetched_count": 3,
        "previously_firstparty_seen_original_ids": already,
        "net_new_distinct_eis_44fz_original_ids_vs_17_oct": new,
        "net_new_eis_44fz_original_count_vs_17_oct": 2,
    }


def _eis_record(notice: dict, observed: datetime, fetch) -> dict:
    number = notice["number"]
    if notice["source_notice_type"] not in METHODS or not NUMBER.fullmatch(number):
        raise PublicStageError("unknown official notice type/number")
    route = official_url(number, METHODS[notice["source_notice_type"]])
    printform = OFFICIAL + number
    result = {
        "number": number,
        "archived_notice_sha256": notice["original_xml_sha256"],
        "archived_notice_version": notice["selected_archived_version"],
        "original_archived_end_dt": notice["source_archived_end_dt"],
        "checked_at_utc": observed.astimezone(UTC).isoformat(),
        "request_live_info_url": route,
        "request_printform_url": printform,
        "current_legal_stage_verified": False,
        "current_official_xml_latest_edition_verified": False,
        "authenticated_bidder_eligibility_verified": False,
        "bid_ready": False,
    }
    for mode, url in (("live_common_info", route), ("public_printform", printform)):
        response = fetch(url)
        status = response.get("http_state")
        if not isinstance(status, str) or not status:
            raise PublicStageError("unusable fetch metadata")
        row = {"http_state": status, "firstparty_displayed_stage": "UNKNOWN",
               "archive_deadline_comparison": "UNKNOWN"}
        if status == "HTTP_200":
            raw = response.get("raw")
            if not isinstance(raw, bytes):
                raise PublicStageError("HTTP200 without source bytes")
            row.update({"source_html_sha256": hashlib.sha256(raw).hexdigest(),
                        "source_html_bytes": len(raw)})
            if mode == "live_common_info":
                try:
                    stage, deadline = parse_official_card(raw, number)
                except (ValueError, UnicodeError):
                    row["source_parse_state"] = "UNVERIFIED_CARD_CONTENT"
                else:
                    row["firstparty_displayed_stage"] = stage
                    row["firstparty_displayed_deadline"] = deadline or "UNKNOWN"
                    row["archive_deadline_comparison"] = compare_deadline(
                        deadline, notice["source_archived_end_dt"]
                    )
                    row["source_parse_state"] = "EXACT_NUMBER_STAGE_AT_CAPTURE_ONLY"
            else:
                text = raw.decode("utf-8", errors="replace")
                if re.search(rf"(?<!\d){re.escape(number)}(?!\d)", text):
                    row["source_parse_state"] = "NUMBER_MATCH_ONLY_NOT_LEGAL_STAGE"
                else:
                    row["source_parse_state"] = "UNVERIFIED_PRINTFORM"
        result[mode] = row
    return result


def _commercial_record(source: dict, observed: datetime, fetch) -> dict:
    url = source["exact_platform_detail_url"]
    if not url.startswith("https://www.b2b-center.ru/app/market-next/") or not url.endswith("/tender-4643484/"):
        raise PublicStageError("wrong original B2B-Center domain/card")
    response = fetch(url)
    status = response.get("http_state")
    item = {
        "number": "4643484", "original_public_url": url, "checked_at_utc": observed.astimezone(UTC).isoformat(),
        "http_state": status,
        "platform_displayed_stage": "UNKNOWN",
        "platform_displayed_deadline": "UNKNOWN",
        "full_sow_confirmed": False, "buyer_budget_confirmed": False,
        "vendor_account_entitlement_confirmed": False,
        "documented_comparable_completed_cases_confirmed": False,
        "bid_ready": False,
    }
    if status != "HTTP_200":
        return item
    raw = response.get("raw")
    if not isinstance(raw, bytes):
        raise PublicStageError("HTTP200 with no HTML")
    item["html_sha256"] = hashlib.sha256(raw).hexdigest()
    item["html_bytes"] = len(raw)
    try:
        vals = _visible(raw)
    except (UnicodeError, PublicStageError):
        item["source_parse_state"] = "UNVERIFIED_CARD"
        return item
    title = ("Разработка корпоративного сайта под ключ с обязательным предоставлением "
             "реализованных кейсов и коммерческих предложений")
    has_title = any(title in s and "4643484" in s for s in vals[:60])
    has_organizer = any("ТЕХ ВЗРЫВ ИНВЕСТ" in s for s in vals[:90])
    stages = [s for s in vals[:90] if s in {"Приём заявок", "Прием заявок", "Завершён", "Приём заявок завершён"}]
    deadlines = [s for s in vals[:100] if s == "до 21.10.2026 06:00, по МСК"]
    if not has_title or not has_organizer or len(stages) != 1 or len(deadlines) != 1:
        item["source_parse_state"] = "AMBIGUOUS_OR_CHANGED_STAGE"
        return item
    item["platform_displayed_stage"] = stages[0]
    item["platform_displayed_deadline"] = source["original_printed_deadline_moscow"]
    if stages[0] != "Приём заявок":
        item["source_parse_state"] = "FIRST_PARTY_TERMINAL_STAGE_AT_CAPTURE"
        return item
    deadline = datetime.fromisoformat(source["original_printed_deadline_moscow"])
    if deadline.tzinfo is None:
        raise PublicStageError("unverified commercial timezone")
    if observed >= deadline:
        item["source_parse_state"] = "EXPIRED_PRINTED_DEADLINE_DESPITE_ACTIVE_LABEL"
        return item
    item["source_parse_state"] = "FIRST_PARTY_PUBLIC_STAGE_AT_CAPTURE_ONLY"
    return item


def observe(source: dict, baseline: dict, b2b: dict, *, observed: datetime, fetch) -> dict:
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise PublicStageError("naive capture time")
    deduped = dedupe_new_ids(source, baseline)
    if b2b.get("registry_number") != "4643484" or b2b.get("buyer_go_or_bid_ready") is not False:
        raise PublicStageError("prior original commercial receipt invalid")
    eis = [_eis_record(row, observed, fetch) for row in source["records"]]
    commercial = _commercial_record(b2b, observed, fetch)
    home = fetch(OFFICIAL_HOME)
    home_status = home.get("http_state")
    if not isinstance(home_status, str):
        raise PublicStageError("unverified source host control")
    eis_host_control = {
        "official_home_url": OFFICIAL_HOME,
        "http_state": home_status,
        "proves_specific_notice_stage": False,
    }
    if home_status == "HTTP_200":
        body = home.get("raw")
        if isinstance(body, bytes) and 0 < len(body) <= MAX_BYTES:
            eis_host_control["html_sha256"] = hashlib.sha256(body).hexdigest()
            eis_host_control["html_bytes"] = len(body)
        else:
            eis_host_control["source_body_attested"] = False
            eis_host_control["http_state"] = "HTTP200_BODY_NOT_ATTESTED"
    return {
        "contract_version": "b2b_oct18_3eis_1b2b_firstparty_display_check_v1",
        "checked_at_utc": observed.astimezone(UTC).isoformat(),
        "archival_eis_source_dedupe": deduped,
        "net_new_unique_b2bcenter_primary_original_ids": ["4643484"],
        "new_distinct_primary_source_attestations_vs_17_oct": 3,
        "eis_live_notice_pages_parsed": sum(
            row["live_common_info"]["source_parse_state"] == "EXACT_NUMBER_STAGE_AT_CAPTURE_ONLY"
            for row in eis if "source_parse_state" in row["live_common_info"]
        ),
        "eis_current_legal_notice_status_verified_count": 0,
        "company_confirmed_bid_eligible_count": 0,
        "goal_15_20_strictly_qualified_met": False,
        "source_only_no_authenticated_actions": True,
        "eis_host_control": eis_host_control,
        "eis_rows": eis,
        "commercial_primary": commercial,
    }


def main() -> int:
    cli = argparse.ArgumentParser()
    cli.add_argument("--out", type=Path)
    args = cli.parse_args()
    result = observe(
        json.loads(EIS.read_text(encoding="utf8")),
        json.loads(OLD.read_text(encoding="utf8")),
        json.loads(B2B.read_text(encoding="utf8")),
        observed=datetime.now(UTC), fetch=_read_public,
    )
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.write_text(output, encoding="utf8")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
