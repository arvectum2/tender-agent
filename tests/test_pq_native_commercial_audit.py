import hashlib
import json
from pathlib import Path

import pytest
from docx import Document

from src.modules.market_intelligence.pq_native_commercial_audit import audit


def _fixture(tmp_path: Path):
    cases = []
    for number, pdf_id, kind in [
        ("COM07102500074", "4211433", "original_cancel_pdf_sha"),
        ("COM16012600053", "1835376", "original_results_pdf_sha"),
    ]:
        page_dir = tmp_path / "roseltorg-original-pages" / number
        page_dir.mkdir(parents=True)
        card = (
            f"<html>{number}<a href=\"https://com.roseltorg.ru/file/get/"
            f"t/Protocols/id/{pdf_id}/name/test.pdf\">source</a></html>"
        ).encode()
        (page_dir / "original.html").write_bytes(card)
        pdf_dir = tmp_path / "roseltorg-original-files" / number
        pdf_dir.mkdir(parents=True)
        pdf = b"%PDF-1.4 source fixture " + number.encode()
        (pdf_dir / (pdf_id + ".pdf")).write_bytes(pdf)
        cases.append({
            "id": number,
            "class": "irrelevant_0.4kV_cancelled",
            "original_card_sha": hashlib.sha256(card).hexdigest(),
            kind: hashlib.sha256(pdf).hexdigest(),
            "signed_contract": False,
        })
    number = "RAD260049805"
    rad = tmp_path / "rad-originals" / number
    rad.mkdir(parents=True)
    html = (f"<html>{number} <a href=\"/etp/downloadppf?uuid="
            "dbfile19718ug0000q23smrosvj7mv2g\">ТЗ</a></html>").encode()
    (rad / "card.html").write_bytes(html)
    doc = Document()
    quotes = [
        "Установка БСК 35 кВ - 1 шт.",
        "оборудование, закупленное и передаваемое подрядчику в виде давальческого оборудования",
    ]
    for quote in quotes:
        doc.add_paragraph(quote)
    doc.save(rad / "technical.docx")
    cases.append({
        "id": number, "class": "relevant_35kV_design_installation_owner_furnished",
        "original_card_sha": hashlib.sha256(html).hexdigest(),
        "original_technical_docx_sha": hashlib.sha256(
            (rad / "technical.docx").read_bytes()).hexdigest(),
        "native_quotes": quotes, "owner_furnished": True,
        "signed_contract": False,
    })
    review = tmp_path / "review.json"
    review.write_text(json.dumps({
        "schema_version": "pq-first-party-etp-review/1",
        "cases": cases,
    }))
    return review


def test_source_grade_commercial_etp_overlay_without_fake_equipment_sales(tmp_path: Path):
    review = _fixture(tmp_path)
    result = audit(runtime=tmp_path, review=review)
    assert result["source_case_count"] == 3
    assert result["signed_suppliers_verified"] == 0
    assert result["equipment_only_sales_verified"] == 0
    cases = {x["procedure_id"]: x for x in result["records"]}
    assert cases["COM07102500074"]["source_outcome_scope"] == "visual_review_provisional"
    assert cases["COM16012600053"]["voltage_6_35_verified_from_native_text"] is False
    assert cases["RAD260049805"]["source_outcome_scope"] == "35kv_design_install_owner_furnished_bsk"
    assert cases["RAD260049805"]["equipment_supply_contract_verified"] is False


def test_tampered_primary_pdf_is_rejected(tmp_path: Path):
    review = _fixture(tmp_path)
    pdf = tmp_path / "roseltorg-original-files" / "COM07102500074" / "4211433.pdf"
    pdf.write_bytes(b"%PDF-1.4 altered")
    with pytest.raises(ValueError, match="not bound"):
        audit(runtime=tmp_path, review=review)


def test_false_signed_supplier_from_visual_review_rejected(tmp_path: Path):
    review = _fixture(tmp_path)
    data = json.loads(review.read_text())
    data["cases"][0]["signed_contract"] = True
    review.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="cannot certify signed"):
        audit(runtime=tmp_path, review=review)


def test_owner_furnished_rad_docx_quote_must_be_exact(tmp_path: Path):
    review = _fixture(tmp_path)
    data = json.loads(review.read_text())
    data["cases"][2]["native_quotes"].append("БСК поставлена подрядчиком")
    review.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="quote not found"):
        audit(runtime=tmp_path, review=review)
