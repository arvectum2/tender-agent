import pytest

from scripts.acceptance.apr06_preliminary_shortlist import ROOT, SOURCES, build


def test_shortlist_is_mixed_but_not_commercial_gold():
    out = build()
    assert out['law_counts'] == {'44fz': 20, '223fz': 1}
    assert out['original_attachment_count'] == 100
    assert [x['registry_number'] for x in out['cases'] if x['law'] == '223fz'] == ['32616444788']
    assert all(x['human_review'] is None for x in out['cases'])
    assert not out['commercial_corpus_frozen'] and not out['commercial_release_authorized']


def test_changed_historical_source_rejected(tmp_path):
    for name in SOURCES:
        (tmp_path / name).write_bytes((ROOT / name).read_bytes())
    path = tmp_path / next(iter(SOURCES))
    path.write_bytes(path.read_bytes() + b' ')
    with pytest.raises(ValueError, match='changed'):
        build(tmp_path)
