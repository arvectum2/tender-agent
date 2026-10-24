"""Immutable tenant-scoped Market Intelligence report bundle store.

Only a trusted local operator may publish reviewed evaluation objects; no HTTP
upload/publish endpoint. Authenticated tenant principals are supplied by SaaS.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any

from .finance_and_export import export_account_csv, export_customer_html

_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{1,63}\Z")
_FORMATS = {"html": ("report.html", "text/html; charset=utf-8"),
            "csv": ("accounts.csv", "text/csv; charset=utf-8"),
            "json": ("evaluation.json", "application/json; charset=utf-8")}
_MAX_SOURCE_BYTES = 5 * 1024 * 1024
_MAX_REPORT_BYTES = 6 * 1024 * 1024


class ReportAccessError(ValueError):
    pass


def _identifier(value: str) -> str:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise ReportAccessError("invalid tenant or report identifier")
    return value


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class ReportBundleStore:
    """No cross-tenant sharing, absolute user-supplied paths or mutable reports."""

    def __init__(self, root: Path):
        self.root = Path(root).absolute()

    def _tenant_base(self, tenant_id: str) -> Path:
        return self.root / _identifier(tenant_id)

    def _bundle_dir(self, tenant_id: str, report_id: str) -> Path:
        return self._tenant_base(tenant_id) / _identifier(report_id)

    def publish(
        self, tenant_id: str, evaluation: dict[str, Any], *,
        report_id: str | None = None,
    ) -> dict[str, Any]:
        """Invoked only by trusted local reviewed-report publishing workflow."""
        tenant = _identifier(tenant_id)
        report = _identifier(report_id) if report_id is not None else uuid.uuid4().hex
        if evaluation.get("schema_version") != "mi003-power-quality-evaluation/0.1":
            raise ReportAccessError("unsupported pilot report schema")
        if (
            evaluation.get("verified_hardware_market_size_rub") is not None
            or evaluation.get("coverage", {}).get("full_market_census") is not False
            or evaluation.get("known_winning_epc")
            or evaluation.get("known_verified_designers")
        ):
            raise ReportAccessError("pilot cannot publish unverified total, winner or full census")
        source_bytes = json.dumps(evaluation, ensure_ascii=False).encode("utf-8")
        if len(source_bytes) > _MAX_SOURCE_BYTES:
            raise ReportAccessError("source evaluation exceeds maximum bytes")
        data = {
            "html": export_customer_html(evaluation).encode("utf-8"),
            "csv": export_account_csv(evaluation).encode("utf-8"),
            "json": json.dumps(evaluation, ensure_ascii=False, indent=2).encode("utf-8"),
        }
        if any(len(payload) > _MAX_REPORT_BYTES for payload in data.values()):
            raise ReportAccessError("bundle artifact exceeds maximum bytes")
        base = self._tenant_base(tenant)
        if base.is_symlink() or self.root.is_symlink():
            raise ReportAccessError("symlinked data directory is not allowed")
        base.mkdir(parents=True, exist_ok=True, mode=0o700)
        target = self._bundle_dir(tenant, report)
        if target.exists() or target.is_symlink():
            raise ReportAccessError("report ID already published, immutable")
        stage = Path(tempfile.mkdtemp(prefix=".staging-", dir=base))
        try:
            assets = {}
            for fmt, payload in data.items():
                filename = _FORMATS[fmt][0]
                file = stage / filename
                file.write_bytes(payload)
                os.chmod(file, 0o600)
                assets[fmt] = {"file": filename, "sha256": _sha(payload),
                               "bytes": len(payload)}
            manifest = {
                "schema_version": "mi005-tenant-report-bundle/0.1",
                "tenant_id": tenant, "report_id": report,
                "state": "source_limited_qualification_not_market_census",
                "market_size_rub": None,
                "assets": assets,
            }
            (stage / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            os.chmod(stage / "manifest.json", 0o600)
            os.chmod(stage, 0o700)
            # Creation is exclusive: never overwrite a published revision.
            stage.rename(target)
            return manifest
        finally:
            if stage.exists():
                shutil.rmtree(stage)

    def _manifest(self, tenant_id: str, report_id: str) -> dict[str, Any]:
        bundle = self._bundle_dir(tenant_id, report_id)
        if bundle.is_symlink() or not bundle.is_dir():
            raise ReportAccessError("report not found")
        file = bundle / "manifest.json"
        if file.is_symlink() or not file.is_file() or file.stat().st_size > 64 * 1024:
            raise ReportAccessError("report manifest absent or unsafe")
        try:
            meta = json.loads(file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeError) as exc:
            raise ReportAccessError("corrupt report manifest") from exc
        if (
            not isinstance(meta, dict)
            or meta.get("schema_version") != "mi005-tenant-report-bundle/0.1"
            or meta.get("tenant_id") != tenant_id
            or meta.get("report_id") != report_id
            or meta.get("market_size_rub") is not None
        ):
            raise ReportAccessError("report tenant or version mismatch")
        if not isinstance(meta.get("assets"), dict):
            raise ReportAccessError("report assets manifest invalid")
        return meta

    def list_reports(self, tenant_id: str) -> list[dict[str, Any]]:
        base = self._tenant_base(tenant_id)
        if base.is_symlink() or not base.exists():
            return []
        results = []
        for path in sorted(base.iterdir()):
            if path.is_symlink() or not path.is_dir():
                continue
            try:
                meta = self._manifest(tenant_id, path.name)
            except ReportAccessError:
                continue
            results.append({
                "report_id": meta["report_id"], "state": meta["state"],
                "available_formats": sorted(meta["assets"]),
                "market_size_rub": None,
            })
        return results

    def read(self, tenant_id: str, report_id: str, fmt: str) -> tuple[bytes, str]:
        _identifier(tenant_id)
        _identifier(report_id)
        if fmt not in _FORMATS:
            raise ReportAccessError("unsupported report format")
        manifest = self._manifest(tenant_id, report_id)
        path = self._bundle_dir(tenant_id, report_id) / _FORMATS[fmt][0]
        asset = manifest.get("assets", {}).get(fmt)
        if (
            path.is_symlink() or not path.is_file()
            or not isinstance(asset, dict)
            or asset.get("file") != path.name
            or not isinstance(asset.get("bytes"), int)
            or not 0 <= asset["bytes"] <= _MAX_REPORT_BYTES
            or path.stat().st_size != asset["bytes"]
        ):
            raise ReportAccessError("report artifact not available")
        content = path.read_bytes()
        if _sha(content) != asset.get("sha256"):
            raise ReportAccessError("report content checksum mismatch")
        return content, _FORMATS[fmt][1]
