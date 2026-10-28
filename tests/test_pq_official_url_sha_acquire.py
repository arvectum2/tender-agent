import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from src.modules.market_intelligence.pq_official_url_sha_acquire import (
    acquire, batch, extract_links,
)

URL = ("https://zakupki.gov.ru/223/filestore/public/1.0/"
       "download/fz223/file.html?uid=" + "C" * 32)


def _case():
    payload = b"\xd0\xcf\x11\xe0Original Word DOC"
    return payload, {
        "procedure_id": "32616355390",
        "evidence": [
            {"url": URL, "sha256": hashlib.sha256(payload).hexdigest(),
             "source_tier": "primary_EIS_final_commission_protocol_DOC_sha256_verified"},
            {"url": "https://evil.test/file.html?uid=" + "C"*32,
             "sha256": "f"*64,
             "source_tier": "primary_EIS_TZ_DOCX_sha256_verified"},
        ],
    }


def _downloader(content: bytes):
    def fake(attachments, *, target_dir, **kwargs):
        assert len(attachments) == 1
        name = attachments[0].name
        path = target_dir / name
        path.write_bytes(content)
        saved = [SimpleNamespace(
            stored_name=name, sha256=hashlib.sha256(content).hexdigest(),
            source_url=attachments[0].url)]
        return SimpleNamespace(saved=saved, skipped=[])
    return fake


def test_exact_url_and_sha_verification_with_redacted_receipt(tmp_path: Path):
    blob, case = _case()
    assert len(extract_links(case)) == 1
    a = acquire(case=case, root=tmp_path, download=_downloader(blob))
    assert a["files_verified"] == 1
    receipt = tmp_path / case["procedure_id"] / "official-sha-receipt.json"
    text = receipt.read_text()
    assert URL not in text
    assert "C" * 32 not in text
    record = json.loads(text)["verified"][0]
    assert record["sha256"] == hashlib.sha256(blob).hexdigest()
    assert (receipt.parent / record["stored_name"]).read_bytes() == blob
    assert acquire(case=case, root=tmp_path,
                   download=lambda *a, **k: 1)["status"] == "existing_receipt"


def test_sha_mismatch_cannot_promote_false_original(tmp_path: Path):
    blob, case = _case()
    a = acquire(case=case, root=tmp_path,
                download=_downloader(b"changed payload"))
    assert a["files_verified"] == 0
    assert a["rejected_count"] == 1
    assert list((tmp_path / case["procedure_id"]).glob("*.doc")) == []


def test_batch_persists_original_attempt_and_skips_verified(tmp_path: Path):
    blob, case = _case()
    leads = tmp_path / "leads.json"
    leads.write_text(json.dumps({"records": [case]}))
    journal = tmp_path / "journal.json"
    first = batch(leads=leads, root=tmp_path / "originals",
                  journal=journal, download=_downloader(blob))
    assert first["original_files_sha_verified"] == 1
    assert batch(leads=leads, root=tmp_path / "originals",
                 journal=journal, download=_downloader(blob))["cases_attempted"] == 0
