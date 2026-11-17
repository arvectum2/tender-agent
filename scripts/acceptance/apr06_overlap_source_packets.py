"""Read-only historical source review; not commercial or current EIS attestation."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from scripts.acceptance.apr06_review_readiness import POOL, inventory
from scripts.acceptance.build_r4_competitive_semantic_audit import _PINS, _pinned
from scripts.quality.apr067_corrected_cohort_integrity import (
    CORRECTED_PATH,
    ORIGINAL_PATH,
)
from scripts.quality.apr067_r4_development_cohort import check_original_zip
from src.modules.tender_operator_agent_demo.r4_archived_notice_attachment_coverage import (
    verify_attachment_coverage,
)

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / 'docs/quality/APR067_R4_20_HISTORICAL_DEVELOPMENT_SOURCE_MANIFEST_2026-10-15.json'
MANIFEST_SHA = '0acdc6599cff1884bb91a6f32c15f663bc1fab2d13daad4d8d394a4a95281913'
OLDER_CASES = {'0372200172326000015', '0376300000126000193'}


def read_local(root, relative, limit=15_000_000):
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError('Invalid relative source locator')
    path = root / relative
    if ('..' in Path(relative).parts or not path.resolve().is_relative_to(root.resolve())
            or path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= limit):
        raise ValueError('Unsafe or unavailable source file')
    return path.read_bytes()


def key(raw):
    return hashlib.sha256(raw).hexdigest(), len(raw)


def doc_key(doc):
    return doc['original_document_sha256'], doc['original_declared_bytes']


def pinned_paths(ai, pin, entry, docs):
    fields = {'registry_number': 'registry_number', 'archive_sha256': 'archived_zip_sha256',
              'selected_xml_sha256': 'selected_xml_sha256', 'selected_notice_version': 'archived_version',
              'selected_notice_type': 'notice_type'}
    if any(pin[k] != entry[v] for k, v in fields.items()):
        raise ValueError('Individual receipt does not match archived notice')
    locators = {}
    for row in pin['attachments']:
        expected = row['sha256'], row['bytes']
        relative = row['source_root_relative_path']
        if expected in locators or key(read_local(ai, relative)) != expected:
            raise ValueError('Original attachment digest/size mismatch or duplicate')
        locators[expected] = relative
    if len(locators) != len(docs) or set(locators) != {doc_key(d) for d in docs}:
        raise ValueError('Individual receipt and archived attachment inventory disagree')
    return locators


def saved_run_paths(ai, number, docs):
    """Find one complete same-procurement saved run; never mix duplicate runs."""
    wanted = {doc_key(d) for d in docs}
    sizes = {n for _, n in wanted}
    for meta in sorted((ai / 'tender_operator_demo').glob('*/metadata.json')):
        obj = json.loads(read_local(ai, str(meta.relative_to(ai)), 2_000_000))
        if number not in (str(obj.get('notice_number')), str(obj.get('procurement_id'))):
            continue
        matches = {}
        for row in obj.get('files', []):
            filename = row.get('stored_name')
            if not isinstance(filename, str) or Path(filename).name != filename:
                continue
            file = meta.parent / 'input' / filename
            if not file.is_file() or file.is_symlink() or file.stat().st_size not in sizes:
                continue
            relative = str(file.relative_to(ai))
            digest = key(read_local(ai, relative))
            if digest in wanted:
                if digest in matches:
                    raise ValueError('Duplicate attachment within saved run')
                matches[digest] = relative
        if set(matches) == wanted:
            return matches
    raise ValueError('No complete same-procurement saved run with all attested bytes')


def build(source_root):
    ready = inventory(POOL.read_bytes(), ORIGINAL_PATH.read_bytes(), CORRECTED_PATH.read_bytes())
    overlaps = {r['registry_number']: r for r in ready['cases'] if r['membership'] == 'BOTH'}
    manifest = _pinned(MANIFEST, MANIFEST_SHA)
    entries = {r['registry_number']: r for r in manifest['cases']}
    ai = source_root / 'ai-expert-20261012'
    selection = _pinned(ai / 'positive-eis-replacements-20261012/verified-competitive-20-plus-four-negative.json', _PINS['selection'])
    coverage = verify_attachment_coverage(selection, source_root)
    by_case = {r['registry_number']: r for r in coverage['cases']}
    pins = {}
    for path in sorted((ROOT / 'docs/quality').glob('APR067_R4_*.json')):
        raw = read_local(path.parent, path.name, 300_000)
        row = json.loads(raw)
        number = row.get('registry_number')
        if number in overlaps and 'attachments' in row:
            if number in pins:
                raise ValueError('Multiple individual receipts for one overlap')
            pins[number] = (row, path.name, key(raw)[0])
    if set(overlaps) - set(pins) != OLDER_CASES:
        raise ValueError('Individual receipt coverage changed')
    packets, private = [], []
    for number, ready_row in sorted(overlaps.items()):
        entry = entries[number]
        zip_receipt = check_original_zip(source_root=source_root, entry=entry)
        cover = by_case[number]
        docs = cover['documents']
        if (cover['archived_version'] != entry['archived_version']
                or len(docs) != zip_receipt['original_attachment_refs']
                or len({doc_key(d) for d in docs}) != len(docs)):
            raise ValueError('Archived attachment count or revision mismatch')
        if number in pins:
            pin, receipt_name, receipt_sha = pins[number]
            locators = pinned_paths(ai, pin, entry, docs)
        else:
            receipt_name = receipt_sha = None
            locators = saved_run_paths(ai, number, docs)
        base = ('ai-expert-20261012/positive-eis-replacements-20261012' if
                entry['source_role'] == 'NEW_OFFICIAL_POSITIVE_REPLACEMENT' else 'independent-20261012')
        packets.append({'registry_number': number, 'candidate_subject': ready_row['candidate_subject'],
            'archive': zip_receipt, 'archived_version': entry['archived_version'],
            'notice_type': entry['notice_type'], 'attachment_count': len(docs),
            'individual_receipt_name': receipt_name, 'individual_receipt_sha256': receipt_sha,
            'attachments': [{**doc, 'local_bytes_rehashed': True} for doc in docs],
            'current_eis_checked': False, 'legal_review': None, 'commercial_decision': None})
        private.append({'registry_number': number,
            'archive_path': str(source_root / base / number / 'documentation-archive.zip'),
            'documents': [{'slot': d['archive_attachment_slot'], 'path': str(ai / locators[doc_key(d)])} for d in docs]})
    result = {'schema': 'apr06_overlap_historical_source_packets_v1', 'state': 'ARCHIVED_BYTES_VERIFIED_REVIEW_REQUIRED',
        'manifest_sha256': MANIFEST_SHA, 'development_cohort_sha256': ready['development_cohort_sha256'],
        'case_count': len(packets), 'attachment_count': sum(p['attachment_count'] for p in packets),
        'current_eis_checked': False, 'human_reviews_in_this_run': 0,
        'commercial_release_authorized': False, 'cases': packets}
    return result, private


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', required=True, type=Path)
    parser.add_argument('--private-output', type=Path)
    args = parser.parse_args()
    result, private = build(args.source_root.resolve())
    if args.private_output:
        path = args.private_output
        if path.resolve().is_relative_to(ROOT.resolve()) or path.resolve().is_relative_to(args.source_root.resolve()):
            raise ValueError('Private index must be outside repository and original source tree')
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w', encoding='utf8') as stream:
            json.dump({'schema': 'local_review_navigation_v1', 'cases': private}, stream, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
