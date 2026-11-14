import pytest

from scripts.research.import_sibur_public_snapshot import build_rows


def observation():
    return {
        "external_id": "1234567/1", "title": "Test", "subject": "Spec",
        "method": "Request", "published_raw": "14.11.2026", "deadline_raw": "19.11.2026 09:00",
        "organizer": "Buyer", "status_raw": "Open", "category": "Equipment",
        "documentation_label": "Doc", "source": "sibur_public",
        "source_url": "https://www.sibur.ru/ru/procurement/buy/?PAGEN_1=1",
        "source_sha256": "a" * 64, "verification": "PUBLIC_SNAPSHOT_ONLY",
        "source_row": "1", "documentation_urls": [], "unverified_document_links": 0,
    }


def test_import_preserves_source_and_observations():
    first = observation()
    second = {**first, "source_row": "2", "documentation_label": "Other doc"}
    groups = [{"external_id": first["external_id"], "observations": [first, second]}]
    a, b = build_rows(groups)[0], build_rows(groups)[0]
    assert a["source"] == "sibur_public"
    assert a["external_id"] == "1234567/1"
    assert len(a["raw_payload"]["observations"]) == 2
    assert a["content_hash"] == b["content_hash"]
    assert a["application_deadline"] is None
    assert not a["raw_payload"]["deadline_timezone_verified"]


@pytest.mark.parametrize("change", [{"source": "eis"}, {"contact": "x"}, {"external_id": "other"}])
def test_import_rejects_cross_source_or_unknown_fields(change):
    row = {**observation(), **change}
    with pytest.raises(ValueError):
        build_rows([{"external_id": "1234567/1", "observations": [row]}])
