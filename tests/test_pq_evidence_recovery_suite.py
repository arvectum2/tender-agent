"""Market intelligence source recovery invariants (offline fixtures)."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.modules.market_intelligence.pq_etp_card_audit import audit
from src.modules.market_intelligence.pq_materialize_v20 import materialize
from src.modules.market_intelligence.pq_scan_ocr import ocr_pdf
from src.modules.market_intelligence.pq_verified_stage import stage


def test_materializer_missing_corpus_fails_closed(tmp_path):
    with pytest.raises((ValueError, FileNotFoundError)):
        materialize(tmp_path)


def test_materialize_mounted_v20_with_retraction():
    source = Path("/Volumes/ArvectumSSD/arvectum/runtime/mi013-pq-import/data/market_intelligence/power_quality")
    if not source.is_dir():
        pytest.skip("Private mounted research corpus unavailable")
    result = materialize(source)
    assert result["record_count"] == 100
    assert result["market_census_complete"] is False
    assert len({r["canonical_id"] for r in result["records"]}) == 100
    assert "index:energybase:mogocha-statcom-cooling-20240415" not in {
        r["canonical_id"] for r in result["records"]}


def test_stage_SHA_and_idempotence(tmp_path):
    source = tmp_path / "source"
    case = source / "32615969197"
    files = case / "source-bound-attachments"
    files.mkdir(parents=True)
    data = b"%PDF simple"
    (files / "proof.pdf").write_bytes(data)
    checksum = hashlib.sha256(data).hexdigest()
    (case / "download_receipt.json").write_text(json.dumps({
        "registry_number": "32615969197", "status": "downloaded",
        "records": [{"status": "saved", "stored_name": "proof.pdf",
                     "document_sha256": checksum}]}))
    dest = tmp_path / "output"
    first = stage(source_root=source, output_root=dest)
    again = stage(source_root=source, output_root=dest)
    assert first["files_staged"] == again["files_staged"] == 1
    assert first["errors"] == again["errors"] == 0
    (dest / "32615969197" / "proof.pdf").write_text("tampered")
    assert stage(source_root=source, output_root=dest)["errors"] == 1


def test_ocr_pdf_is_explicitly_unverified(tmp_path):
    file = tmp_path / "original.pdf"
    file.write_bytes(b"%PDF-1.7")
    returns = [
        SimpleNamespace(returncode=0, stdout=b"Pages: 1\n"),
        SimpleNamespace(returncode=0, stdout=b"\x89PNGtest"),
        SimpleNamespace(returncode=0, stdout="Компенсация реактивной мощности".encode())]
    with patch("src.modules.market_intelligence.pq_scan_ocr.subprocess.run",
               side_effect=returns):
        result = ocr_pdf(file)
    assert result["status"] == "ocr_unverified"
    assert result["pages_processed"] == 1


def test_etp_retry_and_no_contract_inference(tmp_path):
    source = tmp_path / "known.json"
    source.write_text(json.dumps({"tasks": [{
        "procedure_id": "4565274",
        "mirror": "https://synapsenet.ru/zakupki/b2b/4565274"}]}))
    journal = tmp_path / "journal.json"
    count = []
    def fetched(url):
        count.append(url)
        return {"status": "html_fetched", "http_status": 200,
                "html_sha256": "a" * 64,
                "text": "4565274 предложение УКРМ"}
    first = audit(queue_file=source, journal=journal, fetch=fetched)
    second = audit(queue_file=source, journal=journal, fetch=fetched)
    assert first["html_fetched"] == 1
    assert second["probes"] == 0
    assert len(count) == 1
    assert first["results"][0]["signed_contract_verified"] is False


def test_etp_http_outcomes_are_distinct_and_do_not_prove_award(tmp_path):
    from urllib.error import HTTPError, URLError
    urls = ["https://synapsenet.ru/zakupki/b2b/403",
            "https://synapsenet.ru/zakupki/b2b/404",
            "https://synapsenet.ru/zakupki/b2b/503",
            "https://synapsenet.ru/zakupki/b2b/network"]
    queue = tmp_path / "queue.json"
    queue.write_text(json.dumps({"tasks": [
        {"procedure_id": str(i), "mirror": url}
        for i, url in enumerate(urls)]}))
    def fetch(url):
        suffix = url.rsplit("/", 1)[-1]
        if suffix == "network":
            raise URLError("temporary failure")
        raise HTTPError(url, int(suffix), "error", {}, None)
    result = audit(queue_file=queue, journal=tmp_path / "journal.json",
                   max_tasks=4, fetch=fetch)
    assert [row["status"] for row in result["results"]] == [
        "inaccessible", "not_found", "retryable_http_error", "retryable_network_error"]
    assert [row.get("http_status") for row in result["results"]] == [403, 404, 503, None]
    assert all(row["retry_count"] == 1 and row["next_eligible_retry_at"]
               and row["signed_contract_verified"] is False
               and row["winner_verified"] is False for row in result["results"])
    assert audit(queue_file=queue, journal=tmp_path / "journal.json",
                 max_tasks=4, fetch=fetch)["probes"] == 0
