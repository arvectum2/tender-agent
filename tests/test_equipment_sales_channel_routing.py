from scripts.research.split_equipment_sales_channels import split


def row(i,title,tags,ups=None):
    return {"external_id":i,"title":title,"subject":[title],"core_tags":tags,
            "ups_tags":ups or [],"source_receipts":[]}


def test_ups_only_is_not_general_equipment_lead():
    result = split({"candidates":[row("1","ИБП 20 кВА",["Источники и качество питания","ИБП и комплектующие"],["explicit_ups"])]})
    assert result["channel_counts"]=={"ups_battery":1}
    assert not result["records"][0]["supplier_assigned"]


def test_mix_requires_review_and_keeps_pq():
    result = split({"candidates":[row("2","ИБП и УКРМ",["Источники и качество питания","ИБП и комплектующие"],["explicit_ups"]),
        row("3","АКБ неизвестного назначения",["ИБП и комплектующие"],["battery_application_review"])]})
    assert result["records"][0]["allocation"]=="mixed_package_manual_scope_review"
    assert result["records"][1]["allocation"]=="ups_battery_application_review"
    assert all(not r["execution_allowed"] for r in result["records"])
