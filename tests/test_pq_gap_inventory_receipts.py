"""A retrieval receipt alone is not a procurement original."""
import json

from src.modules.market_intelligence.pq_gap_recovery import inventory


def test_receipt_only_folder_is_not_original_coverage(tmp_path):
    leads = tmp_path / "leads.json"
    leads.write_text(json.dumps({"records": [
        {"procedure_id": "32500000001", "canonical_id": "223fz:32500000001:lot1"},
        {"procedure_id": "32500000002", "canonical_id": "223fz:32500000002:lot1"},
    ]}))
    source = tmp_path / "originals"
    receipt_only = source / "32500000001"
    receipt_only.mkdir(parents=True)
    (receipt_only / "public-page-receipt.json").write_text('{"status": "downloaded"}')
    (receipt_only / "manifest.json").write_text("{}")
    (receipt_only / "file.sha256").write_text("a" * 64)
    with_original = source / "32500000002"
    with_original.mkdir()
    (with_original / "download_receipt.json").write_text("{}")
    (with_original / "01-technical.docx").write_bytes(b"synthetic fixture")
    output = tmp_path / "inventory.json"
    summary = inventory(leads_file=leads, source_roots=[source],
                        queue_dir=tmp_path / "queue", output=output)
    assert summary["with_local_documents"] == 1
    rows = json.loads(output.read_text())["cases"]
    assert rows[0]["source_documents_local"] == []
    assert rows[0]["missing_or_unverified"] == [
        "original_notice", "technical_specification", "award_protocol",
        "signed_contract", "winner", "initial_price", "contract_price",
    ]
    assert len(rows[1]["source_documents_local"]) == 1
    assert rows[1]["source_documents_local"][0].endswith("01-technical.docx")
    assert "signed_contract" in rows[1]["missing_or_unverified"]
