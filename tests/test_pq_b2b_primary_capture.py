import hashlib
import json
from pathlib import Path

import pytest

from src.modules.market_intelligence.pq_b2b_primary_capture import (
    _b2b_eligible, _final_url, _parse, batch, capture,
)

NUM = "4565274"
FINAL = ("https://www.b2b-center.ru/market/"
         "zakupka-kondensatornoi-ustanovki-10-kv-aukrm/tender-4565274/")


def _html(number: str = NUM) -> bytes:
    return (
        "<!DOCTYPE html><html><head>"
        f"<title>Закупка Конденсаторной установки 10 кВ АУКРМ "
        f"(УК1, УК2) для МГБЖ (взамен конкурса № 4538400) — "
        f"Тендер № {number} — ООО УК МЕТАЛЛОИНВЕСТ — B2B-Center</title>"
        '<meta name="description" content="АУКРМ 10 кВ для МГБЖ">'
        "</head><body>"
        "<script>Session_ID='super-secret-do-not-put-in-receipt'</script>"
        "<section>Организатор: ООО УК МЕТАЛЛОИНВЕСТ"
        " Заказчики: АО МИХАЙЛОВСКИЙ ГОК"
        " Дополнительная информация</section>"
        "<span>Статус объявления: в архиве.</span>"
        "<p>Результаты процедуры скрыты по решению ее организатора.</p>"
        "<p>Всего заявок: 11.</p>"
        "</body></html>"
    ).encode("utf-8")


def test_original_b2b_receipt_and_hidden_results(tmp_path: Path):
    result = capture(number=NUM, root=tmp_path,
                     fetch=lambda _: (_html(), FINAL))
    assert result["original_html_sha256"] == hashlib.sha256(_html()).hexdigest()
    assert result["results_hidden_by_organizer"] is True
    assert result["applications_count_not_qualified_bidders"] == 11
    assert result["replaces_reference_in_original_title"] == "4538400"
    assert result["signed_contract_supplier"] is None
    assert result["winner_verified"] is False
    assert result["buyer_platform_display"] == "АО МИХАЙЛОВСКИЙ ГОК"
    receipt = (tmp_path / NUM / "receipt.json").read_text()
    assert "super-secret" not in receipt
    assert "Session_ID" not in receipt
    assert result["source_tier"] == "original_primary_b2b_public_html"
    existing = capture(number=NUM, root=tmp_path,
                       fetch=lambda _: (_html("9999999"), FINAL))
    assert existing == result


def test_original_b2b_tampering_and_cross_id_refused(tmp_path: Path):
    with pytest.raises(ValueError, match="exact original tender"):
        _final_url(NUM, FINAL.replace(NUM, "4561243"))
    with pytest.raises(ValueError, match="title"):
        capture(number=NUM, root=tmp_path,
                fetch=lambda _: (_html("4561243"), FINAL))
    assert not list(tmp_path.iterdir())
    result = capture(number=NUM, root=tmp_path,
                     fetch=lambda _: (_html(), FINAL))
    (tmp_path / NUM / "original-public-b2b.html").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="invalid"):
        capture(number=NUM, root=tmp_path,
                fetch=lambda _: (_html(), FINAL))


def test_maintenance_title_is_not_equipment_supply():
    text = (
        "<!DOCTYPE html><html><head>"
        "<title>Техническое обслуживание установки СТАТКОМ RU-DRIVE SVG "
        "6,3/5-3 Мвар — Тендер № 4302914 — B2B-Center</title>"
        '<meta name="description" content="СТАТКОМ RU-DRIVE"></head>'
        "<body>Статус объявления: в архиве.</body></html>"
    ).encode()
    result = _parse("4302914", text)
    assert result["subject_category"] == "maintenance_of_installed_equipment"
    assert result["applications_count_not_qualified_bidders"] is None


def test_b2b_batch_journal_prevents_repeat(tmp_path: Path):
    leads = tmp_path / "leads.json"
    leads.write_text(json.dumps({"records": [
        {"canonical_id": "b2b:4565274", "procedure_id": NUM, "evidence": [
            {"url": "https://synapsenet.ru/zakupki/b2b/4565274--something"}]},
        {"canonical_id": "other", "procedure_id": "1234567", "evidence": [
            {"url": "https://example.com/other"}]},
    ]}))
    assert _b2b_eligible(json.loads(leads.read_text())["records"][0])
    journal = tmp_path / "journal.json"
    sources = tmp_path / "sources"
    calls = []
    def fake(n: str):
        calls.append(n)
        return _html(), FINAL
    first = batch(leads=leads, root=sources, journal=journal, fetch=fake)
    assert first["first_party_original_cards_verified"] == 1
    second = batch(leads=leads, root=sources, journal=journal, fetch=fake)
    assert second["attempted"] == 0
    assert calls == [NUM]
    assert len(json.loads(journal.read_text())["attempts"]) == 1
