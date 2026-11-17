"""Archived procedure and attachment boundaries must not inflate commercial readiness."""
import json
from types import SimpleNamespace

import pytest

from scripts.acceptance.apr06_mixed_archive_selection import (
    ROOT,
    key,
    method_class,
    verified_downloads,
)


def test_unknown_and_noncompetitive_methods_never_qualify():
    for code in ('310289', '33505', '336318'):
        assert method_class(code) == 'NONCOMPETITIVE_CONTROL'
    for code in ('202025', '196761'):
        assert method_class(code) == 'COMPETITIVE_REVIEW_CANDIDATE'
    assert method_class('371782') == 'METHOD_REQUIRES_REVIEW'
    assert method_class('unknown') == 'METHOD_REQUIRES_REVIEW'


def test_same_bytes_distinct_notice_protocol_refs_do_not_collapse(tmp_path):
    number = '32616447910'
    folder = tmp_path / number
    folder.mkdir()
    html, content = b'archived page', b'archived doc'
    (folder / 'official-documents.html').write_bytes(html)
    urls = ['https://zakupki.gov.ru/223/one', 'https://zakupki.gov.ru/223/two']
    items, docs = [], []
    for i, url in enumerate(urls, 1):
        (folder / f'attachment-{i:02d}.bin').write_bytes(content)
        items.append({'id': i, 'source': url, 'sha256': key(content)[0], 'bytes': len(content)})
        docs.append(SimpleNamespace(file_url=url, file_name='doc', raw_meta={
            'source_document_kind': 'purchaseNotice' if i == 1 else 'purchaseProtocol',
            'evidence': {'xml_sha256': str(i) * 64}}))
    rec = {'number': number, 'official_html_sha256': key(html)[0], 'attachment_count': 2, 'attachments': items}
    raw = SimpleNamespace(documents=docs)
    result = verified_downloads(tmp_path, rec, raw)
    assert len(result) == 2 and result[0]['sha256'] == result[1]['sha256']
    assert result[0]['source_kind'] != result[1]['source_kind']
    (folder / 'attachment-02.bin').write_bytes(b'tampered')
    with pytest.raises(ValueError, match='bytes mismatch'):
        verified_downloads(tmp_path, rec, raw)
    items[1]['source'] = urls[0]
    with pytest.raises(ValueError, match='uniquely matched'):
        verified_downloads(tmp_path, rec, raw)


def test_saved_mixed_inventory_is_not_a_frozen_corpus():
    path = ROOT / 'docs/acceptance/apr06_mixed_archive_readiness_2026-11-17.json'
    out = json.loads(path.read_bytes())
    assert out['additional_44fz_count'] == 4 and out['additional_44fz_attachments'] == 21
    cases = out['historical_ri223_cases']
    assert len(cases) == 6
    assert sum(c['selection_class'] == 'NONCOMPETITIVE_CONTROL' for c in cases) == 3
    assert sum(c['selection_class'] == 'COMPETITIVE_REVIEW_CANDIDATE' and c['archived_attachment_reference_coverage_complete'] for c in cases) == 1
    assert sum(len(c['documents']) for c in cases) == 11
    assert len(out['original_223fz_candidates']) == 8 and out['original_223fz_candidates_complete'] == 0
    assert not out['commercial_corpus_frozen'] and not out['commercial_release_authorized']
    assert not out['current_eis_checked'] and out['human_reviews_in_this_run'] == 0
