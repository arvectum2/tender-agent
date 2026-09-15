#!/usr/bin/env python3
"""DISCOVERY-QA-001 governed 44-FZ ranking benchmark.

The workflow is deliberately split into four commands so blind labels can be
created and frozen before the production relevance scorer is ever run:

  acquire -> independent evaluator -> freeze -> run-sut -> compare

`run-sut` never reads blind label files. `compare` is the first stage that sees
both frozen labels and SUT output.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import time
import zipfile
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from src.modules.benchmark_pipeline.calibration import (
    DISCOVERY_CONTEXT_KEY,
    bind_discovery_context,
    build_discovery_context,
    discovery_context_sha256,
)
from src.modules.benchmark_pipeline.contract import (
    CONTRACT_VERSION,
    canonical_sha256,
    file_sha256,
    load_artifact,
    source_bundle_sha256,
    write_artifact,
)
from src.modules.benchmark_pipeline.workflow import (
    freeze_blind_labels,
    prepare_evaluator_bundle,
    verify_frozen_labels,
)
from src.modules.discovery_quality.benchmark import (
    aggregate_discovery_metrics,
    evaluate_query_ranking,
)
from src.modules.tender_operator_agent_demo.relevance_scoring import (
    score_procurement_card,
)
from src.modules.tender_operator_agent_demo.supplier_profile import SupplierProfile
from src.tender_research.providers.public_44fz_search import (
    Public44FzSearchProvider,
    PublicSearchStatus,
)

CORPUS_VERSION = "1"
DEFAULT_CANDIDATES_PER_QUERY = 15
ALLOWED_LABELS = {"RELEVANT", "PARTIALLY_RELEVANT", "IRRELEVANT", "UNCLEAR"}


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp must include timezone: {value}")
    return parsed


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^0-9a-zа-яё]+", "-", value.lower(), flags=re.IGNORECASE).strip("-")
    return cleaned[:48] or "query"


def _git_head() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else "unknown"


def _load_query_plan(path: Path) -> dict[str, Any]:
    plan = _read_json(path)
    if not isinstance(plan, dict):
        raise TypeError("query plan must be an object")
    queries = plan.get("queries")
    if not isinstance(queries, list) or not 1 <= len(queries) <= 10:
        raise ValueError("query plan must contain 1..10 queries")
    normalized = [str(item).strip() for item in queries]
    if any(len(item) < 2 for item in normalized) or len(normalized) != len(set(normalized)):
        raise ValueError("query plan queries must be unique non-empty strings")
    plan["queries"] = normalized
    return plan


def _search_item_snapshot(item: Any, *, query: str, source_rank: int, detail: Any) -> dict[str, Any]:
    detail_payload: dict[str, Any] | None = None
    if detail is not None:
        detail_payload = {
            "registry_number": detail.registry_number,
            "title": detail.title,
            "customer_name": detail.customer_name,
            "customer_inn": detail.customer_inn,
            "customer_kpp": detail.customer_kpp,
            "publication_date": _jsonable(detail.publication_date),
            "application_deadline": _jsonable(detail.application_deadline),
            "nmck_amount": _jsonable(detail.nmck_amount),
            "law_type": detail.law_type,
            "card_url": detail.card_url,
            "source_url": detail.source_url,
            "network_status": detail.network_status,
            "error_message": detail.error_message,
            "documents_url": (detail.raw or {}).get("documents_url"),
            "document_links": [
                {
                    "title": link.title,
                    "file_name": link.file_name,
                    "url": link.url,
                    "content_type": link.content_type,
                    "size_bytes": link.size_bytes,
                    "size_text": link.size_text,
                }
                for link in detail.document_links
            ],
        }
    return {
        "source": "public_eis_html_44fz",
        "law": "44-FZ",
        "query": query,
        "source_rank": source_rank,
        "registry_number": item.registry_number,
        "purchase_number": item.purchase_number,
        "title": item.title,
        "customer_name": item.customer_name,
        "customer_inn": item.customer_inn,
        "customer_kpp": item.customer_kpp,
        "publication_date": _jsonable(item.publication_date),
        "application_deadline": _jsonable(item.application_deadline),
        "initial_price": _jsonable(item.nmck_amount),
        "source_url": item.source_url,
        "card_url": item.card_url,
        "raw_status": (item.raw or {}).get("status"),
        "raw": _jsonable(item.raw or {}),
        "detail": detail_payload,
    }


def _document_ref(path: Path, *, case_dir: Path, source_url: str) -> dict[str, str]:
    return {
        "path": path.relative_to(case_dir).as_posix(),
        "sha256": file_sha256(path),
        "source_url": source_url,
    }


def _unique_urls(values: list[str | None]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = str(raw or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _evaluator_instructions() -> str:
    return """# DISCOVERY-QA-001 independent evaluator instructions

Use only files in this evaluator bundle. Do not inspect Tender Agent code, prompts,
weights, scores, SUT output, previous benchmark labels, network or web sources.

For every case in `cohort_evaluator_index.json`, judge whether the procurement is
relevant to the frozen supplier profile and query context in that case's
`evaluator_bundle.json`.

Allowed labels:
- `RELEVANT`: clear fit for the supplier's goods/capabilities.
- `PARTIALLY_RELEVANT`: meaningful fit exists, but the procurement is mixed,
  peripheral, or material scope uncertainty remains.
- `IRRELEVANT`: source evidence shows the procurement is outside supplier scope.
- `UNCLEAR`: bundled public-source evidence is insufficient to decide safely.

Every non-UNCLEAR label must cite at least one evidence `source_ref` exactly equal
to a path listed in that case's evaluator bundle documents, normally
`source/card.json`, `source/common_info.html`, or `source/documents.html`.
Do not infer missing facts. Keep quotes short. Return one label per case.
"""


def acquire(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise SystemExit(f"output directory must be new/empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    profile_path = Path(args.supplier_profile).resolve()
    query_plan_path = Path(args.query_plan).resolve()
    profile_payload = _read_json(profile_path)
    profile = SupplierProfile(**profile_payload)
    plan = _load_query_plan(query_plan_path)
    date_from = date.fromisoformat(args.date_from)
    date_to = date.fromisoformat(args.date_to)
    if date_from > date_to:
        raise SystemExit("date_from must not be after date_to")
    candidates_per_query = int(args.candidates_per_query)
    if not 10 <= candidates_per_query <= 30:
        raise SystemExit("candidates_per_query must be between 10 and 30")

    acquired_at = _utcnow()
    provider = Public44FzSearchProvider(timeout_seconds=args.timeout, delay_seconds=args.page_delay)
    case_records: list[dict[str, Any]] = []
    query_records: list[dict[str, Any]] = []

    shutil.copy2(profile_path, output_dir / "supplier_profile.json")
    shutil.copy2(query_plan_path, output_dir / "query_plan.json")

    for query_index, query in enumerate(plan["queries"], start=1):
        pages = provider.search_pages(
            query=query,
            date_from=date_from,
            date_to=date_to,
            max_pages=args.max_pages,
            page_size=max(candidates_per_query, 15),
            law_type="44fz",
        )
        candidates: list[Any] = []
        seen_registry: set[str] = set()
        search_urls: list[str] = []
        for page in pages:
            if page.source_url:
                search_urls.append(page.source_url)
            if page.status not in {PublicSearchStatus.SUCCESS, PublicSearchStatus.EMPTY}:
                raise SystemExit(f"EIS search failed for {query!r}: {page.status}: {page.error}")
            for item in page.items:
                registry = str(item.registry_number or "").strip()
                if not registry or registry in seen_registry:
                    continue
                seen_registry.add(registry)
                candidates.append(item)
                if len(candidates) >= candidates_per_query:
                    break
            if len(candidates) >= candidates_per_query:
                break
        if len(candidates) < candidates_per_query:
            raise SystemExit(
                f"query {query!r} produced only {len(candidates)} unique candidates; "
                f"need {candidates_per_query}"
            )

        query_case_ids: list[str] = []
        for source_rank, item in enumerate(candidates[:candidates_per_query], start=1):
            registry = str(item.registry_number or "").strip()
            case_id = f"dq1-q{query_index:02d}-r{source_rank:02d}-{registry}"
            case_dir = output_dir / "cases" / case_id
            source_dir = case_dir / "source"
            source_dir.mkdir(parents=True, exist_ok=False)

            detail = provider.fetch_detail(item)
            snapshot = _search_item_snapshot(item, query=query, source_rank=source_rank, detail=detail)
            card_path = source_dir / "card.json"
            _write_json(card_path, snapshot)

            documents: list[dict[str, str]] = [
                _document_ref(card_path, case_dir=case_dir, source_url=item.card_url or item.source_url)
            ]
            if detail.common_info_html:
                common_path = source_dir / "common_info.html"
                common_path.write_text(detail.common_info_html, encoding="utf-8")
                documents.append(
                    _document_ref(
                        common_path,
                        case_dir=case_dir,
                        source_url=detail.card_url or item.card_url or item.source_url,
                    )
                )
            documents_url = (detail.raw or {}).get("documents_url")
            if detail.documents_html and documents_url:
                docs_path = source_dir / "documents.html"
                docs_path.write_text(detail.documents_html, encoding="utf-8")
                documents.append(
                    _document_ref(docs_path, case_dir=case_dir, source_url=documents_url)
                )

            source_urls = _unique_urls(
                [item.source_url, item.card_url, detail.source_url, detail.card_url, documents_url]
            )
            manifest = {
                "schema_version": CONTRACT_VERSION,
                "case_id": case_id,
                "procurement": {
                    "registry_number": registry,
                    "query": query,
                    "source_rank": source_rank,
                },
                "source_urls": source_urls,
                "acquired_at": acquired_at,
                "documents": documents,
                "source_scope": "Public EIS 44-FZ search card plus available common-info/documents index pages; read-only acquisition.",
                "source_bundle_sha256": source_bundle_sha256(documents),
                "source_conflict": False,
                "provenance_sufficient": bool(item.card_url and item.title),
            }
            context = build_discovery_context(
                supplier_profile=profile.model_dump(mode="json"),
                registry_number=registry,
                source="public_eis_html_44fz",
                law="44-FZ",
                as_of=acquired_at,
                query=query,
                selection_mode="SEARCH_RESULT",
            )
            manifest = bind_discovery_context(manifest, context)
            write_artifact(case_dir / "case_manifest.json", manifest, "case_manifest")
            evaluator_bundle = prepare_evaluator_bundle(manifest, prepared_at=_utcnow())
            write_artifact(case_dir / "evaluator_bundle.json", evaluator_bundle, "evaluator_bundle")

            record = {
                "case_id": case_id,
                "query": query,
                "query_index": query_index,
                "source_rank": source_rank,
                "registry_number": registry,
                "case_dir": f"cases/{case_id}",
                "case_manifest_sha256": canonical_sha256(manifest),
                "evaluator_bundle_sha256": canonical_sha256(evaluator_bundle),
                "source_bundle_sha256": manifest["source_bundle_sha256"],
                "discovery_context_sha256": discovery_context_sha256(manifest),
            }
            case_records.append(record)
            query_case_ids.append(case_id)
            if args.detail_delay:
                time.sleep(args.detail_delay)

        query_records.append({"query": query, "query_index": query_index, "case_ids": query_case_ids})

    cohort_manifest = {
        "corpus_version": CORPUS_VERSION,
        "cohort_id": args.cohort_id,
        "acquired_at": acquired_at,
        "repository_head_at_acquisition": _git_head(),
        "law": "44-FZ",
        "source": "public_eis_html_44fz",
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "candidates_per_query": candidates_per_query,
        "supplier_profile_sha256": file_sha256(output_dir / "supplier_profile.json"),
        "query_plan_sha256": file_sha256(output_dir / "query_plan.json"),
        "queries": query_records,
        "cases": case_records,
    }
    _write_json(output_dir / "cohort_manifest.json", cohort_manifest)
    evaluator_index = {
        "corpus_version": CORPUS_VERSION,
        "cohort_id": args.cohort_id,
        "supplier_profile_sha256": cohort_manifest["supplier_profile_sha256"],
        "query_plan_sha256": cohort_manifest["query_plan_sha256"],
        "cases": [
            {
                "case_id": record["case_id"],
                "query": record["query"],
                "source_rank": record["source_rank"],
                "registry_number": record["registry_number"],
                "evaluator_bundle": f"cases/{record['case_id']}/evaluator_bundle.json",
            }
            for record in case_records
        ],
    }
    _write_json(output_dir / "cohort_evaluator_index.json", evaluator_index)
    (output_dir / "EVALUATOR_INSTRUCTIONS.md").write_text(_evaluator_instructions(), encoding="utf-8")

    zip_path = output_dir / f"{args.cohort_id}-blind-evaluator-input.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for root_file in (
            "supplier_profile.json",
            "query_plan.json",
            "cohort_evaluator_index.json",
            "EVALUATOR_INSTRUCTIONS.md",
        ):
            archive.write(output_dir / root_file, root_file)
        for record in case_records:
            case_dir = output_dir / record["case_dir"]
            archive.write(
                case_dir / "evaluator_bundle.json",
                f"{record['case_dir']}/evaluator_bundle.json",
            )
            for source_path in sorted((case_dir / "source").iterdir()):
                archive.write(source_path, f"{record['case_dir']}/source/{source_path.name}")

    result = {
        "status": "DISCOVERY_QA_PHASE_A_COMPLETE",
        "cohort_id": args.cohort_id,
        "case_count": len(case_records),
        "query_count": len(query_records),
        "cohort_manifest": str(output_dir / "cohort_manifest.json"),
        "cohort_manifest_sha256": file_sha256(output_dir / "cohort_manifest.json"),
        "evaluator_zip": str(zip_path),
        "evaluator_zip_sha256": file_sha256(zip_path),
        "query_plan_sha256": cohort_manifest["query_plan_sha256"],
        "supplier_profile_sha256": cohort_manifest["supplier_profile_sha256"],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def freeze(args: argparse.Namespace) -> None:
    cohort_dir = Path(args.cohort_dir).resolve()
    cohort = _read_json(cohort_dir / "cohort_manifest.json")
    labels_payload = _read_json(Path(args.labels).resolve())
    evaluator = str(labels_payload.get("evaluator") or "").strip()
    evaluated_at = str(labels_payload.get("evaluated_at") or "").strip()
    if not evaluator or not evaluated_at:
        raise SystemExit("labels payload requires evaluator and evaluated_at")
    _parse_time(evaluated_at)
    rows = labels_payload.get("labels")
    if not isinstance(rows, list):
        raise SystemExit("labels payload requires a labels array")
    labels_by_case = {row.get("case_id"): row for row in rows if isinstance(row, dict)}
    expected_ids = {record["case_id"] for record in cohort["cases"]}
    if set(labels_by_case) != expected_ids:
        missing = sorted(expected_ids - set(labels_by_case))
        extra = sorted(set(labels_by_case) - expected_ids)
        raise SystemExit(f"label case set mismatch; missing={missing}, extra={extra}")

    frozen_at = _utcnow()
    freeze_index: list[dict[str, Any]] = []
    for record in cohort["cases"]:
        case_id = record["case_id"]
        case_dir = cohort_dir / record["case_dir"]
        evaluator_bundle = load_artifact(case_dir / "evaluator_bundle.json", "evaluator_bundle")
        row = labels_by_case[case_id]
        label = str(row.get("label") or "")
        if label not in ALLOWED_LABELS:
            raise SystemExit(f"invalid label for {case_id}: {label}")
        evidence = row.get("evidence") or []
        if not isinstance(evidence, list):
            raise SystemExit(f"evidence must be an array for {case_id}")
        discovery_label = {
            "schema_version": CONTRACT_VERSION,
            "case_id": case_id,
            "source_bundle_sha256": evaluator_bundle["source_bundle_sha256"],
            "label": label,
            "reason": str(row.get("reason") or "").strip(),
            "confidence": float(row.get("confidence")),
            "evidence": evidence,
            "evaluator": evaluator,
            "evaluated_at": evaluated_at,
        }
        document_truth = {
            "schema_version": CONTRACT_VERSION,
            "case_id": case_id,
            "source_bundle_sha256": evaluator_bundle["source_bundle_sha256"],
            "facts": [],
            "confidence": 1.0,
            "evaluator": f"{evaluator}:discovery-only-empty-document-truth",
            "evaluated_at": evaluated_at,
        }
        receipt = freeze_blind_labels(
            evaluator_bundle,
            discovery_label,
            document_truth,
            frozen_at=frozen_at,
        )
        write_artifact(case_dir / "blind_discovery_label.json", discovery_label, "blind_discovery_label")
        write_artifact(case_dir / "blind_document_truth.json", document_truth, "blind_document_truth")
        write_artifact(case_dir / "frozen_label.json", receipt, "frozen_label")
        freeze_index.append(
            {
                "case_id": case_id,
                "label_set_sha256": receipt["label_set_sha256"],
                "frozen_at": receipt["frozen_at"],
            }
        )

    freeze_manifest = {
        "corpus_version": CORPUS_VERSION,
        "cohort_id": cohort["cohort_id"],
        "frozen_at": frozen_at,
        "evaluator": evaluator,
        "labels_payload_sha256": file_sha256(Path(args.labels).resolve()),
        "cases": freeze_index,
    }
    _write_json(cohort_dir / "cohort_freeze.json", freeze_manifest)
    print(
        json.dumps(
            {
                "status": "DISCOVERY_QA_LABELS_FROZEN",
                "case_count": len(freeze_index),
                "cohort_freeze_sha256": file_sha256(cohort_dir / "cohort_freeze.json"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def run_sut(args: argparse.Namespace) -> None:
    cohort_dir = Path(args.cohort_dir).resolve()
    cohort = _read_json(cohort_dir / "cohort_manifest.json")
    if not (cohort_dir / "cohort_freeze.json").is_file():
        raise SystemExit("cohort labels are not frozen; run freeze before run-sut")
    produced_at = _utcnow()
    runtime_version = args.runtime_version or f"relevance_scoring@{_git_head()}"
    sut_cases: list[dict[str, Any]] = []

    for record in cohort["cases"]:
        case_dir = cohort_dir / record["case_dir"]
        manifest = load_artifact(case_dir / "case_manifest.json", "case_manifest")
        freeze_receipt = load_artifact(case_dir / "frozen_label.json", "frozen_label")
        if _parse_time(produced_at) <= _parse_time(freeze_receipt["frozen_at"]):
            raise SystemExit(f"SUT timestamp is not after freeze for {record['case_id']}")
        context = manifest["procurement"][DISCOVERY_CONTEXT_KEY]
        profile = SupplierProfile(**context["supplier_profile"])
        card = _read_json(case_dir / "source" / "card.json")
        result = score_procurement_card(
            title=str(card.get("title") or ""),
            initial_price=card.get("initial_price"),
            customer_name=card.get("customer_name"),
            submission_deadline=card.get("application_deadline"),
            profile=profile,
        )
        detail = card.get("detail") or {}
        sut_cases.append(
            {
                "case_id": record["case_id"],
                "query": record["query"],
                "source_rank": record["source_rank"],
                "registry_number": record["registry_number"],
                "score": result.score,
                "status": result.status.value,
                "recommendation": result.recommendation.value,
                "reasons": result.reasons,
                "breakdown": result.breakdown,
                "source_status": card.get("raw_status"),
                "source_deadline": card.get("application_deadline"),
                "detail_status": detail.get("status"),
                "detail_deadline": detail.get("application_deadline"),
                "source_bundle_sha256": manifest["source_bundle_sha256"],
                "discovery_context_sha256": discovery_context_sha256(manifest),
                "label_set_sha256_at_generation": freeze_receipt["label_set_sha256"],
                "produced_at": produced_at,
            }
        )

    artifact = {
        "corpus_version": CORPUS_VERSION,
        "cohort_id": cohort["cohort_id"],
        "runtime_version": runtime_version,
        "produced_at": produced_at,
        "cohort_manifest_sha256": file_sha256(cohort_dir / "cohort_manifest.json"),
        "cases": sut_cases,
    }
    _write_json(cohort_dir / "sut_cohort.json", artifact)
    print(
        json.dumps(
            {
                "status": "DISCOVERY_QA_SUT_COMPLETE",
                "case_count": len(sut_cases),
                "runtime_version": runtime_version,
                "sut_cohort_sha256": file_sha256(cohort_dir / "sut_cohort.json"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def compare(args: argparse.Namespace) -> None:
    cohort_dir = Path(args.cohort_dir).resolve()
    cohort = _read_json(cohort_dir / "cohort_manifest.json")
    sut = _read_json(cohort_dir / "sut_cohort.json")
    sut_by_case = {row["case_id"]: row for row in sut["cases"]}
    labels: dict[str, str] = {}
    query_cases: dict[str, list[dict[str, Any]]] = {row["query"]: [] for row in cohort["queries"]}

    for record in cohort["cases"]:
        case_id = record["case_id"]
        case_dir = cohort_dir / record["case_dir"]
        evaluator_bundle = load_artifact(case_dir / "evaluator_bundle.json", "evaluator_bundle")
        discovery_label = load_artifact(case_dir / "blind_discovery_label.json", "blind_discovery_label")
        document_truth = load_artifact(case_dir / "blind_document_truth.json", "blind_document_truth")
        receipt = load_artifact(case_dir / "frozen_label.json", "frozen_label")
        verify_frozen_labels(receipt, evaluator_bundle, discovery_label, document_truth)
        row = sut_by_case.get(case_id)
        if row is None:
            raise SystemExit(f"SUT output missing case: {case_id}")
        if row["source_bundle_sha256"] != receipt["source_bundle_sha256"]:
            raise SystemExit(f"SUT source binding mismatch: {case_id}")
        if row["label_set_sha256_at_generation"] != receipt["label_set_sha256"]:
            raise SystemExit(f"SUT freeze binding mismatch: {case_id}")
        if row["discovery_context_sha256"] != discovery_context_sha256(evaluator_bundle):
            raise SystemExit(f"SUT discovery-context binding mismatch: {case_id}")
        if _parse_time(row["produced_at"]) <= _parse_time(receipt["frozen_at"]):
            raise SystemExit(f"SUT output was not produced after freeze: {case_id}")
        labels[case_id] = discovery_label["label"]
        query_cases[record["query"]].append(row)

    query_results = [
        evaluate_query_ranking(query=query, sut_cases=query_cases[query], blind_labels=labels)
        for query in query_cases
    ]
    aggregate = aggregate_discovery_metrics(query_results)
    comparison = {
        "corpus_version": CORPUS_VERSION,
        "cohort_id": cohort["cohort_id"],
        "compared_at": _utcnow(),
        "runtime_version": sut["runtime_version"],
        "cohort_manifest_sha256": file_sha256(cohort_dir / "cohort_manifest.json"),
        "cohort_freeze_sha256": file_sha256(cohort_dir / "cohort_freeze.json"),
        "sut_cohort_sha256": file_sha256(cohort_dir / "sut_cohort.json"),
        "metric_semantics": {
            "precision_relevant_labels": ["RELEVANT", "PARTIALLY_RELEVANT"],
            "ndcg_grades": {"RELEVANT": 2, "PARTIALLY_RELEVANT": 1, "IRRELEVANT": 0},
            "unclear": "excluded from scored ranking denominators and reported separately",
            "primary_k": 10,
        },
        "metrics": aggregate,
    }
    _write_json(cohort_dir / "comparison.json", comparison)
    print(json.dumps(comparison, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    acquire_parser = sub.add_parser("acquire", help="Acquire source-only EIS cases and prepare evaluator bundle")
    acquire_parser.add_argument("--output-dir", required=True)
    acquire_parser.add_argument("--cohort-id", required=True)
    acquire_parser.add_argument("--query-plan", required=True)
    acquire_parser.add_argument("--supplier-profile", required=True)
    acquire_parser.add_argument("--date-from", required=True)
    acquire_parser.add_argument("--date-to", required=True)
    acquire_parser.add_argument("--candidates-per-query", type=int, default=DEFAULT_CANDIDATES_PER_QUERY)
    acquire_parser.add_argument("--max-pages", type=int, default=3)
    acquire_parser.add_argument("--timeout", type=int, default=20)
    acquire_parser.add_argument("--page-delay", type=float, default=0.25)
    acquire_parser.add_argument("--detail-delay", type=float, default=0.15)
    acquire_parser.set_defaults(func=acquire)

    freeze_parser = sub.add_parser("freeze", help="Validate independent labels and freeze before SUT")
    freeze_parser.add_argument("--cohort-dir", required=True)
    freeze_parser.add_argument("--labels", required=True)
    freeze_parser.set_defaults(func=freeze)

    sut_parser = sub.add_parser("run-sut", help="Run production deterministic relevance scorer after freeze")
    sut_parser.add_argument("--cohort-dir", required=True)
    sut_parser.add_argument("--runtime-version")
    sut_parser.set_defaults(func=run_sut)

    compare_parser = sub.add_parser("compare", help="Compare frozen labels and already-persisted SUT ranking")
    compare_parser.add_argument("--cohort-dir", required=True)
    compare_parser.set_defaults(func=compare)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
