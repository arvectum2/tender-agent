from scripts.research.report_gpb_named_competitors import build


def test_no_double_count_or_mixed_tax_or_contract_claim():
    a={"parser_schema":"gpb_named_outcome_v4","external_id":"etp:1","participant_name_as_published":"ООО «Тест»",
       "participant_address_as_published":"123456, г. Москва","best_bid_rub":"100.00","best_bid_tax_basis":"excludes_vat",
       "initial_price_rub":"200.00","initial_price_tax_basis":"excludes_vat"}
    t={"source":"etp_gpb","purchase_number":"1","title":"Поставка электрооборудования",
       "customer_name":"Заказчик","publication_date":"2024-01-01"}
    r=build([a,a|{"document_url":"u2"},a|{"external_id":"etp:2","best_bid_tax_basis":"includes_vat"}],
            {"etp:1":t,"etp:2":t})
    assert r["verified_named_procedures"]==2
    assert r["companies"][0]["selected_procedures"]==2
    assert r["companies"][0]["best_bid_sums_by_tax_basis"]=={"excludes_vat":"100.00","includes_vat":"100.00"}
    assert r["verified_signed_contracts"]==0
    assert build([a,a|{"best_bid_rub":"99.00"}],{"etp:1":t})["review_count"]==1
