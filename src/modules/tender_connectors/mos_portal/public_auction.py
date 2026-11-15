"""Strict source contract for the observed public Moscow quotation-session API."""
from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal

LIST = "https://old.zakupki.mos.ru/api/Cssp/Purchase/Query"
DETAIL = "https://zakupki.mos.ru/newapi/api/Auction/Get"
STATE = {19000002: "active", 19000003: "failed", 19000004: "finished",
         19000005: "canceled", 19000006: "confirm", 19000008: "offers_signed",
         19000009: "waiting_for_approval"}
COMPLETED = {19000004, 19000008}


def query(skip=0, take=10, states=(19000004, 19000008)):
    if not 0 <= skip <= 100000 or not 1 <= take <= 20 or not set(states) <= set(STATE):
        raise ValueError("bounded public query required")
    return {"filter": {"typeIn": {"values": [1]}, "nameLike": {}, "regionPaths": {},
                       "customerInnOrName": {"contains": True}, "numberLike": {"contains": True},
                       "externalNumberLike": {"contains": True},
                       "auctionSpecificFilter": {"stateIdIn": list(states)},
                       "needSpecificFilter": {}, "tenderSpecificFilter": {}, "ptkrSpecificFilter": {}},
            "order": [{"field": "PublishDate", "desc": True}], "withCount": False,
            "take": take, "skip": skip}


def money(v, *, required=False):
    if v is None and not required:
        return None
    if isinstance(v, bool) or not isinstance(v, (int, float, str, Decimal)):
        raise TypeError("unexpected numeric field")
    d = Decimal(str(v))
    if not d.is_finite() or d < 0:
        raise ValueError("invalid numeric field")
    return str(d)


def date_text(v):
    if v is None:
        return None
    datetime.strptime(v, "%d.%m.%Y %H:%M:%S")  # noqa: DTZ007 - validate wire format only
    return v  # timezone not inferred from the wire value


def identity(v):
    if not isinstance(v, dict) or not isinstance(v.get("name"), str) or not v["name"].strip():
        raise ValueError("missing public legal identity")
    inn = v.get("inn")
    if inn is not None and not re.fullmatch(r"(?:[0-9]{10}|[0-9]{12})", inn):
        raise ValueError("invalid source INN")
    return {"name": v["name"], "inn": inn, "ogrn": v.get("ogrn")}


def list_row(raw):
    i = raw.get("auctionId")
    if (type(i) is not int or i <= 0 or raw.get("tradeType") != 1
            or raw.get("id") != f"Auction{i}" or raw.get("number") != str(i)):
        raise ValueError("source auction identity mismatch")
    status = STATE.get(raw.get("stateId"))
    if status is None or not isinstance(raw.get("name"), str) or not raw["name"].strip():
        raise ValueError("unknown public auction status/title")
    customers = raw.get("customers")
    if not isinstance(customers, list) or not customers:
        raise ValueError("missing customer list")
    bids = raw.get("offerCount")
    if bids is not None and (type(bids) is not int or bids < 0):
        raise ValueError("invalid offer count")
    return {"source": "mos_portal", "external_id": str(i), "title": raw["name"],
            "url": f"https://zakupki.mos.ru/auction/{i}", "state": status,
            "state_id": raw["stateId"], "state_raw": raw.get("stateName"),
            "customers": [identity(c) for c in customers], "winner": identity(raw["winner"]) if raw.get("winner") else None,
            "list_initial_price_rub": money(raw.get("startPrice"), required=True),
            "list_current_bid_rub": money(raw.get("auctionCurrentPrice")),
            "offer_count": bids, "region": raw.get("regionName"), "law": raw.get("federalLawName"),
            "begin_raw": date_text(raw.get("beginDate")), "end_raw": date_text(raw.get("endDate")),
            "signed_contract_amount": None, "verification": "PUBLIC_AUCTION_LIST_ONLY"}


def detail_row(raw, listing):
    if str(raw.get("id")) != listing["external_id"]:
        raise ValueError("detail identity mismatch")
    if raw.get("state", {}).get("id") != listing["state_id"]:
        raise ValueError("detail status changed; review")
    if raw.get("name") != listing["title"]:
        raise ValueError("detail title changed; review")
    start = money(raw.get("startCost"), required=True)
    if Decimal(start) != Decimal(listing["list_initial_price_rub"]):
        raise ValueError("initial price mismatch")
    last = money(raw.get("lastBetCost"))
    current = listing["list_current_bid_rub"]
    if last is not None and current is not None and Decimal(last) != Decimal(current):
        raise ValueError("list/detail bid mismatch")
    items = []
    seen = set()
    for item in raw.get("items") or []:
        position = item.get("id")
        sku = item.get("skuId")
        if type(position) is not int or position <= 0 or position in seen or not item.get("name"):
            raise ValueError("invalid position identity")
        if sku is not None and (type(sku) is not int or sku <= 0):
            raise ValueError("invalid SKU identity")
        seen.add(position)
        items.append({"position_id": position, "sku_id": sku, "name": item["name"],
                      "quantity": money(item.get("currentValue"), required=True),
                      "unit": item.get("okeiName"), "initial_unit_price_rub": money(item.get("costPerUnit")),
                      "category": item.get("productionDirectoryName"), "okpd_name": item.get("okpdName"),
                      "winning_unit_price_rub": None})
    if not items:
        raise ValueError("no verified position rows")
    line_sum = (sum(Decimal(i["quantity"]) * Decimal(i["initial_unit_price_rub"]) for i in items)
                if all(i["initial_unit_price_rub"] is not None for i in items) else None)
    total_matches = line_sum is not None and abs(line_sum - Decimal(start)) <= Decimal("0.01")
    # A published aggregate bid is not a signed contract or an allocated SKU price.
    return {**listing, "verification": "PUBLIC_AUCTION_LIST_AND_DETAIL", "items": items,
            "initial_position_sum_rub": str(line_sum) if line_sum is not None else None,
            "initial_position_sum_matches": total_matches, "detail_last_bid_rub": last,
            "published_contract_cost_unverified": money(raw.get("contractCost")),
            "signed_contract_amount": None}
