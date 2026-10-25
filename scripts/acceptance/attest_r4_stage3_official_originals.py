"""Source-only attest an immutable 8-case cross-vendor candidate set by EIS.

No legal clauses, training labels, tender-agent predictions or business action.
Every candidate is attempted in pre-registered order; no replacement by rank9.
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from scripts.acceptance.audit_r5_official_sources import audit_archive
from scripts.acceptance.build_r4_official_current_freshness import notice_attachments
from scripts.acceptance.select_r4_stage3_crossvendor_candidates import (
    select_stage3_candidates,
)
from src.modules.tender_operator_agent_demo.r4_official_original_acquisition import (
    retrieve_original_binary,
)
from src.modules.tender_operator_agent_demo.settings import ZakupkiSoapSettings
from src.modules.tender_operator_agent_demo.zakupki_soap_client import ZakupkiSoapClient

COMPETITIVE_44FZ = {"epNotificationEF2020", "epNotificationEZK2020", "epNotificationEOK2020"}


def verify_and_acquire(
    *, selected: dict,
    output_root: Path,
    client: ZakupkiSoapClient,
    expected_candidate_count: int = 8,
) -> dict:
    if selected.get("sut_inference_allowed") is not False or selected.get("official_eis_originals_verified") != 0:
        raise ValueError("Input must be immutable source-only discoveries")
    rows = selected.get("selected_discovery_only")
    if not isinstance(rows, list) or len(rows) != expected_candidate_count or not 1 <= expected_candidate_count <= 20:
        raise ValueError("Exactly the preregistered candidate count is required; no backfill")
    if output_root.exists() and any(output_root.iterdir()):
        raise ValueError("Do not overwrite previously retrieved original archive bytes")
    output_root.mkdir(parents=True, exist_ok=True)
    results = []
    for original in rows:
        number = original["registry_number"]
        case = {"registry_number": number, "status": "INCOMPLETE_OFFICIAL_SOURCE"}
        try:
            response = client.get_docs_by_reestr_number(number)
            if response.status != "completed" or len(response.archive_urls) != 1:
                raise ValueError("Official EIS did not provide precisely one archive")
            local_root = output_root / number
            client.download_archive(response.archive_urls[0], local_root)
            zip_file = local_root / "documentation-archive.zip"
            official = audit_archive(zip_file, number)
            if official["highest"]["notice_type"] not in COMPETITIVE_44FZ:
                raise ValueError("Official notice is not a listed competitive 44FZ type")
            attachments = notice_attachments(zip_file, number, official["highest"]["version"])
            if not 1 <= len(attachments) <= 60:
                raise ValueError("No finite official original binary list")
            acquired = []
            for uid, item in attachments.items():
                def fetch(url: str, size: int) -> bytes:
                    data, _ = client._http_get(
                        url, headers={"User-Agent": client.settings.user_agent},
                        timeout=40, max_bytes=size,
                    )
                    return data

                proof = retrieve_original_binary(
                    uid=uid, source_item=item,
                    source_root=local_root / "originals", fetch=fetch,
                )
                acquired.append({
                    "relative_path": str(Path(number) / "originals" / proof["relative_path"]),
                    "sha256": proof["sha256"],
                })
                print("STAGE3_FIRSTPARTY_SHA_VERIFIED", number, len(acquired),
                      "OF", len(attachments), flush=True)
            case = {
                "registry_number": number,
                "retrieval_provenance": "OFFICIAL_GETDOCSIP_TLS_VERIFIED",
                "status": "ALL_OFFICIAL_EIS_ORIGINALS_VERIFIED",
                "official_archive_relpath": str(Path(number) / "documentation-archive.zip"),
                "official_zip_sha256": official["zip_sha256"],
                "official_xml_sha256": official["highest"]["xml_sha256"],
                "documents": acquired,
                "original_count": len(acquired),
            }
        except (OSError, RuntimeError, ValueError) as exc:
            case["failure_type"] = type(exc).__name__
            print("STAGE3_SOURCE_UNATTESTED", number, type(exc).__name__, flush=True)
        results.append(case)
        (output_root / "source-only-attestation-checkpoint-private.json").write_text(
            json.dumps({
                "attempted_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
                "candidate_selection_intent_sha256": selected["source_intent_sha256"],
                "all_preselected_verified": len(results) == expected_candidate_count and all(
                    row["status"] == "ALL_OFFICIAL_EIS_ORIGINALS_VERIFIED" for row in results
                ),
                "cases": results,
                "model_ran": False,
                "human_gold_signed": 0,
            }, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        )
    print("STAGE3_ATTESTED_EIS_CASES",sum(x["status"]=="ALL_OFFICIAL_EIS_ORIGINALS_VERIFIED" for x in results),"OF",len(results))
    return {"cases":results}


def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--intent",type=Path,required=True)
    ap.add_argument("--source-capture-receipt",type=Path,required=True)
    ap.add_argument("--source-capture-root",type=Path,required=True)
    ap.add_argument("--development-audit",type=Path,required=True)
    ap.add_argument("--previous-blind-lock",type=Path,action="append",required=True)
    ap.add_argument("--selected-discovery-receipt",type=Path,required=True)
    ap.add_argument("--private-output-root",type=Path,required=True)
    args=ap.parse_args()
    intent=json.loads(args.intent.read_text())
    expected=select_stage3_candidates(
        intent=intent,
        original_capture_receipt=json.loads(args.source_capture_receipt.read_text()),
        private_capture_root=args.source_capture_root,
        development_audit=json.loads(args.development_audit.read_text()),
        previous_locks=[json.loads(p.read_text()) for p in args.previous_blind_lock],
    )
    actual=json.loads(args.selected_discovery_receipt.read_text())
    if expected != actual:
        raise ValueError("Selected source case order was tampered with")
    client=ZakupkiSoapClient(ZakupkiSoapSettings.from_env(),runtime_status_enabled=False)
    if not client.is_configured():
        raise ValueError("Read-only official getDocsIP not configured")
    verify_and_acquire(selected=actual,output_root=args.private_output_root,client=client)


if __name__=="__main__":
    main()
