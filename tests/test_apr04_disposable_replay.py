import hashlib
import json

import pytest

from scripts.acceptance.apr04_owner_company_isolated_e2e import (
    RECEIPT,
    RUN_ID,
    verify_legacy,
)


def fixture(root):
    report = root / 'runs' / RUN_ID / 'output' / 'report.json'
    report.parent.mkdir(parents=True)
    report.write_bytes(b'archived report')
    hashes = ['a' * 64, 'b' * 64]
    (root / 'company-identity-private.json').write_text(json.dumps({'documents_offline_not_uploaded': [{'source_sha256': h} for h in hashes]}))
    receipt = root / RECEIPT
    receipt.parent.mkdir()
    receipt.write_text(json.dumps({'source_report_sha256_unchanged': hashlib.sha256(report.read_bytes()).hexdigest(),
        'corporate_documents_offline_source_hashes': hashes, 'actual_official_pdfs_copied_to_remote': False, 'go_permission': False}))
    return report, receipt


def test_legacy_inventory_excludes_database_and_storage(tmp_path):
    fixture(tmp_path)
    (tmp_path / 'apr04-isolated.sqlite').write_bytes(b'old database must not be copied')
    inventory = verify_legacy(tmp_path)
    assert len(inventory) == 3
    assert 'apr04-isolated.sqlite' not in inventory


def test_legacy_report_tamper_fails(tmp_path):
    report, _ = fixture(tmp_path)
    report.write_bytes(b'changed report')
    with pytest.raises(ValueError, match='binding mismatch'):
        verify_legacy(tmp_path)


def test_receipt_cannot_claim_go(tmp_path):
    _, receipt = fixture(tmp_path)
    row = json.loads(receipt.read_bytes())
    row['go_permission'] = True
    receipt.write_text(json.dumps(row))
    with pytest.raises(ValueError, match='binding mismatch'):
        verify_legacy(tmp_path)


def test_symlink_source_refused(tmp_path):
    report, _ = fixture(tmp_path)
    (report.parent / 'external').symlink_to('/tmp')
    with pytest.raises(ValueError, match='Unsafe saved run tree'):
        verify_legacy(tmp_path)
