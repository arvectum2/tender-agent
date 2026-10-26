from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

import pytest

from src.modules.market_intelligence.eis_contract223_registry import (
    extract_public_rd223_registry,
)


def _xml(revision: str = "1", price: str = "1833358.30") -> bytes:
    return f"""<contractCutted><body><item><contractData>
      <registrationNumber>5027707146726000265000{revision}</registrationNumber>
      <contractRegNumber>50277071467260002650000</contractRegNumber>
      <version>{revision}</version><contractDate>2026-04-14</contractDate>
      <name>РЭС-1.16.7/Д-01325</name>
      <customer><mainInfo><inn>0277071467</inn><fullName>Bashkirenergo</fullName></mainInfo></customer>
      <purchaseNoticeInfo><purchaseNoticeNumber>32615614821</purchaseNoticeNumber></purchaseNoticeInfo>
      <price>{price}</price><endExecutionDate>2026-12-31</endExecutionDate>
      <subjectContract>EPC with capacitor bank</subjectContract>
    </contractData></item></body></contractCutted>""".encode()


def _zip(tmp: Path, files: list[tuple[str, bytes]]) -> tuple[Path, str]:
    p = tmp / "original.zip"
    with zipfile.ZipFile(p, "w") as z:
        for name, data in files:
            z.writestr(name, data)
    return p, hashlib.sha256(p.read_bytes()).hexdigest()


def test_real_223_registry_identity_and_total_not_equipment(tmp_path: Path):
    p, digest = _zip(tmp_path, [("revision.xml", _xml())])
    r = extract_public_rd223_registry(p, archive_sha256=digest)
    assert len(r) == 1
    v = r[0]
    assert v["registry_number"] == "50277071467260002650000"
    assert v["linked_procurement"] == "32615614821"
    assert v["buyer_inn"] == "0277071467"
    assert v["registered_total_price_rub"] == "1833358.30"
    assert v["verified_public_contract_registry"] is True
    assert v["supplier_inn"] is None
    assert v["pq_equipment_sale_rub"] is None
    assert v["amount_paid_verified"] is False
    assert v["proof"]["archive_sha256"] == digest


def test_two_revisions_do_not_become_two_contracts(tmp_path: Path):
    p, digest = _zip(tmp_path, [("v1.xml", _xml("1")), ("v3.xml", _xml("3"))])
    rows = extract_public_rd223_registry(p, archive_sha256=digest)
    assert len(rows) == 2
    assert [x["revision"] for x in rows] == ["1", "3"]
    assert len({x["registry_number"] for x in rows}) == 1


def test_rejects_source_tampering_entities_and_zip_traversal(tmp_path: Path):
    p, digest = _zip(tmp_path, [("v1.xml", _xml())])
    with pytest.raises(ValueError, match="SHA-256"):
        extract_public_rd223_registry(p, archive_sha256="f" * 64)
    p, digest = _zip(tmp_path, [("a.xml", b'<!DOCTYPE x [<!ENTITY x "oops">]><contractCutted>&x;</contractCutted>')])
    with pytest.raises(ValueError, match="DTD"):
        extract_public_rd223_registry(p, archive_sha256=digest)
    p, digest = _zip(tmp_path, [("../evil.xml", _xml())])
    with pytest.raises(ValueError, match="Unsafe"):
        extract_public_rd223_registry(p, archive_sha256=digest)


def test_invalid_contract_price_and_non_contract_skip(tmp_path: Path):
    p, digest = _zip(tmp_path, [("revision.xml", _xml(price="1 833 358,30"))])
    with pytest.raises(ValueError, match="price"):
        extract_public_rd223_registry(p, archive_sha256=digest)
    p, digest = _zip(tmp_path, [("other.xml", b"<purchaseNotice/>")])
    assert extract_public_rd223_registry(p, archive_sha256=digest) == []
