"""Explicit opt-in, bounded Tender Agent receipt reconciler.

No daemon or production scheduler is automatically installed. Each cycle
reconciles only tenders already admitted to the durable receipt journal.
"""

from __future__ import annotations

import argparse
import logging
import time

from sqlalchemy import case, create_engine, func, select
from sqlalchemy.orm import Session

from src.shared.config.settings import get_settings
from src.shared.data_platform import DataPlatformError
from src.shared.db.base import Base
from src.tender_research.config import load_config
from src.tender_research.models import TenderAsyncIndexReceipt
from src.tender_research.rag.data_platform import build_data_platform_client
from src.tender_research.rag.durable_async import DurableTenderAsyncIndex
from src.tender_research.repository import TenderRepository

logger = logging.getLogger(__name__)


def run_one_cycle(
    repo: TenderRepository,
    client,
    *,
    batch_size: int = 8,
    minimum_async_chunks: int = 9,
    max_tenders: int = 4,
) -> dict[str, int]:
    """Progress at most max_tenders with one <=batch_size wave each."""
    if not 1 <= max_tenders <= 16:
        raise ValueError("max_tenders must be 1..16")
    ids = list(
        repo._session.scalars(
            select(TenderAsyncIndexReceipt.tender_id)
            .group_by(
                TenderAsyncIndexReceipt.tender_id, TenderAsyncIndexReceipt.collection_id
            )
            .having(
                (func.count() < func.max(TenderAsyncIndexReceipt.expected_chunks))
                | (
                    func.sum(
                        case(
                            (TenderAsyncIndexReceipt.status != "completed", 1), else_=0
                        )
                    )
                    > 0
                )
            )
            .order_by(TenderAsyncIndexReceipt.tender_id)
            .limit(max_tenders)
        )
    )
    stats = {"tenders_seen": 0, "ready": 0, "waiting": 0, "failed": 0}
    for tender_id in ids:
        stats["tenders_seen"] += 1
        try:
            progress = DurableTenderAsyncIndex(
                repo,
                client,
                minimum_async_chunks=minimum_async_chunks,
                batch_size=batch_size,
            ).advance(tender_id)
            stats["ready" if progress.ready else "waiting"] += 1
        except (DataPlatformError, ValueError):
            # A failed SQL flush or remote exception must not leave an aborted
            # transaction poisoning subsequent independent tender cycles.
            repo._session.rollback()
            stats["failed"] += 1
            logger.warning(
                "Background Tender Agent index cycle failed (type-only reason)"
            )
            # Fail closed; do not acknowledge unfinished work, suppress errors
            # as successes, or loop without delay. The caller sees failed count.
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-worker", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--loop", action="store_true")
    args = parser.parse_args()
    if not args.allow_worker or args.once == args.loop:
        parser.error(
            "explicit --allow-worker and exactly one of --once/--loop required"
        )
    settings = get_settings()
    if not settings.rag_async_ingest_enabled:
        parser.error("background Tender Agent ingest flag is disabled")
    config = load_config(settings)
    engine = create_engine(settings.database_url)
    # Never create schema implicitly in a worker. Requires reviewed migration.
    if TenderAsyncIndexReceipt.__tablename__ not in Base.metadata.tables:
        parser.error("durable receipt registry unavailable")
    try:
        with build_data_platform_client(config) as client:
            if not callable(getattr(client, "enqueue_ingest_document_bytes", None)):
                parser.error("updated Data Platform SDK not installed")
            while True:
                # Never sleep with an open SQLAlchemy transaction or stale
                # identity map; release it after EACH reconciliation cycle.
                with Session(engine) as session:
                    repo = TenderRepository(session)
                    result = run_one_cycle(
                        repo,
                        client,
                        batch_size=config.rag_async_ingest_batch_size,
                        minimum_async_chunks=config.rag_async_ingest_min_chunks,
                    )
                print(
                    "tenders_seen={tenders_seen} ready={ready} waiting={waiting} "
                    "failed={failed}".format(**result),
                    flush=True,
                )
                if args.once:
                    if result["failed"]:
                        raise SystemExit(2)
                    return
                time.sleep(5)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
