"""Do not promote HTTP 200 ETP access-denied HTML to a ZIP original."""
import io
import zipfile

import pytest

from scripts.market_intelligence.capture_primary_source import store

CID = '223fz:32616433248:lot1'
URL = 'https://rosseti.roseltorg.ru/file/get/t/LotDocuments/id/511337/name/test.zip'


def test_access_denied_html_is_rejected_without_receipt(tmp_path):
    raw = ('<html><h1>An error occurred</h1>'
           '<h2>У вашей организации нет доступа к данной процедуре.</h2></html>').encode()
    with pytest.raises(ValueError, match='not a primary original'):
        store(tmp_path, CID, URL, raw, 'text/html; charset=UTF-8')
    assert not (tmp_path / 'captures').exists()


def test_valid_zip_receipts_are_immutable_and_distinct(tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr('protocol.txt', 'Verified public original protocol')
    a = store(tmp_path, CID, URL, buf.getvalue(), 'application/zip')
    b = store(tmp_path, CID, URL, buf.getvalue(), 'application/zip')
    assert a['sha256'] == b['sha256']
    assert a['relative_file'] != b['relative_file']
