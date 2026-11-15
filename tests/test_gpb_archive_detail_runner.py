from scripts.research.run_gpb_archive_details import select


def test_selection_never_overlaps_prior_queue_or_seen():
    q={"candidates":[{"external_id":str(x)} for x in range(6)]}
    assert select(q,{"0","3"},{"1"},2)==[{"external_id":"2"},{"external_id":"4"}]
