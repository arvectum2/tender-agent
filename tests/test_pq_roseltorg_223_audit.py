import hashlib
import json
from pathlib import Path

import pytest

from src.modules.market_intelligence.pq_roseltorg_223_audit import (
    MEMBERS,
    verify,
)

NUMBER = "32616400421"
DOC_URLS = {
    "cancellation.7z": "https://corp.roseltorg.ru/api/v1/documents/476985f6-bbf1-11f1-9925-d762a15dcfbc",
    "documentation.7z": "https://corp.roseltorg.ru/api/v1/documents/ad495bda-b70f-11f1-94bc-e59c6cd3a685",
}
PAGE_URL = "https://www.roseltorg.ru/procedure/" + NUMBER


def _fixture(tmp_path: Path):
    case = tmp_path / "originals" / NUMBER
    case.mkdir(parents=True)
    queue = tmp_path / "queue"
    queue.mkdir()
    original_members = {
        alias: b"PK\x03\x04" + alias.encode() for alias in MEMBERS
    }
    hashes = {alias: hashlib.sha256(b).hexdigest()
              for alias, b in original_members.items()}
    body = (
        f"<html><title>{NUMBER} Россети Сибирь отмена</title>"
        + "".join(f'<a href="{value}">{name}</a>'
                  for name, value in DOC_URLS.items())
        + "</html>"
    ).encode()
    (case / "original-page.html").write_bytes(body)
    docs = []
    for name, url in DOC_URLS.items():
        binary = bytes.fromhex("377abcaf271c0004") + name.encode()
        (case / name).write_bytes(binary)
        docs.append({
            "filename": name, "source_url": url,
            "sha256": hashlib.sha256(binary).hexdigest(),
            "bytes": len(binary),
        })
    (case / "source-manifest.json").write_text(json.dumps({
        "schema_version": "pq-roseltorg-223-originals/1",
        "registry_number": NUMBER,
        "source_page_url": PAGE_URL,
        "source_page_sha256": hashlib.sha256(body).hexdigest(),
        "first_party_documents": docs,
    }))
    sources = [
        {
            "filename": "cancellation-protocol.docx",
            "sha256": hashes["cancellation-protocol.docx"],
            "text": (
                "Решили: отказаться от проведения конкурса в электронной форме № 26-1149 "
                "на право поставки батарей статических конденсаторов"
            ),
        },
        {
            "filename": "original-technical-system.docx",
            "sha256": hashes["original-technical-system.docx"],
            "text": (
                "Номинальное напряжение, кВ | 110 "
                "Тип МПУ | МПУ-30000/10 УХЛ1 "
                "Номинальное напряжение, кВ | 10"
            ),
        },
        {"filename": "original-supply-specification.docx",
         "sha256": hashes["original-supply-specification.docx"], "text": "БСК"},
        {"filename": "original-notice.docx",
         "sha256": hashes["original-notice.docx"], "text": "370 504 918,04"},
    ]
    identity = NUMBER + "-" + "a" * 24
    (queue / (identity + ".json")).write_text(json.dumps({
        "schema_version": "pq-review-queue/1", "id": identity,
        "state": "reviewed",
        "packet": {"registry_number": NUMBER, "documents": sources},
        "review": {"classification": "uncertain",
                   "evidence": [{"sha256": sources[0]["sha256"],
                                 "quote": "Решили: отказаться от проведения конкурса в электронной форме № 26-1149"}]},
    }))
    binaries = {member: original_members[alias] for alias, (_archive, member)
                in MEMBERS.items()}
    return case.parent, queue, binaries


def test_exact_primary_roseltorg_223_source_cancellation_and_110_10kv(tmp_path: Path):
    root, queue, binaries = _fixture(tmp_path)
    result = verify(root=root, queue=queue,
                    extractor=lambda _archive, member: binaries[member])
    assert result["first_party_original_223_cases"] == 1
    assert result["reviewed_commission_cancellation_cases"] == 1
    item = result["records"][0]
    assert item["commission_cancellation_source_verified"] is True
    assert item["scope_hypothesis"] == "110kv_reactive_power_system_with_10kv_converter"
    assert item["equipment_only_6_35kv_price_verified"] is False
    assert item["signed_contract_verified"] is False


def test_source_archive_sha_tamper_fails_before_any_market_claim(tmp_path: Path):
    root, queue, binaries = _fixture(tmp_path)
    (root / NUMBER / "documentation.7z").write_bytes(b"forged")
    with pytest.raises(ValueError, match="archive SHA mismatch"):
        verify(root=root, queue=queue,
               extractor=lambda _archive, member: binaries[member])


def test_fake_cross_host_attachment_refused(tmp_path: Path):
    root, queue, binaries = _fixture(tmp_path)
    manifest = root / NUMBER / "source-manifest.json"
    data = json.loads(manifest.read_text())
    data["first_party_documents"][0]["source_url"] = (
        "https://example.com/api/v1/documents/476985f6-bbf1-11f1-9925-d762a15dcfbc")
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Non-original"):
        verify(root=root, queue=queue,
               extractor=lambda _archive, member: binaries[member])


def test_unreviewed_source_is_not_counted_as_verified_cancellation(tmp_path: Path):
    root, queue, binaries = _fixture(tmp_path)
    for p in queue.glob("*.json"):
        p.unlink()
    with pytest.raises(ValueError, match="Missing source-SHA reviewed"):
        verify(root=root, queue=queue,
               extractor=lambda _archive, member: binaries[member])
