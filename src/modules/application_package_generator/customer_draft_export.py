"""Bounded unsigned customer-oriented draft projection, never a submission package."""
from __future__ import annotations

import hashlib
import io
import zipfile

from .private_review_bundle import verify_private_review_bundle

ALLOWED = {
    'price_offer': ('drafts/price-offer.docx', 'UNSIGNED_OFFER', 'offer_receipt'),
    'declarations': ('drafts/declarations.docx', 'UNSIGNED_DECLARATIONS', 'declaration_receipt'),
}
OUTPUT = {'price_offer': 'UNSIGNED-price-offer.docx', 'declarations': 'UNSIGNED-declarations.docx'}


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _eligible_member(manifest, key):
    inventory = {i['path']: i for i in manifest['inventory']}
    rows = {r['code']: r for r in manifest['items']}
    path, role, receipt_key = ALLOWED[key]
    item = inventory.get(path)
    if not item or item['role'] != role:
        raise ValueError('Selected reviewed draft unavailable')
    row = rows[item['item_code']]
    if row['applicability'] not in ('REQUIRED', 'OPTIONAL_EVIDENCE'):
        raise ValueError('Unresolved applicability')
    receipt = row.get(receipt_key) or {}
    if key == 'price_offer':
        if (row['role'] != 'PRICE' or row['state'] != 'OFFER_OWNER_REVIEW_REQUIRED'
                or receipt.get('status') != 'OFFER_OWNER_REVIEW_REQUIRED' or not receipt.get('source')):
            raise ValueError('Offer confirmation unavailable')
    else:
        statements = receipt.get('rows') or []
        if (row['role'] != 'DECLARATION' or receipt.get('status') != 'DECLARATIONS_DRAFT_REVIEW_ONLY'
                or receipt.get('unanswered_count') != 0 or not statements
                or any(s.get('state') != 'OWNER_CONFIRMED_REVIEW_REQUIRED' or not s.get('source') for s in statements)):
            raise ValueError('Declarations contain unresolved statements')
    if any(receipt.get(k) is not False for k in ('application_ready', 'signed', 'submitted')):
        raise ValueError('Unexpected approval state')
    return path


def customer_draft_options(manifest):
    result = []
    for key in ALLOWED:
        try:
            _eligible_member(manifest, key)
        except ValueError:
            continue
        result.append(key)
    return result


def _selected(raw, expected_sha256, selection):
    if not selection or len(selection) != len(set(selection)) or set(selection) - set(ALLOWED):
        raise ValueError('Explicit distinct export selection required')
    m = verify_private_review_bundle(raw, expected_sha256=expected_sha256)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        return {OUTPUT[key]: z.read(_eligible_member(m, key)) for key in selection}


def verify_customer_draft_export(export, expected_files):
    """Check exact permitted members independently of the ZIP writer."""
    if not expected_files or set(expected_files) - set(OUTPUT.values()) or len(export) > 2 * 1024 * 1024:
        raise ValueError('Invalid export bounds')
    with zipfile.ZipFile(io.BytesIO(export)) as z:
        infos = z.infolist()
        names = [i.filename for i in infos]
        if len(names) != len(set(names)) or set(names) != set(expected_files):
            raise ValueError('Unexpected customer draft member')
        for i in infos:
            data = expected_files[i.filename]
            if i.file_size != len(data) or _sha(z.read(i)) != _sha(data):
                raise ValueError('Customer draft bytes changed')


def build_customer_draft_export(raw, *, expected_sha256, selection):
    files = _selected(raw, expected_sha256, selection)
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name)
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)
    export = out.getvalue()
    verify_customer_draft_export(export, files)
    return export
