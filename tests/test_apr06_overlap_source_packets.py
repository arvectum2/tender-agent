"""A historical review packet must not accept substituted bytes or mixed runs."""
import json

import pytest

from scripts.acceptance.apr06_overlap_source_packets import (
    key,
    pinned_paths,
    read_local,
    saved_run_paths,
)


def doc(raw):
    digest, size = key(raw)
    return {'original_document_sha256': digest, 'original_declared_bytes': size}


def test_pinned_attachment_has_exact_bytes_and_notice(tmp_path):
    entry = {'registry_number': '1', 'archived_zip_sha256': 'a', 'selected_xml_sha256': 'b',
             'archived_version': 2, 'notice_type': 'n'}
    raw = b'fixture original'
    (tmp_path / 'original.docx').write_bytes(raw)
    d = doc(raw)
    receipt = {'registry_number': '1', 'archive_sha256': 'a', 'selected_xml_sha256': 'b',
               'selected_notice_version': 2, 'selected_notice_type': 'n', 'attachments': [
                   {'sha256': d['original_document_sha256'], 'bytes': len(raw),
                    'source_root_relative_path': 'original.docx'}]}
    assert pinned_paths(tmp_path, receipt, entry, [d]) == {key(raw): 'original.docx'}
    with pytest.raises(ValueError, match='archived notice'):
        pinned_paths(tmp_path, receipt, {**entry, 'archived_version': 3}, [d])
    (tmp_path / 'original.docx').write_bytes(b'changed original')
    with pytest.raises(ValueError, match='digest/size'):
        pinned_paths(tmp_path, receipt, entry, [d])


def test_saved_run_never_mixes_incomplete_or_other_case_runs(tmp_path):
    def run(name, number, files):
        root = tmp_path / 'tender_operator_demo' / name
        (root / 'input').mkdir(parents=True)
        rows = []
        for n, content in files.items():
            (root / 'input' / n).write_bytes(content)
            rows.append({'stored_name': n})
        (root / 'metadata.json').write_text(json.dumps({'procurement_id': number, 'files': rows}))
    docs = [doc(b'one'), doc(b'two')]
    run('a', 'case1', {'1': b'one'})
    run('b', 'case1', {'2': b'two'})
    run('c', 'foreign', {'1': b'one', '2': b'two'})
    with pytest.raises(ValueError, match='No complete'):
        saved_run_paths(tmp_path, 'case1', docs)
    run('d', 'case1', {'1': b'one', '2': b'two'})
    found = saved_run_paths(tmp_path, 'case1', docs)
    assert set(found) == {key(b'one'), key(b'two')}
    assert all('/d/input/' in path for path in found.values())


def test_private_source_locator_rejects_escape_and_symlink(tmp_path):
    outside = tmp_path / 'outside'
    outside.write_bytes(b'private')
    root = tmp_path / 'root'
    root.mkdir()
    (root / 'link').symlink_to(outside)
    for locator in ('../outside', str(outside), 'link', 'missing'):
        with pytest.raises(ValueError):
            read_local(root, locator)
