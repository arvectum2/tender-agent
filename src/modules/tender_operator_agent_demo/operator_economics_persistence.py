"""Product-owned quote and economics persisted payload compatibility projection.

Legacy quote placeholders and absent monetary fields remain review-only;
this module does not infer suppliers, prices, margins, or procurement approval.
"""

from __future__ import annotations

from typing import Any


def _serialize_quote_comparison(quote_comparison) -> dict[str, Any]:
    return quote_comparison.model_dump(mode="json")


def _serialize_economics_summary(economics_summary) -> dict[str, Any]:
    return economics_summary.model_dump(mode="json")


def _maybe_float(value: Any) -> float | None:
    if value in (None, "", "unknown"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_quote_comparison_payload(payload: dict[str, Any]):
    from src.modules.tender_operator_agent_demo.schemas import QuoteComparison

    suppliers = []
    for index, item in enumerate(payload.get("suppliers", []), start=1):
        if isinstance(item, dict) and "supplier_id" in item and "supplier_name" in item:
            suppliers.append(item)
            continue
        suppliers.append(
            {
                "supplier_id": f"SUP-{index:02d}",
                "supplier_name": item.get("supplier_name")
                or item.get("supplier")
                or item.get("supplier_label")
                or f"Supplier {index}",
                "source_file": item.get("source_file")
                or item.get("supplier_label")
                or "uploaded quote",
                "source_sheet": item.get("source_sheet"),
                "document_type": item.get("document_type", "legacy_quote_placeholder"),
                "total_amount": _maybe_float(
                    item.get("total_amount") or item.get("price_total")
                ),
                "currency": item.get("currency", "RUB"),
                "items_count": item.get("items_count", 0),
                "delivery_summary": item.get("delivery_summary")
                or item.get("delivery_time_days"),
                "completeness_score": item.get("completeness_score", 0.0),
                "price_confidence": item.get("price_confidence", 0.0),
                "warnings": item.get("warnings", []),
                "items": item.get("items", []),
            }
        )
    manual_checks = [
        item
        if isinstance(item, dict)
        else {"code": "manual_check", "message": str(item)}
        for item in payload.get("manual_checks", [])
    ]
    warnings = [
        item if isinstance(item, dict) else {"code": "warning", "message": str(item)}
        for item in payload.get("warnings", [])
    ]
    return QuoteComparison.model_validate(
        {
            "status": payload.get("status", "blocked"),
            "analysis_mode": payload.get("analysis_mode", "unknown"),
            "supplier_quotes_found": payload.get("supplier_quotes_found", 0),
            "items_extracted": payload.get("items_extracted", 0),
            "suppliers": suppliers,
            "items": payload.get("items", []),
            "comparison_summary": payload.get("comparison_summary", {}),
            "manual_checks": manual_checks,
            "warnings": warnings,
            "limitations": payload.get("limitations", []),
        }
    )


def _coerce_economics_summary_payload(payload: dict[str, Any]):
    from src.modules.tender_operator_agent_demo.schemas import EconomicsSummary

    manual_checks = [
        item
        if isinstance(item, dict)
        else {"code": "manual_check", "message": str(item)}
        for item in payload.get("manual_checks", [])
    ]
    warnings = [
        item if isinstance(item, dict) else {"code": "warning", "message": str(item)}
        for item in payload.get("warnings", [])
    ]
    return EconomicsSummary.model_validate(
        {
            "status": payload.get("status", "blocked"),
            "analysis_mode": payload.get("analysis_mode", "unknown"),
            "currency": payload.get("currency"),
            "supplier_cost_min": payload.get("supplier_cost_min"),
            "supplier_cost_selected": payload.get("supplier_cost_selected"),
            "expected_revenue": payload.get("expected_revenue"),
            "preliminary_bid_price": payload.get("preliminary_bid_price"),
            "gross_margin_amount": payload.get("gross_margin_amount"),
            "gross_margin_percent": payload.get("gross_margin_percent"),
            "logistics_reserve": payload.get("logistics_reserve"),
            "risk_reserve": payload.get("risk_reserve"),
            "payment_delay_days": payload.get("payment_delay_days"),
            "cash_gap_estimate": payload.get("cash_gap_estimate"),
            "economics_status": payload.get("economics_status", "insufficient_data"),
            "selected_supplier_name": payload.get("selected_supplier_name"),
            "assumptions": payload.get("assumptions", {}),
            "manual_checks": manual_checks,
            "warnings": warnings,
            "limitations": payload.get("limitations", []),
        }
    )
