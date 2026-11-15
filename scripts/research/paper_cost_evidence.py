"""Conservative admission gate for supplier price observations in a paper replay.

Search snippets and post-auction quotes must never become historical cost evidence.
No network, DB mutations, live bids, or inferred contract performance.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit


def decimal(value):
    try:
        n = Decimal(str(value))
        return n if n.is_finite() and n > 0 else None
    except (InvalidOperation, ValueError):
        return None


def aware(value):
    try:
        dt = datetime.fromisoformat(value)
        return dt if dt.utcoffset() is not None else None
    except (ValueError, TypeError):
        return None


def assess(position, offer, decision_at, *, original_bytes=None):
    reasons = []
    cutoff = aware(decision_at)
    observed = aware(offer.get("observed_at"))
    valid_until = aware(offer.get("valid_until"))
    if not cutoff or not observed or not valid_until:
        reasons.append("TIME_OR_VALIDITY_UNKNOWN")
    elif not observed <= cutoff <= valid_until:
        reasons.append("NOT_AVAILABLE_AT_DECISION_TIME")
    if offer.get("source_kind") != "verified_supplier_original":
        reasons.append("SOURCE_NOT_VERIFIED_ORIGINAL")
    sha = offer.get("source_sha256")
    url = urlsplit(offer.get("source_url") or "")
    if not isinstance(sha,str) or not re.fullmatch("[0-9a-f]{64}",sha) or url.scheme!="https" or not url.hostname:
        reasons.append("SOURCE_PROVENANCE_MISSING")
    if not isinstance(original_bytes, bytes) or not original_bytes or hashlib.sha256(original_bytes).hexdigest() != sha:
        reasons.append("SOURCE_ORIGINAL_NOT_HASH_VERIFIED")
    # A marketplace-local SKU is not a manufacturer article. A human-verified
    # crosswalk and exact variant/unit evidence are required, not fuzzy titles.
    if (offer.get("position_id") != position.get("position_id")
            or not position.get("verified_manufacturer_article")
            or offer.get("manufacturer_article") != position["verified_manufacturer_article"]
            or offer.get("variant_verified") is not True
            or not position.get("unit") or offer.get("unit") != position["unit"]):
        reasons.append("EXACT_ITEM_OR_UNIT_UNVERIFIED")
    qty, available, minimum = map(decimal,(position.get("quantity"),offer.get("available_quantity"),offer.get("minimum_order")))
    if not qty or not available or not minimum or not minimum <= qty <= available:
        reasons.append("STOCK_OR_MINIMUM_ORDER_UNVERIFIED")
    price = decimal(offer.get("unit_price"))
    if not price or offer.get("currency") != "RUB" or offer.get("price_binding") != "firm":
        reasons.append("BINDING_PRICE_UNKNOWN")
    if offer.get("vat_basis") not in {"included","excluded","not_applicable"}:
        reasons.append("VAT_UNKNOWN")
    delivery = aware(offer.get("delivery_by"))
    required = aware(position.get("required_delivery_by"))
    if not delivery or not required or not cutoff or not cutoff <= delivery <= required:
        reasons.append("DELIVERY_UNVERIFIED")
    return {"eligible_for_paper_cost":not reasons,"reasons":reasons,
            "observed_goods_cost_rub":str(price*qty) if not reasons else None,
            "profit_rub":None,"execution_allowed":False}
