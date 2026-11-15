"""First-party B2B-Center public discovery proof, not participation authorization.

Only a pinned public tender URL reached from original public platform index.
No login, purchase, invitation or bid. Original HTML never persisted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

INDEX = "https://www.b2b-center.ru/search/industry/razrabotka-sajtov/"
DETAIL = (
    "https://www.b2b-center.ru/app/market-next/"
    "razrabotka-korporativnogo-saita-pod-kliuch-s-obiazatelnym/tender-4643484/"
)
_NUMBER = "4643484"
_TITLE = "Разработка корпоративного сайта под ключ с обязательным предоставлением реализованных кейсов"
_END = "до 21.10.2026 06:00, по МСК"
_MAX = 900_000


class PrimaryMarketError(ValueError):
    """Unable to establish original primary public source on official host."""


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def verify(index: bytes, detail: bytes, *, observed_at: datetime) -> dict:
    if (not 0 < len(index) <= _MAX or not 0 < len(detail) <= _MAX
            or observed_at.tzinfo is None or observed_at.utcoffset() is None):
        raise PrimaryMarketError("oversized/empty/naive official observation")
    a, b = index.decode("utf-8"), detail.decode("utf-8")
    if (not 1 <= a.count(DETAIL) <= 20
            or _NUMBER not in a
            or _NUMBER not in b
            or "ТЕХ ВЗРЫВ ИНВЕСТ" not in a
            or _TITLE not in b
            or _END not in b
            or not re.search(r'АО[^<]{0,60}ТЕХ ВЗРЫВ ИНВЕСТ', b, re.IGNORECASE)):
        raise PrimaryMarketError("not same official original tender / no verified deadline")
    return {
        "contract_version": "b2bcenter_4643484_first_party_readonly_v1",
        "registry_number": _NUMBER,
        "source": "B2B_CENTER_ORIGINAL_PUBLIC_PLATFORM_INDEX_AND_DIRECT_TENDER",
        "official_category_index": INDEX,
        "exact_platform_detail_url": DETAIL,
        "index_html_sha256": _sha(index),
        "index_html_bytes": len(index),
        "detail_html_sha256": _sha(detail),
        "detail_html_bytes": len(detail),
        "observed_at_utc": observed_at.astimezone(UTC).isoformat(),
        "original_organizer": 'АО "ТЕХ ВЗРЫВ ИНВЕСТ"',
        "original_subject": "Корпоративный сайт под ключ, с подтверждёнными кейсами и КП",
        "original_printed_deadline_moscow": "2026-10-21T06:00:00+03:00",
        "public_original_listing_seen": True,
        "full_commercial_specification_verified": False,
        "bidder_portfolio_acceptance_verified": False,
        "platform_business_account_entitlement_verified": False,
        "platform_fees_confirmed_for_this_bid": False,
        "confirmed_initial_purchase_price": None,
        "buyer_go_or_bid_ready": False,
        "payment_or_external_message": False,
    }


def _public_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=16) as response:
        if response.status != 200 or response.geturl() != url:
            raise PrimaryMarketError("platform redirect / non-200")
        blob = response.read(_MAX + 1)
        if len(blob) > _MAX:
            raise PrimaryMarketError("original HTML exceeds byte bound")
        return blob


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    result = verify(_public_get(INDEX), _public_get(DETAIL), observed_at=datetime.now(UTC))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
