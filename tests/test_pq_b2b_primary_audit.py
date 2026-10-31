import json
from pathlib import Path

import pytest

from src.modules.market_intelligence.pq_b2b_primary_audit import verify
from src.modules.market_intelligence.pq_b2b_primary_capture import capture

URL = "https://www.b2b-center.ru/market/original-ukrm/tender-4561243/"


def _set_up(tmp_path: Path) -> Path:
    html = (
        "<!DOCTYPE html><html><head>"
        "<title>Закупка конденсаторных установок 10 кВ АУКРМ "
        "— Тендер № 4561243 — B2B-Center</title>"
        '<meta name="description" content="АУКРМ УК3 УК4">'
        "</head><body>"
        "Организатор: ООО УК МЕТАЛЛОИНВЕСТ"
        " Заказчики: АО МИХАЙЛОВСКИЙ ГОК"
        " Дополнительная информация"
        " Статус объявления: в архиве."
        " Результаты процедуры скрыты по решению ее организатора."
        " Всего заявок: 6."
        "</body></html>"
    ).encode()
    capture(number="4561243", root=tmp_path,
            fetch=lambda _: (html, URL))
    return tmp_path / "4561243"


def test_original_b2b_audit_preserves_hidden_outcome(tmp_path: Path):
    _set_up(tmp_path)
    result = verify(source_root=tmp_path)
    assert result["first_party_cards_verified"] == 1
    row = result["source_records"][0]
    assert row["applications_count_not_qualified_bidders"] == 6
    assert row["results_hidden_by_organizer"] is True
    assert result["winner_identity_verified"] == 0
    assert row["signed_contract_verified"] is False
    assert row["contract_price_rub"] is None


def test_auditor_rejects_false_winner_and_changed_raw_html(tmp_path: Path):
    case = _set_up(tmp_path)
    receipt = case / "receipt.json"
    item = json.loads(receipt.read_text())
    item["winner_verified"] = True
    receipt.write_text(json.dumps(item))
    with pytest.raises(ValueError, match="cannot establish"):
        verify(source_root=tmp_path)
    item["winner_verified"] = False
    receipt.write_text(json.dumps(item))
    (case / "original-public-b2b.html").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="SHA"):
        verify(source_root=tmp_path)


def test_original_organizer_cancellation_explicitly_links_replaced_tender(tmp_path: Path):
    old = (
        '<!DOCTYPE html><html><head>'
        '<title>Закупка установки УКРМ для МГБЖ — Тендер № 4538400 — B2B-Center</title>'
        '</head><body>Организатор: ООО МЕТАЛЛОИНВЕСТ '
        'Заказчики: АО МИХАЙЛОВСКИЙ ГОК Дополнительная информация '
        'Статус объявления: в архиве. Организатор принял решение отменить процедуру. '
        'Основание отмены процедуры: открыт новый конкурс № 4565274 (корректировка ОЛ) '
        'Всего заявок: Скрыто</body></html>'
    ).encode()
    new = (
        '<!DOCTYPE html><html><head>'
        '<title>Закупка АУКРМ 10 кВ (взамен конкурса № 4538400) — '
        'Тендер № 4565274 — B2B-Center</title></head><body>'
        'Организатор: ООО МЕТАЛЛОИНВЕСТ '
        'Заказчики: АО МИХАЙЛОВСКИЙ ГОК Дополнительная информация '
        'Статус объявления: в архиве. Всего заявок: 11.</body></html>'
    ).encode()
    old_url = 'https://www.b2b-center.ru/market/old-ukrm/tender-4538400/'
    new_url = 'https://www.b2b-center.ru/market/new-ukrm/tender-4565274/'
    capture(number='4538400', root=tmp_path, fetch=lambda _: (old, old_url))
    capture(number='4565274', root=tmp_path, fetch=lambda _: (new, new_url))
    audit = verify(source_root=tmp_path)
    assert audit['organizer_cancelled_cases_verified'] == 1
    edge = audit['explicit_source_verified_replacement_links'][0]
    assert edge['cancelled_tender_id'] == '4538400'
    assert edge['replacement_tender_id'] == '4565274'
    assert edge['same_buyer_and_organizer_verified'] is True
    assert edge['signed_contract_verified'] is False
    assert 'открыт новый конкурс № 4565274' in edge['source_cancellation_quote']
    # Both page identities are checked against saved source SHA.
    assert len(edge['cancelled_original_sha256']) == 64
    assert len(edge['replacement_original_sha256']) == 64
