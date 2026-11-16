from scripts.research.triage_sibur_document_text import classify_text


def test_extracts_source_bound_spans():
    text = "Поставка УКРМ и частотных преобразователей. Монтаж АСУ ТП."
    evidence = classify_text(text)
    assert set(evidence) == {"power_quality", "electrical", "automation_instrumentation"}
    for records in evidence.values():
        for item in records:
            assert item["excerpt"] == text[item["start"]:item["end"]]
            assert item["match"] in item["excerpt"]


def test_no_false_approval():
    assert not classify_text("Поставка бумаги и канцтоваров")
