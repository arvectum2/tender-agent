"""False positive guard: pedestrian safety reflectors are not grid flicker."""

from pathlib import Path

import yaml

from src.modules.market_intelligence.technical_matching import _matching_terms


def test_flicker_requires_power_quality_context():
    path = Path(__file__).resolve().parents[1] / "data/market_intelligence/power_quality/ontology.v1.yaml"
    ontology = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert _matching_terms("Тип фликера: значок светоотражающий", ontology) == []
    found = _matching_terms("Фликер: модернизация подстанции", ontology)
    assert any(item["family"] == "power_quality_system" for item in found)
