import json
import zipfile
from pathlib import Path

from src.modules.market_intelligence.pq_contract_xml_index import scan


def test_exact_notice_and_source_provenance(tmp_path: Path):
    root = tmp_path / "contracts"
    archive = root / "test" / "archive-01" / "documentation-archive.zip"
    archive.parent.mkdir(parents=True)
    xml = b"""<contractCutted><body><item><contractData>
    <registrationNumber>12345678901234567890</registrationNumber>
    <contractRegNumber>12345678901234567890</contractRegNumber>
    <purchaseNoticeInfo><purchaseNoticeNumber>32615614821</purchaseNoticeNumber></purchaseNoticeInfo>
    <lotNum>1</lotNum><price>1833358.30</price><status>P</status>
    </contractData></item></body></contractCutted>"""
    with zipfile.ZipFile(archive, "w") as writer:
        writer.writestr("contract.xml", xml)
    leads = tmp_path / "leads.json"
    leads.write_text(json.dumps({"records": [
        {"procedure_id": "32615614821"}, {"procedure_id": "32699999999"}]}))
    result = scan(root, leads)
    assert result["archives_inspected"] == 1
    assert len(result["records"]) == 1
    record = result["records"][0]
    assert record["procedure_id"] == "32615614821"
    assert record["source_xml_sha256"]
    assert record["source_archive_sha256"]
    assert record["price_text"] == "1833358.30"
    assert record["supplier_verified"] is False
    assert record["signed_contract_verified"] is False


def test_reject_symlink_root(tmp_path: Path):
    source = tmp_path / "actual"
    source.mkdir()
    shortcut = tmp_path / "alias"
    shortcut.symlink_to(source, target_is_directory=True)
    leads = tmp_path / "leads.json"
    leads.write_text('{"records":[]}')
    import pytest
    with pytest.raises(ValueError):
        scan(shortcut, leads)
