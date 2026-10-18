"""Bounded source-first daily Tender Agent intake, owner-private and review-only.

Pipeline:
  independent primary-source discovery -> exact original attestation -> immutable
  original snapshot + canonical learning candidate -> analysis-pending manifest.

All external access is read-only. Actual DB mutation requires --apply,
--confirm-database arvectum, and a separately validated prewrite backup.

Do not confuse a source candidate with a real saved analytical run, human gold,
current EIS legal status, confirmed company eligibility or submission to ETP.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

from lxml import html
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from scripts.procurement_llm import collect_eis_official_archives as eis
from scripts.procurement_llm import collect_public_market_originals as market
from scripts.procurement_llm.import_candidates import _engine_url
from scripts.procurement_llm.source_pipeline_runtime import (
    fresh_pg_backup,
    save_private_receipt,
    single_runner,
)
from src.tender_research.config import TenderResearchConfig
from src.tender_research.registry_discovery import RegistryNumberDiscovery, SourceType

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "docs/roadmap/source_pipeline_policy_v1.json"
WORKSPACE_RSS = "https://workspace.ru/tenders/rss/"
B2B_INDEX = "https://www.b2b-center.ru/search/industry/{}/"
B2B_CATEGORIES = {
    "razrabotka-sajtov", "crm-sistemy",
    "texpodderzhka", "razrabotka-mobilnogo-prilozheniya",
}
CARD_EXACT = re.compile(r"https://workspace\.ru/tenders/[a-z0-9-]+-(\d{4,7})/\Z")
B2B_EXACT = re.compile(
    r"https://www\.b2b-center\.ru/(?:app/market-next|market)/"
    r"[a-z0-9-]+/tender-(\d{7})/\Z"
)
IT_TERMS = (
    "сайт", "веб", "web", "crm", "битрикс", "интеграц", "разработк",
    "автоматизац", "программ", "мобильн", "приложен", "сервис",
    "искусственн", "нейросет", "ai ", "ии-", "информационн", "чат-бот",
    "бота", "доработ", "erp", "баз данн", "электронн",
)
MAX_INDEX_BYTES = 700_000
EIS_TITLE_IT_MARKERS = (
    "программного обеспечен", "информационной систем",
    "информационнoй систем", "сайта", "веб-сайт", "битрикс",
    "автоматизации учета", "автоматизации учёта",
    "внедрение crm", "разработка crm", "доработка crm",
    "создание мобильного приложения", "разработка мобильного приложения",
    "интеграция информационных систем", "разработка чат-бота",
)


class PipelineError(ValueError):
    """Source/operational contract failure; cannot assert full success."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise PipelineError("index redirected outside exact source contract")


def read_index(url: str) -> tuple[bytes, str]:
    if url != WORKSPACE_RSS and url not in [
        B2B_INDEX.format(x) for x in B2B_CATEGORIES
    ]:
        raise PipelineError("not a configured exact primary source index")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    opener = urllib.request.build_opener(_NoRedirect)
    with opener.open(req, timeout=15) as response:
        mime = response.headers.get_content_type()
        payload = response.read(MAX_INDEX_BYTES + 1)
        if response.status != 200 or response.geturl() != url:
            raise PipelineError("index is not canonical public HTTP200")
    if not 100 < len(payload) <= MAX_INDEX_BYTES:
        raise PipelineError("index empty/too large")
    if mime not in ({"text/html"} if url != WORKSPACE_RSS else
                    {"application/rss+xml", "application/xml", "text/xml"}):
        raise PipelineError("wrong original index MIME")
    return payload, mime


def parse_workspace_rss(raw: bytes, *, max_items: int) -> list[dict]:
    if not isinstance(raw, bytes) or not 100 < len(raw) <= MAX_INDEX_BYTES:
        raise PipelineError("RSS bytes outside bounded source envelope")
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise PipelineError("RSS DTD/entity rejected")
    try:
        tree = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise PipelineError("bad original Workspace RSS") from exc
    if tree.tag.lower() != "rss":
        raise PipelineError("no official-looking Workspace RSS root")
    result = []
    seen = set()
    for row in tree.findall("./channel/item")[:100]:
        url = (row.findtext("link") or "").strip()
        title = " ".join((row.findtext("title") or "").casefold().split())
        m = CARD_EXACT.fullmatch(url)
        if m is None or not any(x in title for x in IT_TERMS):
            continue
        card = {"platform": "workspace", "id": m.group(1), "url": url}
        market._url(card)
        key = (card["platform"], card["id"])
        if key in seen:
            raise PipelineError("duplicate Workspace primary RSS identity")
        seen.add(key)
        result.append(card)
        if len(result) >= max_items:
            break
    return result


def parse_b2b_index(raw: bytes, *, max_items: int) -> list[dict]:
    if not isinstance(raw, bytes) or not 100 < len(raw) <= MAX_INDEX_BYTES:
        raise PipelineError("B2B primary index outside bounded source envelope")
    try:
        tree = html.fromstring(raw, parser=html.HTMLParser(no_network=True))
    except (ValueError, TypeError, html.ParserError) as exc:
        raise PipelineError("invalid B2B primary index HTML") from exc
    found = []
    seen = set()
    for link in tree.xpath("//a[@href]"):
        url = link.get("href", "")
        match = B2B_EXACT.fullmatch(url)
        if not match:
            continue
        card = {"platform": "b2bcenter", "id": match.group(1), "url": url}
        market._url(card)
        if card["id"] in seen:
            continue
        seen.add(card["id"])
        found.append(card)
        if len(found) >= max_items:
            break
    return found


def validate_policy(config: dict) -> dict:
    if not isinstance(config, dict) or set(config) != {
        "schema", "b2b_categories", "max_index_items",
        "max_market_new_per_run", "max_existing_refresh",
        "eis_known_numbers_refresh", "fail_if_source_unavailable",
        "eis_public_44fz_discovery_enabled", "eis_public_days_back",
        "eis_public_sample_limit", "eis_public_new_max",
    } or config["schema"] != "arvectum_source_pipeline_v1":
        raise PipelineError("unknown provider pipeline configuration")
    categories = config["b2b_categories"]
    if (not isinstance(categories, list) or len(set(categories)) != len(categories)
            or not 1 <= len(categories) <= 4
            or set(categories) - B2B_CATEGORIES):
        raise PipelineError("unsafe/misconfigured provider categories")
    for key, minimum, maximum in (
        ("max_index_items", 1, 40),
        ("max_market_new_per_run", 1, 8),
        ("max_existing_refresh", 0, 2),
    ):
        v = config[key]
        if type(v) is not int or not minimum <= v <= maximum:
            raise PipelineError("unsafe pipeline limit " + key)
    eis.validate_numbers(config["eis_known_numbers_refresh"])
    for key, low, high in (
        ("eis_public_days_back", 1, 7),
        ("eis_public_sample_limit", 1, 40),
        ("eis_public_new_max", 0, 3),
    ):
        value = config[key]
        if type(value) is not int or not low <= value <= high:
            raise PipelineError("unsafe official public discovery limit " + key)
    if not isinstance(config["eis_public_44fz_discovery_enabled"], bool):
        raise PipelineError("public EIS discovery flag not boolean")
    if not isinstance(config["fail_if_source_unavailable"], bool):
        raise PipelineError("source failure policy must be explicit boolean")
    return config


def discover(policy: dict, *, read=read_index) -> tuple[list[dict], dict]:
    config = validate_policy(policy)
    observed = []
    statuses = []
    indexes = [(WORKSPACE_RSS, "workspace")] + [
        (B2B_INDEX.format(category), "b2bcenter")
        for category in config["b2b_categories"]
    ]
    for url, platform in indexes:
        try:
            raw, mime = read(url)
            allowed = {"text/html"} if platform == "b2bcenter" else {
                "text/xml", "application/xml", "application/rss+xml"
            }
            if mime not in allowed:
                raise PipelineError("primary source original index MIME mismatch")
            cards = (
                parse_workspace_rss(raw, max_items=config["max_index_items"])
                if platform == "workspace"
                else parse_b2b_index(raw, max_items=config["max_index_items"])
            )
            if not cards:
                raise PipelineError("valid index but no bounded IT cards found")
            statuses.append({
                "source": platform, "status": "OK",
                "source_bytes_sha256": hashlib.sha256(raw).hexdigest(),
                "card_count": len(cards),
            })
            observed.extend(cards)
        except Exception as exc:  # noqa: BLE001 - per-source failure is an explicit status
            statuses.append({
                "source": platform, "status": "UNAVAILABLE_OR_AMBIGUOUS",
                "error_class": type(exc).__name__,
            })
    if config["fail_if_source_unavailable"] and any(
        x["status"] != "OK" for x in statuses
    ):
        raise PipelineError("one or more primary discovery indexes unavailable")
    seen = set()
    exact = []
    for item in observed:
        identity = (item["platform"], item["id"])
        if identity not in seen:
            seen.add(identity)
            exact.append(item)
    return exact, {"indexes": statuses, "raw_card_count": len(observed)}



def discover_public_eis_numbers(*, days_back: int, sample_limit: int) -> tuple[list[str], dict]:
    """Read *real* existing public 44-FZ source, never a demo/seed fallback.

    This is a sampled current index; it DOES NOT prove current buyer status,
    complete EIS coverage, or IT fit (title gate is conservative/heuristic).
    An original only enters learning after getDocsIP ZIP/XML verification.
    """
    settings = TenderResearchConfig()
    settings.public_search_timeout_seconds = 8
    settings.public_search_delay_seconds = 0
    result = RegistryNumberDiscovery(config=settings).discover(
        source="external_public_44fz", days_back=days_back,
        limit=sample_limit, page_size=sample_limit,
    )
    if (
        result.is_demo or
        result.selected_source_type != SourceType.EXTERNAL_PUBLIC_44FZ or
        result.network_status not in {"success", "empty"}
    ):
        raise PipelineError("real EIS public 44-FZ discovery unavailable")
    numbers = []
    for item in result.numbers:
        number = item.registry_number
        title = (item.tender_title or "").casefold()
        if (
            isinstance(number, str) and re.fullmatch(r"[0-9]{19}", number) and
            any(marker in title for marker in EIS_TITLE_IT_MARKERS) and
            number not in numbers
        ):
            numbers.append(number)
    return numbers, {
        "source": "eis_external_public_44fz",
        "status": "OK",
        "sampled_listings": len(result.numbers),
        "it_title_heuristic_matches": len(numbers),
        "demo_or_seed_data_accepted": False,
        "sampling_not_full_eis_registry": True,
    }


def recorded_source_refs(session: Session) -> tuple[set[str], set[str]]:
    """A generic historical analysis_run never closes a specific source SHA.

    Completion must be signed by our actual-worker verified persisted run,
    matching latest original bytes and its report. No second database.
    """
    from scripts.procurement_llm.analysis_queue_worker import (
        completed_source_versions,
        source_rows,
    )

    originals = source_rows(session)
    linked = completed_source_versions(session)
    return (
        {item.procurement_ref for item in originals},
        {
            item.procurement_ref for item in originals
            if item.observation_id in linked
        },
    )


def plan(cards: list[dict], *, known: set[str], analyzed: set[str],
         max_new: int, max_refresh: int) -> dict:
    """Bounded round-robin across providers, so RSS cannot starve B2B cards.

    The source listing order is discovery order, NOT a current deadline or
    verified company legal eligibility ranking.
    """
    fresh_by_provider: dict[str, list[dict]] = {}
    refresh_by_provider: dict[str, list[dict]] = {}
    for card in cards:
        ref = card["platform"] + ":" + card["id"]
        bucket = refresh_by_provider if ref in known else fresh_by_provider
        bucket.setdefault(card["platform"], []).append(card)

    def balanced(buckets: dict[str, list[dict]], cap: int) -> list[dict]:
        out: list[dict] = []
        platforms = list(buckets)
        while len(out) < cap and any(buckets.values()):
            for provider in platforms:
                if buckets[provider] and len(out) < cap:
                    out.append(buckets[provider].pop(0))
        return out

    fresh = balanced(fresh_by_provider, max_new)
    refresh = balanced(refresh_by_provider, max_refresh)
    selected = fresh + refresh
    return {
        "fresh_source_refs": [x["platform"] + ":" + x["id"] for x in fresh],
        "recheck_source_refs": [x["platform"] + ":" + x["id"] for x in refresh],
        "selected": selected,
        "needs_analysis": [
            x["platform"] + ":" + x["id"]
            for x in selected if x["platform"] + ":" + x["id"] not in analyzed
        ],
        "real_independent_analysis_runs_created": 0,
        "legal_bid_go": 0,
    }


def run(policy: dict, *, index_read=read_index, market_fetch=market.fetch_original,
        eis_fetch=eis.fetch_official_archive,
        eis_public_search=discover_public_eis_numbers,
        known: set[str] | None = None,
        analyzed: set[str] | None = None, apply: bool = False,
        backup_verified: bool = False,
        market_root: Path = market.OWNER_PRIVATE,
        engine_factory=None, observed: datetime | None = None) -> dict:
    """One finite cycle. No scheduled task is created by this function."""
    config = validate_policy(policy)
    observed = observed or datetime.now(UTC)
    cards, discovery = discover(config, read=index_read)
    known = known or set()
    analyzed = analyzed or set()
    picked = plan(cards, known=known, analyzed=analyzed,
                  max_new=config["max_market_new_per_run"],
                  max_refresh=config["max_existing_refresh"])
    if apply and not backup_verified:
        raise PipelineError("full canonical PostgreSQL backup required BEFORE source mutation")
    eis_numbers = list(config["eis_known_numbers_refresh"])
    eis_status = {
        "source": "eis_external_public_44fz",
        "status": "DISABLED",
        "sampled_listings": 0,
        "it_title_heuristic_matches": 0,
        "sampling_not_full_eis_registry": True,
    }
    if config["eis_public_44fz_discovery_enabled"]:
        try:
            discovered, eis_status = eis_public_search(
                days_back=config["eis_public_days_back"],
                sample_limit=config["eis_public_sample_limit"],
            )
            checked = 0
            for number in discovered:
                if (
                    not isinstance(number, str) or not re.fullmatch(r"[0-9]{19}", number)
                    or number in eis_numbers or number in known
                    or checked >= config["eis_public_new_max"]
                ):
                    continue
                eis_numbers.append(number)
                checked += 1
            eis_status = dict(eis_status)
            eis_status["new_original_numbers_selected"] = checked
        except Exception as exc:  # noqa: BLE001 - explicit EIS search transport status
            eis_status = {
                "source": "eis_external_public_44fz",
                "status": "UNAVAILABLE_OR_AMBIGUOUS",
                "error_class": type(exc).__name__,
                "sampling_not_full_eis_registry": True,
            }
    discovery["eis_public"] = eis_status
    sources = {
        "market_selected": len(picked["selected"]),
        "eis_existing_known_watchlist": len(config["eis_known_numbers_refresh"]),
        "eis_new_public_title_heuristic_selected": (
            len(eis_numbers) - len(config["eis_known_numbers_refresh"])
        ),
    }
    stored = []
    failures = []
    for card in picked["selected"]:
        try:
            result = market.collect(
                [card], fetch=market_fetch, root=market_root,
                apply=apply, observed=observed, engine_factory=engine_factory,
            )
            stored.append({
                "ref": card["platform"] + ":" + card["id"],
                "capture_state": "OWNER_PRIVATE_SOURCE_AND_CANONICAL_DB"
                if apply else "OFFLINE_SOURCE_ATTESTED_DRY_RUN",
                "new_canonical_rows": result.get("inserted", 0),
                "existing_versions": result.get("existing", 0),
            })
        except Exception as exc:  # noqa: BLE001 - explicit failed card, no fictional capture
            failures.append({"ref": card["platform"] + ":" + card["id"],
                             "reason_class": type(exc).__name__})
    # EIS getDocsIP attests known IDs and separately sampled real current
    # public 44-FZ title-gated IDs. Legacy SOAP search remains unused.
    for number in eis_numbers:
        try:
            result = eis.collect(
                [number], fetch=eis_fetch, root=market_root,
                apply=apply, observed=observed, engine_factory=engine_factory,
            )
            stored.append({
                "ref": number,
                "capture_state": "OWNER_PRIVATE_SOURCE_AND_CANONICAL_DB"
                if apply else "OFFICIAL_ARCHIVE_VERIFIED_DRY_RUN",
                "new_canonical_rows": result.get("inserted", 0),
                "existing_versions": result.get("existing", 0),
            })
        except Exception as exc:  # noqa: BLE001 - bounded EIS diagnostic, no token
            failures.append({"ref": number, "reason_class": type(exc).__name__})
    successfully_captured = {x["ref"] for x in stored}
    # Previously observed sources are pending until a genuine analysis_run
    # exists. A dry run never adds hypothetical source candidates to this
    # queue; it reports them separately.
    pending = sorted(
        (known | (successfully_captured if apply else set())) - analyzed
    )
    # All pending entries are ANALYSIS_PENDING, never automatically trainable.
    return {
        "schema": "arvectum_daily_source_pipeline_receipt_v1",
        "observed_at_utc": observed.astimezone(UTC).isoformat(),
        "mode": "owner_authorized_capture" if apply else "source_read_only_dry_run",
        "discovery": discovery,
        "selection": sources,
        "known_originals_at_start": len(known),
        "originals": stored,
        "failures": failures,
        "successful_original_count": len(successfully_captured),
        "new_learning_source_observations": sum(
            x["new_canonical_rows"] for x in stored
        ),
        "pending_actual_tender_agent_analysis": pending,
        "would_queue_if_captured": sorted(successfully_captured - analyzed)
        if not apply else [],
        "queue_state": "SOURCE_ONLY_PENDING_ACTUAL_ANALYSIS",
        "independent_chatgpt_evaluation_performed": False,
        "independent_tender_agent_evaluation_performed": False,
        "all_eis_new_procurements_autodiscovery": False,
        "fully_qualified_bid_go": 0,
        "training_gold_created": False,
        "all_requested_originals_captured": (
            not failures
            and all(x["status"] == "OK" for x in discovery["indexes"])
            and eis_status["status"] in {"OK", "DISABLED"}
        ),
        "external_customer_or_etp_actions": False,
    }


def load_policy(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 10_000:
        raise PipelineError("policy missing or oversized")
    def no_dupes(pairs):
        out = {}
        for key, val in pairs:
            if key in out:
                raise PipelineError("duplicate policy key")
            out[key] = val
        return out
    return validate_policy(json.loads(path.read_text(), object_pairs_hook=no_dupes))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, default=POLICY)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-database", choices=["arvectum"])
    args = parser.parse_args()
    if args.apply and args.confirm_database != "arvectum":
        parser.error("apply requires --confirm-database arvectum")
    config = load_policy(args.policy)
    # Dry-run intentionally still reads canonical DB source IDs, never mutates
    # it. If DB unavailable, fail closed instead of recrawling all old tenders.
    with single_runner():
        engine = create_engine(_engine_url(), future=True)
        try:
            with Session(engine) as db:
                known, analyzed = recorded_source_refs(db)
                db.rollback()
            backup = fresh_pg_backup() if args.apply else None
            result = run(
                config, known=known, analyzed=analyzed,
                apply=args.apply, backup_verified=bool(backup),
            )
            if backup is not None:
                result["prewrite_backup"] = backup
                receipt = save_private_receipt(result)
                result["owner_private_cycle_receipt"] = str(receipt)
        finally:
            engine.dispose()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 2 if not result["all_requested_originals_captured"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
