"""MI-003 integration acceptance: intake, hybrid retrieval and role evidence."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.modules.market_intelligence.portfolio_pipeline import (
    PortfolioInputError,
    ingest_supplier,
    monthly_coverage,
    portfolio_collection,
    propose_families,
    search_demand,
    validated_role_graph,
)


@pytest.fixture
def ontology():
    path = Path(__file__).resolve().parents[1] / "data/market_intelligence/power_quality/ontology.v1.yaml"
    return yaml.safe_load(path.read_text())


class FakePlatform:
    def contract(self):
        return {"version": "1.0", "capabilities": ["search", "terminology_search_v1"]}

    def __init__(self, hits=None):
        self.calls = []
        self.hits = hits or []

    def ensure_collection(self, **kwargs):
        self.calls.append(("ensure", kwargs))
        return {"collection_id": kwargs["collection_id"]}

    def ingest_document(self, **kwargs):
        self.calls.append(("text", kwargs))
        return {"resource_id": "r-text", "document_id": "d-text", "extraction_status": "extracted"}

    def ingest_document_bytes(self, **kwargs):
        self.calls.append(("file", kwargs))
        return {"resource_id": "r-file", "document_id": "d-file", "extraction_status": "extracted"}

    def ingest_url(self, **kwargs):
        self.calls.append(("url", kwargs))
        return {"resource_id": "r-url", "document_id": "d-url", "extraction_status": "extracted"}

    def search(self, **kwargs):
        self.calls.append(("search", kwargs))
        return self.hits


def _hit(text: str, **changes):
    row = {
        "chunk_id": "chunk-123", "document_id": "document-123",
        "canonical_uri": "https://zakupki.gov.ru/notices/item",
        "title": "Строительство ПС 110 кВ", "text": text,
        "scores": {"fusion": 0.47}, "metadata": {
            "source_sha256": "b" * 64,
            # Simulates source-scoped annotation from Data Platform, not MI.
            "terminology_matches": ([{
                "id": "statcom", "terms": ["СТАТКОМ"],
                "contexts": [], "classification": "explicit_technical_candidate",
            }] if "СТАТКОМ" in text else []),
        },
    }
    row.update(changes)
    return row


def test_tenant_and_run_separate_collections():
    assert portfolio_collection("tenant_01", "run_01") != portfolio_collection("tenant_02", "run_01")
    assert portfolio_collection("tenant_01", "run_01") != portfolio_collection("tenant_01", "run_02")
    assert portfolio_collection("tenant_01", "run_01") == portfolio_collection("tenant_01", "run_01")
    with pytest.raises(PortfolioInputError):
        portfolio_collection("../admin", "run_01")


def test_multi_source_intake_binds_all_calls_to_same_tenant_collection(tmp_path):
    file = tmp_path / "offer.pdf"
    file.write_bytes(b"%PDF-1.4\nDummy header")
    client = FakePlatform()
    result = ingest_supplier(
        client, tenant_id="tenant_01", run_id="run_01",
        company_name="Технический поставщик",
        text="Поставляем устройства STATCOM и УКРМ", urls=["https://example.com/catalog"],
        files=[file],
    )
    assert result["material_count"] == 3
    kinds = [x[0] for x in client.calls]
    assert kinds == ["ensure", "text", "url", "file"]
    collections = [x[1]["collection_id"] for x in client.calls]
    assert len(set(collections)) == 1
    assert all(x["collection_id"] == result["portfolio_collection"] for x in result["materials"])


@pytest.mark.parametrize("url", [
    "http://example.com", "file:///etc/passwd", "https://127.0.0.1/path",
    "https://localhost/x", "https://user:pass@example.com/",
    "https://192.168.1.5/", "https://example.com:8443/", "https://service.internal",
])
def test_ssrf_inputs_rejected_before_remote_collection_creation(url):
    client = FakePlatform()
    with pytest.raises(PortfolioInputError):
        ingest_supplier(client, tenant_id="tenant_01", run_id="run_01",
                        company_name="Supply", urls=[url])
    assert not client.calls


def test_unsupported_or_oversize_upload_fails_before_dp(tmp_path):
    client = FakePlatform()
    p = tmp_path / "code.sh"
    p.write_text("rm -rf /")
    with pytest.raises(PortfolioInputError):
        ingest_supplier(client, tenant_id="tenant_01", run_id="run_01",
                        company_name="Supply", files=[p])
    assert not client.calls


def test_power_quality_product_family_proposals_are_not_verified(ontology):
    proposed = propose_families(
        "Оборудование STATCOM динамическая компенсация. УКРМ для КТП. "
        "Фильтр высших гармоник.", ontology
    )
    assert {r["family"] for r in proposed} == {"statcom", "ukrm", "harmonic_filter"}
    assert all(r["review_state"] == "candidate_supplier_capability" for r in proposed)


def test_svg_graphics_and_bare_pq_not_technical_pq(ontology):
    proposed = propose_families("Мы рисуем SVG vector graphics. Работаем с PQ.", ontology)
    assert "statcom" not in {r["family"] for r in proposed}


def test_hybrid_search_finds_pq_in_embedded_epc_document(ontology):
    client = FakePlatform([_hit("КТП и ЛЭП, установка СТАТКОМ 5 МВАр для стабилизации")])
    result = search_demand(
        client, tenant_id="tenant_01", source_collections=["eis_223_tenant_01"],
        families=["statcom"], ontology=ontology,
        authorized_collection_ids={"eis_223_tenant_01"},
        reviewed_source_hashes={"https://zakupki.gov.ru/notices/item": "b" * 64},
    )
    assert result["retrieval_count"] == 1
    hit = result["candidate_hits"][0]
    assert hit["classification"] == "explicit_technical_candidate"
    assert hit["source_grade"] == "reviewed_source_manifest"
    assert hit["procurement_verified"] is False and hit["winner"] is None
    assert hit["market_value_rub"] is None
    assert result["contract_and_market_facts_promoted"] == 0
    assert client.calls[0][1]["mode"] == "hybrid"
    assert client.calls[0][1]["collections"] == ["eis_223_tenant_01"]
    assert client.calls[0][1]["terminology_groups"][0]["id"] == "statcom"
    assert "SVG" in client.calls[0][1]["terminology_groups"][0]["ambiguous_aliases"]
    assert "query_variants" not in client.calls[0][1]
    assert result["queries"][0]["expansion_owner"] == "data_platform"
    assert client.calls[0][1]["terminology_version"] == "power-quality-ontology/0.1"


def test_vector_hit_without_technical_statement_is_unreviewed(ontology):
    client = FakePlatform([_hit("Поставка трансформатора. Реконструкция подстанции")])
    result = search_demand(
        client, tenant_id="tenant_01", source_collections=["eis_223_tenant_01"],
        families=["statcom"], ontology=ontology,
        authorized_collection_ids={"eis_223_tenant_01"}
    )
    assert result["candidate_hits"][0]["classification"] == "semantic_candidate_requires_manual_review"
    assert result["candidate_hits"][0]["award_verified"] is False


def test_unbound_source_hash_keeps_retrieval_unverified(ontology):
    client = FakePlatform([_hit("Строительство подстанции. СТАТКОМ в составе проекта",
                                 metadata={})])
    r = search_demand(
        client, tenant_id="tenant_01", source_collections=["eis_223_tenant_01"],
        families=["statcom"], ontology=ontology,
        authorized_collection_ids={"eis_223_tenant_01"}
    )
    assert r["candidate_hits"][0]["source_grade"] == "pending_original_source_hash_or_url"


def test_source_search_rejects_unauthorized_cross_tenant_collection(ontology):
    client = FakePlatform()
    with pytest.raises(PortfolioInputError, match="explicitly authorized"):
        search_demand(
            client, tenant_id="tenant_01", source_collections=["private_tenant_02"],
            authorized_collection_ids={"eis_223_tenant_01"},
            families=["statcom"], ontology=ontology,
        )
    assert not client.calls


def test_source_hash_in_search_hit_not_a_trusted_manifest(ontology):
    client = FakePlatform([_hit("СТАТКОМ для новой подстанции")])
    result = search_demand(
        client, tenant_id="tenant_01", source_collections=["eis_223_tenant_01"],
        authorized_collection_ids={"eis_223_tenant_01"},
        families=["statcom"], ontology=ontology,
    )
    assert result["candidate_hits"][0]["source_grade"] == "unverified_index_metadata"
    assert result["candidate_hits"][0]["procurement_verified"] is False


def test_source_search_rejects_unknown_family_before_api(ontology):
    client = FakePlatform()
    with pytest.raises(PortfolioInputError):
        search_demand(client, tenant_id="tenant_01",
                      source_collections=["eis_223_tenant_01"], families=["unicorn"], ontology=ontology,
                      authorized_collection_ids={"eis_223_tenant_01"})
    assert not client.calls


def test_assertions_require_primary_source_and_human_review():
    value = {
        "project_id": "substation_01", "role": "epc_contractor",
        "organization": {"inn": "7707083893", "name": "EPC Company"},
        "evidence": {
            "source_type": "signed_contract", "review_state": "approved",
            "reviewer": "analyst_01", "url": "https://zakupki.gov.ru/epz/contract/01",
            "locator": "Договор 1, пункт 2.1",
            "excerpt": "Подрядчик выполняет проектирование и монтаж",
            "document_sha256": "a" * 64,
        },
    }
    graph = validated_role_graph([value], permitted_project_ids={"substation_01"})
    assert len(graph["verified_edges"]) == 1
    assert graph["verified_edges"][0]["confidence"] == "human_verified_primary"
    secondary = {
        **value,
        "evidence": {**value["evidence"], "source_type": "third_party_card"}
    }
    quarantined = validated_role_graph([secondary], permitted_project_ids={"substation_01"})
    assert len(quarantined["verified_edges"]) == 0
    assert quarantined["unverified_role_count"] == 1


def test_winner_role_not_from_project_marketing():
    sample = {
        "project_id": "P", "role": "winning_bidder",
        "organization": {"inn": "7707083893"},
        "evidence": {"source_type": "primary_project_document",
                     "review_state": "approved", "reviewer": "human",
                     "locator": "page 2", "excerpt": "proposal",
                     "document_sha256": "a" * 64,
                     "url": "https://example.org/doc.pdf"},
    }
    assert not validated_role_graph([sample], permitted_project_ids={"P"})["verified_edges"]


def test_coverage_unknown_denominators_are_null_not_zero():
    result = monthly_coverage(
        start="2023-10-24", end="2026-10-24", sources=["EIS-44", "EIS-223", "ETP"],
        receipts=[{"source": "EIS-223", "month": "2026-10", "status": "failed"}]
    )
    assert result["source_month_slots"] == 37 * 3
    assert result["verified_complete_slots"] == 0
    assert result["national_tam_rub"] is None
    assert next(x for x in result["coverage_grid"] if x["month"] == "2026-10"
                and x["source"] == "EIS-223")["status"] == "failed"
    assert all(item["expected"] is None for item in result["coverage_grid"])


def test_can_not_claim_complete_without_independent_expected_count():
    with pytest.raises(PortfolioInputError, match="independently measured"):
        monthly_coverage(
            start="2026-10-01", end="2026-10-24",
            sources=["EIS-223"],
            receipts=[{"source": "EIS-223", "month": "2026-10",
                       "status": "verified_complete", "observed": 0, "expected": None}]
        )



def test_old_sdk_rejected_without_silent_legacy_query_fallback(ontology):
    class OldSdk:
        def contract(self):
            return {"version": "1.0", "capabilities": ["terminology_search_v1"]}

        def search(self, *, query, collections, limit, mode="hybrid",
                   query_variants=None):
            return []

    with pytest.raises(PortfolioInputError, match="SDK >=0.4"):
        search_demand(
            OldSdk(), tenant_id="tenant_01",
            source_collections=["eis_223_tenant_01"],
            authorized_collection_ids={"eis_223_tenant_01"},
            families=["statcom"], ontology=ontology,
        )


def test_dp_tag_is_only_candidate_not_verified_purchase(ontology):
    client = FakePlatform([_hit("Модернизация ПС 110 кВ, монтаж СТАТКОМ")])
    report = search_demand(
        client, tenant_id="tenant_01",
        source_collections=["eis_223_tenant_01"],
        authorized_collection_ids={"eis_223_tenant_01"},
        families=["statcom"], ontology=ontology,
    )
    candidate = report["candidate_hits"][0]
    assert candidate["classification"] == "explicit_technical_candidate"
    assert candidate["winner"] is None
    assert candidate["market_value_rub"] is None
    assert candidate["award_verified"] is False
    assert candidate["procurement_verified"] is False



def test_legacy_dp_server_that_ignores_new_json_fields_fails_closed(ontology):
    class OldServer(FakePlatform):
        def contract(self):
            return {"version": "1.0", "capabilities": ["search"]}

    client = OldServer()
    with pytest.raises(PortfolioInputError, match="terminology_search_v1"):
        search_demand(
            client, tenant_id="tenant_01",
            source_collections=["eis_223_tenant_01"],
            authorized_collection_ids={"eis_223_tenant_01"},
            families=["statcom"], ontology=ontology,
        )
    assert not client.calls
