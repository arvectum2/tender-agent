"""Blind, source-only evaluator packs from pre-locked official EIS binaries.

Does not include tender-agent predictions, generated labels or source text
selected by a model. Reuses existing benchmark_pipeline 1.1.0 workflow.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.acceptance.audit_r5_official_sources import audit_archive
from scripts.acceptance.build_r4_official_current_freshness import notice_attachments
from src.modules.benchmark_pipeline.contract import (
    source_bundle_sha256,
    validate_case_manifest_consistency,
    verify_manifest_source_files,
    write_artifact,
)
from src.modules.benchmark_pipeline.workflow import prepare_evaluator_bundle
from src.modules.tender_operator_agent_demo.r4_semantic_holdout import (
    verify_cohort_lock,
)

ROUTES_BY_KIND = {
    "epNotificationEF2020": "ea20",
    "epNotificationEZK2020": "zk20",
    "epNotificationEOK2020": "ok20",
}


def prepare_blind_bundles(
    lock: dict, candidates: list[dict], source_root: Path,
    *, acquired_at: str,
) -> list[tuple[dict, dict]]:
    verify_cohort_lock(lock)
    source_rows = {v["registry_number"]: v for v in candidates}
    if len(source_rows) != len(candidates) or set(source_rows) != {
        case["registry_number"] for case in lock["cases"]
    }:
        raise ValueError("Official source receipt differs from preregistered cohort")
    output = []
    for item in lock["cases"]:
        number = item["registry_number"]
        original = source_rows[number]
        official_path = source_root / original["official_archive_relpath"]
        source_info = audit_archive(official_path, number)
        if (
            source_info["zip_sha256"] != item["official_zip_sha256"]
            or source_info["highest"]["xml_sha256"] != item["official_xml_sha256"]
        ):
            raise ValueError("Blind source ZIP changed after preregistration")
        if source_info["highest"]["notice_type"] not in ROUTES_BY_KIND:
            raise ValueError("Noncompetitive procedure in blind source")
        attachments = notice_attachments(
            official_path, number, source_info["highest"]["version"]
        )
        expected_shas = set(item["original_attachment_sha256"])
        docs = []
        for source in original["documents"]:
            relative = source["relative_path"]
            binary_sha = source["sha256"]
            filename = Path(relative).name
            matches = [
                row for uid, row in attachments.items()
                if filename.startswith(uid + ".") and (
                    "." + filename.rsplit(".", 1)[-1].lower()
                ) == Path(row["fileName"]).suffix.lower()
            ]
            if len(matches) != 1:
                raise ValueError("Original source UID/filename missing in XML")
            row = matches[0]
            docs.append({
                "path": relative,
                "sha256": binary_sha,
                "source_url": row["url"],
            })
        if {v["sha256"] for v in docs} != expected_shas:
            raise ValueError("Original binary evidence differs from immutable blind lock")
        route = ROUTES_BY_KIND[source_info["highest"]["notice_type"]]
        notice_url = (
            f"https://zakupki.gov.ru/epz/order/notice/{route}/view/"
            f"common-info.html?regNumber={number}"
        )
        manifest = {
            "schema_version": "1.1.0",
            "case_id": f"R4-BLIND-{number}",
            "procurement": {"notice_number": number},
            "source_urls": [notice_url],
            "acquired_at": acquired_at,
            "documents": sorted(docs, key=lambda x: x["path"]),
            "source_scope": (
                "Independently locked official getDocsIP notice and raw attached "
                "originals; legal interpretation not yet authored"
            ),
            "source_bundle_sha256": source_bundle_sha256(docs),
            "source_conflict": False,
            "provenance_sufficient": True,
        }
        validate_case_manifest_consistency(manifest)
        verify_manifest_source_files(manifest, source_root)
        bundle = prepare_evaluator_bundle(manifest, prepared_at=acquired_at)
        output.append((manifest, bundle))
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    lock = json.loads(args.lock.read_text())
    candidates = json.loads(args.candidates.read_text())
    packs = prepare_blind_bundles(
        lock, candidates, args.source_root, acquired_at=lock["locked_at_utc"]
    )
    for manifest, bundle in packs:
        output = args.output_dir / manifest["case_id"]
        write_artifact(output / "case_manifest.json", manifest, "case_manifest")
        write_artifact(output / "evaluator_bundle.json", bundle, "evaluator_bundle")
    print("BLIND_EVALUATOR_PACKS_PREPARED", len(packs), "GOLD_ISSUED", 0)


if __name__ == "__main__":
    main()
