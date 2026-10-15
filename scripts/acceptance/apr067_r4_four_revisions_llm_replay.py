"""Isolated real-EIS saved-run operator E2E, invoking the actual localhost LLM.

Copy an earlier first-party read-only EIS run to a dedicated staging runs dir
before execution. Never point this script at live production data or existing
operator-run storage; it writes to the supplied private staging directory.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import time
from pathlib import Path
from secrets import token_urlsafe


def verify_copy_source(saved: Path, pinned: dict) -> int:
    """Fail closed on a tampered original, duplicated ID or unsafe archive path."""
    if pinned.get("run_id") != saved.name or pinned.get("registry_number") != "0162200011826003089":
        raise ValueError("the pinned R4 historical case identity does not match")
    rows = pinned.get("all_input_sha256")
    if not isinstance(rows, list) or len(rows) != 17 or pinned.get("archive_xml_originals") != 12:
        raise ValueError("the exact 17-source original inventory was not retained")
    input_dir = (saved / "input").resolve()
    checked = set()
    for item in rows:
        if not isinstance(item, dict):
            raise TypeError("malformed saved official original")
        file_id, stored, expected = item.get("file_id"), item.get("stored_name"), item.get("sha256")
        if (not isinstance(file_id, str) or file_id in checked
                or not isinstance(stored, str) or not isinstance(expected, str)
                or len(expected) != 64):
            raise ValueError("duplicate/unbound original")
        checked.add(file_id)
        path = input_dir / stored
        if (path.is_symlink() or not path.resolve().is_relative_to(input_dir)
                or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected):
            raise ValueError("official original has changed")
    archive = input_dir / "documentation-archive.zip"
    if (archive.is_symlink() or not archive.is_file()
            or hashlib.sha256(archive.read_bytes()).hexdigest() != pinned.get("archived_eis_zip_sha256")):
        raise ValueError("original official source ZIP differs from the pinned archived copy")
    return len(checked)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    root = args.stage.resolve()
    runs = root / "runs"
    saved = runs / args.run_id
    if not (saved / "metadata.json").is_file() or root.name != "ta-apr067-r4-four-revisions-20261015":
        parser.error("Only the designated isolated historical R4 case copy is allowed")
    meta = json.loads((saved / "metadata.json").read_text())
    if (meta.get("mode") != "procurement_search_intake"
            or len(meta.get("files", [])) != 17
            or meta.get("procurement_id") != "0162200011826003089"):
        parser.error("Expected seventeen firstparty official archived EIS original documents")
    pinned = json.loads((root / "output/offline_archived_source_receipt.json").read_text())
    try:
        verify_copy_source(saved, pinned)
    except (TypeError, ValueError) as exc:
        parser.error(str(exc))
    password = token_urlsafe(32)
    db = root / "e2e-only-llm.sqlite"
    os.environ.update({
        "AI_CORP_TENDER_OPERATOR_DEMO_RUNS_DIR": str(runs),
        "AI_CORP_DATABASE_URL": "sqlite:///" + str(db),
        "AI_CORP_LLM_PROVIDER": "openai_compatible",
        "AI_CORP_OPENAI_API_KEY": "local-e2e-no-external-key",
        "AI_CORP_OPENAI_BASE_URL": "http://127.0.0.1:8081/v1",
        "AI_CORP_LLM_MODEL": "arvectum-gemma4-12b-it-qat-q4_0",
        "AI_CORP_LOCAL_LLM_BASE_URL": "http://127.0.0.1:8081/v1",
        "AI_CORP_RAG_DATA_PLATFORM_BASE_URL": "http://127.0.0.1:18095",
        "AI_CORP_RAG_DATA_PLATFORM_TIMEOUT_SECONDS": "90",
        "AI_CORP_LLM_TIMEOUT_SECONDS": "240",
        "AI_CORP_LLM_MAX_RETRIES": "1",
        "AI_CORP_LLM_STORE_RAW_RESPONSE": "false",
        "AI_CORP_YANDEX_SEARCH_API_KEY": "",
        "AI_CORP_YANDEX_SEARCH_FOLDER_ID": "",
        "AI_CORP_PILOT_AUTH_ENABLED": "true",
        "AI_CORP_PILOT_AUTH_USERNAME": "e2e-operator",
        "AI_CORP_PILOT_AUTH_PASSWORD": password,
    })
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from src.modules.tender_operator_agent_demo import router as operator_router
    from src.shared.api.middleware import TenderPilotBasicAuthMiddleware
    from src.shared.config.settings import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    assert settings.llm_provider == "openai_compatible"
    assert settings.openai_base_url == "http://127.0.0.1:8081/v1"

    app = FastAPI()
    app.include_router(operator_router.router)
    app.add_middleware(
        TenderPilotBasicAuthMiddleware,
        username="e2e-operator",
        password=password,
        protected=("/pilot/tender-agent", "/api/demo/tender-agent"),
        public=("/health",),
    )
    prefix = "/api/demo/tender-agent/runs/" + args.run_id
    auth = "Basic " + base64.b64encode(("e2e-operator:" + password).encode()).decode()
    checked = {}
    with TestClient(app) as client:
        for path in ("/pilot/tender-agent/workspace", prefix + "/report",
                     f"/api/demo/tender-agent/workspace/runs/{args.run_id}/evidence"):
            resp = client.get(path)
            checked["unauth_" + path.split("/")[-1]] = resp.status_code
        ui = client.get("/pilot/tender-agent/workspace", headers={"Authorization": auth})
        checked["authenticated_workspace"] = ui.status_code
        run_before = client.get(prefix, headers={"Authorization": auth})
        checked["saved_run_reopened_before"] = run_before.status_code
        print("ISOLATED_START",args.run_id,"files",len(meta["files"]),"ui",ui.status_code,flush=True)
        start = time.monotonic()
        try:
            result = client.post(prefix + "/analyze", headers={"Authorization": auth})
            checked["analysis_http"] = result.status_code
            if result.status_code == 200:
                analysis = result.json()
                checked["analysis_mode"] = analysis.get("analysis_mode")
                checked["analysis_status"] = analysis.get("status")
            else:
                checked["analysis_error_kind"] = "HTTP_"+str(result.status_code)
        except Exception as exc:  # noqa: BLE001 - log only exception class
            checked["analysis_error_kind"] = type(exc).__name__
            checked["analysis_http"] = 0
        checked["analysis_elapsed_seconds"] = round(time.monotonic()-start,2)
        print("MODEL_ANALYSIS_FINISHED",checked["analysis_http"],checked.get("analysis_mode"),
              "duration",checked["analysis_elapsed_seconds"],flush=True)
        for name,path in {
            "reopen":prefix, "steps":prefix+"/steps",
            "report_json":prefix+"/report",
            "source_evidence":f"/api/demo/tender-agent/workspace/runs/{args.run_id}/evidence",
            "history":"/api/demo/tender-agent/runs",
            "read_only_registry":"/api/demo/tender-agent/workspace/registry",
            "pdf_export":prefix+"/export/pdf", "docx_export":prefix+"/export/docx"
        }.items():
            try:
                resp = client.get(path, headers={"Authorization":auth})
                checked[name+"_http"] = resp.status_code
                if resp.status_code==200 and name=="report_json":
                    obj=resp.json()
                    checked["report_keys"]=sorted(obj) if isinstance(obj,dict) else []
                if resp.status_code==200 and name=="source_evidence":
                    obj=resp.json()
                    checked["source_evidence_keys"]=sorted(obj) if isinstance(obj,dict) else []
            except Exception as exc:  # noqa: BLE001 - log only exception class
                checked[name+"_error_kind"]=type(exc).__name__
        savedmeta=json.loads((saved/"metadata.json").read_text())
        checked["persisted_analysis_mode"]=savedmeta.get("analysis_mode")
        checked["persisted_llm_invoked"]=savedmeta.get("ai_runtime_provenance",{}).get("llm_invoked")
        checked["persisted_status"]=savedmeta.get("status")
        checked["original_file_sha_preserved"] = all(
            hashlib.sha256((saved / "input" / source["stored_name"]).read_bytes()).hexdigest()
            == source["sha256"] for source in pinned["all_input_sha256"]
        )
        checked["official_zip_sha_preserved"] = (
            hashlib.sha256((saved / "input/documentation-archive.zip").read_bytes()).hexdigest()
            == pinned["archived_eis_zip_sha256"]
        )
        checked["registry_number"] = savedmeta.get("procurement_id")
        checked["source_warning_count"] = len(savedmeta.get("warnings", []))
        checked["extracted_original_count"] = sum(
            1 for item in savedmeta.get("files", []) if item.get("extracted_text_available") is True
        )
        checked["failed_original_count"] = sum(
            1 for item in savedmeta.get("files", []) if item.get("text_extraction_status") != "extracted"
        )
        checked["file_extraction_statuses"] = [item.get("text_extraction_status") for item in savedmeta.get("files", [])]
        checked["warning_count"] = len(savedmeta.get("warnings", []))
        report=saved/"output"/"report.html"
        if report.exists():
            checked["report_sha256"]=hashlib.sha256(report.read_bytes()).hexdigest()
        for file in (saved/"output").glob("*.json"):
            if file.name in {"requirements.json","trace.json"}:
                document=json.loads(file.read_text())
                checked[file.stem+"_top_level_keys"]=sorted(document) if isinstance(document,dict) else []
        events=(saved/"events.jsonl")
        if events.is_file():
            event_types=[]
            for line in events.read_text().splitlines():
                try: event_types.append(json.loads(line).get("event_type"))
                except ValueError: pass
            checked["events_last_8"]=event_types[-8:]
    output=root/"output"/"apr067_r4_four_version_replay.json"
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(checked,ensure_ascii=False,indent=2,sort_keys=True)+"\n")
    print("E2E_RECEIPT",output,flush=True)
    return 0 if (checked.get("analysis_http")==200
                 and checked.get("persisted_analysis_mode")=="llm_tender_operator_provider"
                 and checked.get("persisted_llm_invoked") is True
                 and checked.get("extracted_original_count") == 17
                 and checked.get("failed_original_count") == 0
                 and checked.get("original_file_sha_preserved") is True
                 and checked.get("official_zip_sha_preserved") is True
                 and checked.get("pdf_export_http") == 409
                 and checked.get("docx_export_http") == 409) else 1


if __name__ == "__main__":
    raise SystemExit(main())
