"""44-FZ originals need their own 19-digit notice identity, never a 223-FZ alias."""
import hashlib

import pytest

from scripts.market_intelligence.capture_primary_source import store

URL = "https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0373100009926000182"


def test_44fz_exact_notice_captured_with_sha_and_readback(tmp_path):
    content = b"<html><body>44fz original evidence</body></html>"
    receipt = store(tmp_path, "44fz:0373100009926000182:lot1", URL, content, "text/html")
    assert receipt["sha256"] == hashlib.sha256(content).hexdigest()
    assert (tmp_path / receipt["relative_file"]).read_bytes() == content
    assert receipt["case_id"] == "44fz:0373100009926000182:lot1"


@pytest.mark.parametrize("invalid", [
    "44fz:03731000099:lot1", "44fz:0373100009926000182:lot0",
    "44fz:0373100009926000182:lot1/../other",
])
def test_44fz_malformed_identity_rejected(tmp_path, invalid):
    with pytest.raises(ValueError, match="Invalid first-party capture identity"):
        store(tmp_path, invalid, URL, b"<html>not a valid case</html>")
