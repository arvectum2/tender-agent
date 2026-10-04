from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.knowledge_assets.models import (
    KnowledgeAssetLink,
    KnowledgeAssetRecord,
    KnowledgeAssetSet,
)
from src.shared.config.settings import get_settings
from src.shared.data_platform import DataPlatformHttpClient
from src.shared.errors import ConflictError, NotFoundError

_COLLECTION_PREFIX = "arvectum-os:knowledge"
_ASSET_URI_PREFIX = "arvectum-os-knowledge://"


@dataclass(frozen=True)
class KnowledgeAssetIndexSummary:
    collection_id: str
    records_seen: int
    records_indexed: int
    chunks_created: int
    embeddings_created: int


@dataclass(frozen=True)
class KnowledgeAssetSearchHit:
    knowledge_asset_id: str
    asset_title: str
    asset_type: str
    summary_text: str
    score: float
    source_refs: tuple[str, ...]


def build_data_platform_client() -> DataPlatformHttpClient:
    settings = get_settings()
    return DataPlatformHttpClient(
        base_url=settings.rag_data_platform_base_url,
        api_key=settings.rag_data_platform_api_key,
        timeout_seconds=settings.rag_data_platform_timeout_seconds,
    )


def _records_for_deal(
    session: Session,
    deal_id: str,
) -> list[KnowledgeAssetRecord]:
    return list(
        session.scalars(
            select(KnowledgeAssetRecord)
            .join(
                KnowledgeAssetSet,
                KnowledgeAssetSet.knowledge_asset_set_id
                == KnowledgeAssetRecord.knowledge_asset_set_id,
            )
            .where(KnowledgeAssetSet.deal_id == deal_id)
            .order_by(
                KnowledgeAssetRecord.created_at.asc(),
                KnowledgeAssetRecord.knowledge_asset_id.asc(),
            )
        )
    )


def _links_for_asset(
    session: Session,
    knowledge_asset_id: str,
) -> tuple[str, ...]:
    return tuple(
        session.scalars(
            select(KnowledgeAssetLink.source_ref)
            .where(KnowledgeAssetLink.knowledge_asset_id == knowledge_asset_id)
            .order_by(KnowledgeAssetLink.created_at.asc(), KnowledgeAssetLink.id.asc())
        )
    )


def _asset_type_value(record: KnowledgeAssetRecord) -> str:
    value = getattr(record.asset_type, "value", record.asset_type)
    return str(value)


def render_knowledge_asset(record: KnowledgeAssetRecord) -> str:
    payload = json.dumps(
        record.asset_payload_json or {},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "\n".join(
        [
            record.asset_title.strip(),
            f"asset_type: {_asset_type_value(record)}",
            record.summary_text.strip(),
            f"payload: {payload}",
        ]
    ).strip()


def build_knowledge_collection_id(
    deal_id: str,
    records: list[KnowledgeAssetRecord],
) -> str:
    if not records:
        raise NotFoundError(f"No knowledge assets found for deal '{deal_id}'")
    revision_input = "\n".join(
        f"{record.knowledge_asset_id}:{hashlib.sha256(render_knowledge_asset(record).encode('utf-8')).hexdigest()}"
        for record in sorted(records, key=lambda item: item.knowledge_asset_id)
    )
    revision = hashlib.sha256(revision_input.encode("utf-8")).hexdigest()[:16]
    return f"{_COLLECTION_PREFIX}:{deal_id}:{revision}"


def _asset_uri(knowledge_asset_id: str) -> str:
    return f"{_ASSET_URI_PREFIX}{knowledge_asset_id}"


def _asset_id_from_uri(uri: str) -> str | None:
    if not uri.startswith(_ASSET_URI_PREFIX):
        return None
    value = uri[len(_ASSET_URI_PREFIX) :].strip()
    return value or None


def index_knowledge_assets(
    session: Session,
    *,
    deal_id: str,
    client: DataPlatformHttpClient | None = None,
) -> KnowledgeAssetIndexSummary:
    records = _records_for_deal(session, deal_id)
    collection_id = build_knowledge_collection_id(deal_id, records)
    owns_client = client is None
    runtime_client = client or build_data_platform_client()
    try:
        runtime_client.ensure_collection(
            collection_id=collection_id,
            owner="arvectum-os",
            name=f"Arvectum OS knowledge for {deal_id}",
        )
        chunks_created = 0
        embeddings_created = 0
        for record in records:
            result = runtime_client.ingest_document(
                collection_id=collection_id,
                canonical_uri=_asset_uri(record.knowledge_asset_id),
                title=record.asset_title,
                text=render_knowledge_asset(record),
                filename=f"{record.knowledge_asset_id}.txt",
                pre_chunked=True,
            )
            chunks_created += int(result.get("chunks", 0) or 0)
            embeddings_created += int(result.get("embeddings", 0) or 0)
        return KnowledgeAssetIndexSummary(
            collection_id=collection_id,
            records_seen=len(records),
            records_indexed=len(records),
            chunks_created=chunks_created,
            embeddings_created=embeddings_created,
        )
    finally:
        if owns_client:
            runtime_client.close()


def search_knowledge_assets(
    session: Session,
    *,
    deal_id: str,
    query: str,
    limit: int = 10,
    client: DataPlatformHttpClient | None = None,
) -> tuple[str, list[KnowledgeAssetSearchHit]]:
    records = _records_for_deal(session, deal_id)
    collection_id = build_knowledge_collection_id(deal_id, records)
    records_by_id = {record.knowledge_asset_id: record for record in records}
    owns_client = client is None
    runtime_client = client or build_data_platform_client()
    try:
        if not runtime_client.collection_exists(collection_id):
            raise ConflictError(
                f"Knowledge index for deal '{deal_id}' is not prepared for the current revision"
            )
        raw_hits = runtime_client.search(
            query=query,
            collections=[collection_id],
            limit=max(limit * 2, limit),
            mode="hybrid",
        )
        hits: list[KnowledgeAssetSearchHit] = []
        seen: set[str] = set()
        for raw in raw_hits:
            asset_id = _asset_id_from_uri(str(raw.get("canonical_uri") or ""))
            if not asset_id or asset_id in seen:
                continue
            record = records_by_id.get(asset_id)
            if record is None:
                continue
            scores = raw.get("scores")
            score = (
                float(scores.get("fusion", 0.0))
                if isinstance(scores, dict)
                else 0.0
            )
            hits.append(
                KnowledgeAssetSearchHit(
                    knowledge_asset_id=record.knowledge_asset_id,
                    asset_title=record.asset_title,
                    asset_type=_asset_type_value(record),
                    summary_text=record.summary_text,
                    score=score,
                    source_refs=_links_for_asset(session, record.knowledge_asset_id),
                )
            )
            seen.add(asset_id)
            if len(hits) >= limit:
                break
        return collection_id, hits
    finally:
        if owns_client:
            runtime_client.close()
