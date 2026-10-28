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


def test_etp_cross_journal_dedup_and_source_url_aliases(tmp_path):
    from datetime import UTC, datetime, timedelta

    url = "https://synapsenet.ru/zakupki/b2b/4565274"
    queue = tmp_path / "queue.json"
    queue.write_text(json.dumps({"tasks": [
        {"procedure_id": "4565274", "mirror": url},
        {"procedure_id": "4565274-alias", "mirror": url}]}))
    native = tmp_path / "native.json"
    native.write_text(json.dumps({"schema_version": "pq-etp-native-source-attempts/1",
        "attempts": [{"timestamp": datetime.now(UTC).isoformat(),
                      "procedure_id": "4565274", "url": url,
                      "status": "html_fetched", "html_sha256": "a" * 64}]}))
    seen = []
    def fetch(value):
        seen.append(value)
        return {"status": "html_fetched", "http_status": 200, "text": "4565274 УКРМ"}
    journal = tmp_path / "journal.json"
    assert audit(queue_file=queue, journal=journal, fetch=fetch,
                 prior_journals=[native])["probes"] == 0
    assert not seen
    native.write_text(json.dumps({"attempts": [{
        "timestamp": (datetime.now(UTC) - timedelta(hours=13)).isoformat(),
        "url": url, "status": "inaccessible"}]}))
    result = audit(queue_file=queue, journal=journal, fetch=fetch,
                   prior_journals=[native])
    assert result["probes"] == 1
    assert seen == [url]
    assert result["results"][0]["signed_contract_verified"] is False


def test_etp_malformed_prior_journal_fails_closed(tmp_path):
    url = "https://synapsenet.ru/zakupki/b2b/4565274"
    queue = tmp_path / "queue.json"
    queue.write_text(json.dumps({"tasks": [
        {"procedure_id": "4565274", "mirror": url}]}))
    prior = tmp_path / "native.json"
    prior.write_text(json.dumps({"attempts": [{"url": url,
                                               "timestamp": "not-a-timestamp"}]}))
    with pytest.raises(ValueError, match="timestamp"):
        audit(queue_file=queue, journal=tmp_path / "journal.json",
              prior_journals=[prior], fetch=lambda _: {"status": "html_fetched"})


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


def test_gap_inventory_preserves_all_v20_source_delta_variants(tmp_path):
    from src.modules.market_intelligence.pq_gap_recovery import inventory
    leads = tmp_path / "leads.json"
    leads.write_text(json.dumps({"records": [{
        "procedure_id": "4559984", "canonical_id": "commercial:4559984:lot1",
        "evidence": [{"url": "https://example.org/notice"}],
        "sources": [{"url": "https://example.org/original"},
                    {"url": "https://example.org/notice"}],
        "source_url": "https://example.org/registry",
        "source": "https://example.org/market",
        "supporting_source": "https://example.org/secondary",
    }, {
        "procedure_id": "4561228", "canonical_id": "commercial:4561228:lot1",
        "sources": [{"url": "https://example.org/other"}],
        "source": "file:///etc/passwd",
        "supporting_source": "https://user:password@example.org/private",
    }]}))
    root = tmp_path / "sources"
    root.mkdir()
    result = inventory(leads_file=leads, source_roots=[root],
                       queue_dir=tmp_path / "queue", output=tmp_path / "gaps.json")
    assert result["lead_count"] == 2
    rows = json.loads((tmp_path / "gaps.json").read_text())["cases"]
    assert rows[0]["evidence_urls"] == [
        "https://example.org/notice", "https://example.org/original",
        "https://example.org/registry", "https://example.org/market",
        "https://example.org/secondary"]
    assert rows[1]["evidence_urls"] == ["https://example.org/other"]
    assert "signed_contract" in rows[0]["missing_or_unverified"]


def test_etp_verified_tls_fallback_only_on_transport_failure():
    from unittest.mock import MagicMock
    from urllib.error import HTTPError, URLError

    from src.modules.market_intelligence.pq_etp_card_audit import _fetch
    opener = MagicMock()
    opener.open.side_effect = URLError("proxy certificate failed")
    with patch("src.modules.market_intelligence.pq_etp_card_audit.urllib.request.build_opener",
               return_value=opener), patch(
        "src.modules.market_intelligence.pq_etp_card_audit._fetch_direct_verified_tls",
        return_value={"status": "html_fetched", "text": "UKRM 10 kV"}) as direct:
        assert _fetch("https://synapsenet.ru/zakupki/b2b/4561228")["text"] == "UKRM 10 kV"
        direct.assert_called_once()
        opener.open.side_effect = HTTPError("https://synapsenet.ru/", 403, "forbidden", {}, None)
        with pytest.raises(HTTPError):
            _fetch("https://synapsenet.ru/zakupki/b2b/4561228")
        direct.assert_called_once()
    with pytest.raises(ValueError, match="allowlisted"):
        _fetch("https://127.0.0.1/secret")


def test_etp_direct_tls_response_hash_and_incomplete_response_fail_closed():
    from urllib.error import URLError

    from src.modules.market_intelligence.pq_etp_card_audit import (
        MAX_HTML_BYTES,
        _fetch_direct_verified_tls,
    )
    url = "https://synapsenet.ru/zakupki/b2b/4561228"
    payload = b"<html>10kV UKRM source</html>"
    def fake_curl(args, **_kwargs):
        Path(args[args.index("--output") + 1]).write_bytes(payload)
        Path(args[args.index("--dump-header") + 1]).write_text(
            "HTTP/1.1 200 OK\nContent-Type: text/html\n")
        return SimpleNamespace(returncode=0, stdout=f"200|0|{url}")
    with patch("src.modules.market_intelligence.pq_etp_card_audit.subprocess.run",
               side_effect=fake_curl):
        result = _fetch_direct_verified_tls(url)
    assert result["html_sha256"] == hashlib.sha256(payload).hexdigest()
    assert result["status"] == "html_fetched"

    def incomplete_curl(args, **_kwargs):
        Path(args[args.index("--output") + 1]).write_bytes(payload)
        return SimpleNamespace(returncode=56, stdout=f"200|0|{url}")
    with patch("src.modules.market_intelligence.pq_etp_card_audit.subprocess.run",
               side_effect=incomplete_curl), pytest.raises(URLError):
        _fetch_direct_verified_tls(url)

    def too_large_curl(args, **_kwargs):
        Path(args[args.index("--output") + 1]).write_bytes(b"x" * MAX_HTML_BYTES)
        return SimpleNamespace(returncode=56, stdout=f"200|0|{url}")
    with patch("src.modules.market_intelligence.pq_etp_card_audit.subprocess.run",
               side_effect=too_large_curl):
        assert _fetch_direct_verified_tls(url)["status"] == "body_budget_exceeded"


def test_sha_bound_secondary_candidates_are_not_signed_awards():
    root = Path(__file__).resolve().parents[1]
    path = root / "data/market_intelligence/power_quality/etp_secondary_candidate_receipts_20261028.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema_version"] == "pq-etp-secondary-candidates/1"
    assert data["market_population_complete"] is False
    assert data["signed_contracts_verified"] == 0
    assert len(data["records"]) >= 8
    assert len({row["procedure_id"] for row in data["records"]}) == len(data["records"])
    for row in data["records"]:
        assert len(row["source_sha256"]) == 64
        assert row["source_tier"] == "secondary_public_index"
        assert row["source_url"].startswith("https://")
        assert len(row["exact_quote"]) >= 12
        assert row["winner_verified"] is False
        assert row["signed_contract_verified"] is False
        assert row["original_etp_documents_verified"] is False
        assert row["contract_price_rub"] is None
        assert row["initial_price_rub"] is None


def test_scanned_commission_candidate_cannot_be_promoted_as_signed_supply():
    root = Path(__file__).resolve().parents[1]
    path = root / "data/market_intelligence/power_quality/ocr_provisional_commission_32616280467.json"
    row = json.loads(path.read_text(encoding="utf-8"))
    assert row["schema_version"] == "pq-visual-ocr-provisional-commission-candidate/1"
    assert row["procedure_id"] == "32616280467"
    assert len(row["original_pdf_sha256"]) == 64
    assert len(row["derived_ocr_sha256"]) == 64
    assert len(row["visual_page_jpeg_sha256"]) == 5
    assert row["ocr_requires_visual_verification"] is True
    assert row["signed_contract_verified"] is False
    assert row["supplier_of_signed_contract_verified"] is False
    assert row["executed_contract_price_verified"] is False
    assert row["equipment_supply_verified"] is False
    assert row["market_total_eligible"] is False


def test_unnumbered_lead_never_inherits_source_root_manifests(tmp_path):
    from src.modules.market_intelligence.pq_gap_recovery import inventory
    root = tmp_path / "originals"
    root.mkdir()
    (root / "canonical-manifest.json").write_text("{}")
    leads = tmp_path / "leads.json"
    leads.write_text(json.dumps({"records": [{
        "procedure_id": None, "canonical_id": "index:ukrm:unresolved",
        "source_url": "https://example.org/lead",
    }]}))
    result = inventory(leads_file=leads, source_roots=[root],
                       queue_dir=tmp_path / "queue", output=tmp_path / "gaps.json")
    row = json.loads((tmp_path / "gaps.json").read_text())["cases"][0]
    assert result["lead_count"] == 1
    assert result["with_local_documents"] == 0
    assert row["procedure_id"] == ""
    assert row["evidence_urls"] == ["https://example.org/lead"]
    assert row["source_documents_local"] == []
    assert "original_notice" in row["missing_or_unverified"]
