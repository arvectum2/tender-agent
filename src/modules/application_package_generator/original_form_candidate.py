"""Private archived original DOCX candidate; no route, release or current-law assertion."""
from __future__ import annotations

import hashlib
import io
import re
import zipfile
from datetime import UTC, datetime

from docx import Document
from lxml import etree

from .checklist_bundle_gate import digest
from .customer_content_review import _review_text
from .source_bound_fill import (
    ReviewedTemplateMap,
    _resolve,
    _utc,
    render_reviewed_identity_draft,
)

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
DOC = 'word/document.xml'
MAX_BYTES = 512 * 1024
TOKEN = re.compile(r'\{\{[A-Z][A-Z0-9_]{0,60}\}\}')


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _parts(raw):
    if not 0 < len(raw) <= MAX_BYTES:
        raise ValueError('Form outside bounded size')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        infos = z.infolist()
        names = [i.filename for i in infos]
        if (len(names) > 64 or len(names) != len(set(names))
                or sum(i.file_size for i in infos) > 8 * 1024 * 1024
                or any(i.flag_bits & 1 for i in infos)):
            raise ValueError('Invalid form package')
        return {i.filename: z.read(i) for i in infos}


def _xml(raw):
    root = etree.fromstring(raw, parser=etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False))
    if root.getroottree().docinfo.doctype:
        raise ValueError('Unsupported XML document type')
    return root


def verify_identity_delta(original, rendered, mapping, fields):
    """Restricted XML mutation oracle: plain body and standard default ancillary parts."""
    if mapping.format != 'docx' or len(fields) != len(mapping.fields):
        raise ValueError('Only restricted DOCX forms supported')
    blank = io.BytesIO()
    Document().save(blank)
    a, b, standard = _parts(original), _parts(rendered), _parts(blank.getvalue())
    if set(a) != set(standard) or set(b) != set(a):
        raise ValueError('Unexpected OOXML parts')
    if any(a[k] != standard[k] or b[k] != a[k] for k in a if k != DOC):
        raise ValueError('Nonstandard or changed ancillary OOXML part')
    root = _xml(a[DOC])
    allowed = {'document','body','p','pPr','pStyle','r','rPr','b','i','u','t',
               'tbl','tblPr','tblStyle','tblW','tblLook','tblGrid','gridCol','tr','tc','tcPr','tcW',
               'sectPr','pgSz','pgMar','cols','docGrid'}
    for node in root.iter():
        if not isinstance(node.tag, str) or not node.tag.startswith(W) or node.tag[len(W):] not in allowed:
            raise ValueError('Unsupported body construct')
        if node.tag == W+'pStyle' and node.get(W+'val') not in {'Normal','Title','Heading1','Heading2'}:
            raise ValueError('Unsupported paragraph style')
        if node.tag == W+'tblStyle' and node.get(W+'val') not in {'TableGrid','TableNormal'}:
            raise ValueError('Unsupported table style')
        if node.tag == W+'t':
            _review_text(TOKEN.sub('', node.text or ''))
    replacements = {}
    for f, row in zip(mapping.fields, fields, strict=True):
        token, value = f.expected_placeholder, row.get('value')
        if (not TOKEN.fullmatch(token) or f.target_locator != 'docx:token:'+token or token in replacements
                or row.get('field_code') != f.field_code or row.get('target_locator') != f.target_locator
                or row.get('state') != 'FILLED_OWNER_REVIEWED_VALUE' or not value or not row.get('source')):
            raise ValueError('Unresolved mapped field')
        _review_text(value)
        replacements[token] = value
    nodes = list(root.iter(W+'t'))
    observed = [token for node in nodes for token in TOKEN.findall(node.text or '')]
    if sorted(observed) != sorted(replacements):
        raise ValueError('Unmapped or duplicate original placeholder')
    for node in nodes:
        if node.text is None:
            continue
        text = TOKEN.sub(lambda m: replacements[m.group()], node.text)
        if '{{' in text or '}}' in text:
            raise ValueError('Residual or split placeholder')
        node.text = text
    if etree.tostring(root, method='c14n') != etree.tostring(_xml(b[DOC]), method='c14n'):
        raise ValueError('Rendered form differs outside identity delta')


def build_original_form_candidate(session, *, customer_id, run_id, item_code, file_id,
                                  mapping: ReviewedTemplateMap, signatory='UNKNOWN', goods_used=None, now=None):
    from .original_form_source import observe_original_form

    now = _utc(now or datetime.now(UTC))
    args = (run_id, customer_id, item_code, file_id, signatory, goods_used)
    original, source = observe_original_form(*args)
    output, receipt = render_reviewed_identity_draft(session, customer_id=customer_id,
        template_bytes=original, template_map=mapping, now=now)
    if receipt['unknown_count']:
        raise ValueError('All mapped identity values must be current')
    verify_identity_delta(original, output, mapping, receipt['fields'])
    if session.new or session.dirty or session.deleted:
        raise ValueError('Candidate requires clean session')
    session.expire_all()
    if (_resolve(session, customer_id, mapping.fields, now) != receipt['fields']
            or observe_original_form(*args) != (original, source)):
        raise ValueError('Candidate source or identity changed')
    binding = {'schema': 'archived-original-form-candidate-v1', 'source': source,
               'map_sha256': digest(mapping.model_dump(mode='json')),
               'identity_fields_sha256': digest(receipt['fields']), 'output_sha256': _sha(output)}
    return output, {**binding, 'candidate_sha256': digest(binding), 'status': 'PRIVATE_FORM_CANDIDATE_ONLY',
                    'current_revision_attested': False, 'mapping_exhaustive': False,
                    'independent_human_review': False, 'official_identity_verified': False,
                    'application_ready': False, 'external_export_allowed': False, 'submitted': False}
