"""Offline source-grounded review leads, not commercial KPI measurements or decisions."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from scripts.acceptance.apr06_overlap_source_packets import ROOT, build
from scripts.acceptance.build_r4_competitive_semantic_audit import build_review
from src.modules.commercial_acceptance.acceptance import METRICS

PACKET = ROOT / 'docs/acceptance/apr06_overlap_historical_source_packets_2026-11-17.json'
PACKET_SHA = '89a8e3b4d690710fe51e70df8c26739452d31b7ac75ee4b1d082113a0beee77c'
AUDIT_SHA = '707e5bbb3ab5c18c8b42f2cfda89e6ae3770a2a0c4b41978969905c9d8652e0d'
QUOTE_STATES = {
    'EXACT_QUOTE_FROM_SAVED_TEXT_WITH_OFFICIAL_BINARY_SHA',
    'WHITESPACE_VARIANT_WITH_OFFICIAL_BINARY_SHA',
    'QUOTE_NOT_SUPPORTED_AS_LIVE_QUOTATION',
}


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def summarize(packet_bytes, audit_bytes):
    if digest(packet_bytes) != PACKET_SHA or digest(audit_bytes) != AUDIT_SHA:
        raise ValueError('Frozen source packet or historical audit changed')
    packet, audit = json.loads(packet_bytes), json.loads(audit_bytes)
    cases = {row['registry_number']: row for row in packet['cases']}
    triage = audit['all_original_material_condition_triage']
    topics = {row['registry_number']: row for row in triage['cases']}
    scope = {row['registry_number']: row for row in triage['cross_document_original_scope_review']['cases']}
    reports = {row['registry_number']: row for row in audit['historical_model_report_deadline_audit']['cases']}
    quotes = {row['registry_number']: row for row in audit['saved_model_claims']['cases']}
    notices = {row['registry_number']: row for row in audit['competitive_notices']}
    output = []
    for number, case in sorted(cases.items()):
        notice, topic, contrast = notices[number], topics[number], scope[number]
        if (notice['original_xml_sha256'] != case['archive']['selected_xml_sha256']
                or notice['original_zip_sha256'] != case['archive']['zip_sha256']
                or topic['source_documents_read'] != case['attachment_count']):
            raise ValueError('Evidence edition/document mismatch')
        checks = quotes[number]['checks'] if number in quotes else []
        counts = Counter(row['status'] for row in checks)
        if set(counts) - QUOTE_STATES:
            raise ValueError('Unrecognized historical quote outcome')
        hashes = {row['original_document_sha256'] for row in case['attachments']}
        sources = contrast['archival_source_excerpts']
        if not sources or any(row['original_binary_sha256'] not in hashes for row in sources):
            raise ValueError('Cross-document contrast has unbound original')
        output.append({
            'registry_number': number,
            'archived_deadline': notice['archived_submission_end'],
            'source_document_count': case['attachment_count'],
            'topic_first_mentions': topic['literal_topic_leads'],
            'all_fixed_pattern_occurrences': topic['all_pattern_occurrences'],
            'sampled_saved_quotes': len(checks),
            'sampled_quote_states': dict(sorted(counts.items())),
            'unsupported_quote_sha256': [r['quote_sha256'] for r in checks if r['status'] == 'QUOTE_NOT_SUPPORTED_AS_LIVE_QUOTATION'],
            'saved_report_deadline_review': reports.get(number),
            'cross_document_review_question': contrast['scope_question'],
            'cross_document_source_refs': [{k: row[k] for k in ('original_filename', 'original_binary_sha256', 'source_text_sha256', 'source_locator', 'quote_sha256')} for row in sources],
            'human_commercial_decision': None,
        })
    totals = Counter()
    for row in output:
        totals.update(row['sampled_quote_states'])
    return {'schema': 'apr06_historical_review_findings_v1',
        'scope': 'ARCHIVED_DEVELOPMENT_OVERLAP_SELECTED_CLAIMS_NOT_COMMERCIAL_ACCEPTANCE',
        'historical_audit_sha256': AUDIT_SHA, 'source_packet_sha256': PACKET_SHA,
        'case_count': len(output), 'source_document_count': sum(r['source_document_count'] for r in output),
        'first_topic_mentions': sum(r['topic_first_mentions'] for r in output),
        'all_fixed_pattern_occurrences': sum(r['all_fixed_pattern_occurrences'] for r in output),
        'sampled_quote_case_count': sum(r['sampled_saved_quotes'] > 0 for r in output),
        'sampled_quote_count': sum(totals.values()), 'sampled_quote_states': dict(sorted(totals.items())),
        'historical_deadline_conflicts': sum(r['saved_report_deadline_review'] is not None and r['saved_report_deadline_review']['historical_deadline_relation'] == 'CONFLICTS_WITH_HISTORICAL_ORIGINAL' for r in output),
        'historical_strong_blocker_claims_unattested': sum(r['saved_report_deadline_review'] is not None and r['saved_report_deadline_review']['model_claims_strong_blocker'] for r in output),
        'historical_deadline_report_count': sum(r['saved_report_deadline_review'] is not None for r in output),
        'commercial_metrics': dict.fromkeys(METRICS), 'commercial_release_authorized': False,
        'current_eis_checked': False, 'human_reviews_in_this_run': 0, 'cases': output}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    root = parser.parse_args().source_root.resolve()
    actual, _ = build(root)
    if encoded(actual) != PACKET.read_bytes():
        raise ValueError('Reverified source packets differ from published snapshot')
    result = summarize(PACKET.read_bytes(), encoded(build_review(root)))
    print(encoded(result).decode(), end='')


if __name__ == '__main__':
    main()
