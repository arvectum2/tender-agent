from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Load .env and .env.local early so ZakupkiSoapSettings (which reads os.environ)
# can find ZAKUPKI_GOV_RU_SOAP_TOKEN and other env vars.
_load_dotenv_result = load_dotenv(".env", override=False)
_load_dotenv_local_result = load_dotenv(".env.local", override=False)

from src.tender_research.config import load_config
from src.tender_research.pipeline import TenderResearchPipeline
from src.tender_research.providers.public_44fz_search import (
    Public44FzSearchProvider,
    PublicSearchStatus,
)
from src.tender_research.registry_discovery import (
    DiscoveryResult,
    RegistryNumberDiscovery,
    SourceType,
)
from src.tender_research.repository import TenderRepository
from src.tender_research.models import ProcurementTenderDocument
from src.shared.config.settings import get_settings
from src.shared.db.base import Base
from src.shared.db.diagnostics import get_database_diagnostics

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("tender_research.cli")


SOURCE_CHOICES = [
    "auto",
    "external_public_44fz",
    "local_db",
    "seed_file",
    "demo",
    "backend_search_real",
]


def _get_session() -> Session:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    from sqlalchemy.orm import sessionmaker
    return sessionmaker(bind=engine)()


def _print_discovery_result(result: DiscoveryResult) -> None:
    print(f"selected_source: {result.selected_source}")
    print(f"selected_source_type: {result.selected_source_type}")
    print(f"is_demo: {result.is_demo}")
    if result.requested_limit is not None:
        print(f"requested_limit: {result.requested_limit}")
    if result.effective_limit is not None:
        print(f"effective_limit: {result.effective_limit}")
    if result.requested_page_size:
        print(f"requested_page_size: {result.requested_page_size}")
    if result.effective_page_size:
        print(f"effective_page_size: {result.effective_page_size}")
    if result.date_from:
        print(f"date_from: {_serialize_dt(result.date_from)}")
    if result.date_to:
        print(f"date_to: {_serialize_dt(result.date_to)}")
    if result.source_url:
        print(f"source_url: {result.source_url}")
    print(f"discovered_count: {result.discovered_count}")
    print(f"pages_read: {result.pages_read}")
    print(f"page_size: {result.page_size}")
    print(f"items_raw_count: {result.items_raw_count}")
    print(f"items_with_registry_number: {result.items_with_registry_number}")
    print(f"items_skipped_without_registry_number: {result.skipped_without_registry_number}")
    print(f"items_after_dedupe: {result.items_after_dedupe}")
    print(f"items_after_demo_filter: {result.items_after_demo_filter}")
    if result.network_status:
        print(f"network_status: {result.network_status}")
    if result.warnings:
        for w in result.warnings:
            print(f"  warning: {w}")
    if result.errors:
        for e in result.errors:
            print(f"  error: {e}")
    print(f"total_numbers: {len(result.numbers)}")
    for rn in result.numbers[:10]:
        demo_tag = " [DEMO]" if rn.is_demo else ""
        print(f"  {rn.registry_number}{demo_tag}")
    if len(result.numbers) > 10:
        print(f"  ... and {len(result.numbers) - 10} more")


def cmd_check_eis_config(args: argparse.Namespace) -> None:
    config = load_config()
    print(f"eis_mode: {config.eis_mode}")
    print(f"eis_discovery_mode: {config.eis_discovery_mode}")
    if config.eis_mode != "real":
        print("(switching to real mode for diagnostics)")
    try:
        from src.tender_research.eis_real_loader import RealEisLoader
        loader = RealEisLoader()
        info = loader.check_config()
    except Exception as e:
        print(f"check_config error: {e}")
        return
    for k, v in info.items():
        if isinstance(v, list):
            print(f"  {k}: {', '.join(v)}")
        else:
            print(f"  {k}: {v}")
    print()
    print("dotenv loaded .env:", _load_dotenv_result)
    print("dotenv loaded .env.local:", _load_dotenv_local_result)


def cmd_check_network_config(args: argparse.Namespace) -> None:
    import platform
    import subprocess

    from src.tender_research.providers.public_44fz_search import (
        _hostname_matches_no_proxy,
        _resolve_no_proxy_domains,
    )

    config = load_config()
    eis_hosts = ["zakupki.gov.ru", "int.zakupki.gov.ru", "int44.zakupki.gov.ru", "www.zakupki.gov.ru"]

    print(f"platform: {platform.platform()}")
    print(f"hostname: {platform.node()}")
    print()
    print("=== Env proxy variables ===")
    for var in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy"):
        val = os.environ.get(var, "")
        if val:
            masked = _mask_proxy_url(val)
            print(f"  {var}: {masked}")
        else:
            print(f"  {var}: (not set)")
    print()
    print("=== Config ===")
    print(f"  AI_CORP_PUBLIC_SEARCH_BYPASS_PROXY: {config.public_search_bypass_proxy}")
    print(f"  AI_CORP_PUBLIC_SEARCH_NO_PROXY_DOMAINS: {config.public_search_no_proxy_domains}")
    no_proxy_resolved = _resolve_no_proxy_domains(config.public_search_no_proxy_domains)
    print(f"  resolved no_proxy domains: {', '.join(no_proxy_resolved)}")
    print()
    print("=== macOS system proxy ===")
    for svc in ("Wi-Fi", "Ethernet", "Thunderbolt Ethernet"):
        for cmd in (
            ["networksetup", "-getwebproxy", svc],
            ["networksetup", "-getsecurewebproxy", svc],
            ["networksetup", "-getautoproxyurl", svc],
        ):
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    out = result.stdout.strip()
                    if out and "Error" not in out and "not present" not in out.lower():
                        print(f"  {' '.join(cmd)}:")
                        for line in out.splitlines():
                            print(f"    {line}")
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
    print()
    print("=== Effective decision ===")
    for host in eis_hosts:
        bypass = config.public_search_bypass_proxy and _hostname_matches_no_proxy(host, no_proxy_resolved)
        print(f"  {host}:")
        print(f"    bypass_proxy: {bypass}")
        print(f"    matches no_proxy: {_hostname_matches_no_proxy(host, no_proxy_resolved)}")
        if bypass:
            print(f"    → Will connect DIRECT (no proxy)")
        elif os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy"):
            masked = _mask_proxy_url(os.environ.get("HTTPS_PROXY", os.environ.get("https_proxy", "")))
            print(f"    → Will use HTTPS_PROXY: {masked}")
        elif os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy"):
            masked = _mask_proxy_url(os.environ.get("HTTP_PROXY", os.environ.get("http_proxy", "")))
            print(f"    → Will use HTTP_PROXY: {masked}")
        else:
            print(f"    → Will follow urllib default (env proxy if set)")
    print()
    print("=== curl diagnostics (run manually) ===")
    print("  # Direct (no proxy)")
    print("  curl --noproxy '*' -I https://zakupki.gov.ru")
    print()
    print("  # Via system proxy (if set)")
    proxy_url = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    if proxy_url:
        print(f"  curl --proxy {_mask_proxy_url(proxy_url)} -I https://zakupki.gov.ru")


def cmd_check_db(args: argparse.Namespace) -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url, future=True)
    info = get_database_diagnostics(engine)
    for key in (
        "database_dialect",
        "database_url_masked",
        "can_connect",
        "current_migration",
        "migration_head",
        "pgvector_extension_available",
        "tables_count",
    ):
        print(f"{key}: {info.get(key)}")
    if info.get("error"):
        print(f"error: {info['error']}")


def _mask_proxy_url(url: str) -> str:
    if not url:
        return ""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.password:
        return url.replace(parsed.password, "****")
    if parsed.username:
        return url.replace(parsed.username + ":", "****:")
    return url


def _serialize_dt(value):
    return value.isoformat() if hasattr(value, "isoformat") else value


def _document_extension(doc: ProcurementTenderDocument) -> str:
    candidate = doc.file_name or doc.local_path or ""
    suffix = Path(candidate).suffix.lower()
    return suffix or "<none>"


def _looks_like_html(path: str | None) -> bool:
    if not path or not Path(path).exists():
        return False
    try:
        head = Path(path).read_bytes()[:2048].lower()
    except OSError:
        return False
    return b"<html" in head or b"<!doctype html" in head


def build_document_quality_report(repo: TenderRepository, limit: int = 100) -> dict:
    docs = list(
        repo._session.query(ProcurementTenderDocument)
        .order_by(ProcurementTenderDocument.updated_at.desc())
        .limit(limit)
        .all()
    )
    ext_counter = Counter()
    content_type_counter = Counter()
    empty_by_ext = Counter()
    unsupported_by_ext = Counter()
    failed_by_error = Counter()
    suspicious_html = []
    empty_examples = []
    unsupported_examples = []
    largest = []
    for doc in docs:
        ext = _document_extension(doc)
        ext_counter[ext] += 1
        content_type_counter[doc.content_type or "<none>"] += 1
        if doc.text_extraction_status == "empty":
            empty_by_ext[ext] += 1
            if len(empty_examples) < 10:
                empty_examples.append({
                    "file_name": doc.file_name,
                    "extension": ext,
                    "content_type": doc.content_type,
                    "error_message": doc.error_message,
                })
        if doc.text_extraction_status == "unsupported":
            unsupported_by_ext[ext] += 1
            if len(unsupported_examples) < 10:
                unsupported_examples.append({
                    "file_name": doc.file_name,
                    "extension": ext,
                    "content_type": doc.content_type,
                    "error_message": doc.error_message,
                })
        if doc.download_status == "failed" and doc.error_message:
            failed_by_error[doc.error_message] += 1
        if _looks_like_html(doc.local_path) and ext not in {".html", ".htm"}:
            suspicious_html.append({
                "file_name": doc.file_name,
                "extension": ext,
                "local_path": doc.local_path,
            })
        largest.append({
            "file_name": doc.file_name,
            "size_bytes": doc.size_bytes or 0,
            "extension": ext,
            "content_type": doc.content_type,
        })
    largest.sort(key=lambda item: item["size_bytes"], reverse=True)
    return {
        "total_documents": repo.count_documents(),
        "downloaded": repo.count_documents_by_status("downloaded"),
        "failed_downloads": repo.count_documents_by_status("failed"),
        "extracted": repo.count_documents_by_text_status("extracted"),
        "empty": repo.count_documents_by_text_status("empty"),
        "unsupported": repo.count_documents_by_text_status("unsupported"),
        "failed_extraction": repo.count_documents_by_text_status("failed"),
        "top_extensions": ext_counter.most_common(10),
        "top_content_types": content_type_counter.most_common(10),
        "empty_by_extension": empty_by_ext.most_common(10),
        "unsupported_by_extension": unsupported_by_ext.most_common(10),
        "failed_by_error_message": failed_by_error.most_common(10),
        "zip_count": sum(count for ext, count in ext_counter.items() if ext == ".zip"),
        "pdf_count": sum(count for ext, count in ext_counter.items() if ext == ".pdf"),
        "docx_count": sum(count for ext, count in ext_counter.items() if ext == ".docx"),
        "xlsx_count": sum(count for ext, count in ext_counter.items() if ext in {".xlsx", ".xls"}),
        "html_count": sum(count for ext, count in ext_counter.items() if ext in {".html", ".htm"}),
        "files_with_suspicious_html_instead_of_document": suspicious_html[:10],
        "largest_files": largest[:10],
        "empty_examples": empty_examples,
        "unsupported_examples": unsupported_examples,
    }


def cmd_stats(args: argparse.Namespace) -> None:
    session = _get_session()
    repo = TenderRepository(session)
    config = load_config()
    data_dir = Path(config.data_dir)
    data_size = 0
    if data_dir.exists():
        for f in data_dir.rglob("*"):
            if f.is_file():
                data_size += f.stat().st_size
    print(f"tenders_total: {repo.count_tenders()}")
    print(f"tenders_with_real_title: {repo.count_tenders_with_real_title()}")
    print(f"tenders_with_customer: {repo.count_tenders_with_customer()}")
    print(f"tenders_with_publication_date: {repo.count_tenders_with_publication_date()}")
    print(f"tenders_with_nmck: {repo.count_tenders_with_nmck()}")
    print(f"placeholder_title_count: {repo.count_placeholder_titles()}")
    print(f"customers_total: {repo.count_customers()}")
    print(f"documents_total: {repo.count_documents()}")
    print(f"documents_downloaded: {repo.count_documents_by_status('downloaded')}")
    print(f"failed_document_downloads: {repo.count_documents_by_status('failed')}")
    print(f"extracted_texts_total: {repo.count_documents_by_text_status('extracted')}")
    print(f"unsupported_documents: {repo.count_documents_by_text_status('unsupported')}")
    print(f"empty_text_documents: {repo.count_documents_by_text_status('empty')}")
    print(f"search_queries_total: {repo.count_search_queries()}")
    print(f"search_results_total: {repo.count_search_results()}")
    print(f"web_pages_fetched: {repo.count_web_pages_by_status('fetched')}")
    print(f"web_pages_failed: {repo.count_web_pages_by_status('failed')}")
    print(f"artifacts_total: {repo.count_artifacts()}")
    print(f"data_dir_size_mb: {data_size / 1024 / 1024:.1f}")


def _build_pipeline(args: argparse.Namespace) -> TenderResearchPipeline:
    config = load_config()
    if args.eis_mode:
        object.__setattr__(config, "eis_mode", args.eis_mode)
    session = _get_session()
    return TenderResearchPipeline(session, config=config)


def cmd_ingest_eis_registry_list(args: argparse.Namespace) -> None:
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Seed file not found: {file_path}")
        return
    if file_path.suffix.lower() == ".json":
        numbers = _load_json_seed(file_path)
    else:
        numbers = [
            line.strip() for line in file_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
    if not numbers:
        print("No registry numbers found in seed file.")
        return
    print(f"Loaded {len(numbers)} registry numbers from {file_path}")

    pipeline = _build_pipeline(args)
    result = pipeline.ingest_eis_by_registry_numbers(
        registry_numbers=numbers,
        limit=args.limit,
        checkpoint_key=args.checkpoint_key,
    )
    print("Registry ingest complete:")
    print(f"  total: {result['total']}")
    print(f"  saved: {result['saved']}")
    print(f"  skipped: {result['skipped']}")
    print(f"  no_data: {result['no_data']}")
    print(f"  connection_resets: {result['connection_resets']}")
    print(f"  missing_token: {result['missing_token']}")
    if result.get("checkpoint_key"):
        print(f"  checkpoint: {result['checkpoint_key']} status={result.get('checkpoint_status')} next_index={result.get('next_index')}")
    if result["errors"]:
        print(f"  errors ({len(result['errors'])}):")
        for e in result["errors"][:5]:
            print(f"    - {e}")


def _load_json_seed(file_path: Path) -> list[str]:
    try:
        raw = json.loads(file_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"Failed to parse JSON seed: {exc}")
        return []
    if isinstance(raw, dict):
        items = raw.get("items", raw.get("numbers", []))
    elif isinstance(raw, list):
        items = raw
    else:
        print("Unexpected JSON format")
        return []
    numbers = []
    for item in items:
        if isinstance(item, str):
            numbers.append(item)
        elif isinstance(item, dict):
            rn = item.get("registry_number") or item.get("reestr_number") or item.get("number")
            if rn:
                numbers.append(str(rn))
    return numbers


def cmd_ingest_eis(args: argparse.Namespace) -> None:
    pipeline = _build_pipeline(args)
    date_from = datetime.fromisoformat(args.date_from) if args.date_from else None
    date_to = datetime.fromisoformat(args.date_to) if args.date_to else None
    count = pipeline.ingest_eis_tenders(
        date_from=date_from,
        date_to=date_to,
        limit=args.limit,
        law_type=args.law_type,
        query=args.query,
    )
    print(f"Ingested {count} tenders from EIS.")


def cmd_research_batch(args: argparse.Namespace) -> None:
    pipeline = _build_pipeline(args)
    date_from = datetime.fromisoformat(args.date_from) if args.date_from else None
    date_to = datetime.fromisoformat(args.date_to) if args.date_to else None
    results = pipeline.run_batch(
        date_from=date_from,
        date_to=date_to,
        limit=args.limit,
        law_type=args.law_type,
        query=args.query,
        web_search=args.web_search,
    )
    ok = sum(1 for r in results if "error" not in r)
    failed = sum(1 for r in results if "error" in r)
    print(f"Batch complete: {ok} ok, {failed} failed")
    for r in results:
        status = "OK" if "error" not in r else f"FAIL: {r['error']}"
        title = r.get("title", r.get("external_id", "?"))
        print(f"  [{status}] {title}")


def cmd_research_one(args: argparse.Namespace) -> None:
    pipeline = _build_pipeline(args)
    repo = pipeline._repo
    tender = repo.get_tender_by_external("eis", args.external_id)
    if not tender:
        from src.tender_research.eis_loader import EisTenderLoader
        loader = EisTenderLoader()
        raw = loader.fetch_tender_details(args.external_id)
        if raw:
            count = pipeline.ingest_eis_tenders(query=raw.title, limit=1)
            if count:
                tender = repo.get_tender_by_external("eis", args.external_id)
        if not tender:
            print(f"Tender {args.external_id} not found")
            return
    result = pipeline.run_full(tender.id)
    print(f"Results for {args.external_id}:")
    for k, v in result.items():
        print(f"  {k}: {v}")


def cmd_build_queries(args: argparse.Namespace) -> None:
    session = _get_session()
    pipeline = TenderResearchPipeline(session)
    count = pipeline.build_search_queries(args.tender_id)
    print(f"Built {count} search queries for tender {args.tender_id}")


def cmd_web_search(args: argparse.Namespace) -> None:
    session = _get_session()
    pipeline = TenderResearchPipeline(session)
    count = pipeline.run_web_search(args.tender_id)
    print(f"Saved {count} search results for tender {args.tender_id}")


def cmd_fetch_pages(args: argparse.Namespace) -> None:
    session = _get_session()
    pipeline = TenderResearchPipeline(session)
    result = pipeline.fetch_search_results(args.tender_id, max_pages=args.limit)
    print(f"Fetched {result.get('fetched', 0)} pages, {result.get('failed', 0)} failed")


def cmd_discover_registry_numbers(args: argparse.Namespace) -> None:
    pipeline = _build_pipeline(args)
    result = pipeline.discover_registry_numbers(
        source=args.source,
        days_back=args.days_back,
        limit=args.limit,
        seed_file=args.seed_file,
        page_size=args.page_size,
    )
    _print_discovery_result(result)

    if args.output and result.numbers:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if output_path.suffix.lower() == ".json":
            items = [
                {
                    "registry_number": rn.registry_number,
                    "title": rn.tender_title,
                    "purchase_number": rn.purchase_number,
                    "customer_name": rn.customer_name,
                    "customer_inn": rn.customer_inn,
                    "customer_kpp": rn.customer_kpp,
                    "publication_date": _serialize_dt(rn.publication_date),
                    "application_deadline": _serialize_dt(rn.application_deadline),
                    "nmck_amount": rn.nmck_amount,
                    "law_type": rn.law_type,
                    "source_url": rn.source_url,
                    "card_url": rn.card_url,
                    "source": rn.source,
                    "is_demo": rn.is_demo,
                }
                for rn in result.numbers if not rn.is_demo
            ]
            output_path.write_text(
                json.dumps({"source": result.selected_source, "items": items}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        else:
            lines = [f"# discovered via {result.selected_source} (is_demo={result.is_demo})"]
            lines += [f"# {w}" for w in result.warnings]
            lines += [rn.registry_number for rn in result.numbers if not rn.is_demo]
            output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        print(f"Saved {sum(1 for rn in result.numbers if not rn.is_demo)} numbers to {output_path}")


def cmd_collect_registry_numbers(args: argparse.Namespace) -> None:
    provider = Public44FzSearchProvider(
        timeout_seconds=args.timeout or 30,
        delay_seconds=args.delay or 3.0,
        bypass_proxy=not args.use_proxy,
    )
    date_from = datetime.now().date()
    date_to = datetime.now().date()
    if args.days_back:
        from datetime import timedelta
        date_from = date_from - timedelta(days=args.days_back)

    if not args.output:
        print("--output is required for collect-registry-numbers")
        return

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    pages = provider.search_pages(
        query=None,
        date_from=date_from,
        date_to=date_to,
        max_pages=max(1, (args.limit + args.page_size - 1) // args.page_size) if args.limit else 10,
        page_size=args.page_size,
        law_type=args.law_type or "44fz",
    )

    first_status = pages[0].status if pages else PublicSearchStatus.EMPTY
    if first_status not in (PublicSearchStatus.SUCCESS, PublicSearchStatus.EMPTY):
        print(f"collect-registry-numbers failed: {first_status}")
        if pages[0].error:
            print(f"  error: {pages[0].error}")
        return

    numbers = provider.extract_registry_numbers(pages)
    if args.limit:
        numbers = numbers[:args.limit]

    items = []
    for page_obj in pages:
        for item in page_obj.items:
            if item.registry_number and item.registry_number in numbers[:args.limit] if args.limit else True:
                items.append({
                    "registry_number": item.registry_number,
                    "purchase_number": item.purchase_number,
                    "title": item.title,
                    "customer_name": item.customer_name,
                    "customer_inn": item.customer_inn,
                    "customer_kpp": item.customer_kpp,
                    "publication_date": _serialize_dt(item.publication_date),
                    "application_deadline": _serialize_dt(item.application_deadline),
                    "nmck_amount": float(item.nmck_amount) if item.nmck_amount is not None else None,
                    "law_type": item.law_type,
                    "source_url": item.source_url,
                    "card_url": item.card_url,
                    "raw": item.raw,
                })
                if args.limit and len(items) >= args.limit:
                    break
        if args.limit and len(items) >= args.limit:
            break

    success_pages = sum(1 for p in pages if p.status == PublicSearchStatus.SUCCESS)

    if output_path.suffix.lower() == ".json":
        output_path.write_text(
            json.dumps({
                "source": "external_public_44fz",
                "date_from": date_from.isoformat(),
                "date_to": date_to.isoformat(),
                "pages_read": len(pages),
                "success_pages": success_pages,
                "items": items,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    else:
        lines = [f"# collected via external_public_44fz, date_from={date_from}, date_to={date_to}"]
        lines += [item["registry_number"] for item in items]
        output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"collect-registry-numbers complete:")
    print(f"  pages_read: {len(pages)}")
    print(f"  success_pages: {success_pages}")
    print(f"  discovered: {len(items)}")
    print(f"  output: {output_path}")
    print()
    if items:
        print("First 10 registry numbers:")
        for item in items[:10]:
            print(f"  {item['registry_number']}  {item.get('title', '')[:60] or ''}")
    if len(items) > 10:
        print(f"  ... and {len(items) - 10} more")
    for p in pages:
        if p.status == PublicSearchStatus.BLOCKED:
            print(f"  [BLOCKED] external_public_44fz blocked by network (captcha or connection reset)")
        elif p.status == PublicSearchStatus.TIMEOUT:
            print(f"  [TIMEOUT] external_public_44fz timed out")
        elif p.status == PublicSearchStatus.BAD_GATEWAY:
            print(f"  [BAD_GATEWAY] external_public_44fz returned 502 from proxy")


def cmd_ingest_collected_registry_numbers(args: argparse.Namespace) -> None:
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"File not found: {file_path}")
        return

    numbers = _load_json_seed(file_path)
    if not numbers:
        print("No registry numbers found in collected file.")
        return

    pipeline = _build_pipeline(args)
    result = pipeline.ingest_eis_by_registry_numbers(
        registry_numbers=numbers,
        limit=args.limit,
        checkpoint_key=args.checkpoint_key,
    )
    print("Registry ingest complete:")
    print(f"  total: {result['total']}")
    print(f"  saved: {result['saved']}")
    print(f"  skipped: {result['skipped']}")
    print(f"  no_data: {result['no_data']}")
    print(f"  connection_resets: {result['connection_resets']}")
    print(f"  missing_token: {result['missing_token']}")
    if result.get("checkpoint_key"):
        print(f"  checkpoint: {result['checkpoint_key']} status={result.get('checkpoint_status')} next_index={result.get('next_index')}")
    if result["errors"]:
        print(f"  errors ({len(result['errors'])}):")
        for e in result["errors"][:5]:
            print(f"    - {e}")


def cmd_research_discovered(args: argparse.Namespace) -> None:
    pipeline = _build_pipeline(args)
    if args.web_search:
        object.__setattr__(pipeline._config, "web_search_enabled", True)
    if args.fetch_pages:
        object.__setattr__(pipeline._config, "web_fetch_enabled", True)
    result = pipeline.run_discovered_batch(
        source=args.source,
        days_back=args.days_back,
        limit=args.limit,
        seed_file=args.seed_file,
        page_size=args.page_size,
    )
    ok = sum(1 for r in result if "error" not in r)
    failed = sum(1 for r in result if "error" in r)
    print(f"Discovered batch complete: {ok} ok, {failed} failed")
    summary = pipeline.last_discovered_batch_summary or {}
    if summary:
        for key in (
            "requested_limit",
            "effective_limit",
            "requested_page_size",
            "effective_page_size",
            "date_from",
            "date_to",
            "source_url",
            "discovered_count",
            "selected_source",
            "pages_read",
            "items_raw_count",
            "items_with_registry_number",
            "items_skipped_without_registry_number",
            "items_after_dedupe",
            "items_after_demo_filter",
            "detail_fetch_attempts",
            "detail_fetch_success",
            "ingest_attempts",
            "tenders_created",
            "tenders_updated",
            "tenders_with_title",
            "tenders_with_customer",
            "tenders_with_publication_date",
            "tenders_with_nmck",
            "placeholder_title_count",
            "customers_created",
            "public_detail_fetched",
            "public_detail_failed",
            "public_document_links_found",
            "documents_created_from_public_links",
            "documents_downloaded",
            "extracted_texts_total",
            "unsupported_documents",
            "empty_text_documents",
            "failed_document_downloads",
        ):
            if key in summary:
                print(f"{key}: {summary[key]}")
        for error in summary.get("errors", [])[:10]:
            print(f"error: {error}")
    for r in result:
        status = "OK" if "error" not in r else f"FAIL: {r['error']}"
        title = r.get("title", r.get("registry_number", "?"))
        print(f"  [{status}] {title}")


def cmd_backfill_public_metadata(args: argparse.Namespace) -> None:
    pipeline = _build_pipeline(args)
    summary = pipeline.backfill_public_metadata(
        limit=args.limit,
        only_placeholders=args.only_placeholders,
        days_back=args.days_back,
        with_documents=args.with_documents,
        dry_run=args.dry_run,
    )
    for key in (
        "placeholders_found",
        "processed",
        "enriched_title_count",
        "enriched_customer_count",
        "enriched_publication_date_count",
        "enriched_nmck_count",
        "public_document_links_found",
        "documents_created",
        "documents_downloaded",
        "extracted_texts_created",
        "failed_count",
    ):
        print(f"{key}: {summary.get(key, 0)}")
    for error in summary.get("errors", [])[:10]:
        print(f"error: {error}")


def cmd_document_quality_report(args: argparse.Namespace) -> None:
    session = _get_session()
    repo = TenderRepository(session)
    report = build_document_quality_report(repo, limit=args.limit)
    for key in (
        "total_documents",
        "downloaded",
        "failed_downloads",
        "extracted",
        "empty",
        "unsupported",
        "failed_extraction",
        "zip_count",
        "pdf_count",
        "docx_count",
        "xlsx_count",
        "html_count",
    ):
        print(f"{key}: {report[key]}")
    print(f"top_extensions: {report['top_extensions']}")
    print(f"top_content_types: {report['top_content_types']}")
    print(f"empty_by_extension: {report['empty_by_extension']}")
    print(f"unsupported_by_extension: {report['unsupported_by_extension']}")
    print(f"failed_by_error_message: {report['failed_by_error_message']}")
    print(f"files_with_suspicious_html_instead_of_document: {report['files_with_suspicious_html_instead_of_document']}")
    print(f"largest_files: {report['largest_files']}")
    print(f"empty_examples: {report['empty_examples']}")
    print(f"unsupported_examples: {report['unsupported_examples']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Tender Research Pipeline CLI")
    parser.add_argument("--data-dir", default=None, help="Data directory override")
    sub = parser.add_subparsers(dest="command", required=True)

    p_stats = sub.add_parser("stats", help="Show pipeline statistics")

    p_check = sub.add_parser("check-eis-config", help="Check EIS SOAP configuration and available methods")
    sub.add_parser("check-db", help="Show database dialect, connectivity, migration state, and pgvector status")

    p_net = sub.add_parser("check-network-config", help="Diagnose proxy/PAC/NO_PROXY configuration for EIS hosts")

    _common = argparse.ArgumentParser(add_help=False)
    _common.add_argument("--eis-mode", default=None, choices=["demo", "real"], help="EIS loader mode")

    p_ingest = sub.add_parser("ingest-eis", parents=[_common], help="Ingest tenders from EIS")
    p_ingest.add_argument("--date-from", default=None, help="ISO date (e.g. 2026-07-01)")
    p_ingest.add_argument("--date-to", default=None, help="ISO date")
    p_ingest.add_argument("--limit", type=int, default=None, help="Max tenders")
    p_ingest.add_argument("--law-type", default=None, help="44fz / 223fz")
    p_ingest.add_argument("--query", default=None, help="Search query")

    p_batch = sub.add_parser("research-batch", parents=[_common], help="Full cycle for a batch of tenders")
    p_batch.add_argument("--date-from", default=None)
    p_batch.add_argument("--date-to", default=None)
    p_batch.add_argument("--limit", type=int, default=None)
    p_batch.add_argument("--law-type", default=None)
    p_batch.add_argument("--query", default=None)
    p_batch.add_argument("--web-search", action="store_true", help="Enable web search")

    p_reg = sub.add_parser("ingest-eis-registry-list", parents=[_common], help="Ingest tenders by registry number list")
    p_reg.add_argument("--file", default="data/eis_seed/registry_numbers.txt", help="Path to seed file")
    p_reg.add_argument("--limit", type=int, default=None, help="Max tenders to process")
    p_reg.add_argument("--checkpoint-key", default=None, help="Durable resume key for this exact registry-number batch")

    p_one = sub.add_parser("research-one", parents=[_common], help="Full cycle for one tender")
    p_one.add_argument("external_id", help="EIS external ID")

    p_q = sub.add_parser("build-queries", help="Build search queries for a tender")
    p_q.add_argument("tender_id", help="Tender UUID (id)")

    p_ws = sub.add_parser("web-search", help="Run web search for a tender")
    p_ws.add_argument("tender_id", help="Tender UUID")

    p_fp = sub.add_parser("fetch-pages", help="Fetch pages from search results")
    p_fp.add_argument("tender_id", help="Tender UUID")
    p_fp.add_argument("--limit", type=int, default=10, help="Max pages to fetch")

    p_disc = sub.add_parser("discover-registry-numbers", parents=[_common],
                            help="Discover registry numbers from EIS sources")
    p_disc.add_argument("--source", default="auto", choices=SOURCE_CHOICES,
                        help="Discovery source (default: auto)")
    p_disc.add_argument("--days-back", type=int, default=None, help="Days to look back")
    p_disc.add_argument("--limit", type=int, default=10, help="Max numbers to discover")
    p_disc.add_argument("--page-size", type=int, default=30, help="Results per page (default: 30, max: 100)")
    p_disc.add_argument("--seed-file", default=None, help="Path to seed file (for seed_file source)")
    p_disc.add_argument("--output", default=None,
                        help="Save non-demo numbers to file (.txt or .json)")

    p_collect = sub.add_parser("collect-registry-numbers",
                               help="Collect registry numbers from external machine with EIS access")
    p_collect.add_argument("--days-back", type=int, default=3, help="Days to look back")
    p_collect.add_argument("--limit", type=int, default=300, help="Max numbers to collect")
    p_collect.add_argument("--page-size", type=int, default=30, help="Results per page (default: 30, max: 100)")
    p_collect.add_argument("--law-type", default="44fz", help="44fz / 223fz")
    p_collect.add_argument("--timeout", type=int, default=30, help="HTTP timeout in seconds")
    p_collect.add_argument("--delay", type=float, default=3.0, help="Delay between pages in seconds")
    p_collect.add_argument("--use-proxy", action="store_true", help="Use system proxy (default: bypass)")
    p_collect.add_argument("--output", required=True, help="Output file (.txt or .json)")

    p_ingest_collected = sub.add_parser("ingest-collected-registry-numbers", parents=[_common],
                                        help="Ingest collected registry numbers from JSON file")
    p_ingest_collected.add_argument("--file", required=True, help="Path to collected JSON file")
    p_ingest_collected.add_argument("--limit", type=int, default=None, help="Max tenders to process")
    p_ingest_collected.add_argument("--checkpoint-key", default=None, help="Durable resume key for this exact registry-number batch")

    p_disc_batch = sub.add_parser("research-discovered", parents=[_common],
                                  help="Discover and research tenders in one step")
    p_disc_batch.add_argument("--source", default="auto", choices=SOURCE_CHOICES)
    p_disc_batch.add_argument("--days-back", type=int, default=None)
    p_disc_batch.add_argument("--limit", type=int, default=10)
    p_disc_batch.add_argument("--page-size", type=int, default=30, help="Results per page for external_public_44fz")
    p_disc_batch.add_argument("--seed-file", default=None, help="Path to seed file (for seed_file source)")
    p_disc_batch.add_argument("--web-search", action="store_true", help="Enable web search")
    p_disc_batch.add_argument("--fetch-pages", action="store_true", help="Fetch web pages")

    p_backfill = sub.add_parser("backfill-public-metadata", parents=[_common],
                                help="Backfill saved tenders with public search/detail metadata")
    p_backfill.add_argument("--limit", type=int, default=50)
    p_backfill.add_argument("--days-back", type=int, default=None)
    p_backfill.add_argument("--only-placeholders", action=argparse.BooleanOptionalAction, default=True)
    p_backfill.add_argument("--with-documents", action=argparse.BooleanOptionalAction, default=True)
    p_backfill.add_argument("--dry-run", action="store_true")

    p_doc_quality = sub.add_parser("document-quality-report", help="Show document extraction quality report")
    p_doc_quality.add_argument("--limit", type=int, default=100)

    args = parser.parse_args()

    if args.command == "stats":
        cmd_stats(args)
    elif args.command == "check-db":
        cmd_check_db(args)
    elif args.command == "check-eis-config":
        cmd_check_eis_config(args)
    elif args.command == "check-network-config":
        cmd_check_network_config(args)
    elif args.command == "ingest-eis":
        cmd_ingest_eis(args)
    elif args.command == "ingest-eis-registry-list":
        cmd_ingest_eis_registry_list(args)
    elif args.command == "research-batch":
        cmd_research_batch(args)
    elif args.command == "research-one":
        cmd_research_one(args)
    elif args.command == "build-queries":
        cmd_build_queries(args)
    elif args.command == "web-search":
        cmd_web_search(args)
    elif args.command == "fetch-pages":
        cmd_fetch_pages(args)
    elif args.command == "discover-registry-numbers":
        cmd_discover_registry_numbers(args)
    elif args.command == "collect-registry-numbers":
        cmd_collect_registry_numbers(args)
    elif args.command == "ingest-collected-registry-numbers":
        cmd_ingest_collected_registry_numbers(args)
    elif args.command == "research-discovered":
        cmd_research_discovered(args)
    elif args.command == "backfill-public-metadata":
        cmd_backfill_public_metadata(args)
    elif args.command == "document-quality-report":
        cmd_document_quality_report(args)


if __name__ == "__main__":
    main()
