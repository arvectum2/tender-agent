"""Historical mixed-law candidate readiness, never a frozen commercial corpus."""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from scripts.acceptance.apr06_overlap_source_packets import (
    MANIFEST,
    MANIFEST_SHA,
    ROOT,
    key,
    read_local,
)
from scripts.acceptance.apr06_review_readiness import POOL, inventory
from scripts.acceptance.build_r4_competitive_semantic_audit import _PINS, _pinned
from scripts.acceptance.observe_original_ri223_scoring import replay
from scripts.quality.apr067_corrected_cohort_integrity import (
    CORRECTED_PATH,
    ORIGINAL_PATH,
)
from scripts.quality.apr067_r4_development_cohort import check_original_zip
from src.modules.tender_operator_agent_demo.r4_archived_notice_attachment_coverage import (
    verify_attachment_coverage,
)
from src.tender_research.providers.ri223_soap_evidence import parse_ri223_archive

RI_MANIFEST_SHA = 'e27d6a93c0f641e27743ccaaaf3be790dbcac9c04f138e9cb8dc5a0ce9716de2'
PROBE_SHA = '700ef2329c692e3d065183e79eb5c01c2eadb96610fb71ffb2eedfb37d067d10'
DOWNLOAD_SHA = '823c82154ed37706e7bad4684c8e3264a2e4176fc5ada898bb2e5a018eb9c484'
SCORING_SHA = 'b5f2591cf4ef5a452330e00ba3e66c09997fae0ea2bed41a1d6633283a306d0c'
SINGLE = {'310289', '33505', '336318'}
COMPETITIVE = {'202025', '196761'}


def method_class(code):
    if code in SINGLE:
        return 'NONCOMPETITIVE_CONTROL'
    if code in COMPETITIVE:
        return 'COMPETITIVE_REVIEW_CANDIDATE'
    return 'METHOD_REQUIRES_REVIEW'


def observe(archive, number, sha):
    if archive.is_symlink() or not archive.is_file() or archive.stat().st_size > 100_000_000:
        raise ValueError('Unavailable archived RI223 ZIP')
    if key(archive.read_bytes())[0] != sha:
        raise ValueError('Archived RI223 digest mismatch')
    raw = parse_ri223_archive(archive, number)
    data = raw.raw_payload
    evidence = data['evidence']
    with zipfile.ZipFile(archive) as bundle:
        xml = bundle.read(evidence['xml_member'])
    if key(xml)[0] != evidence['xml_sha256']:
        raise ValueError('Selected notice bytes mismatch')
    root = ET.fromstring(xml)
    def field(name):
        values = [v.text for v in root.iter() if v.tag.rsplit('}', 1)[-1] == name]
        if len(values) != 1 or not values[0]:
            raise ValueError('Ambiguous archived procedure method')
        return values[0]
    code = field('purchaseMethodCode')
    return raw, {'registry_number': number, 'archive_sha256': sha,
        'selected_xml_sha256': evidence['xml_sha256'], 'observed_version': data['notice_version'],
        'method_code': code, 'method_name': field('purchaseCodeName'), 'selection_class': method_class(code),
        'notice_attachment_count': data['notice_attachment_count'], 'all_source_reference_count': len(raw.documents),
        'lots': len(data['lots']), 'explanations': len(data['explanations']), 'historical_nmck_rub': raw.nmck_amount,
        'current_eis_checked': False, 'commercial_decision': None}


def verified_downloads(root, rec, raw):
    number = rec['number']
    html = read_local(root, number + '/official-documents.html')
    if key(html)[0] != rec['official_html_sha256']:
        raise ValueError('Archived HTML digest mismatch')
    references = {d.file_url: d for d in raw.documents}
    attached = rec['attachments']
    if len(attached) != rec['attachment_count'] or len(references) != len(raw.documents):
        raise ValueError('Unexpected reference count')
    seen, results = set(), []
    for item in attached:
        url = item['source']
        if url in seen or url not in references:
            raise ValueError('Attachment not uniquely matched to XML reference')
        seen.add(url)
        content = read_local(root, f"{number}/attachment-{item['id']:02d}.bin")
        if key(content) != (item['sha256'], item['bytes']):
            raise ValueError('RI223 attachment bytes mismatch')
        doc = references[url]
        results.append({'name': doc.file_name, 'sha256': item['sha256'], 'bytes': item['bytes'],
            'source_kind': doc.raw_meta['source_document_kind'], 'xml_sha256': doc.raw_meta['evidence']['xml_sha256']})
    if seen != set(references):
        raise ValueError('Incomplete archived source reference coverage')
    return results


def additional_44(source_root, ready):
    ids = {r['registry_number'] for r in ready['cases'] if r['membership'] == 'DEVELOPMENT_ONLY'}
    manifest = _pinned(MANIFEST, MANIFEST_SHA)
    entries = {r['registry_number']: r for r in manifest['cases']}
    selection = _pinned(source_root / 'ai-expert-20261012/positive-eis-replacements-20261012/verified-competitive-20-plus-four-negative.json', _PINS['selection'])
    coverage = verify_attachment_coverage(selection, source_root)
    results = []
    for row in coverage['cases']:
        number = row['registry_number']
        if number not in ids:
            continue
        entry = entries[number]
        docs = row['documents']
        original = check_original_zip(source_root=source_root, entry=entry)
        if len(docs) != original['original_attachment_refs'] or row['archived_version'] != entry['archived_version']:
            raise ValueError('Additional 44-FZ source revision mismatch')
        if any(d['source_proof'] != 'ADDITIONAL_ORIGINAL_DOWNLOAD' for d in docs):
            raise ValueError('Expected direct original rehash path for all four additions')
        results.append({'registry_number': number, 'archive': original, 'documents': docs,
            'archived_version': entry['archived_version'], 'candidate_membership': 'DEVELOPMENT_ONLY',
            'source_attachment_bytes_revalidated_by_coverage': True, 'commercial_decision': None})
    if {r['registry_number'] for r in results} != ids:
        raise ValueError('Incomplete development-only coverage')
    return results


def build(source_root, ri_root):
    ready = inventory(POOL.read_bytes(), ORIGINAL_PATH.read_bytes(), CORRECTED_PATH.read_bytes())
    dev = additional_44(source_root, ready)
    manifest = _pinned(ri_root / 'manifest.json', RI_MANIFEST_SHA)
    cases = []
    for rec in manifest['records']:
        n = rec['number']
        raw, row = observe(ri_root / n / 'ri223-soap.zip', n, rec['soap_archive_sha256'])
        row['documents'] = verified_downloads(ri_root, rec, raw)
        row['archived_attachment_reference_coverage_complete'] = True
        cases.append(row)
    # A genuine multi-lot/revision case has verified XML but not a complete binary set.
    multi = '32616376947'
    _, row = observe(ri_root / multi / 'documentation-archive.zip', multi,
                     '840927b8dddba00cc682e78192ffb263cbd89d3fec1acbaba3fa60af63fd3575')
    row['documents'] = []
    row['archived_attachment_reference_coverage_complete'] = False
    cases.append(row)
    # The separately pinned RAR scoring source is reverified using existing narrow observer.
    n = '32616445795'
    receipt_path = ROOT / 'docs/acceptance/ri223_32616445795_original_scoring_receipt_2026-10-13.json'
    receipt = _pinned(receipt_path, SCORING_SHA)
    archive = ri_root / n / 'ri223-soap.zip'
    rar = ri_root / n / 'attachments/01-3727.rar'
    raw, row = observe(archive, n, receipt['soap_original_sha256'])
    scoring = replay(soap_archive=archive, rar_archive=rar, receipt_file=receipt_path)
    if len(raw.documents) != 1 or raw.documents[0].file_name != receipt['original_attachment_name']:
        raise ValueError('Original scoring source attachment inventory changed')
    row['documents'] = [{'name': receipt['original_attachment_name'], 'sha256': receipt['original_attachment_sha256'],
                         'bytes': rar.stat().st_size, 'source_kind': 'purchaseNotice',
                         'xml_sha256': row['selected_xml_sha256']}]
    row['archived_attachment_reference_coverage_complete'] = True
    row['narrow_scoring_source_replay'] = scoring
    cases.append(row)
    # Original APR06 223-FZ candidates remain separate from these APR02 examples.
    probe = _pinned(ROOT / 'docs/acceptance/apr06_223fz_public_probe_2026-10-09.json', PROBE_SHA)
    downloaded = _pinned(ROOT / 'docs/acceptance/apr06_223fz_download_receipts_2026-10-09.json', DOWNLOAD_SHA)
    original_ids = {r['registry_number'] for r in ready['cases'] if r['candidate_law'] == '223fz'}
    if {r['reg_number'] for r in probe['cases']} != original_ids or original_ids & {r['registry_number'] for r in cases}:
        raise ValueError('Original and supplemental RI223 candidates overlap or drift')
    partial = {r['reg_number']: r for r in downloaded['items']}
    if set(partial) - original_ids:
        raise ValueError('Unexpected partial download candidate')
    original = [{'registry_number': r['reg_number'], 'original_probe_status': r['status'],
                 'historical_download_receipt': partial.get(r['reg_number']),
                 'complete_revision_bound_originals_proven': False,
                 'commercial_decision': None} for r in sorted(probe['cases'], key=lambda r:r['reg_number'])]
    return {'schema': 'apr06_mixed_archive_readiness_v1', 'state': 'SUPPLEMENTAL_SELECTION_REVIEW_REQUIRED',
        'development_only_44fz': dev, 'additional_44fz_count': len(dev),
        'additional_44fz_attachments': sum(len(r['documents']) for r in dev),
        'historical_ri223_cases': sorted(cases, key=lambda r:r['registry_number']),
        'original_223fz_candidates': original, 'original_223fz_candidates_complete': 0,
        'commercial_corpus_frozen': False, 'human_reviews_in_this_run': 0,
        'current_eis_checked': False, 'commercial_release_authorized': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--ri223-root', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.source_root.resolve(), args.ri223_root.resolve()), ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
