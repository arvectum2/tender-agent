from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from src.modules.commercial_core.schemas import CommercialCoreResponse
from src.modules.commercial_core.service import build_commercial_core
from src.modules.tender_operator_agent_demo import upload_service_legacy as _legacy
from src.modules.tender_operator_agent_demo.report_model import (
    build_customer_report_projection,
)

_ALLOWED_CATALOG_SUFFIXES = {".csv", ".xlsx", ".xlsm"}
_MAX_CATALOG_BYTES = 12 * 1024 * 1024


def _safe_catalog_name(filename: str) -> str:
    name = Path(filename or "catalog").name
    suffix = Path(name).suffix.lower()
    if suffix not in _ALLOWED_CATALOG_SUFFIXES:
        raise HTTPException(status_code=400, detail=f"Unsupported commercial catalog type: {suffix or 'unknown'}")
    stem = re.sub(r"[^0-9A-Za-zА-Яа-я._-]+", "-", Path(name).stem).strip("._-") or "catalog"
    return f"{stem[:80]}{suffix}"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise HTTPException(status_code=409, detail="Analyze the tender run before commercial catalog matching")
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def _persist_source(run_id: str, filename: str, content: bytes) -> Path:
    safe_name = _safe_catalog_name(filename)
    digest = hashlib.sha256(content).hexdigest()[:12]
    target_dir = _legacy.get_demo_run_input_dir(run_id) / "commercial_catalogs"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{digest}-{safe_name}"
    target.write_bytes(content)
    return target


def evaluate_run_commercial_core(
    run_id: str,
    *,
    catalog_filename: str,
    catalog_content: bytes,
    default_currency: str | None = None,
    target_bid_amount: float | None = None,
) -> CommercialCoreResponse:
    if len(catalog_content) > _MAX_CATALOG_BYTES:
        raise HTTPException(status_code=413, detail="Commercial catalog exceeds the 12 MB limit")
    safe_name = _safe_catalog_name(catalog_filename)
    output_dir = _legacy.get_demo_run_output_dir(run_id)
    canonical_path = output_dir / "canonical_report.json"
    model = _load_json(canonical_path)
    result = build_commercial_core(
        model,
        catalog_filename=safe_name,
        catalog_content=catalog_content,
        default_currency=default_currency,
        target_bid_amount=target_bid_amount,
    )
    persisted_source = _persist_source(run_id, safe_name, catalog_content)
    payload = result.model_dump(mode="json")
    payload["catalog"]["stored_source"] = {
        "file_name": persisted_source.name,
        "sha256": result.catalog.source_sha256,
    }
    _write_json(output_dir / "commercial_core.json", payload)

    model["commercial_core"] = payload
    _write_json(canonical_path, model)

    report_path = output_dir / "report.json"
    if report_path.is_file():
        report = _load_json(report_path)
        report["commercial_core"] = build_customer_report_projection(model).get("commercial_core")
        _write_json(report_path, report)

    from src.modules.tender_operator_agent_demo.upload_service import (
        _render_customer_report_html,
    )

    (output_dir / "report.html").write_text(_render_customer_report_html(model), encoding="utf-8")
    return CommercialCoreResponse.model_validate(payload)


def get_run_commercial_core(run_id: str) -> CommercialCoreResponse:
    path = _legacy.get_demo_run_output_dir(run_id) / "commercial_core.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Commercial Core result is not available yet")
    return CommercialCoreResponse.model_validate(_load_json(path))
