"""Critical source-type and report-language regression for three earlier SOAP gaps."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from src.modules.tender_operator_agent_demo import (
    r4_price_inquiry_primary_audit as audit,
)

_DATA = Path(__file__).resolve().parents[1] / "docs" / "acceptance" / "data"


def _matrix():
    return json.loads(
        (_DATA / "TDP_R4_20_LATER_BINARY_RECOVERY_2026-10-14.json").read_text(encoding="utf8")
    )


def _fake_originals(tmp_path: Path, monkeypatch):
    originals = tmp_path / "official"
    originals.mkdir()
    (originals / "official-attachments-private-20261014").mkdir()
    records = []
    file_receipts = []
    binaries = {}
    for number, case in audit._CASES.items():
        pages = {}
        for kind, url in audit._official_urls(number).items():
            text = (
                f"Запрос цен товаров, работ, услуг. {number}. "
                f"{case['title']}; {case['customer']}; {case['published']}; "
                f"{case['pricing_deadline']}; {case['official_page_status']}"
            )
            links = "".join(
                '<a href="https://zakupki.gov.ru/44fz/filestore/public/1.0/'
                f'download/pricereq/file.html?uid={i:032X}">'
                f'{case["source_citation_labels"][i-1]}</a>'
                for i in range(1, case["attachment_count"] + 1)
            ) if kind == "docs" else ""
            raw_html = (text + links).encode("utf8")
            raw_txt = (text + " " + " ".join(case["source_citation_labels"])).encode("utf8")
            (originals / f"{number}-{kind}.html").write_bytes(raw_html)
            (originals / f"{number}-{kind}.txt").write_bytes(raw_txt)
            pages[kind] = {
                "url": url, "http_status": 200,
                "html_sha256": hashlib.sha256(raw_html).hexdigest(),
                "text_sha256": hashlib.sha256(raw_txt).hexdigest(),
            }
        records.append({"reg_number": number, "category_attested_by_first_party": True, "pages":pages})
        prefix=originals/"official-attachments-private-20261014"
        for filename, phrase in case["proofs_in_extracts"]:
            txt=prefix/filename
            existing=txt.read_text(encoding="utf8") if txt.exists() else ""
            txt.write_text(existing + "\n" + phrase,encoding="utf8")
        for idx in range(1, case["attachment_count"]+1):
            extension={("0148300050426000047",1):".docx",
                       ("0318200087026000163",1):".doc",
                       ("0318200087026000163",2):".docx",
                       ("0348100024426000052",1):".pdf"}[(number,idx)]
            fn=f"{number}-{idx}{extension}"
            raw=f"original EIS attachment {number}/{idx}".encode()
            (prefix/fn).write_bytes(raw)
            sha=hashlib.sha256(raw).hexdigest()
            binaries[fn]=(sha,len(raw))
            file_receipts.append({
                "registry_number": number, "local_file": fn, "status":"DOWNLOADED_ORIGINAL",
                "http_status":200, "sha256":sha, "bytes":len(raw),
            })
    receipt=(json.dumps({"results": records},sort_keys=True,ensure_ascii=False)).encode()
    (originals/"first-party-registry-receipt.json").write_bytes(receipt)
    attachments=(json.dumps(file_receipts,ensure_ascii=False,sort_keys=True)).encode()
    (originals/"official-attachments-private-20261014"/"manifest-private.json").write_bytes(attachments)
    monkeypatch.setattr(audit,"_PRICE_PRIMARY_PIN",hashlib.sha256(receipt).hexdigest())
    monkeypatch.setattr(audit,"_ATTACHMENT_RECEIPT_PIN",hashlib.sha256(attachments).hexdigest())
    monkeypatch.setattr(audit,"_BINARY_RECEIPTS",binaries)
    return originals


def test_machine_source_audit_disproves_three_missing_records(tmp_path,monkeypatch):
    orig=_fake_originals(tmp_path,monkeypatch)
    matrix=_matrix()
    before=json.dumps(matrix,sort_keys=True)
    result=audit.reconcile_price_inquiry_originals(matrix,orig)
    assert json.dumps(matrix,sort_keys=True)==before
    assert result["summary"]["original_price_inquiry_cards_confirmed"]==3
    assert result["summary"]["price_inquiry_original_attachments_retrieved"]==4
    assert len(result["cases"])==20
    for c in result["cases"]:
        if c["reg_number"] not in audit._CASES:
            continue
        assert c["official_archive_status"]=="NO_DATA"  # historical SOAP method-only truth
        assert c["verified_primary_record_type"]=="EIS_PRICE_INFORMATION_REQUEST"
        assert "документы доступны" in c["customer_source_status"]
        assert c["official_document_count"]>=1
        assert c["client_maximum_contract_price"] is None
        assert c["bid_ready"] is False
        assert c["expert_gold"] is False
        assert "MARKET_PRICE_INFORMATION_ONLY_NO_COMPETITIVE_BID" in c["blockers"]


def test_customer_report_clear_and_technical_messages_excluded(tmp_path,monkeypatch):
    result=audit.reconcile_price_inquiry_originals(_matrix(),_fake_originals(tmp_path,monkeypatch))
    report=audit.client_expert_source_report(result)
    for banned in ("no_data","getDocsIP","HTTP 409","SOURCE_UNAVAILABLE","Traceback",
                   "SHA256","status_code","JSONDecodeError","UNKNOWN/DEFER"):
        assert banned not in report
    assert report.count("### ")==3
    assert "до 31 декабря 2025 года" in report
    assert "пять календарных дней" in report
    assert "83 физические страницы" in report
    assert "актуальной" in report
    assert "сведения" in report.lower()


def test_bad_official_html_evidence_does_not_allow_source_classification(tmp_path,monkeypatch):
    orig=_fake_originals(tmp_path,monkeypatch)
    fp=orig/"0148300050426000047-card.html"
    fp.write_bytes(fp.read_bytes()+b"tampered")
    with pytest.raises(ValueError, match="digest"):
        audit.reconcile_price_inquiry_originals(_matrix(),orig)


def test_bad_official_binary_evidence_fails_closed(tmp_path,monkeypatch):
    orig=_fake_originals(tmp_path,monkeypatch)
    fp=orig/"official-attachments-private-20261014"/"0348100024426000052-1.pdf"
    fp.write_bytes(fp.read_bytes()+b"tampered")
    with pytest.raises(ValueError, match="bytes"):
        audit.reconcile_price_inquiry_originals(_matrix(),orig)


def test_missing_first_party_page_is_not_imputed_from_secondary_source(tmp_path,monkeypatch):
    orig=_fake_originals(tmp_path,monkeypatch)
    (orig/"0318200087026000163-docs.txt").unlink()
    with pytest.raises(FileNotFoundError):
        audit.reconcile_price_inquiry_originals(_matrix(),orig)


def test_three_original_price_inquiries_are_not_turned_into_competitions(tmp_path,monkeypatch):
    orig=_fake_originals(tmp_path,monkeypatch)
    matrix=_matrix()
    wrong=next(c for c in matrix["cases"] if c["reg_number"]=="0148300050426000047")
    wrong["official_archive_status"]="HISTORIC_ARCHIVED_ZIP"
    with pytest.raises(ValueError,match="SOAP archive absence"):
        audit.reconcile_price_inquiry_originals(matrix,orig)


def test_unmatched_number_and_source_receipt_not_trusted(tmp_path,monkeypatch):
    orig=_fake_originals(tmp_path,monkeypatch)
    raw=json.loads((orig/"first-party-registry-receipt.json").read_text())
    raw["results"][0]["reg_number"]="0348100024426000052"
    bb=json.dumps(raw,sort_keys=True,ensure_ascii=False).encode()
    (orig/"first-party-registry-receipt.json").write_bytes(bb)
    monkeypatch.setattr(audit,"_PRICE_PRIMARY_PIN",hashlib.sha256(bb).hexdigest())
    with pytest.raises(ValueError,match="set incomplete/duplicated"):
        audit.reconcile_price_inquiry_originals(_matrix(),orig)


def test_real_first_party_originals_mac_mini_readonly_replay():
    import os
    provided=os.environ.get("TA_PRIVATE_EIS_PRICE_REQUEST_ORIGINALS")
    if not provided:
        pytest.skip("private originals unavailable on CI; synthetic negative tests still run")
    result=audit.reconcile_price_inquiry_originals(_matrix(),Path(provided))
    assert result["summary"]["original_price_inquiry_cards_confirmed"]==3
    assert result["summary"]["price_inquiry_original_attachments_retrieved"]==4
    assert all(c["bid_ready"] is False for c in result["cases"])
