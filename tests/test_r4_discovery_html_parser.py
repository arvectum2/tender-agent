"""Synthetic card fixture and recorded layout intent: no case outcomes."""
from __future__ import annotations

import pytest

from src.modules.tender_operator_agent_demo.r4_discovery_html_parser import (
    parse_source_cards,
)


def card(law, link):
    return (
        f'<article class="tender-card"><div class="tags"><span class="tag grad">{law}</span></div>'
        f'<div class="card-body"><h3><a href="{link}">Procurement title</a></h3></div></article>'
    )


def markup(cards):
    return ('<!doctype html><html><head><meta charset="utf-8"></head><body>'
            + ''.join(cards) + '</body></html>').encode()


def eis(number):
    return f"https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber={number}"


def test_rank_includes_223_fz_non_eligible_source_card():
    rows = parse_source_cards(markup([
        card('44-ФЗ', eis('9000000000000000001')),
        card('223-ФЗ', 'https://other.example.org/auction/123456'),
        card('44-ФЗ', eis('9000000000000000002')),
    ]))
    assert [v['visible_rank'] for v in rows] == [1, 2, 3]
    assert [v['law'] for v in rows] == ['44-ФЗ', '223-ФЗ', '44-ФЗ']
    assert [v['registry_number'] for v in rows] == [
        '9000000000000000001', None, '9000000000000000002',
    ]


@pytest.mark.parametrize("items", [
    [card('44-ФЗ', 'https://fraud.example.org/epz/order/notice/ea20/view/common-info.html?regNumber=9000000000000000001')],
    [card('44-ФЗ', 'http://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=9000000000000000001')],
    [card('44-ФЗ', eis('9000000000000000001') + '&regNumber=9000000000000000002')],
    [card('44-ФЗ', 'https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=bad')],
    [card('unknown', eis('9000000000000000001'))],
    [card('44-ФЗ', eis('9000000000000000001')), card('44-ФЗ', eis('9000000000000000001'))],
])
def test_unapproved_or_fabricated_cards_rejected(items):
    with pytest.raises(ValueError):
        parse_source_cards(markup(items))


def test_absent_source_cards_fail_instead_of_fabricating():
    with pytest.raises(ValueError, match='layout'):
        parse_source_cards(b'<html><body>' + b'x'*130 + b'</body></html>')
