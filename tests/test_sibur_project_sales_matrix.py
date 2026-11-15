from scripts.research.build_sibur_project_sales_matrix import build


def row(i,title,org="ПАО СИБУР Холдинг"):
    return {"external_id":i,"title":title,"publication_date":"2026-11-01","observations":[{
        "title":title,"subject":title,"organizer":org,"status_raw":"Прием предложений",
        "source_url":"https://example.test/","source_sha256":"a"*64,"source_row":"1"}]}


def test_full_project_scan_and_no_supplier_inference():
    r=build([row("1/1","NPG SPR распределительные шкафы"),row("2/1","ПНР стирольная цепочка"),
             row("3/1","АГПЗ, сети АГХК"),row("4/1","металлоценовые катализаторы")],{"candidates":[]})
    assert r["unique_project_publications"]==4
    assert r["summary"]["NPG_SPR"]["tiers"]=={"expanded_electrical_candidate":1}
    assert r["summary"]["STYRENE"]["tiers"]=={"project_package_review":1}
    assert r["summary"]["AGHK"]["mixed_project_records"]==1
    assert "METALLOCENE_PE" not in r["summary"]
    assert all(x["contract"] is None and x["supplier"] is None for x in r["records"])


def test_technical_after_budget_not_commercial():
    r=build([row("1/1","НПГ СПР техническая оценка после бюджетной оценки")],{"candidates":[]})
    assert r["records"][0]["phase"]=="technical_assessment"
