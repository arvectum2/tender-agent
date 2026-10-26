"""EIS SOAP backfill tests: generated XML fixtures; no network or actual keys."""

from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from src.modules.market_intelligence.eis_soap_backfill import (
    _classify_transport,
    _matching_terms,
    _tasks,
    collect,
    scan_archive,
)


@pytest.fixture
def ontology():
    p = Path(__file__).resolve().parents[1] / "data/market_intelligence/power_quality/ontology.v1.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def _xml(body: str, number: str = "32615969197") -> bytes:
    return (
        f'<purchaseNotice xmlns="http://zakupki.gov.ru/223fz/purchase/1">'
        f'<purchaseNoticeData><registrationNumber>{number}</registrationNumber>'
        f'<name>{body}</name></purchaseNoticeData>'
        f'<lots><lot><lotItems><lotItem><name>'
        f'{body}</name></lotItem></lotItems></lot></lots></purchaseNotice>'
    ).encode()


def _zip(path: Path, texts: list[tuple[str, bytes]]) -> None:
    with zipfile.ZipFile(path, "w") as bundle:
        for name, body in texts:
            bundle.writestr(name, body)


def test_detects_ukrm_inside_223fz_xml_and_keeps_source_hash(tmp_path, ontology):
    p = tmp_path / "notice.zip"
    _zip(p, [("notice.xml", _xml("Проектирование и поставка УКРМ 10 кВ"))])
    evidence = scan_archive(p, ontology)
    assert evidence["xml_documents_inspected"] == 1
    assert evidence["candidate_numbers"] == ["32615969197"]
    assert all(x["classification"] == "lexical_candidate_not_verified" for x in evidence["matches"])
    assert any(e["family"] == "ukrm" and "УКРМ" in e["matched_terms"]
               for e in evidence["matches"])
    assert all(len(x["source"]["xml_sha256"]) == 64 for x in evidence["matches"])
    assert all(x["source"]["xml_member"] == "notice.xml" for x in evidence["matches"])


def test_44fz_source_notice_number_ignores_internal_short_id(tmp_path, ontology):
    p = tmp_path / "eis44.zip"
    xml = (
        b"<export><epNotificationEF2020><commonInfo>"
        b"<purchaseNumber>0372100005626000037</purchaseNumber>"
        b"</commonInfo><purchaseObject><name>"
        + "Активный фильтр гармоник".encode()
        + b"</name><purchaseNumber>0048</purchaseNumber>"
        b"</purchaseObject></epNotificationEF2020></export>"
    )
    _zip(p, [("epNotificationEF2020_0372100005626000037_1.xml", xml)])
    result = scan_archive(p, ontology)
    assert result["candidate_numbers"] == ["0372100005626000037"]
    assert all(hit["number"] == "0372100005626000037" for hit in result["matches"])


def test_generic_reactive_compensation_is_not_asserted_ukrm(tmp_path, ontology):
    p = tmp_path / "generic.zip"
    _zip(p, [("a.xml", _xml(
        "Реконструкция ПС 110 кВ в части установки устройств компенсации реактивной мощности"
    ))])
    result = scan_archive(p, ontology)
    assert result["candidate_numbers"] == ["32615969197"]
    assert any(x["family"] == "power_quality_system" for x in result["matches"])
    assert not any(x["family"] == "ukrm" for x in result["matches"])


def test_statcom_inside_epc_lot_is_candidate_not_award(tmp_path, ontology):
    p = tmp_path / "epc.zip"
    _zip(p, [("a.xml", _xml("Комплексная модернизация подстанции с СТАТКОМ и фильтром гармоник"))])
    r = scan_archive(p, ontology)
    families = {m["family"] for m in r["matches"]}
    assert "statcom" in families
    assert "harmonic_filter" in families
    assert all(m["classification"] != "awarded" for m in r["matches"])


def test_svg_as_graphics_is_not_reactive_compensation(ontology):
    hits = _matching_terms("SVG vector graphics file", ontology)
    assert not any(x["family"] == "statcom" for x in hits)


def test_rejects_xml_entity_declarations(tmp_path, ontology):
    path = tmp_path / "entity.zip"
    _zip(path, [("payload.xml", b'<!DOCTYPE x [<!ENTITY x "boom">]><x>&x;</x>')])
    with pytest.raises(ValueError, match="DTD"):
        scan_archive(path, ontology)


def test_rejects_zip_bomb_member_limit(tmp_path, ontology):
    path = tmp_path / "huge.zip"
    with zipfile.ZipFile(path, "w") as bundle:
        b = _xml("УКРМ")
        bundle.writestr("x.xml", b)
    # This tests the raw XML scanning safety and does not synthesize a 500MB archive.
    evidence = scan_archive(path, ontology)
    assert evidence["xml_documents_inspected"] == 1


def test_date_window_and_bounds():
    assert _tasks(["77", "78"], date(2026, 10, 7), date(2026, 10, 8), 3) == [
        ("77", "2026-10-07"), ("78", "2026-10-07"), ("77", "2026-10-08"),
    ]
    with pytest.raises(ValueError, match="two-digit"):
        _tasks(["bad"], date(2026, 10, 7), date(2026, 10, 8), 2)
    with pytest.raises(ValueError, match="interval"):
        _tasks(["77"], date(2026, 1, 1), date(2026, 5, 1), 2)
    with pytest.raises(ValueError, match="max_requests"):
        _tasks(["77"], date(2026, 1, 1), date(2026, 1, 1), 201)


@dataclass
class FakeClient:
    root: Path
    fail: bool = False
    calls: int = 0
    download_calls: int = 0
    settings = SimpleNamespace(token="FAKE_TEST_SECRET_NO_REAL_TOKEN")

    def get_docs_by_org_region(self, org_region: str, exact_date: str,
                               document_type44: str, subsystem_type: str = "RI223"):
        self.calls += 1
        if self.fail:
            raise RuntimeError("SOAP request: Connection reset by peer")
        return SimpleNamespace(status="completed", archive_urls=[
            "https://int.zakupki.gov.ru/test-archive.zip"
        ])

    def download_archive(self, archive_url: str, target_dir: Path):
        self.download_calls += 1
        target_dir.mkdir(parents=True, exist_ok=True)
        _zip(target_dir / "documentation-archive.zip",
             [("real-soap-shaped.xml", _xml("Поставка СТАТКОМ 5 МВАр"))])
        return SimpleNamespace(stored_name="documentation-archive.zip")


def _collect(tmp_path, ontology, client, **changes):
    kwargs = {
        "regions": ["77"], "first": date(2026, 10, 8), "last": date(2026, 10, 8),
        "root": tmp_path, "ontology": ontology,
        "max_requests": 1, "subsystem": "RI223", "document_type": "purchaseNotice",
        "client": client, "download_archives": True,
    }
    kwargs.update(changes)
    return collect(**kwargs)


def test_collection_persists_source_receipt_and_skips_duplicate(tmp_path, ontology):
    c = FakeClient(tmp_path)
    first = _collect(tmp_path, ontology, c)
    assert len(first) == 1
    assert first[0]["status"] == "complete_with_archive_scan"
    assert first[0]["archive_count"] == 1
    assert first[0]["candidate_numbers"] == ["32615969197"]
    assert c.calls == 1 and c.download_calls == 1
    receipt = tmp_path / "RI223/purchaseNotice/2026-10-08/region-77.json"
    stored = json.loads(receipt.read_text(encoding="utf-8"))
    assert stored["archive_scan_complete"] is True
    assert stored["archives"][0]["matches"][0]["classification"] == "lexical_candidate_not_verified"
    assert "FAKE_TEST_SECRET_NO_REAL_TOKEN" not in receipt.read_text()
    second = _collect(tmp_path, ontology, c)
    assert second == first
    assert c.calls == 1 and c.download_calls == 1


def test_transient_error_breaks_bounded_batch_then_can_retry(tmp_path, ontology):
    c = FakeClient(tmp_path, fail=True)
    result = _collect(tmp_path, ontology, c,
                      regions=["77", "78"], max_requests=2)
    assert len(result) == 1
    assert result[0]["status"] == "retryable_network_failure"
    assert c.calls == 1
    second = _collect(tmp_path, ontology, c)
    assert second[0]["status"] == "retryable_network_failure"
    assert c.calls == 1
    c.fail = False
    third = _collect(tmp_path, ontology, c, force_retry=True)
    assert third[0]["status"] == "complete_with_archive_scan"
    assert c.calls == 2


def test_token_in_error_is_never_persisted(tmp_path, ontology):
    class TokenError(FakeClient):
        def get_docs_by_org_region(self, *args, **kwargs):
            raise RuntimeError("SSLError FAKE_TEST_SECRET_NO_REAL_TOKEN connection reset by peer")
    c = TokenError(tmp_path)
    result = _collect(tmp_path, ontology, c)
    assert result[0]["status"] == "retryable_network_failure"
    data = (tmp_path / "RI223/purchaseNotice/2026-10-08/region-77.json").read_text()
    assert "FAKE_TEST_SECRET_NO_REAL_TOKEN" not in data
    assert "[redacted]" in data


def test_classifies_auth_failure_separately():
    assert _classify_transport(RuntimeError("HTTP 401")) == "authentication_or_access_failure"
    assert _classify_transport(RuntimeError("HTTP 434")) == "provider_access_failure"
    assert _classify_transport(RuntimeError("HTTP 503")) == "retryable_network_failure"


def test_accepts_actual_eis_sized_xml_up_to_40mib_without_relaxing_xml_safety(
    tmp_path, ontology,
):
    """44-FZ real-world notices can exceed 32.8 MiB; hard cap remains."""
    from src.modules.market_intelligence.eis_soap_backfill import MAX_XML_BYTES

    assert MAX_XML_BYTES == 40 * 1024 * 1024
    moderate_path = tmp_path / "large-legit-eis.zip"
    padding = "z" * (33 * 1024 * 1024)
    xml = (
        "<root><purchaseName>Поставка СТАТКОМ 5 МВАр</purchaseName>"
        f"<irrelevant>{padding}</irrelevant></root>"
    ).encode()
    with zipfile.ZipFile(moderate_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("actual-eis-sized.xml", xml)
    report = scan_archive(moderate_path, ontology)
    assert report["xml_documents_inspected"] == 1
    assert any(m["family"] == "statcom" for m in report["matches"])

    rejected = tmp_path / "too-large.zip"
    with zipfile.ZipFile(rejected, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("over-limit.xml", b"<x>" + b"z" * (40 * 1024 * 1024) + b"</x>")
    with pytest.raises(ValueError, match="XML member exceeds size limit"):
        scan_archive(rejected, ontology)


def test_same_date_multiple_regions_cannot_overwrite_archive_evidence(
    tmp_path, ontology,
):
    """Regression: two regional receipts used to share archive-001 directory."""
    class RegionSpecific(FakeClient):
        def get_docs_by_org_region(self, org_region, exact_date, document_type44,
                                   subsystem_type="RI223"):
            self.calls += 1
            return SimpleNamespace(
                status="completed",
                archive_urls=[f"https://int.zakupki.gov.ru/region-{org_region}.zip"],
            )

        def download_archive(self, archive_url, target_dir):
            self.download_calls += 1
            target_dir.mkdir(parents=True, exist_ok=True)
            region = "77" if "region-77.zip" in archive_url else "78"
            _zip(
                target_dir / "documentation-archive.zip",
                [(f"region-{region}.xml", _xml(f"Поставка СТАТКОМ для региона {region}"))],
            )
            return SimpleNamespace(stored_name="documentation-archive.zip")

    c = RegionSpecific(tmp_path)
    rows = _collect(tmp_path, ontology, c, regions=["77", "78"], max_requests=2)
    assert len(rows) == 2
    assert all(r["status"] == "complete_with_archive_scan" for r in rows)
    assert c.calls == c.download_calls == 2
    first = (tmp_path / "RI223/purchaseNotice/2026-10-08/region-77"
             / "archive-001/documentation-archive.zip")
    second = (tmp_path / "RI223/purchaseNotice/2026-10-08/region-78"
              / "archive-001/documentation-archive.zip")
    assert first.is_file() and second.is_file()
    assert first.read_bytes() != second.read_bytes()
    assert rows[0]["archives"][0]["archive_sha256"] != rows[1]["archives"][0]["archive_sha256"]


def test_legacy_collision_receipt_root_fails_closed(tmp_path, ontology):
    (tmp_path / "UNTRUSTED_REGION_COLLISION.json").write_text('{"invalid":true}')
    with pytest.raises(ValueError, match="unsafe legacy"):
        _collect(tmp_path, ontology, FakeClient(tmp_path))
