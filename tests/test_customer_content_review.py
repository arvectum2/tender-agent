"""Exact generated OOXML verification; synthetic terms only."""
import io
import zipfile
from datetime import UTC, datetime

import pytest
from test_operator_cashflow_calendar import cost
from test_reviewed_commercial_drafts import declarations, offer

from src.modules.application_package_generator import (
    reviewed_commercial_drafts as producer,
)
from src.modules.application_package_generator.customer_content_review import (
    review_customer_export,
)

NOW = datetime(2026, 11, 18, 10, tzinfo=UTC)


def archive(members):
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for key, data in members.items():
            z.writestr(key, data)
    return out.getvalue()


def generated(monkeypatch, o=None, d=None):
    monkeypatch.setattr(producer, '_assertion', lambda *args: {'synthetic': True})
    o, d = o or offer(), d or declarations()
    price, _ = producer.render_offer(None, customer_id='fixture', terms=o, cost=cost(), now=NOW)
    declaration, _ = producer.render_declarations(None, customer_id='fixture', terms=d, now=NOW)
    return o, d, {'UNSIGNED-price-offer.docx': price, 'UNSIGNED-declarations.docx': declaration}


def review(raw, o, d):
    return review_customer_export(raw, selection=['price_offer', 'declarations'],
                                  offer_terms=o, declaration_terms=d)


def test_independent_content_exact_match(monkeypatch):
    o, d, files = generated(monkeypatch)
    result = review(archive(files), o, d)
    assert result['status'] == 'EXACT_GENERATED_CONTENT_MATCH'
    assert not result['semantic_confidentiality_verified']
    assert not result['independent_human_review']
    assert not result['submission_allowed']


@pytest.mark.parametrize('change', ['body', 'core', 'hidden_part', 'unexpected_outer'])
def test_reject_unexpected_ooxml(monkeypatch, change):
    o, d, files = generated(monkeypatch)
    name = 'UNSIGNED-price-offer.docx'
    if change == 'unexpected_outer':
        files['private.json'] = b'{}'
    else:
        with zipfile.ZipFile(io.BytesIO(files[name])) as z:
            parts = {i.filename: z.read(i) for i in z.infolist()}
        if change == 'body':
            parts['word/document.xml'] = parts['word/document.xml'].replace(b'Synthetic service A', b'Altered service A')
        elif change == 'core':
            parts['docProps/core.xml'] += b' '
        else:
            parts['word/comments.xml'] = b'<hidden/>'
        files[name] = archive(parts)
    with pytest.raises(ValueError):
        review(archive(files), o, d)


@pytest.mark.parametrize('marker', ['Внутренний расчёт', 'себестоимость', 'target_profit_rub', '{{NAME}}', 'hidden\u200btext'])
def test_reject_known_sensitive_or_unresolved_text(monkeypatch, marker):
    o = offer()
    line = o.lines[0].model_copy(update={'description': marker})
    o = o.model_copy(update={'lines': [line, *o.lines[1:]]})
    o, d, files = generated(monkeypatch, o=o)
    with pytest.raises(ValueError):
        review(archive(files), o, d)
