"""The archived evidence report must not be treated as commercial measurements."""
import json

import pytest

from scripts.acceptance.apr06_overlap_review_findings import (
    PACKET,
    PACKET_SHA,
    ROOT,
    digest,
    summarize,
)
from src.modules.commercial_acceptance.acceptance import METRICS


def test_published_findings_preserve_scope_and_denominators():
    assert digest(PACKET.read_bytes()) == PACKET_SHA
    result = json.loads((ROOT / 'docs/acceptance/apr06_overlap_review_findings_2026-11-17.json').read_bytes())
    packet = json.loads(PACKET.read_bytes())
    assert result['case_count'] == len(result['cases']) == 16
    assert result['source_document_count'] == 75
    assert result['sampled_quote_case_count'] == 10
    assert result['sampled_quote_count'] == 26
    assert sum(result['sampled_quote_states'].values()) == 26
    assert result['historical_deadline_conflicts'] == 2
    assert result['historical_strong_blocker_claims_unattested'] == 8
    assert result['commercial_metrics'] == dict.fromkeys(METRICS)
    assert result['human_reviews_in_this_run'] == 0
    assert result['commercial_release_authorized'] is result['current_eis_checked'] is False
    per_case = {row['registry_number']: row for row in packet['cases']}
    for row in result['cases']:
        assert row['human_commercial_decision'] is None
        originals = {doc['original_document_sha256'] for doc in per_case[row['registry_number']]['attachments']}
        assert row['cross_document_source_refs']
        assert all(ref['original_binary_sha256'] in originals for ref in row['cross_document_source_refs'])


def test_unpinned_packet_or_audit_never_reaches_findings():
    for packet, audit in [(b'{}', b'{}'), (PACKET.read_bytes(), b'{"commercial_release_authorized": true}')]:
        with pytest.raises(ValueError, match='Frozen source packet or historical audit changed'):
            summarize(packet, audit)
