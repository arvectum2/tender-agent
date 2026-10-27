"""ChatGPT classifications must be tied to exact original text."""
import pytest

from src.modules.market_intelligence.pq_chatgpt_review import validate_review


def test_grounded_review():
    packet = {"registry_number": "32313113128", "documents": [
        {"sha256": "a" * 64, "text": "поставка автомобиля для аварийно-спасательного формирования"}]}
    review = {"registry_number": "32313113128", "classification": "irrelevant",
              "evidence": [{"sha256": "a" * 64,
                            "quote": "поставка автомобиля для аварийно-спасательного формирования"}]}
    result = validate_review(packet=packet, review=review)
    assert result["classification"] == "irrelevant"
    assert result["market_total_rub"] is None
    review["evidence"][0]["quote"] = "несуществующая поставка компенсаторов мощности"
    with pytest.raises(ValueError):
        validate_review(packet=packet, review=review)
