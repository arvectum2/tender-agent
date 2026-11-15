from scripts.research.capture_gpb_priority_details import select_candidates


def test_sale_not_counted_as_demand_or_consuming_batch():
    rows = [{"observation": {"external_id": value}} for value in
            ["sale:1", "etp:2", "etp:3", "price_request:4"]]
    priority = {"sale:1", "etp:2", "etp:3", "price_request:4"}
    selected, sales = select_candidates(rows, priority, {"etp:2"}, 2)
    assert [r["external_id"] for r in selected] == ["etp:3", "price_request:4"]
    assert [r["external_id"] for r in sales] == ["sale:1"]
