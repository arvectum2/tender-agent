import pytest

from src.modules.tender_operator_agent_demo.relevance_scoring import (
    RelevanceRecommendation,
    RelevanceStatus,
    score_procurement_card,
    score_procurement_document_text,
)
from src.modules.tender_operator_agent_demo.supplier_profile import SupplierProfile


@pytest.fixture
def demo_profile():
    return SupplierProfile.load_demo_fixture()


@pytest.fixture
def empty_profile():
    return SupplierProfile(supplier_id="empty-001", name="Empty Profile")


class TestScoreProcurementCard:
    def test_no_profile_returns_not_recommended(self):
        result = score_procurement_card(title="Любая закупка")
        assert result.score == 0.0
        assert result.status == RelevanceStatus.NOT_RECOMMENDED
        assert result.recommendation == RelevanceRecommendation.MANUAL_REVIEW_REQUIRED

    def test_empty_profile_returns_not_recommended(self, empty_profile):
        result = score_procurement_card(title="Поставка оборудования", profile=empty_profile)
        assert result.score == 0
        assert result.status == RelevanceStatus.NOT_RECOMMENDED

    def test_highly_relevant_card(self, demo_profile):
        result = score_procurement_card(
            title="Поставка электротехнического оборудования и кабельной продукции",
            initial_price=5_000_000.0,
            profile=demo_profile,
        )
        assert result.score >= 50
        assert result.reasons is not None
        assert "keywords" in result.breakdown
        assert "price_range" in result.breakdown

    def test_stop_word_triggers_penalty(self, demo_profile):
        result = score_procurement_card(
            title="Строительный ремонт помещений",
            initial_price=500_000.0,
            profile=demo_profile,
        )
        assert result.breakdown["stop_words"] < 0
        assert any("стоп-слово" in r.lower() for r in result.reasons)

    def test_price_out_of_range(self, demo_profile):
        result = score_procurement_card(
            title="Поставка электротехнического оборудования",
            initial_price=100_000_000.0,
            profile=demo_profile,
        )
        assert result.breakdown["price_range"] < 20
        assert any("выше максимальной" in r for r in result.reasons)

    def test_price_below_minimum(self, demo_profile):
        result = score_procurement_card(
            title="Поставка электротехнического оборудования",
            initial_price=10_000.0,
            profile=demo_profile,
        )
        assert result.breakdown["price_range"] < 20
        assert any("ниже минимальной" in r for r in result.reasons)

    def test_price_none(self, demo_profile):
        result = score_procurement_card(
            title="Поставка электротехнического оборудования",
            initial_price=None,
            profile=demo_profile,
        )
        assert result.breakdown["price_range"] == 5.0

    def test_score_ranges_high(self, demo_profile):
        result = score_procurement_card(
            title="Поставка электротехнического оборудования, кабельной продукции, шкафов управления и силового оборудования для распределительного узла",
            initial_price=5_000_000.0,
            profile=demo_profile,
        )
        assert result.score >= 65
        assert result.status == RelevanceStatus.HIGH
        assert result.recommendation == RelevanceRecommendation.PARTICIPATE

    def test_score_ranges_medium(self, demo_profile):
        result = score_procurement_card(
            title="Поставка кабельной продукции",
            initial_price=1_000_000.0,
            profile=demo_profile,
        )
        assert 40 <= result.score < 65
        assert result.status == RelevanceStatus.MEDIUM
        assert result.recommendation == RelevanceRecommendation.PARTICIPATE_CONDITIONALLY

    def test_score_ranges_low(self, demo_profile):
        result = score_procurement_card(
            title="Электромонтажные работы строительного характера",
            initial_price=100_000_000.0,
            profile=demo_profile,
        )
        assert 20 <= result.score < 40
        assert result.status == RelevanceStatus.LOW

    def test_score_ranges_not_recommended(self, demo_profile):
        result = score_procurement_card(
            title="Ремонт помещений и уборка",
            profile=demo_profile,
        )
        assert result.score < 20
        assert result.status == RelevanceStatus.NOT_RECOMMENDED
        assert result.recommendation == RelevanceRecommendation.DO_NOT_PARTICIPATE

    def test_unrelated_in_range_card_gets_no_neutral_relevance_boost(self, demo_profile):
        irrelevant = score_procurement_card(
            title="Оказание услуг по диагностике и ремонту автотранспорта",
            initial_price=1_000_000.0,
            submission_deadline="2026-10-01",
            profile=demo_profile,
        )
        relevant = score_procurement_card(
            title="Оказание услуг по техническому обслуживанию электротехнического оборудования",
            initial_price=50_000.0,
            submission_deadline="2026-10-01",
            profile=demo_profile,
        )

        assert irrelevant.score == 0
        assert irrelevant.breakdown["price_range"] == 0
        assert irrelevant.breakdown["risk"] == 0
        assert relevant.score > irrelevant.score

    def test_automation_does_not_match_automated_information_system(self, demo_profile):
        result = score_procurement_card(
            title="Модернизация автоматизированной информационной системы управления имуществом",
            initial_price=5_000_000.0,
            submission_deadline="2026-10-01",
            profile=demo_profile,
        )

        assert result.breakdown["keywords"] == 0
        assert result.score == 0

    def test_russian_inflections_still_match_profile_terms(self, demo_profile):
        electrical = score_procurement_card(
            title="Обслуживание электротехническим персоналом электрооборудования",
            profile=demo_profile,
        )
        commissioning = score_procurement_card(
            title="Монтаж оборудования и пусконаладочные работы",
            profile=demo_profile,
        )

        assert electrical.breakdown["keywords"] > 0
        assert commissioning.breakdown["keywords"] > 0

    def test_to_dict_contains_all_keys(self, demo_profile):
        result = score_procurement_card(
            title="Поставка оборудования",
            initial_price=1_000_000.0,
            profile=demo_profile,
        )
        d = result.to_dict()
        assert "score" in d
        assert "status" in d
        assert "recommendation" in d
        assert "reasons" in d
        assert "breakdown" in d

    def test_result_is_frozen_dataclass(self, demo_profile):
        result = score_procurement_card(
            title="Поставка оборудования",
            profile=demo_profile,
        )
        with pytest.raises(AttributeError):
            result.score = 99.0

    def test_result_dataclass_equality(self, demo_profile):
        r1 = score_procurement_card(title="Поставка оборудования", profile=demo_profile)
        r2 = score_procurement_card(title="Поставка оборудования", profile=demo_profile)
        assert r1 == r2


class TestScoreProcurementDocumentText:
    def test_no_profile(self):
        result = score_procurement_document_text(text="Любой текст документа")
        assert result["document_score"] == 0.0
        assert result["document_match_found"] is False

    def test_keyword_match_in_document(self, demo_profile):
        result = score_procurement_document_text(
            text="В техническом задании указано электротехническое оборудование для распределительного узла, включая кабель и шкаф управления.",
            profile=demo_profile,
        )
        assert result["document_score"] > 0
        assert len(result["document_matched_terms"]) > 0

    def test_certificate_match_in_document(self, demo_profile):
        result = score_procurement_document_text(
            text="Требуется сертификат соответствия ТР ТС 004/2011 на низковольтное оборудование.",
            profile=demo_profile,
        )
        assert result["document_score"] > 0

    def test_no_match(self, demo_profile):
        result = score_procurement_document_text(
            text="Договор на аренду строительной техники для ремонта помещений.",
            profile=demo_profile,
        )
        assert result["document_score"] == 0.0
        assert result["document_match_found"] is False

    def test_score_capped_at_100(self, demo_profile):
        long_matching_text = " ".join(demo_profile.criteria.keywords * 20)
        result = score_procurement_document_text(text=long_matching_text, profile=demo_profile)
        assert result["document_score"] <= 100.0
