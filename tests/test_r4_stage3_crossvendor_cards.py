"""Only artificial HTML fixtures; procurement identities come from real files separately."""
from __future__ import annotations

import pytest

from src.modules.tender_operator_agent_demo.r4_stage3_crossvendor_cards import (
    MOS,
    SYNAPS,
    parse_stage3_cards,
)


def synaps(cards: list[str]) -> bytes:
    return ('<html><head><meta charset="utf-8"></head><body>' + ''.join(cards) + '</body></html>').encode()


def synaps_card(num: str, label: str = "44-ФЗ", origin: str = "") -> str:
    return (
        '<div class="sp-tender-block"><b>' + label + '</b>'
        '<a href="' + origin + '/zakupki/fz44/' + num + '%231--software"></a>'
        '</div>'
    )


def mos(cards: list[str]) -> bytes:
    return ('<html><head><meta charset="utf-8"></head><body><table class="theme_header">' + ''.join(cards) +
            '</table></body></html>').encode()


def mos_card(num: str) -> str:
    return (
        '<div><div><a href="https://mos-tenders.ru/zakupki-v-tenderah-po-44-fz/'
        'goszakupka-111-' + num + '-service"></a></div></div>'
    )


def test_synaps_physical_rank_preserved_with_non_44fz_cards():
    rows = parse_stage3_cards(SYNAPS, synaps([
        synaps_card("9000000000000000001"),
        '<div class="sp-tender-block"><b>223-ФЗ</b></div>',
        synaps_card("9000000000000000002"),
    ]))
    assert [x["source_card_rank"] for x in rows] == [1,2,3]
    assert [x["registry_number"] for x in rows] == [
        "9000000000000000001",None,"9000000000000000002",
    ]
    assert rows[1]["law"] == "OTHER"


@pytest.mark.parametrize("card", [
    synaps_card("9000000000000000001", origin="https://evil.example"),
    synaps_card("9000000000000000001", label="223-ФЗ"),
    synaps_card("9000000000000000001", label="44-ФЗ 223-ФЗ"),
    '<div class="sp-tender-block">44-ФЗ <a href="/zakupki/fz44/unverified"></a></div>',
])
def test_synaps_untrusted_or_ambiguous_identity_rejected(card):
    with pytest.raises(ValueError):
        parse_stage3_cards(SYNAPS,synaps([card]))


def test_mos_rank_deduplicated_by_selection_not_within_original_cards():
    rows=parse_stage3_cards(MOS,mos([
        mos_card("9000000000000000001"),
        mos_card("9000000000000000001"),
        '<div class="info">Informational panel without notice link</div>',
        mos_card("9000000000000000002"),
    ]))
    assert [row["source_card_rank"] for row in rows] == [1,2,3,4]
    assert rows[2]["registry_number"] is None
    assert rows[2]["law"] == "UNVERIFIABLE"
    assert rows[0]["registry_number"]==rows[1]["registry_number"]


def test_mos_missing_official_law_url_rejected():
    bad='<div><a href="https://example.org/zakupki-v-tenderah-po-44-fz/goszakupka-11-9000000000000000001-test">Tender</a></div>'
    with pytest.raises(ValueError,match="missing 44-ФЗ"):
        parse_stage3_cards(MOS,mos([bad]))


def test_both_providers_fail_when_page_structure_changes():
    with pytest.raises(ValueError, match="layout"):
        parse_stage3_cards(MOS,b'<html><body>'+b'x'*150+b'</body></html>')
    with pytest.raises(ValueError, match="layout"):
        parse_stage3_cards(SYNAPS,b'<html><body>'+b'x'*150+b'</body></html>')
