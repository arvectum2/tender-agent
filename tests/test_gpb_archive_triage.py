from scripts.research.triage_gpb_archive_imports import SALE, matches


def test_pq_is_high_precision_and_offsets_are_source_based():
    title="Модернизация УКРМ и системы компенсации реактивной мощности"
    result=matches(title)
    assert "power_quality" in result and "engineering_epc" in result
    for found in result.values():
        for span in found:
            assert title[span["start"]:span["end"]]==span["match"]
    assert SALE.search("Продажа трансформатора")
    assert not SALE.search("Поставка трансформатора")
