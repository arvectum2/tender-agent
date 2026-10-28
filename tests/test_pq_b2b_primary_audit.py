import json
from pathlib import Path

import pytest

from src.modules.market_intelligence.pq_b2b_primary_capture import capture
from src.modules.market_intelligence.pq_b2b_primary_audit import verify

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
    ).encode("utf-8")
    capture(number="4561243", root=tmp_path,
            fetch=lambda _: (html, URL))
    return tmp_path / "4561243"


def test_original_b2b_audit_preserves_hidden_outcome(tmp_path: Path):
    case = _set_up(tmp_path)
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
