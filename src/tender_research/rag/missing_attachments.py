"""Restore an empty public EIS 44-FZ attachment inventory, not a new revision."""

from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qs, urlsplit

from src.tender_research.providers.public_44fz_search import Public44FzSearchProvider


def _official_url(url: str, *, registry: str | None = None) -> bool:
    parsed = urlsplit(url)
    return (
        parsed.scheme == "https"
        and parsed.hostname == "zakupki.gov.ru"
        and parsed.username is None
        and parsed.password is None
        and parsed.port in (None, 443)
        and (registry is None or parse_qs(parsed.query).get("regNumber") == [registry])
    )


def recover_missing_attachments(repo, tender, *, provider=None) -> int:
    """Register only a verified full active revision on a previously empty card.

    Caller owns transaction and storage gate. Existing rows and prior card
    payload stay unchanged. A source error must not be treated as empty success.
    """
    if tender.source != "eis" or tender.law_type != "44fz" or tender.documents:
        return 0
    registry = str(tender.registry_number or "")
    raw = tender.raw_payload
    if not re.fullmatch(r"\d{19}", registry) or not isinstance(raw, dict):
        return 0
    prior = raw.get("public_detail")
    if not isinstance(prior, dict) or prior.get("network_status") == "success":
        return 0
    card = prior.get("card_url")
    if not isinstance(card, str) or not _official_url(card, registry=registry):
        raise ValueError("missing attachment recovery: unbound card URL")
    detail = (provider or Public44FzSearchProvider(bypass_proxy=True)).fetch_detail(
        registry_number=registry, card_url=card
    )
    selection = detail.raw.get("document_revision_selection") or {}
    revision = detail.active_revision
    if (
        detail.registry_number != registry
        or detail.law_type != "44fz"
        or detail.network_status != "success"
        or detail.raw.get("documents_fetch_status") != "success"
        or selection.get("status") != "active_revision_selected"
        or selection.get("requires_review") is not False
        or revision is None
        or revision.active is not True
        or not isinstance(revision.revision, int)
        or revision.revision <= 0
        or not revision.publication_timestamp
        or not revision.source_url
        or not _official_url(revision.source_url, registry=registry)
        or not detail.documents_html
        or not detail.document_links
        or detail.document_links != revision.document_links
    ):
        raise ValueError("missing attachment recovery: active revision not proven")
    rows = []
    ids = set()
    for link in detail.document_links:
        name = link.file_name or link.title
        identity = str((link.raw or {}).get("uid") or link.url)
        if (
            not name
            or not _official_url(link.url)
            or not identity
            or identity.casefold() in ids
        ):
            raise ValueError(
                "missing attachment recovery: invalid or duplicate document"
            )
        ids.add(identity.casefold())
        rows.append(
            {
                "tender_id": tender.id,
                "source_document_id": identity,
                "file_name": name,
                "file_url": link.url,
                "content_type": link.content_type,
                "size_bytes": link.size_bytes,
                "raw_meta": {
                    "source": "external_public_44fz_detail",
                    "card_url": card,
                    "revision": revision.revision,
                    "revision_publication_timestamp": revision.publication_timestamp,
                    "revision_source_url": revision.source_url,
                    "documents_html_sha256": hashlib.sha256(
                        detail.documents_html.encode("utf-8")
                    ).hexdigest(),
                    "raw": link.raw,
                },
            }
        )
    # All links validated before any write. Lock and recheck emptiness to avoid
    # racing another writer that populated the inventory during the fetch.
    from sqlalchemy import select

    from src.tender_research.models import ProcurementTender, ProcurementTenderDocument

    session = repo._session
    session.execute(
        select(ProcurementTender.id)
        .where(ProcurementTender.id == tender.id)
        .with_for_update()
    ).scalar_one()
    if session.execute(
        select(ProcurementTenderDocument.id)
        .where(ProcurementTenderDocument.tender_id == tender.id)
        .limit(1)
    ).first():
        return 0
    with session.begin_nested():
        for row in rows:
            repo.upsert_document(row)
    session.expire(tender, ["documents"])
    return len(rows)
