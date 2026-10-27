import hashlib
import json
import zipfile
from pathlib import Path

from src.modules.market_intelligence.pq_contract_outcome_audit import audit


def _fixture(tmp_path: Path, *, rub: str | None = None, price: str = "3680106.21",
             currency: str = "RUB", digital: str = "643") -> tuple[Path, Path, Path, Path]:
    root = tmp_path / "contracts"
    zpath = root / "56450925977260018070000" / "archive-01" / "documentation-archive.zip"
    zpath.parent.mkdir(parents=True)
    xml = b"<contractCutted><body><item><contractData/></item></body></contractCutted>"
    with zipfile.ZipFile(zpath, "w") as z:
        z.writestr("contract.xml", xml)
    leads = tmp_path / "leads.json"
    leads.write_text(json.dumps({"records": [
        {"procedure_id": "32616280467", "canonical_id": "223fz:32616280467:lot1",
         "family": "power_quality_system", "scope": "design"},
        {"procedure_id": "32699999999", "canonical_id": "extra"}
    ]}))
    entry = {"procedure_id": "32616280467",
             "contract_register_number": "56450925977260018070000",
             "lot_number": "1", "price_text": price, "ruble_price_text": rub,
             "currency_code": currency, "currency_numeric_code": digital,
             "revision_price_conflict": False, "source_archive": str(zpath),
             "source_archive_sha256": hashlib.sha256(zpath.read_bytes()).hexdigest(),
             "source_xml_member": "contract.xml",
             "source_xml_sha256": hashlib.sha256(xml).hexdigest(),
             "source_revisions": [{"source_xml_sha256": hashlib.sha256(xml).hexdigest()}]}
    contracts = tmp_path / "contract-index.json"
    contracts.write_text(json.dumps({"records": [entry]}))
    day = tmp_path / "day-scan.json"
    day.write_text(json.dumps({"records": [{"matches": [{
        "notice": "32616280467", "registry": "56450925977260018070000",
        "source_xml_sha256": hashlib.sha256(xml).hexdigest()
    }]}]}))
    return root, leads, contracts, day


def test_verified_rub_currency_fallback_with_original_sha(tmp_path: Path):
    root, leads, contracts, day = _fixture(tmp_path)
    result = audit(leads_path=leads, contracts_path=contracts,
                   contract_root=root, day_scan_path=day)
    assert result["leads_total"] == 2
    assert result["distinct_contract_lots_matched"] == 1
    assert result["contract_lots_with_rub_price"] == 1
    assert result["contract_lots_correlated_with_original_day_scan"] == 1
    record = result["records"][0]
    assert record["registry_rub_price"] == "3680106.21"
    assert record["source_integrity"] == "local_xml_verified"
    assert record["signed_contract_verified"] is False
    assert record["supplier"] is None


def test_non_rub_currency_never_infers_rub_price(tmp_path: Path):
    root, leads, contracts, day = _fixture(tmp_path, price="999", currency="USD", digital="840")
    result = audit(leads_path=leads, contracts_path=contracts,
                   contract_root=root, day_scan_path=day)
    assert result["records"][0]["registry_rub_price"] is None


def test_source_sha_tamper_blocks_price(tmp_path: Path):
    root, leads, contracts, day = _fixture(tmp_path)
    data = json.loads(contracts.read_text())
    data["records"][0]["source_xml_sha256"] = "0" * 64
    contracts.write_text(json.dumps(data))
    result = audit(leads_path=leads, contracts_path=contracts,
                   contract_root=root, day_scan_path=day)
    assert result["records"][0]["registry_rub_price"] is None
    assert result["records"][0]["source_integrity"] == "xml_sha_mismatch"


def test_revision_conflict_blocks_price(tmp_path: Path):
    root, leads, contracts, day = _fixture(tmp_path, rub="3680106.21")
    data = json.loads(contracts.read_text())
    data["records"][0]["revision_price_conflict"] = True
    contracts.write_text(json.dumps(data))
    result = audit(leads_path=leads, contracts_path=contracts,
                   contract_root=root, day_scan_path=day)
    assert result["records"][0]["registry_price_conflict"] is True
    assert result["records"][0]["registry_rub_price"] is None
