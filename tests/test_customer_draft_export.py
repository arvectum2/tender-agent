# ruff: noqa: F811

"""Synthetic private-to-customer projection, no actual customer documents."""
import hashlib
import io
import zipfile

import pytest
from test_private_review_bundle import build
from test_qualification_readiness import fixture  # noqa: F401
from test_reviewed_commercial_drafts import assertion, declarations, offer

from src.modules.application_package_generator.customer_draft_export import (
    build_customer_draft_export,
    verify_customer_draft_export,
)
from src.modules.application_package_generator.reviewed_commercial_drafts import (
    DeclarationTerms,
)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def approved_bundle(fixture, complete=True):
    s, *_ = fixture
    o, d = offer(), declarations()
    assertion(s, 'draft_offer:synthetic-quotation', o)
    for statement in d.statements if complete else d.statements[:1]:
        assertion(s, 'draft_declaration:' + statement.code,
                  DeclarationTerms(procurement_ref=d.procurement_ref, statements=[statement]))
    return build(fixture, offer_terms=o, declaration_terms=d, selections={})[0]


def test_exact_unsigned_projection(fixture):
    raw = approved_bundle(fixture)
    chosen = ['declarations', 'price_offer']
    result = build_customer_draft_export(raw, expected_sha256=digest(raw), selection=chosen)
    assert result == build_customer_draft_export(raw, expected_sha256=digest(raw), selection=chosen[::-1])
    with zipfile.ZipFile(io.BytesIO(result)) as out, zipfile.ZipFile(io.BytesIO(raw)) as private:
        assert set(out.namelist()) == {'UNSIGNED-price-offer.docx', 'UNSIGNED-declarations.docx'}
        for name in out.namelist():
            assert out.read(name) == private.read('drafts/' + name.removeprefix('UNSIGNED-'))
        assert 'internal/price-scenario.json' in private.namelist()
        assert 'forms/bid.docx' in private.namelist()
        expected = {n: out.read(n) for n in out.namelist()}
    verify_customer_draft_export(result, expected)
    with pytest.raises(ValueError):
        verify_customer_draft_export(result, {**expected, 'manifest.json': b'private'})
    with pytest.raises(ValueError):
        verify_customer_draft_export(result, {**expected, 'UNSIGNED-price-offer.docx': b'changed'})


@pytest.mark.parametrize('selection', [[], ['price_offer', 'price_offer'], ['evidence'], ['forms'], ['internal']])
def test_invalid_selection(fixture, selection):
    raw = approved_bundle(fixture)
    with pytest.raises(ValueError):
        build_customer_draft_export(raw, expected_sha256=digest(raw), selection=selection)


def test_unknown_statements_and_tamper(fixture):
    raw = approved_bundle(fixture, complete=False)
    with pytest.raises(ValueError, match='unresolved'):
        build_customer_draft_export(raw, expected_sha256=digest(raw), selection=['declarations'])
    with pytest.raises(ValueError, match='digest'):
        build_customer_draft_export(raw, expected_sha256='0'*64, selection=['price_offer'])
    assert build_customer_draft_export(raw, expected_sha256=digest(raw), selection=['price_offer'])
