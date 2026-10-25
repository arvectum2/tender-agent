"""EIS binary-to-Data Platform trust boundaries and SDK API regression."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

import pytest

from src.modules.market_intelligence.eis_dp_ingest import (
    EISIndexError,
    TrustedTenant,
    ingest_original_eis_documents,
    procurement_collection,
)


class StubDP:
    def __init__(self, *, owner_override=None, policy_override=None,
                 bad_extraction=False):
        self.calls = []
        self.owner_override = owner_override
        self.policy_override = policy_override
        self.bad_extraction = bad_extraction

    def ensure_collection(self, **kwargs):
        self.calls.append(("ensure_collection", kwargs))
        return {
            "collection_id": kwargs["collection_id"],
            "owner": self.owner_override or kwargs["owner"],
            "access_policy": self.policy_override or kwargs["access_policy"],
        }

    def ingest_document_bytes(self, **kwargs):
        self.calls.append(("ingest_document_bytes", kwargs))
        return {
            "collection_id": kwargs["collection_id"],
            "canonical_uri": kwargs["canonical_uri"],
            "document_id": "dp-document-1",
            "resource_id": "dp-resource-1",
            "extraction_status": "empty" if self.bad_extraction else "extracted",
            "chunks_indexed": 2,
        }


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fixture(tmp_path: Path):
    number = "32313008364"
    notice = (
        b"<purchaseNoticeZKESMBO><body><item><purchaseNoticeZKESMBOData>"
        b"<registrationNumber>32313008364</registrationNumber>"
        b"<guid>9a0e2f63-460d-42a5-aa06-c808427aeedc</guid>"
        b"</purchaseNoticeZKESMBOData></item></body></purchaseNoticeZKESMBO>"
    )
    original_zip = tmp_path / "source-223.zip"
    with zipfile.ZipFile(original_zip, "w") as z:
        z.writestr("original-notice.xml", notice)
    original_zip_sha = _sha(original_zip.read_bytes())
    storage = tmp_path / "downloaded"
    storage.mkdir()
    content = b"PK\x03\x04synthetic-no-extraction; SDK stub accepts bytes"
    saved_name = "official-technical-document.docx"
    (storage / saved_name).write_bytes(content)
    receipt = {
        "registry_number": number, "status": "downloaded", "records": [{
            "status": "saved", "stored_name": saved_name,
            "extension": ".docx", "document_sha256": _sha(content),
            "source_xml_sha256": _sha(notice),
            "original_archive_sha256": original_zip_sha,
            "source_url_sha256": "a" * 64,
            "revision_requires_review": False,
        }],
    }
    return original_zip, original_zip_sha, storage, receipt


def _args(tmp_path: Path, *, tenant="tenant01", run="run01"):
    source, sha, storage, receipt = _fixture(tmp_path)
    collection = procurement_collection(tenant, run)
    return {
        "receipt": receipt,
        "source_archive": source,
        "original_archive_sha256": sha,
        "source_region": "77",
        "source_date": "2026-10-25",
        "subsystem": "RI223",
        "original_files_dir": storage,
        "trusted": TrustedTenant(
            tenant_id=tenant, consumer_id="market-intelligence",
            authorized_collection_ids=frozenset({collection}),
        ),
        "tenant_id": tenant, "run_id": run,
    }


def test_dry_run_only_checks_original_bytes_and_auth(tmp_path: Path):
    args = _args(tmp_path)
    client = StubDP()
    result = ingest_original_eis_documents(client, **args)
    assert client.calls == []
    assert result["indexing_executed"] is False
    assert result["validated_documents"] == 1
    assert result["source_archive_sha256"] == args["original_archive_sha256"]
    assert result["documents"][0]["index_status"] == "verified_not_indexed"
    assert result["winner_verified"] is False


def test_execute_uses_existing_tenant_acl_and_dp_ingest_bytes(tmp_path: Path):
    args = _args(tmp_path)
    client = StubDP()
    result = ingest_original_eis_documents(client, **args, execute=True)
    assert [x[0] for x in client.calls] == ["ensure_collection", "ingest_document_bytes"]
    ensure = client.calls[0][1]
    assert ensure["owner"] == "market-intelligence:tenant01"
    assert ensure["access_policy"] == {
        "tenant_id": "tenant01",
        "allowed_consumers": ["market-intelligence"],
    }
    ingest = client.calls[1][1]
    assert ingest["pre_chunked"] is False
    assert ingest["content_type"] == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert ingest["content"] == (args["original_files_dir"] /
                                 "official-technical-document.docx").read_bytes()
    assert result["indexing_executed"] is True
    assert result["documents"][0]["index_status"] == "ingested_extracted"


def test_replay_is_deterministic_by_source_and_tenant(tmp_path: Path):
    args = _args(tmp_path)
    c = StubDP()
    first = ingest_original_eis_documents(c, **args, execute=True)
    second = ingest_original_eis_documents(c, **args, execute=True)
    assert first["documents"][0]["canonical_uri"] == second["documents"][0]["canonical_uri"]
    assert first["collection_id"] == second["collection_id"]


def test_cross_tenant_cannot_create_collection(tmp_path: Path):
    args = _args(tmp_path)
    args["tenant_id"] = "different"
    c = StubDP()
    with pytest.raises(EISIndexError, match="Cross-tenant"):
        ingest_original_eis_documents(c, **args, execute=True)
    assert c.calls == []


def test_collection_authorization_checked_before_remote_call(tmp_path: Path):
    args = _args(tmp_path)
    args["trusted"] = TrustedTenant("tenant01", "market-intelligence", frozenset())
    c = StubDP()
    with pytest.raises(EISIndexError, match="authorization"):
        ingest_original_eis_documents(c, **args, execute=True)
    assert c.calls == []


@pytest.mark.parametrize("fault", ["xml", "archive", "file", "source_uri"])
def test_corruption_prevents_any_dp_side_effect(tmp_path: Path, fault: str):
    args = _args(tmp_path)
    if fault == "xml":
        args["receipt"]["records"][0]["source_xml_sha256"] = "f" * 64
    elif fault == "archive":
        args["original_archive_sha256"] = "f" * 64
    elif fault == "file":
        (args["original_files_dir"] / "official-technical-document.docx").write_bytes(b"tampered")
    else:
        args["receipt"]["records"][0]["source_url_sha256"] = "wrong"
    c = StubDP()
    with pytest.raises((ValueError, EISIndexError)):
        ingest_original_eis_documents(c, **args, execute=True)
    assert c.calls == []


def test_symlink_and_traversal_rejected(tmp_path: Path):
    args = _args(tmp_path)
    args["receipt"]["records"][0]["stored_name"] = "../other.docx"
    with pytest.raises(EISIndexError, match="file name"):
        ingest_original_eis_documents(StubDP(), **args)
    args["receipt"]["records"][0]["stored_name"] = "official-technical-document.docx"
    original = args["original_files_dir"] / "official-technical-document.docx"
    backup = tmp_path / "backup"
    original.rename(backup)
    original.symlink_to(backup)
    with pytest.raises(EISIndexError, match="symlinked"):
        ingest_original_eis_documents(StubDP(), **args)


def test_existing_foreign_collection_is_rejected_without_ingesting(tmp_path: Path):
    args = _args(tmp_path)
    c = StubDP(owner_override="market-intelligence:attacker")
    with pytest.raises(EISIndexError, match="ACL"):
        ingest_original_eis_documents(c, **args, execute=True)
    assert len(c.calls) == 1


def test_existing_collection_wrong_consumer_acl_is_rejected(tmp_path: Path):
    args = _args(tmp_path)
    c = StubDP(policy_override={"tenant_id": "tenant01", "allowed_consumers": ["foreign"]})
    with pytest.raises(EISIndexError, match="ACL"):
        ingest_original_eis_documents(c, **args, execute=True)
    assert len(c.calls) == 1


def test_failed_extraction_not_reported_as_indexed(tmp_path: Path):
    args = _args(tmp_path)
    with pytest.raises(EISIndexError, match="extraction"):
        ingest_original_eis_documents(StubDP(bad_extraction=True), **args, execute=True)


def test_revision_requires_explicit_review_before_indexing(tmp_path: Path):
    args = _args(tmp_path)
    args["receipt"]["records"][0]["revision_requires_review"] = True
    with pytest.raises(EISIndexError, match="revision"):
        ingest_original_eis_documents(StubDP(), **args)
    result = ingest_original_eis_documents(
        StubDP(), **args, allow_unreviewed_revisions=True,
    )
    assert result["revision_requires_review"] is True
    assert result["indexing_executed"] is False


def test_opaque_7z_and_zip_parent_not_ingested_as_text(tmp_path: Path):
    args = _args(tmp_path)
    row = args["receipt"]["records"][0]
    row["extension"] = ".7z"
    row["stored_name"] = "file.7z"
    with pytest.raises(EISIndexError, match="No supported"):
        ingest_original_eis_documents(StubDP(), **args)
