import hashlib
import json
from pathlib import Path

import pytest

from src.modules.market_intelligence.pq_rad_primary_audit import verify


CASE = "32615966040"
URL = "https://tender.lot-online.ru/etp/app/OfferCard/page?OfferCard.offerUUID=Scorebo19718u80000prm9gt3apraje6o"
BINARY_URL = "https://tender.lot-online.ru/etp/downloadppf?uuid=dbfile19718u80000psji766culv1bck"


def _case(tmp_path: Path):
    root = tmp_path / "originals"
    path = root / CASE
    path.mkdir(parents=True)
    queue = tmp_path / "queue"
    queue.mkdir()
    body = (f"<html><title>Закупка {CASE} RAD260020676</title>"
            f'<a href="/etp/downloadppf?uuid=dbfile19718u80000psji766culv1bck">Протокол</a></html>').encode()
    (path / "original-rad-tender-card.html").write_bytes(body)
    rar = b"Rar!\x1a\x07\x01\x00" + b"public-original-archive-bytes"
    (path / "final-protocol.rar").write_bytes(rar)
    docx = b"PK\x03\x04" + b"synthetic-docx-bytes"
    sha = hashlib.sha256(docx).hexdigest()
    identity = CASE + "-" + "a" * 24
    phrase = "компенсации реактивной мощности на 2 сек 10 кВ"
    (queue / (identity + ".json")).write_text(json.dumps({
        "schema_version": "pq-review-queue/1",
        "id": identity,
        "state": "reviewed",
        "packet": {"registry_number": CASE, "documents": [{
            "filename": "Итоговый протокол.docx",
            "sha256": sha,
            "text": phrase + " ООО ЭНЕРГОСЕТЬ"}]},
        "review": {"classification": "relevant",
                   "evidence": [{"sha256": sha, "quote": phrase}]},
    }))
    manifest = path / "original-source-manifest.json"
    manifest.write_text(json.dumps({
        "schema_version": "pq-rad-original-source-provenance/1",
        "registry_number": CASE,
        "native_etp_id": "RAD260020676",
        "source_card_url": URL,
        "source_card_sha256": hashlib.sha256(body).hexdigest(),
        "originals": [{
            "kind": "final-protocol",
            "source_url": BINARY_URL,
            "stored_name": "final-protocol.rar",
            "sha256": hashlib.sha256(rar).hexdigest(),
            "bytes": len(rar),
            "direct_live_binary_sha_verified": True,
        }],
    }))
    return root, queue, docx, manifest


def test_verified_first_party_archives_bounded_to_source_review(tmp_path: Path):
    root, queue, original, _ = _case(tmp_path)
    result = verify(root=root, queue=queue,
                    extractor=lambda _: (original, "Итоговый протокол.docx"))
    assert result["first_party_223_notice_cases"] == 1
    assert result["reviewed_original_commission_protocol_cases"] == 1
    record = result["records"][0]
    assert record["procedure_id"] == CASE
    assert record["native_etp_id"] == "RAD260020676"
    assert record["final_protocol_docx_sha256"] == hashlib.sha256(original).hexdigest()
    assert record["commission_source_verified"] is True
    assert record["signed_contract_verified"] is False
    assert record["pq_equipment_only_price_rub"] is None


def test_forged_original_archive_fails_closed(tmp_path: Path):
    root, queue, original, _ = _case(tmp_path)
    (root / CASE / "final-protocol.rar").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="original archive SHA|original archive"):
        verify(root=root, queue=queue,
               extractor=lambda _: (original, "x.docx"))


def test_non_original_redirect_url_fails(tmp_path: Path):
    root, queue, original, manifest = _case(tmp_path)
    data = json.loads(manifest.read_text())
    data["originals"][0]["source_url"] = "https://example.com/etp/downloadppf?uuid=dbfile19718u80000psji766culv1bck"
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Untrusted RAD"):
        verify(root=root, queue=queue,
               extractor=lambda _: (original, "x.docx"))


def test_source_archive_is_not_signed_contract_even_without_review(tmp_path: Path):
    root, queue, original, _ = _case(tmp_path)
    for file in queue.glob("*.json"):
        file.unlink()
    result = verify(root=root, queue=queue,
                    extractor=lambda _: (original, "x.docx"))
    assert result["first_party_223_notice_cases"] == 1
    assert result["reviewed_original_commission_protocol_cases"] == 0
    assert result["records"][0]["signed_contract_verified"] is False
