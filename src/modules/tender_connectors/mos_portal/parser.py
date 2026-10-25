from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from src.modules.tender_connectors.base import ParsedPurchase, ParsedPurchaseItem
from src.modules.tender_connectors.shared_fields import (
    parse_portal_datetime,
    pick_nested,
)

_STATE_ID_TO_STATUS: dict[int, str] = {
    19000002: "Прием предложений",
    19000005: "Работа комиссии",
    19000006: "Завершен",
    19000007: "Отменен",
    19000008: "Не состоялся",
}


def parse_purchase_payload(raw: dict[str, Any], source: str = "mos_portal") -> ParsedPurchase:
    items_raw = raw.get("items") or raw.get("positions") or raw.get("purchaseItems") or raw.get("lotItems") or []
    parsed_items: list[ParsedPurchaseItem] = []
    for item_raw in items_raw:
        if not isinstance(item_raw, dict):
            continue
        try:
            parsed_items.append(parse_item_payload(item_raw))
        except Exception:
            continue

    external_id = _pick_external_id(raw) or ""

    return ParsedPurchase(
        source=source,
        external_id=str(external_id),
        title=_pick(raw, ["title", "subject", "name", "purchaseName"]) or f"Закупка {external_id}",
        url=_build_purchase_url(raw, external_id),
        status=_resolve_status(raw),
        region=_pick(raw, ["region", "deliveryRegion", "regionName"])
        or _pick_nested(raw, ["organizerInfo.address", "deliveryInfos.0.deliveryAddress.regionName"]),
        customer_name=_pick(raw, ["customerName", "customer", "organizationName", "buyerName", "organizerName"]),
        submission_deadline=_parse_datetime(
            _pick(raw, ["submissionDeadline", "deadline", "endDate", "bidsEndDate", "applicationFillingEndDate"])
        ),
        commission_fee_amount=_parse_decimal(_pick(raw, ["commissionFeeAmount", "commission", "commissionFee"])),
        security_amount=_parse_decimal(_pick(raw, ["securityAmount", "deposit", "applicationGuarantee"])),
        max_total_price=_parse_decimal(_pick(raw, ["maxTotalPrice", "startPrice", "sum", "initialPrice", "price"])),
        created_at_source=_parse_datetime(_pick(raw, ["createdAt", "publishDate", "creationDate", "updateDate"])),
        items=parsed_items,
        raw_payload=raw,
    )


def parse_item_payload(raw: dict[str, Any]) -> ParsedPurchaseItem:
    name = _pick(raw, ["name", "itemName", "title", "description", "subject", "tradeName"]) or ""
    if not name:
        raise ValueError("item name required")

    quantity = _parse_decimal(_pick(raw, ["quantity", "qty", "count", "amount"])) or Decimal(1)

    return ParsedPurchaseItem(
        position_external_id=_pick(raw, ["positionExternalId", "positionId", "id", "itemId"]),
        name=name,
        description=_pick(raw, ["description", "itemDescription", "details"]),
        okpd2=_pick(raw, ["okpd2", "okpd2Code", "classifier", "okpdCode"]),
        quantity=quantity,
        unit=_pick(raw, ["unit", "measure", "unitName", "okeiTitle", "okeiCode"]),
        max_unit_price=_parse_decimal(_pick(raw, ["maxUnitPrice", "unitPrice", "price"])),
        max_total_price=_parse_decimal(_pick(raw, ["maxTotalPrice", "totalPrice", "sum"])),
        delivery_region=_pick(raw, ["deliveryRegion", "region"]) or _pick_nested(raw, ["deliveryAddress.regionName"]),
        delivery_address=_pick(raw, ["deliveryAddress", "address", "deliveryPlace"])
        or _pick_nested(raw, ["deliveryAddress.formattedFullInfo"]),
        delivery_terms=_pick(raw, ["deliveryTerms", "deliveryConditions", "terms"]),
        raw_payload=raw,
    )


def _pick_external_id(raw: dict[str, Any]) -> str | None:
    return _pick(raw, [
        "externalId", "id", "purchaseNumber", "auctionId", "sessionId",
        "number", "tradeNumber", "announcementId",
    ])


def _build_purchase_url(raw: dict[str, Any], external_id: str) -> str | None:
    url = _pick(raw, ["url", "link", "href"])
    if url:
        return url
    if not external_id:
        return None
    return f"https://zakupki.mos.ru/auction/{external_id}"


def _resolve_status(raw: dict[str, Any]) -> str | None:
    direct = _pick(raw, ["status", "statusName", "lotState", "dealState"])
    if direct:
        normalized = direct.strip().lower()
        if normalized == "активная":
            return "Прием предложений"
        return direct

    state = raw.get("state") or raw.get("statusInfo") or raw.get("auctionSpecificFilter")
    if isinstance(state, dict):
        state_name = _pick(state, ["name", "status", "statusName"])
        if state_name:
            normalized = state_name.strip().lower()
            if normalized == "активная":
                return "Прием предложений"
            return state_name
        state_id = state.get("id")
        mapped = _map_state_id_to_status(state_id)
        if mapped:
            return mapped

    mapped = _map_state_id_to_status(raw.get("stateId"))
    if mapped:
        return mapped

    return None


def _map_state_id_to_status(value: Any) -> str | None:
    if value is None:
        return None
    try:
        state_id = int(str(value).strip())
    except Exception:
        return None
    return _STATE_ID_TO_STATUS.get(state_id)


def _pick(raw: dict[str, Any], keys: list[str]) -> str | None:
    for key in keys:
        value = raw.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _pick_nested(raw: dict[str, Any], paths: list[str]) -> str | None:
    return pick_nested(raw, paths)


def _parse_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    normalized = str(value).replace("\u00a0", "").replace(" ", "").replace(",", ".")
    cleaned = "".join(ch for ch in normalized if ch in "0123456789.-")
    if cleaned in {"", "-", ".", "-."}:
        return None
    try:
        return Decimal(cleaned)
    except Exception:
        return None


def _parse_datetime(value: str | None) -> datetime | None:
    return parse_portal_datetime(value)


def _to_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
