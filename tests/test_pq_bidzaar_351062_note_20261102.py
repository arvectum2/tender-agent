"""Prevent stale original-download warnings in verified customer snapshots."""
from scripts.market_intelligence.export_fgi_deck_snapshot import (
    source_bound_bidzaar_351062_note,
)


def test_note_requires_both_sha_bound_originals():
    power_sha = "e53a74ef8a4fda14aedce7254488013187aba3bba7780b5a9c6443e4d0caacaf"
    voltage_sha = "e7927732264deb30813bcf967740763cfb032f5710ca78156f76646f8cc0d831"
    d = {"canonical_id": "commercial:351-062:lot1", "quantity": 2,
         "equipment_voltage_kv": "6.3",
         "power": "3000 кВАр (по опросному листу; не умножать на 2)",
         "evidence": [{"sha256": power_sha}, {"sha256": voltage_sha}]}
    m = {"bidzaar_351062_p2": {"original_sha256": power_sha},
         "bidzaar_351062_voltage": {"original_sha256": voltage_sha}}
    assert "получены SHA-проверенные" in source_bound_bidzaar_351062_note(d, m)
    assert source_bound_bidzaar_351062_note({**d, "evidence": []}, m) is None
