"""Independent source coverage audit must not manufacture procurement outcomes."""
from datetime import date

import pytest

from src.modules.market_intelligence.pq_source_audit import audit_window


def test_empty_archive_window_has_no_market_claim(tmp_path):
    report = audit_window(root=tmp_path, first=date(2024, 1, 1),
                          last=date(2024, 1, 2),
                          regions=["77"], subsystems=["RI223"])
    assert report["source_day_status"] == {"missing": 2}
    assert report["unique_procurements"] is None
    assert report["confirmed_winners"] is None
    assert report["market_total_rub"] is None
    assert report["coverage_is_representative"] is False


def test_reject_invalid_scope(tmp_path):
    with pytest.raises(ValueError):
        audit_window(root=tmp_path, first=date(2024, 1, 2),
                     last=date(2024, 1, 1), regions=["77"], subsystems=["RI223"])
    with pytest.raises(ValueError):
        audit_window(root=tmp_path, first=date(2024, 1, 1),
                     last=date(2024, 1, 2), regions=["77"], subsystems=["INVALID"])
