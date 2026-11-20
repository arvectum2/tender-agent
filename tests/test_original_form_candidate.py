"""Synthetic source and identity fixtures; no private procurement data."""
import hashlib
import io
from types import SimpleNamespace

import pytest
from docx import Document
from docx.oxml import OxmlElement
from test_source_bound_form_fill import NOW, db, fact, template  # noqa: F401

from src.modules.application_package_generator import original_form_source as source
from src.modules.application_package_generator.original_form_candidate import (
    build_original_form_candidate,
    verify_identity_delta,
)
from src.modules.application_package_generator.source_bound_fill import (
    render_reviewed_identity_draft,
)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def filled(db, raw, mapping):  # noqa: F811
    fact(db, 'legal_name', 'Example A')
    fact(db, 'inn', '1234567890')
    return render_reviewed_identity_draft(db, customer_id='fixture-a', template_bytes=raw,
                                         template_map=mapping, now=NOW)


def test_candidate_and_exact_identity_binding(db, monkeypatch):  # noqa: F811
    raw, mapping = template('docx')
    fact(db, 'legal_name', 'Example A')
    fact(db, 'inn', '1234567890')
    snapshot = {'template_sha256': sha(raw), 'observed_version': '1'}
    monkeypatch.setattr(source, 'observe_original_form', lambda *a: (raw, snapshot))
    out, receipt = build_original_form_candidate(db, customer_id='fixture-a', run_id='fixture',
        item_code='application_form', file_id='f1', mapping=mapping, now=NOW)
    assert receipt['output_sha256'] == sha(out)
    assert receipt['source'] == snapshot
    assert not receipt['external_export_allowed'] and not receipt['current_revision_attested']
    assert not receipt['independent_human_review']
    assert Document(io.BytesIO(out)).paragraphs[1].text == 'INN: 1234567890'


@pytest.mark.parametrize('kind', ['hidden', 'unmapped', 'modified', 'metadata'])
def test_restricted_delta_refuses_unexpected_content(db, kind):  # noqa: F811
    raw, mapping = template('docx')
    if kind != 'modified':
        document = Document(io.BytesIO(raw))
        if kind == 'hidden':
            run = document.add_paragraph().add_run('hidden')
            run._r.get_or_add_rPr().append(OxmlElement('w:vanish'))
        elif kind == 'unmapped':
            document.add_paragraph('{{OTHER}}')
        else:
            document.core_properties.comments = 'internal note'
        stream = io.BytesIO()
        document.save(stream)
        raw = stream.getvalue()
        mapping = mapping.model_copy(update={'template_sha256': sha(raw)})
    output, receipt = filled(db, raw, mapping)
    if kind == 'modified':
        document = Document(io.BytesIO(output))
        document.add_paragraph('unexpected addition')
        stream = io.BytesIO()
        document.save(stream)
        output = stream.getvalue()
    with pytest.raises(ValueError):
        verify_identity_delta(raw, output, mapping, receipt['fields'])


def test_missing_current_value_rejected(db, monkeypatch):  # noqa: F811
    raw, mapping = template('docx')
    monkeypatch.setattr(source, 'observe_original_form', lambda *a: (raw, {}))
    with pytest.raises(ValueError, match='current'):
        build_original_form_candidate(db, customer_id='fixture-a', run_id='fixture',
            item_code='application_form', file_id='f1', mapping=mapping, now=NOW)


@pytest.mark.parametrize('change', [None, 'wrong_hash', 'wrong_revision', 'wrong_role', 'changed_notice'])
def test_source_binding(tmp_path, monkeypatch, change):
    raw, _ = template('docx')
    folder = tmp_path/'input'
    folder.mkdir()
    (folder/'form.docx').write_bytes(raw)
    meta = {'procurement_id':'fixture', 'files':[{'file_id':'f1','source':'ri223_attachment',
        'extension':'.docx','stored_name':'form.docx','ri223_receipts':[
            {'source_kind':'purchaseNotice','xml_sha256':'b'*64}]}]}
    notice = {'status':'PINNED_RI223_ARCHIVED_NOTICE','observed_version':'1',
              'citations':[{'archive_sha256':'a'*64,'source_sha256':'b'*64}]}
    item = SimpleNamespace(code='application_form', role='FORM', applicability='REQUIRED')
    row = {'code':'application_form','source':{'x':[{'file_id':'f1','original_sha256':sha(raw)}]}}
    if change == 'wrong_hash':
        row['source']['x'][0]['original_sha256'] = '0'*64
    elif change == 'wrong_revision':
        meta['files'][0]['ri223_receipts'][0]['xml_sha256'] = '0'*64
    elif change == 'wrong_role':
        item.role = 'DOCUMENT'
    monkeypatch.setattr(source,'checked_search_run',lambda _: (tmp_path,meta))
    monkeypatch.setattr(source,'verified_inventory',lambda *a: {'archived_bytes_complete':True,'projection_complete':True})
    replies = iter([notice,{**notice,'observed_version':'2'} if change=='changed_notice' else notice])
    monkeypatch.setattr(source,'ri223_archive_observation',lambda *a: next(replies))
    monkeypatch.setattr(source,'observe_application',lambda _: {})
    monkeypatch.setattr(source,'_rows',lambda *a: [row])
    monkeypatch.setattr(source,'_derive',lambda *a,**k: (SimpleNamespace(procurement_ref='fixture',items=[item]),
        {'requirements':{'application_form':{'source_sha256':'c'*64}}},'d'*64))
    args = ('fixture','fixture-a','application_form','f1','DIRECTOR',False)
    if change:
        with pytest.raises(ValueError):
            source.observe_original_form(*args)
    else:
        observed, receipt = source.observe_original_form(*args)
        assert observed == raw and receipt['notice_xml_sha256'] == 'b'*64
        assert receipt['observed_version'] == '1'
