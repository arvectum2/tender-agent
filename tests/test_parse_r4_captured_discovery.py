"""Only independently captured HTML can become source-only discovery rows."""
from __future__ import annotations

import copy

import pytest

from scripts.acceptance.parse_r4_captured_discovery import (
    parse_captured_source_snapshots,
)
from tests.test_r4_discovery_capture_provenance import fixture


def test_extracted_rows_bound_to_binary_and_source_capture(tmp_path):
    x = fixture(tmp_path)
    result = parse_captured_source_snapshots(
        intent=x['intent'],
        capture_receipt=x['capture_receipt'],
        captured_original_root=x['captured_original_root'],
    )
    assert result['source_only'] is True
    assert len(result['parsed_snapshots']) == 2
    assert result['summary_by_page'][0]['source_cards_44fz'] == 2
    assert result['official_eis_zip_xml_and_originals_verified'] == 0
    assert result['independent_expert_gold'] == 0


def test_incomplete_or_falsely_attested_tls_source_rejected(tmp_path):
    x = fixture(tmp_path)
    damaged = copy.deepcopy(x['capture_receipt'])
    damaged['pages'][0]['status'] = 'SOURCE_UNAVAILABLE'
    with pytest.raises(ValueError):
        parse_captured_source_snapshots(
            intent=x['intent'], capture_receipt=damaged,
            captured_original_root=x['captured_original_root'],
        )
    damaged = copy.deepcopy(x['capture_receipt'])
    damaged['pages'][0]['content_sha256'] = '0'*64
    with pytest.raises(ValueError):
        parse_captured_source_snapshots(
            intent=x['intent'], capture_receipt=damaged,
            captured_original_root=x['captured_original_root'],
        )
