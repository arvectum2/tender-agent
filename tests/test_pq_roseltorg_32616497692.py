import io
import zipfile

import pytest

from scripts.market_intelligence.enrich_pq_roseltorg_32616497692 import (
    FIELDS,
    QUOTES,
    member,
    verify,
)


def test_exact_first_party_sources_and_field_quotes():
    proof = verify()
    assert proof["role"] == "bidder_not_winner"
    assert proof["winner_proven"] is False
    assert proof["signed_contract_proven"] is False
    assert proof["source_sha256"][1].startswith("c6fb6317471d1bc0")
    assert FIELDS == {"voltage_kv": "10.5", "power": "3150 кВАр", "bid": "79101498.40"}
    assert all(len(q) >= 17 for q in QUOTES.values())


def test_zip_traversal_and_missing_member_fail_closed():
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("../bad.docx", b"bad")
    with pytest.raises(ValueError):
        member(b.getvalue(), "../bad.docx")
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("good.docx", b"good")
    with pytest.raises(ValueError):
        member(b.getvalue(), "missing.docx")
