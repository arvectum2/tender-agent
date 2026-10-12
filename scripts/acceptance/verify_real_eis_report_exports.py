"""Non-production original-document -> Tender Agent report/PDF/DOCX acceptance.

The caller supplies an independently attested original-byte receipt and private
file directory.  The script never fetches external data, writes to production,
or asserts bidder/legal approval.  It exercises the real in-process HTTP API.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from zipfile import ZipFile


def run(*, receipt_path: Path, source_dir: Path, procurement_id: str, output_path: Path, intake_mode: str) -> None:
    # Fail before reading originals if the consumer is not an explicitly local,
    # authenticated test API; never send private source files to remote services.
    base_url = os.environ.get("AI_CORP_RAG_DATA_PLATFORM_BASE_URL", "")
    key = os.environ.get("AI_CORP_RAG_DATA_PLATFORM_API_KEY", "")
    if urlsplit(base_url).hostname not in {"127.0.0.1", "localhost", "::1"} or not key:
        raise ValueError("An authenticated loopback Data Platform test endpoint is required")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    items = receipt["files"]
    if len(items) != 5 or len(procurement_id) != 19 or not procurement_id.isascii() or not procurement_id.isdigit():
        raise ValueError("Expected exactly five original files and a 19-digit EIS number")

    filenames = (
        "price_justification.xls",
        "contract_draft.doc",
        "technical_spec.docx",
        "application_requirements.docx",
        "control_notice.pdf",
    )
    original_bytes: list[bytes] = []
    for item in items:
        uid = str(item["uid"])
        if len(uid) != 32 or not uid.isalnum():
            raise ValueError("Invalid EIS attachment UID")
        raw = (source_dir / f"{uid}.bin").read_bytes()
        if hashlib.sha256(raw).hexdigest() != item["sha256"]:
            raise ValueError("Original EIS binary hash mismatch")
        original_bytes.append(raw)

    with tempfile.TemporaryDirectory(prefix="tdp-ta-original-e2e-") as directory:
        os.environ["AI_CORP_TENDER_OPERATOR_DEMO_RUNS_DIR"] = directory
        os.environ["AI_CORP_DATABASE_URL"] = f"sqlite:///{directory}/acceptance.sqlite3"
        os.environ["AI_CORP_PUBLIC_SEARCH_ENABLED"] = "false"
        os.environ["AI_CORP_LLM_PROVIDER"] = "stub"
        os.environ["AI_CORP_RAG_USE_LLM"] = "false"
        # Editable installations may point to a different checkout. Resolve the
        # API to this script's own repository, not the invoking venv's .pth.
        repository_root = Path(__file__).resolve().parents[2]
        sys.path.insert(0, str(repository_root))
        from fastapi.testclient import TestClient

        from src.main import app
        from src.modules.tender_operator_agent_demo import report_export_service

        assert Path(__import__("src.main", fromlist=["app"]).__file__).resolve().is_relative_to(repository_root)
        # Renderer bytes and safeguards remain unmodified; put test artifacts
        # under the same disposable root rather than the checkout data/demo/.
        default_export_dir = report_export_service._safe_output_dir
        report_export_service._safe_output_dir = lambda: default_export_dir(directory)

        with TestClient(app) as client:
            response = client.post(
                "/api/demo/tender-agent/runs",
                data={
                    "tender_title": f"Non-production EIS {procurement_id} source-locked acceptance",
                    "tender_category": "Услуги",
                    "customer_name": "Staging evidence only",
                },
                files=[
                    ("files", (name, raw, "application/octet-stream"))
                    for name, raw in zip(filenames, original_bytes, strict=True)
                ],
            )
            assert response.status_code == 200, ("create", response.status_code, response.text[:200])
            run_id = response.json()["run_id"]
            run_root = Path(directory) / run_id
            metadata_path = run_root / "metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            # Test-only binding: caller's receipt determines the number.  This is
            # not an assertion of an actual EIS SOAP ingest by the operator API.
            if intake_mode == "official":
                metadata["procurement_source"] = "zakupki_gov_ru_getdocs_ip"
                metadata["procurement_id"] = procurement_id
            metadata["mode"] = "procurement_search_intake"
            metadata_path.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")

            analyzed = client.post(f"/api/demo/tender-agent/runs/{run_id}/analyze")
            assert analyzed.status_code == 200, ("analyze", analyzed.status_code, analyzed.text[:200])
            report = client.get(f"/api/demo/tender-agent/runs/{run_id}/report")
            assert report.status_code == 200, ("report", report.status_code, report.text[:200])
            result = report.json()
            assert result.get("recommendation") == "manual_review_required", result.get("recommendation")

            statuses: dict[str, int] = {}
            sizes: dict[str, int] = {}
            for kind in ("docx", "pdf"):
                export = client.get(f"/api/demo/tender-agent/runs/{run_id}/export/{kind}")
                statuses[kind] = export.status_code
                expected_http = 409 if intake_mode == "official" else 200
                assert export.status_code == expected_http, ("export", kind, export.status_code, export.text[:200])
                if intake_mode == "official":
                    assert "АРХИВНОЕ ИЗВЕЩЕНИЕ ЕИС" in export.text
                    continue
                sizes[kind] = len(export.content)
                if kind == "docx":
                    import io
                    with ZipFile(io.BytesIO(export.content)) as docx:
                        assert docx.testzip() is None
                        assert "word/document.xml" in docx.namelist()
                else:
                    assert export.content.startswith(b"%PDF-")
                    assert b"%%EOF" in export.content[-2048:]

            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            mappings = [f.get("data_platform_source") for f in metadata.get("files", [])]
            assert len(mappings) == 5 and all(isinstance(p, dict) and p.get("resource_id") and p.get("document_id") for p in mappings), [(f.get("text_extraction_status"), f.get("extracted_text_available"), len(f.get("warnings") or [])) for f in metadata.get("files", [])]
            source_chunks = sum(int(p.get("source_chunk_count", 0)) for p in mappings)
            cited_chunks = sum(int(p.get("attributable_chunk_count", 0)) for p in mappings)
            assert source_chunks > 0 and cited_chunks == source_chunks
            summary = {
                "scope": "FRESH_OFFLINE_REAL_SOURCE_DP_HTTP_TO_TA_OPERATOR_EXPORT_NOT_PRODUCTION",
                "intake_mode": intake_mode,
                "procurement_id": procurement_id,
                "source_originals_sha256_verified": len(original_bytes),
                "operator_source_mappings": len(mappings),
                "source_chunks": source_chunks,
                "attributable_chunks": cited_chunks,
                "http_create": response.status_code,
                "http_analyze": analyzed.status_code,
                "http_report": report.status_code,
                "export_http": statuses,
                "export_byte_sizes": sizes,
                "final_recommendation": result["recommendation"],
                "owner_business_go": False,
                "independent_human_legal_gold": False,
                "separate_dp_postgres_staging_proved_by_this_script": False,
                "production_changed": False,
            }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("REAL_EIS_OPERATOR_EXPORT_ACCEPTANCE_PASS", json.dumps(summary, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--original-dir", type=Path, required=True)
    parser.add_argument("--procurement-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--intake-mode", choices=("official", "manual"), required=True)
    args = parser.parse_args()
    run(receipt_path=args.receipt, source_dir=args.original_dir, procurement_id=args.procurement_id, output_path=args.output, intake_mode=args.intake_mode)


if __name__ == "__main__":
    main()
