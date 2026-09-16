from __future__ import annotations

import hashlib
import json
import re as _re
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from src.tender_research.errors import DocumentIdentityConflictError
from src.tender_research.models import (
    ProcurementCustomer,
    ProcurementDocumentChunk,
    ProcurementDocumentEmbedding,
    ProcurementRawArtifact,
    ProcurementTender,
    ProcurementTenderDocument,
    ProcurementTenderSearchQuery,
    ProcurementWebPage,
    ProcurementWebSearchResult,
)


def _revision_identity(raw_meta: dict | None) -> str | None:
    if not isinstance(raw_meta, dict):
        return None
    payload = {
        "revision": raw_meta.get("revision"),
        "publication_timestamp": raw_meta.get("revision_publication_timestamp")
        or raw_meta.get("publication_timestamp"),
        "source_url": raw_meta.get("revision_source_url") or raw_meta.get("source_url"),
    }
    if not any(value not in (None, "") for value in payload.values()):
        return None
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _revision_scopes_equivalent(left: dict | None, right: dict | None) -> bool:
    left_identity = _revision_identity(left)
    right_identity = _revision_identity(right)
    if left_identity is None and right_identity is None:
        return True
    return left_identity is not None and left_identity == right_identity


class TenderRepository:
    def __init__(self, session: Session):
        self._session = session

    # ── ProcurementTender ──

    def upsert_tender(self, data: dict) -> ProcurementTender:
        source = data["source"]
        external_id = data["external_id"]
        existing = self._session.execute(
            select(ProcurementTender).where(
                ProcurementTender.source == source,
                ProcurementTender.external_id == external_id,
            )
        ).scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if existing:
            update_data = {}
            for key in ("title", "description", "customer_name", "customer_inn", "customer_kpp",
                        "region", "platform_name", "platform_url", "eis_url", "nmck_amount",
                        "currency", "publication_date", "application_deadline", "auction_date",
                        "status", "law_type", "registry_number", "purchase_number"):
                if key in data:
                    update_data[key] = data[key]
            if "raw_payload" in data:
                update_data["raw_payload"] = data["raw_payload"]
            if "content_hash" in data:
                update_data["content_hash"] = data["content_hash"]
            update_data["last_seen_at"] = now
            update_data["updated_at"] = now
            self._session.execute(
                update(ProcurementTender).where(
                    ProcurementTender.source == source,
                    ProcurementTender.external_id == external_id,
                ).values(**update_data)
            )
            self._session.flush()
            self._session.refresh(existing)
            return existing
        tender = ProcurementTender(
            source=source,
            external_id=external_id,
            registry_number=data.get("registry_number"),
            purchase_number=data.get("purchase_number"),
            law_type=data.get("law_type"),
            title=data["title"],
            description=data.get("description"),
            customer_name=data.get("customer_name"),
            customer_inn=data.get("customer_inn"),
            customer_kpp=data.get("customer_kpp"),
            region=data.get("region"),
            platform_name=data.get("platform_name"),
            platform_url=data.get("platform_url"),
            eis_url=data.get("eis_url"),
            nmck_amount=data.get("nmck_amount"),
            currency=data.get("currency"),
            publication_date=data.get("publication_date"),
            application_deadline=data.get("application_deadline"),
            auction_date=data.get("auction_date"),
            status=data.get("status"),
            raw_payload=data.get("raw_payload"),
            content_hash=data.get("content_hash"),
            first_seen_at=now,
            last_seen_at=now,
        )
        self._session.add(tender)
        self._session.flush()
        return tender

    def get_tender_by_id(self, tender_id: str) -> ProcurementTender | None:
        return self._session.get(ProcurementTender, tender_id)

    def get_tender_by_external(self, source: str, external_id: str) -> ProcurementTender | None:
        return self._session.execute(
            select(ProcurementTender).where(
                ProcurementTender.source == source,
                ProcurementTender.external_id == external_id,
            )
        ).scalar_one_or_none()

    def list_tenders(self, limit: int = 100, offset: int = 0) -> list[ProcurementTender]:
        return list(self._session.execute(
            select(ProcurementTender).order_by(ProcurementTender.created_at.desc()).limit(limit).offset(offset)
        ).scalars().all())

    def count_tenders(self) -> int:
        return self._session.execute(select(func.count(ProcurementTender.id))).scalar() or 0

    def count_tenders_with_customer(self) -> int:
        return self._session.execute(
            select(func.count(ProcurementTender.id)).where(ProcurementTender.customer_name.is_not(None))
        ).scalar() or 0

    def count_tenders_with_publication_date(self) -> int:
        return self._session.execute(
            select(func.count(ProcurementTender.id)).where(ProcurementTender.publication_date.is_not(None))
        ).scalar() or 0

    def count_tenders_with_nmck(self) -> int:
        return self._session.execute(
            select(func.count(ProcurementTender.id)).where(ProcurementTender.nmck_amount.is_not(None))
        ).scalar() or 0

    def count_tenders_with_real_title(self) -> int:
        return self._session.execute(
            select(func.count(ProcurementTender.id)).where(
                ProcurementTender.title.is_not(None),
                ~ProcurementTender.title.like("Закупка %"),
            )
        ).scalar() or 0

    def count_placeholder_titles(self) -> int:
        return self._session.execute(
            select(func.count(ProcurementTender.id)).where(
                ProcurementTender.title.like("Закупка %")
            )
        ).scalar() or 0

    def list_placeholder_tenders(
        self,
        limit: int = 50,
        only_placeholders: bool = True,
        days_back: int | None = None,
    ) -> list[ProcurementTender]:
        query = select(ProcurementTender).where(
            ProcurementTender.source == "eis",
            ProcurementTender.registry_number.is_not(None),
        )
        if only_placeholders:
            query = query.where(
                (ProcurementTender.title.is_(None)) | (ProcurementTender.title.like("Закупка %"))
            )
        else:
            query = query.where(
                (ProcurementTender.title.is_(None))
                | (ProcurementTender.title.like("Закупка %"))
                | (ProcurementTender.customer_name.is_(None))
                | (ProcurementTender.publication_date.is_(None))
                | (ProcurementTender.nmck_amount.is_(None))
            )
        if days_back is not None:
            threshold = datetime.now(timezone.utc) - timedelta(days=days_back)
            query = query.where(ProcurementTender.last_seen_at >= threshold)
        query = query.order_by(ProcurementTender.updated_at.asc()).limit(limit)
        return list(self._session.execute(query).scalars().all())

    # ── ProcurementCustomer ──

    def upsert_customer(self, data: dict) -> ProcurementCustomer:
        inn = data.get("inn")
        kpp = data.get("kpp")
        normalized_name = _normalize_customer_name(data.get("name", ""))
        existing = None
        if inn and kpp:
            existing = self._session.execute(
                select(ProcurementCustomer).where(
                    ProcurementCustomer.inn == inn,
                    ProcurementCustomer.kpp == kpp,
                )
            ).scalar_one_or_none()
        elif normalized_name:
            query = select(ProcurementCustomer).where(
                ProcurementCustomer.normalized_name == normalized_name,
            )
            region = data.get("region")
            if region:
                query = query.where(
                    (ProcurementCustomer.region == region) | (ProcurementCustomer.region.is_(None))
                )
            existing = self._session.execute(query).scalars().first()
        now = datetime.now(timezone.utc)
        if existing:
            existing.last_seen_at = now
            existing.tenders_count += 1
            if "name" in data:
                existing.name = data["name"]
                existing.normalized_name = normalized_name
            if "region" in data:
                existing.region = data["region"]
            if "raw_last_payload" in data:
                existing.raw_last_payload = data["raw_last_payload"]
            existing.updated_at = now
            self._session.flush()
            self._session.refresh(existing)
            return existing
        customer = ProcurementCustomer(
            name=data.get("name", ""),
            inn=inn,
            kpp=kpp,
            region=data.get("region"),
            normalized_name=normalized_name,
            first_seen_at=now,
            last_seen_at=now,
            tenders_count=1,
            raw_last_payload=data.get("raw_last_payload"),
        )
        self._session.add(customer)
        self._session.flush()
        return customer

    def count_customers(self) -> int:
        return self._session.execute(select(func.count(ProcurementCustomer.id))).scalar() or 0

    # ── ProcurementTenderDocument ──

    def _compute_identity_hash(self, tender_id: str, data: dict) -> tuple[str | None, str | None]:
        source_document_id = data.get("source_document_id")
        file_url = data.get("file_url")
        file_name = data.get("file_name")
        size_bytes = data.get("size_bytes")
        content_type = data.get("content_type")
        raw_meta = data.get("raw_meta")
        revision_identity = _revision_identity(raw_meta)

        if source_document_id:
            identity_source = "source_document_id"
            identity_value = source_document_id.strip().lower()
        elif file_url:
            identity_source = "file_url"
            identity_value = _normalize_url_for_dedup(file_url)
        elif file_name:
            identity_source = "file_name"
            parts = [file_name.strip().lower()]
            if size_bytes is not None:
                parts.append(str(size_bytes))
            if content_type:
                parts.append(content_type.strip().lower())
            identity_value = "|".join(parts)
        elif raw_meta:
            identity_source = "raw_meta"
            identity_value = hashlib.sha256(
                json.dumps(raw_meta, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest()
        else:
            return None, None

        if revision_identity is not None:
            identity_source = f"{identity_source}+revision"
            identity_value = f"{identity_value}|revision={revision_identity}"

        raw = f"{tender_id}|{identity_source}|{identity_value}"
        identity_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return identity_hash, identity_source

    def upsert_document(self, data: dict) -> ProcurementTenderDocument:
        tender_id = data["tender_id"]
        sha256 = data.get("sha256")
        identity_hash, identity_source = self._compute_identity_hash(tender_id, data)

        existing = None

        if identity_hash:
            existing = self._session.execute(
                select(ProcurementTenderDocument).where(
                    ProcurementTenderDocument.tender_id == tender_id,
                    ProcurementTenderDocument.document_identity_hash == identity_hash,
                )
            ).scalar_one_or_none()

        if not existing and sha256:
            existing_by_sha = self._session.execute(
                select(ProcurementTenderDocument).where(
                    ProcurementTenderDocument.tender_id == tender_id,
                    ProcurementTenderDocument.sha256 == sha256,
                )
            ).scalar_one_or_none()
            if existing_by_sha and not _revision_scopes_equivalent(existing_by_sha.raw_meta, data.get("raw_meta")):
                raise DocumentIdentityConflictError(
                    "Document content hash matches an existing row but revision provenance does not; "
                    "refusing to merge distinct or ambiguous source revisions"
                )
            existing = existing_by_sha
        elif existing and sha256:
            if existing.sha256 and existing.sha256 != sha256:
                raise DocumentIdentityConflictError(
                    "Stable document identity produced a different content hash; explicit reconciliation is required"
                )
            existing_by_sha = self._session.execute(
                select(ProcurementTenderDocument).where(
                    ProcurementTenderDocument.tender_id == tender_id,
                    ProcurementTenderDocument.sha256 == sha256,
                )
            ).scalar_one_or_none()
            if existing_by_sha and existing_by_sha.id != existing.id:
                if not _revision_scopes_equivalent(existing_by_sha.raw_meta, data.get("raw_meta")):
                    raise DocumentIdentityConflictError(
                        "Document SHA collision spans different revision provenance; refusing implicit merge"
                    )
                existing = self._merge_documents_by_sha(
                    canonical=existing_by_sha,
                    duplicate=existing,
                    data=data,
                    identity_hash=identity_hash,
                    identity_source=identity_source,
                    sha256=sha256,
                )
                self._session.flush()
                return existing

        if existing:
            if existing.sha256 and sha256 and existing.sha256 != sha256:
                raise DocumentIdentityConflictError(
                    "Existing source document changed content without a distinct revision identity"
                )
            self._apply_document_update(
                existing,
                data,
                identity_hash=identity_hash,
                identity_source=identity_source,
                sha256=sha256,
            )
            self._session.flush()
            return existing

        doc = ProcurementTenderDocument(
            tender_id=tender_id,
            source_document_id=data.get("source_document_id"),
            file_name=data["file_name"],
            file_url=data.get("file_url"),
            local_path=data.get("local_path"),
            content_type=data.get("content_type"),
            size_bytes=data.get("size_bytes"),
            sha256=sha256,
            document_identity_hash=identity_hash,
            document_identity_source=identity_source,
            download_status=data.get("download_status", "pending"),
            text_extraction_status=data.get("text_extraction_status", "pending"),
            extracted_text_path=data.get("extracted_text_path"),
            extracted_text_chars=data.get("extracted_text_chars"),
            raw_meta=data.get("raw_meta"),
            error_message=data.get("error_message"),
        )
        self._session.add(doc)
        self._session.flush()
        return doc

    def _apply_document_update(
        self,
        doc: ProcurementTenderDocument,
        data: dict,
        *,
        identity_hash: str | None,
        identity_source: str | None,
        sha256: str | None,
    ) -> None:
        for key in (
            "local_path",
            "download_status",
            "text_extraction_status",
            "extracted_text_path",
            "extracted_text_chars",
            "error_message",
            "source_document_id",
            "file_name",
            "file_url",
            "content_type",
            "size_bytes",
            "raw_meta",
        ):
            if key in data:
                setattr(doc, key, data[key])
        if identity_hash:
            doc.document_identity_hash = identity_hash
            doc.document_identity_source = identity_source
        if sha256:
            doc.sha256 = sha256
        doc.updated_at = datetime.now(timezone.utc)

    def _merge_documents_by_sha(
        self,
        *,
        canonical: ProcurementTenderDocument,
        duplicate: ProcurementTenderDocument,
        data: dict,
        identity_hash: str | None,
        identity_source: str | None,
        sha256: str,
    ) -> ProcurementTenderDocument:
        if not canonical.source_document_id and duplicate.source_document_id:
            canonical.source_document_id = duplicate.source_document_id
        if not canonical.file_name and duplicate.file_name:
            canonical.file_name = duplicate.file_name
        if not canonical.file_url and duplicate.file_url:
            canonical.file_url = duplicate.file_url
        if not canonical.content_type and duplicate.content_type:
            canonical.content_type = duplicate.content_type
        if canonical.size_bytes is None and duplicate.size_bytes is not None:
            canonical.size_bytes = duplicate.size_bytes
        if not canonical.local_path and duplicate.local_path:
            canonical.local_path = duplicate.local_path
        if not canonical.extracted_text_path and duplicate.extracted_text_path:
            canonical.extracted_text_path = duplicate.extracted_text_path
        if canonical.extracted_text_chars is None and duplicate.extracted_text_chars is not None:
            canonical.extracted_text_chars = duplicate.extracted_text_chars
        if not canonical.raw_meta and duplicate.raw_meta:
            canonical.raw_meta = duplicate.raw_meta
        if (
            canonical.download_status in {"pending", "skipped", "failed"}
            and duplicate.download_status == "downloaded"
        ):
            canonical.download_status = duplicate.download_status
        if (
            canonical.text_extraction_status in {"pending", "failed"}
            and duplicate.text_extraction_status in {"extracted", "empty", "unsupported"}
        ):
            canonical.text_extraction_status = duplicate.text_extraction_status
        if not canonical.error_message and duplicate.error_message:
            canonical.error_message = duplicate.error_message
        if identity_hash and not canonical.document_identity_hash:
            canonical.document_identity_hash = identity_hash
            canonical.document_identity_source = identity_source
        canonical.sha256 = sha256
        self._session.delete(duplicate)
        self._apply_document_update(
            canonical,
            data,
            identity_hash=canonical.document_identity_hash or identity_hash,
            identity_source=canonical.document_identity_source or identity_source,
            sha256=sha256,
        )
        return canonical

    def count_documents(self) -> int:
        return self._session.execute(select(func.count(ProcurementTenderDocument.id))).scalar() or 0

    def count_documents_by_status(self, status: str) -> int:
        return self._session.execute(
            select(func.count(ProcurementTenderDocument.id)).where(
                ProcurementTenderDocument.download_status == status
            )
        ).scalar() or 0

    def count_documents_by_text_status(self, status: str) -> int:
        return self._session.execute(
            select(func.count(ProcurementTenderDocument.id)).where(
                ProcurementTenderDocument.text_extraction_status == status
            )
        ).scalar() or 0

    def list_extracted_documents(self, limit: int = 100, offset: int = 0) -> list[ProcurementTenderDocument]:
        return list(
            self._session.execute(
                select(ProcurementTenderDocument)
                .where(
                    ProcurementTenderDocument.text_extraction_status == "extracted",
                    ProcurementTenderDocument.extracted_text_path.is_not(None),
                )
                .order_by(ProcurementTenderDocument.updated_at.asc())
                .limit(limit)
                .offset(offset)
            ).scalars().all()
        )

    def list_extracted_documents_by_tender(self, tender_id: str) -> list[ProcurementTenderDocument]:
        return list(
            self._session.execute(
                select(ProcurementTenderDocument)
                .where(
                    ProcurementTenderDocument.tender_id == tender_id,
                    ProcurementTenderDocument.text_extraction_status == "extracted",
                    ProcurementTenderDocument.extracted_text_path.is_not(None),
                )
                .order_by(ProcurementTenderDocument.file_name.asc())
            ).scalars().all()
        )

    def count_extracted_documents_by_tender(self, tender_id: str) -> int:
        return self._session.execute(
            select(func.count(ProcurementTenderDocument.id)).where(
                ProcurementTenderDocument.tender_id == tender_id,
                ProcurementTenderDocument.text_extraction_status == "extracted",
            )
        ).scalar() or 0

    # ── ProcurementDocumentChunk ──

    def upsert_document_chunk(self, data: dict) -> ProcurementDocumentChunk:
        document_id = data["document_id"]
        chunk_index = data["chunk_index"]
        text_hash = data["text_hash"]
        existing = self._session.execute(
            select(ProcurementDocumentChunk).where(
                ProcurementDocumentChunk.document_id == document_id,
                ProcurementDocumentChunk.chunk_index == chunk_index,
            )
        ).scalar_one_or_none()
        if not existing:
            existing = self._session.execute(
                select(ProcurementDocumentChunk).where(
                    ProcurementDocumentChunk.document_id == document_id,
                    ProcurementDocumentChunk.text_hash == text_hash,
                )
            ).scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if existing:
            for key in (
                "tender_id",
                "text",
                "text_hash",
                "char_start",
                "char_end",
                "token_estimate",
                "source_file_name",
                "source_text_path",
                "raw_meta",
            ):
                if key in data:
                    setattr(existing, key, data[key])
            existing.updated_at = now
            self._session.flush()
            return existing
        chunk = ProcurementDocumentChunk(
            tender_id=data["tender_id"],
            document_id=document_id,
            chunk_index=chunk_index,
            text=data["text"],
            text_hash=text_hash,
            char_start=data["char_start"],
            char_end=data["char_end"],
            token_estimate=data.get("token_estimate", 0),
            source_file_name=data.get("source_file_name"),
            source_text_path=data.get("source_text_path"),
            raw_meta=data.get("raw_meta"),
            created_at=now,
            updated_at=now,
        )
        self._session.add(chunk)
        self._session.flush()
        return chunk

    def count_document_chunks(self) -> int:
        return self._session.execute(select(func.count(ProcurementDocumentChunk.id))).scalar() or 0

    def list_document_chunks(self, document_id: str) -> list[ProcurementDocumentChunk]:
        return list(
            self._session.execute(
                select(ProcurementDocumentChunk)
                .where(ProcurementDocumentChunk.document_id == document_id)
                .order_by(ProcurementDocumentChunk.chunk_index.asc())
            ).scalars().all()
        )

    def list_chunks_without_embeddings(
        self,
        *,
        provider: str,
        model: str,
        limit: int = 1000,
    ) -> list[ProcurementDocumentChunk]:
        emb_exists = (
            select(ProcurementDocumentEmbedding.id)
            .where(
                ProcurementDocumentEmbedding.chunk_id == ProcurementDocumentChunk.id,
                ProcurementDocumentEmbedding.provider == provider,
                ProcurementDocumentEmbedding.model == model,
            )
            .exists()
        )
        return list(
            self._session.execute(
                select(ProcurementDocumentChunk)
                .where(~emb_exists)
                .order_by(ProcurementDocumentChunk.created_at.asc())
                .limit(limit)
            ).scalars().all()
        )

    def get_document_chunk(self, chunk_id: str) -> ProcurementDocumentChunk | None:
        return self._session.get(ProcurementDocumentChunk, chunk_id)

    def list_chunks_by_tender(self, tender_id: str) -> list[ProcurementDocumentChunk]:
        return list(
            self._session.execute(
                select(ProcurementDocumentChunk)
                .where(ProcurementDocumentChunk.tender_id == tender_id)
                .order_by(ProcurementDocumentChunk.created_at.asc())
            ).scalars().all()
        )

    def count_chunks_by_tender(self, tender_id: str) -> int:
        return self._session.execute(
            select(func.count(ProcurementDocumentChunk.id)).where(
                ProcurementDocumentChunk.tender_id == tender_id
            )
        ).scalar() or 0

    # ── ProcurementDocumentEmbedding ──

    def upsert_document_embedding(self, data: dict) -> ProcurementDocumentEmbedding:
        chunk_id = data["chunk_id"]
        provider = data["provider"]
        model = data["model"]
        existing = self._session.execute(
            select(ProcurementDocumentEmbedding).where(
                ProcurementDocumentEmbedding.chunk_id == chunk_id,
                ProcurementDocumentEmbedding.provider == provider,
                ProcurementDocumentEmbedding.model == model,
            )
        ).scalar_one_or_none()
        if existing:
            for key in ("dimension", "vector_id", "embedding_path", "embedding_hash"):
                if key in data:
                    setattr(existing, key, data[key])
            self._session.flush()
            return existing
        embedding = ProcurementDocumentEmbedding(
            chunk_id=chunk_id,
            provider=provider,
            model=model,
            dimension=data["dimension"],
            vector_id=data.get("vector_id"),
            embedding_path=data.get("embedding_path"),
            embedding_hash=data.get("embedding_hash"),
        )
        self._session.add(embedding)
        self._session.flush()
        return embedding

    def count_document_embeddings(self, provider: str | None = None, model: str | None = None) -> int:
        stmt = select(func.count(ProcurementDocumentEmbedding.id))
        if provider is not None:
            stmt = stmt.where(ProcurementDocumentEmbedding.provider == provider)
        if model is not None:
            stmt = stmt.where(ProcurementDocumentEmbedding.model == model)
        return self._session.execute(stmt).scalar() or 0

    def count_embeddings_by_tender(self, provider: str, model: str, tender_id: str) -> int:
        return self._session.execute(
            select(func.count(ProcurementDocumentEmbedding.id))
            .join(ProcurementDocumentChunk, ProcurementDocumentChunk.id == ProcurementDocumentEmbedding.chunk_id)
            .where(
                ProcurementDocumentChunk.tender_id == tender_id,
                ProcurementDocumentEmbedding.provider == provider,
                ProcurementDocumentEmbedding.model == model,
            )
        ).scalar() or 0

    def list_document_embeddings(
        self,
        *,
        provider: str,
        model: str,
        chunk_ids: list[str] | None = None,
    ) -> list[ProcurementDocumentEmbedding]:
        stmt = select(ProcurementDocumentEmbedding).where(
            ProcurementDocumentEmbedding.provider == provider,
            ProcurementDocumentEmbedding.model == model,
        )
        if chunk_ids is not None:
            if not chunk_ids:
                return []
            stmt = stmt.where(ProcurementDocumentEmbedding.chunk_id.in_(chunk_ids))
        return list(self._session.execute(stmt).scalars().all())

    def get_tender_by_registry_number(self, registry_number: str) -> ProcurementTender | None:
        return self._session.execute(
            select(ProcurementTender).where(ProcurementTender.registry_number == registry_number)
        ).scalar_one_or_none()

    def list_chunk_ids_for_filters(
        self,
        *,
        tender_id: str | None = None,
        registry_number: str | None = None,
        customer_name: str | None = None,
    ) -> list[str]:
        stmt = (
            select(ProcurementDocumentChunk.id)
            .join(ProcurementTenderDocument, ProcurementTenderDocument.id == ProcurementDocumentChunk.document_id)
            .join(ProcurementTender, ProcurementTender.id == ProcurementDocumentChunk.tender_id)
        )
        if tender_id is not None:
            stmt = stmt.where(ProcurementDocumentChunk.tender_id == tender_id)
        if registry_number is not None:
            stmt = stmt.where(ProcurementTender.registry_number == registry_number)
        if customer_name is not None:
            stmt = stmt.where(
                ProcurementTender.customer_name.is_not(None),
                func.lower(ProcurementTender.customer_name).like(f"%{customer_name.lower()}%"),
            )
        return list(self._session.execute(stmt).scalars().all())

    def get_chunk_context(self, chunk_id: str) -> dict | None:
        row = self._session.execute(
            select(
                ProcurementDocumentChunk.id,
                ProcurementDocumentChunk.text,
                ProcurementDocumentChunk.chunk_index,
                ProcurementDocumentChunk.char_start,
                ProcurementDocumentChunk.char_end,
                ProcurementTenderDocument.file_name,
                ProcurementTenderDocument.id,
                ProcurementTender.id,
                ProcurementTender.registry_number,
                ProcurementTender.title,
                ProcurementTender.customer_name,
            )
            .join(ProcurementTenderDocument, ProcurementTenderDocument.id == ProcurementDocumentChunk.document_id)
            .join(ProcurementTender, ProcurementTender.id == ProcurementDocumentChunk.tender_id)
            .where(ProcurementDocumentChunk.id == chunk_id)
        ).first()
        if row is None:
            return None
        return {
            "chunk_id": row[0],
            "text": row[1],
            "chunk_index": row[2],
            "char_start": row[3],
            "char_end": row[4],
            "file_name": row[5],
            "document_id": row[6],
            "tender_id": row[7],
            "registry_number": row[8],
            "tender_title": row[9],
            "customer_name": row[10],
        }

    def list_top_customers(self, limit: int = 10) -> list[tuple[str, int]]:
        rows = self._session.execute(
            select(ProcurementCustomer.name, ProcurementCustomer.tenders_count)
            .order_by(ProcurementCustomer.tenders_count.desc(), ProcurementCustomer.name.asc())
            .limit(limit)
        ).all()
        return [(row[0], row[1]) for row in rows]

    # ── ProcurementTenderSearchQuery ──

    def upsert_search_query(self, data: dict) -> ProcurementTenderSearchQuery:
        tender_id = data["tender_id"]
        query = data["query"]
        provider = data["provider"]
        existing = self._session.execute(
            select(ProcurementTenderSearchQuery).where(
                ProcurementTenderSearchQuery.tender_id == tender_id,
                ProcurementTenderSearchQuery.provider == provider,
                ProcurementTenderSearchQuery.query == query,
            )
        ).scalar_one_or_none()
        if existing:
            if "status" in data:
                existing.status = data["status"]
            existing.results_count = data.get("results_count", existing.results_count)
            existing.error_message = data.get("error_message")
            if data.get("status") == "done":
                existing.executed_at = datetime.now(timezone.utc)
            self._session.flush()
            return existing
        sq = ProcurementTenderSearchQuery(
            tender_id=tender_id,
            query=query,
            query_type=data["query_type"],
            provider=provider,
            status=data.get("status", "pending"),
            results_count=data.get("results_count"),
            error_message=data.get("error_message"),
        )
        self._session.add(sq)
        self._session.flush()
        return sq

    def count_search_queries(self) -> int:
        return self._session.execute(select(func.count(ProcurementTenderSearchQuery.id))).scalar() or 0

    # ── ProcurementWebSearchResult ──

    def upsert_search_result(self, data: dict) -> ProcurementWebSearchResult:
        query_id = data["query_id"]
        url_hash_val = data["url_hash"]
        existing = self._session.execute(
            select(ProcurementWebSearchResult).where(
                ProcurementWebSearchResult.query_id == query_id,
                ProcurementWebSearchResult.url_hash == url_hash_val,
            )
        ).scalar_one_or_none()
        if existing:
            return existing
        sr = ProcurementWebSearchResult(
            tender_id=data["tender_id"],
            query_id=query_id,
            provider=data["provider"],
            rank=data["rank"],
            title=data["title"],
            url=data["url"],
            normalized_url=data["normalized_url"],
            snippet=data["snippet"],
            display_url=data.get("display_url"),
            raw_result=data.get("raw_result"),
            url_hash=url_hash_val,
        )
        self._session.add(sr)
        self._session.flush()
        return sr

    def count_search_results(self) -> int:
        return self._session.execute(select(func.count(ProcurementWebSearchResult.id))).scalar() or 0

    # ── ProcurementWebPage ──

    def upsert_web_page(self, data: dict) -> ProcurementWebPage:
        url_hash_val = data["url_hash"]
        existing = self._session.execute(
            select(ProcurementWebPage).where(ProcurementWebPage.url_hash == url_hash_val)
        ).scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if existing:
            for key in ("fetch_status", "http_status", "content_type", "final_url",
                        "html_path", "text_path", "extracted_title", "extracted_text_chars",
                        "raw_meta", "error_message", "fetched_at", "fetcher"):
                if key in data:
                    setattr(existing, key, data[key])
            existing.updated_at = now
            self._session.flush()
            return existing
        wp = ProcurementWebPage(
            tender_id=data.get("tender_id"),
            search_result_id=data.get("search_result_id"),
            url=data["url"],
            normalized_url=data["normalized_url"],
            url_hash=url_hash_val,
            fetcher=data.get("fetcher", "requests"),
            fetch_status=data.get("fetch_status", "pending"),
            http_status=data.get("http_status"),
            content_type=data.get("content_type"),
            final_url=data.get("final_url"),
            html_path=data.get("html_path"),
            text_path=data.get("text_path"),
            extracted_title=data.get("extracted_title"),
            extracted_text_chars=data.get("extracted_text_chars"),
            raw_meta=data.get("raw_meta", {}),
            error_message=data.get("error_message"),
            fetched_at=data.get("fetched_at"),
        )
        self._session.add(wp)
        self._session.flush()
        return wp

    def count_web_pages(self) -> int:
        return self._session.execute(select(func.count(ProcurementWebPage.id))).scalar() or 0

    def count_web_pages_by_status(self, status: str) -> int:
        return self._session.execute(
            select(func.count(ProcurementWebPage.id)).where(
                ProcurementWebPage.fetch_status == status
            )
        ).scalar() or 0

    # ── ProcurementRawArtifact ──

    def upsert_artifact(self, data: dict) -> ProcurementRawArtifact:
        sha256_val = data["sha256"]
        existing = self._session.execute(
            select(ProcurementRawArtifact).where(ProcurementRawArtifact.sha256 == sha256_val)
        ).scalar_one_or_none()
        if existing:
            return existing
        artifact = ProcurementRawArtifact(
            tender_id=data.get("tender_id"),
            artifact_type=data["artifact_type"],
            source=data["source"],
            local_path=data["local_path"],
            sha256=sha256_val,
            size_bytes=data["size_bytes"],
            content_type=data.get("content_type"),
            raw_meta=data.get("raw_meta"),
        )
        self._session.add(artifact)
        self._session.flush()
        return artifact

    def count_artifacts(self) -> int:
        return self._session.execute(select(func.count(ProcurementRawArtifact.id))).scalar() or 0

    # ── Search query listing ──

    def list_pending_search_queries(self, tender_id: str, provider: str) -> list[ProcurementTenderSearchQuery]:
        return list(self._session.execute(
            select(ProcurementTenderSearchQuery).where(
                ProcurementTenderSearchQuery.tender_id == tender_id,
                ProcurementTenderSearchQuery.provider == provider,
                ProcurementTenderSearchQuery.status == "pending",
            ).order_by(ProcurementTenderSearchQuery.created_at.asc())
        ).scalars().all())

    def list_search_results_for_tender(self, tender_id: str) -> list[ProcurementWebSearchResult]:
        return list(self._session.execute(
            select(ProcurementWebSearchResult).where(
                ProcurementWebSearchResult.tender_id == tender_id,
            ).order_by(ProcurementWebSearchResult.rank.asc())
        ).scalars().all())

    def list_unfetched_results(self, tender_id: str, max_results: int = 20) -> list[ProcurementWebSearchResult]:
        return list(self._session.execute(
            select(ProcurementWebSearchResult).where(
                ProcurementWebSearchResult.tender_id == tender_id,
                ~ProcurementWebSearchResult.id.in_(
                    select(ProcurementWebPage.search_result_id).where(
                        ProcurementWebPage.tender_id == tender_id,
                        ProcurementWebPage.search_result_id.isnot(None),
                    )
                ),
            ).limit(max_results)
        ).scalars().all())


_URL_TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
                        "ref", "referrer", "source", "mc_cid", "mc_eid", "fbclid", "gclid",
                        "yclid", "igshid"}


def _normalize_url_for_dedup(url: str) -> str:
    url = url.strip().lower()
    url = _re.sub(r"#.*$", "", url)
    if "?" in url:
        base, qs = url.split("?", 1)
        params = []
        for part in qs.split("&"):
            if "=" in part:
                key = part.split("=", 1)[0]
                if key not in _URL_TRACKING_PARAMS:
                    params.append(part)
            else:
                params.append(part)
        params.sort()
        url = f"{base}?{'&'.join(params)}" if params else base
    url = url.rstrip("/")
    while "//" in url.replace("://", "::"):
        url = url.replace("//", "/")
    url = url.replace("::", "://")
    return url


def _normalize_customer_name(name: str) -> str:
    cleaned = _re.sub(r"\s+", " ", name.strip().lower())
    for prefix in (
        'ооо', 'оао', 'зао', 'пао', 'ао', 'гоу', 'моу', 'фгуп', 'гуп',
        'гбу', 'гау', 'фгбоу', 'гбдоу', 'мадоу', 'мбдоу',
        '"', '«', '»',
    ):
        cleaned = cleaned.replace(prefix, "").strip()
    return _re.sub(r"\s+", " ", cleaned).strip()
