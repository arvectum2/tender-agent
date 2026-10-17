"""Official EIS finals source verification: no synthetic participants or gold."""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

import pytest

from scripts.procurement_llm.audit_official_finals import SourceSpec, audit_original

REG = "0187200001726001304"
MEMBER = f"epProtocolEZK2020Final_{REG}_1_TEST.xml"


def _source(tmp_path: Path, *, prices=(100, 250, 300), ratings=(1, 2, None)):
    root = tmp_path / REG
    root.mkdir(exist_ok=True)
    path = root / "documentation-archive.zip"
    parts = ["<export><epProtocolEZK2020Final>"]
    for i, (price, rank) in enumerate(zip(prices, ratings, strict=True)):
        parts.append(
            "<applicationInfo>"
            f"<appNumber>{'3630084' if i == 1 else f'other{i}'}</appNumber>"
            f"<finalPrice>{price}</finalPrice>"
            f"<admissionResultsInfo><admissionResultInfo><admitted>{'true' if rank is not None else 'false'}</admitted></admissionResultInfo></admissionResultsInfo>"
            + (f"<appRating>{rank}</appRating>" if rank is not None else "")
            + "</applicationInfo>"
        )
    parts.append("</epProtocolEZK2020Final></export>")
    xml = "".join(parts).encode()
    with ZipFile(path, "w") as z:
        z.writestr(MEMBER, xml)
    spec = SourceSpec(REG, "3630084", sha256(path.read_bytes()).hexdigest(),
                      sha256(xml).hexdigest(), "250", "2", len(prices), 2, "100")
    return path, spec


def test_source_bound_official_bid_and_rank_read_only(tmp_path):
    path, spec = _source(tmp_path)
    before = path.read_bytes()
    out = audit_original(path, spec)
    assert out["registry"] == REG
    assert out["application_number"] == "3630084"
    assert Decimal(out["final_price_rub"]) == Decimal(250)
    assert out["app_rating_raw"] == "2"
    assert out["official_winner_price_rub"] == "100"
    assert out["total_applications"] == 3
    assert out["admitted_applications"] == 2
    assert out["identity_attribution_in_this_xml"] is False
    assert out["training_ready"] is False
    assert out["mutations"] == 0
    assert path.read_bytes() == before


def test_modified_zip_rejected_by_sha(tmp_path):
    path, spec = _source(tmp_path)
    with path.open("ab") as fh:
        fh.write(b"tamper")
    with pytest.raises(ValueError, match="ZIP SHA"):
        audit_original(path, spec)


def test_xml_receipt_sha_mismatch_fails_closed(tmp_path):
    path, spec = _source(tmp_path)
    with pytest.raises(ValueError, match="XML SHA"):
        audit_original(path, replace(spec, xml_sha256="0" * 64))


def test_wrong_app_price_and_rank_rejected(tmp_path):
    path, spec = _source(tmp_path)
    with pytest.raises(ValueError, match="Target bid price"):
        audit_original(path, replace(spec, price_rub="251"))
    with pytest.raises(ValueError, match="appRating"):
        audit_original(path, replace(spec, app_rating="1"))


def test_wrong_official_winner_and_counts_rejected(tmp_path):
    path, spec = _source(tmp_path)
    with pytest.raises(ValueError, match="winner price"):
        audit_original(path, replace(spec, winner_price_rub="200"))
    with pytest.raises(ValueError, match="total application count"):
        audit_original(path, replace(spec, total_applications=55))
    with pytest.raises(ValueError, match="admitted count"):
        audit_original(path, replace(spec, admitted_applications=3))


def test_gap_in_rating_sequence_rejected(tmp_path):
    path, spec = _source(tmp_path, ratings=(1, 3, None))
    with pytest.raises(ValueError, match="contiguous"):
        audit_original(path, replace(spec, app_rating="3"))


def test_symlinked_archive_rejected(tmp_path):
    path, spec = _source(tmp_path)
    link = tmp_path / "linked.zip"
    link.symlink_to(path)
    with pytest.raises(ValueError, match="canonical original"):
        audit_original(link, spec)


def test_duplicated_app_number_rejected(tmp_path):
    path, spec = _source(tmp_path)
    with ZipFile(path) as z:
        old = z.read(MEMBER)
    tampered = old.replace(b"<appNumber>other0</appNumber>", b"<appNumber>3630084</appNumber>")
    with ZipFile(path, "w") as z:
        z.writestr(MEMBER, tampered)
    changed = replace(
        spec, zip_sha256=sha256(path.read_bytes()).hexdigest(),
        xml_sha256=sha256(tampered).hexdigest(),
    )
    with pytest.raises(ValueError, match="ambiguous|Duplicate application"):
        audit_original(path, changed)
