import json
from pathlib import Path

from src.modules.market_intelligence.pq_commission_candidate_audit import extract


def test_qualified_bidder_and_ocr_proposed_winner_are_not_contract_suppliers(tmp_path: Path):
    outcome = tmp_path / "outcome.json"
    outcome.write_text(json.dumps({"records": [
        {"procedure_id": "32615614821"}, {"procedure_id": "32616280467"}]}))
    queue = tmp_path / "queue"
    queue.mkdir()
    native = (
        "Первое место: цена. Лот Реконструкция ПС ООО «Башкирэнерго». "
        "Заявки участников ОБЩЕСТВОМ С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ «ТЕХНОПРОМ» "
        "признаются соответствующими.")
    native = native.replace("ОБЩЕСТВОМ", "ОБЩЕСТВО")
    ocr = ("предлагается признать Победителем запроса цен по результатам "
           "конкурентного предварительного отбора участника, занявшего "
           "первое место, а именно: ООО «Электриксервис»")
    for number, method, body in [
        ("32615614821", "native_pdf_text", native),
        ("32616280467", "ocr_unverified", ocr),
    ]:
        (queue / f"{number}-reviewed.json").write_text(json.dumps({
            "schema_version": "pq-review-queue/1", "state": "reviewed",
            "packet": {"registry_number": number, "documents": [
                {"filename": "minutes.pdf", "method": method,
                 "sha256": "a" * 64 if number == "32615614821" else "b" * 64,
                 "text": body},
            ]}}))
    result = extract(outcome_path=outcome, queue_dir=queue)
    byname = {x["candidate_name"]: x for x in result["records"]}
    assert set(byname) == {"ТЕХНОПРОМ", "Электриксервис"}
    assert byname["ТЕХНОПРОМ"]["role_in_protocol"] == "bidder_qualified_for_consideration"
    assert byname["ТЕХНОПРОМ"]["ocr_visual_review_required"] is False
    assert byname["Электриксервис"]["role_in_protocol"] == "commission_proposed_winner"
    assert byname["Электриксервис"]["ocr_visual_review_required"] is True
    assert all(x["contract_supplier_verified"] is False for x in result["records"])
    assert all(x["award_legally_verified"] is False for x in result["records"])
    assert all(x["evidence_excerpt"] in (native, ocr) for x in result["records"])


def test_pending_packets_not_used(tmp_path: Path):
    outcome = tmp_path / "outcome.json"
    outcome.write_text('{"records":[{"procedure_id":"32616280467"}]}')
    queue = tmp_path / "queue"
    queue.mkdir()
    (queue / "pending.json").write_text(json.dumps({
        "schema_version": "pq-review-queue/1",
        "state": "pending_review",
        "packet": {"registry_number": "32616280467", "documents": [
            {"method": "ocr_unverified", "sha256": "c"*64,
             "text": "признать Победителем, а именно: ООО «Ложный»"}]}}))
    result = extract(outcome_path=outcome, queue_dir=queue)
    assert result["candidate_mentions"] == 0
