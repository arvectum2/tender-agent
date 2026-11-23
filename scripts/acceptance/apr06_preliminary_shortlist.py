"""Pinned historical review shortlist, explicitly not a frozen acceptance corpus."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / 'docs/acceptance'
SOURCES = {
    'apr06_overlap_historical_source_packets_2026-11-17.json': '89a8e3b4d690710fe51e70df8c26739452d31b7ac75ee4b1d082113a0beee77c',
    'apr06_mixed_archive_readiness_2026-11-17.json': 'f1bf6d1cb683738545e9e231fbb8a8e2f5ed174bf3e315ef14a19a73a57e6ef0',
}


def build(root=ROOT):
    snapshots = []
    for name, digest in SOURCES.items():
        path = root / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 500_000:
            raise ValueError('Unsafe historical evidence')
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError('Historical evidence changed')
        snapshots.append(json.loads(raw))
    overlap, mixed = snapshots
    rows = []
    for item in overlap['cases'] + mixed['development_only_44fz']:
        rows.append({'registry_number': item['registry_number'], 'law': '44fz',
                     'archived_notice_sha256': item['archive']['selected_xml_sha256'],
                     'archived_version': item['archived_version'],
                     'original_attachment_count': item['archive']['original_attachment_refs'],
                     'selection_basis': 'HISTORICAL_DEVELOPMENT_ONLY', 'human_review': None})
    for item in mixed['historical_ri223_cases']:
        if item['selection_class'] == 'COMPETITIVE_REVIEW_CANDIDATE' and item['archived_attachment_reference_coverage_complete']:
            rows.append({'registry_number': item['registry_number'], 'law': '223fz',
                         'archived_notice_sha256': item['selected_xml_sha256'], 'archived_version': item['observed_version'],
                         'original_attachment_count': item['notice_attachment_count'],
                         'selection_basis': 'SUPPLEMENTAL_ARCHIVED_SOURCE_ONLY', 'human_review': None})
    if len(rows) != 21 or len({r['registry_number'] for r in rows}) != 21:
        raise ValueError('Unexpected historical shortlist cardinality')
    return {'schema': 'apr06_preliminary_archived_review_shortlist_v1', 'state': 'REVIEW_SHORTLIST_NOT_FROZEN',
            'source_sha256': SOURCES, 'cases': sorted(rows, key=lambda r: (r['law'], r['registry_number'])),
            'case_count': 21, 'law_counts': {'44fz': 20, '223fz': 1},
            'original_attachment_count': sum(r['original_attachment_count'] for r in rows),
            'original_candidate_selection_changed': False, 'representativeness_approved': False,
            'human_reviews': 0, 'commercial_release_authorized': False, 'current_eis_checked': False,
            'commercial_corpus_frozen': False,
            'blockers': ['Independent official source and representative mixed-law corpus approval',
                         'Attributable human review, operator timings and package review', 'Owner KPI threshold approval']}


if __name__ == '__main__':
    print(json.dumps(build(), ensure_ascii=False, sort_keys=True, indent=2))
