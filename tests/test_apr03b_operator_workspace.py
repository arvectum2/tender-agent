"""APR-03B: private browser workspace, strict EIS intake and read-only canonical data."""

from __future__ import annotations

import base64
from contextlib import contextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.modules.tender_operator_agent_demo import operator_workspace_service as service
from src.modules.tender_operator_agent_demo import router as operator_router
from src.shared.api.middleware import TenderPilotBasicAuthMiddleware
from src.shared.config.settings import Settings
from src.tender_research.models import ProcurementTender, ProcurementTenderDocument


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(
        operator_router, "get_settings",
        lambda: Settings(
            pilot_auth_enabled=True,
            pilot_auth_username="test-operator",
            pilot_auth_password="test-secret-unique-12345",
        ),
    )
    app = FastAPI()
    app.include_router(operator_router.router)
    app.add_middleware(
        TenderPilotBasicAuthMiddleware,
        username="test-operator",
        password="test-secret-unique-12345",
        protected=("/pilot/tender-agent", "/api/demo/tender-agent"),
        public=("/health",),
    )
    return TestClient(app)


@pytest.fixture
def auth():
    payload = base64.b64encode(b"test-operator:test-secret-unique-12345").decode()
    return {"Authorization": "Basic " + payload}


@pytest.mark.parametrize(
    ("value", "number", "law"),
    [
        ("0372200172326000015", "0372200172326000015", "44fz"),
        ("32500001234", "32500001234", "223fz"),
        (
            "https://zakupki.gov.ru/epz/order/notice/ok20/view/common-info.html?regNumber=0372200172326000015",
            "0372200172326000015", "44fz",
        ),
        (
            "https://zakupki.gov.ru/223/purchase/public/purchase/info/common-info.html?regNumber=32500001234",
            "32500001234", "223fz",
        ),
    ],
)
def test_strict_eis_reference_accepts_known_formats(value, number, law):
    got, regime, url = service.parse_eis_reference(value)
    assert got == number
    assert regime == law
    if value.startswith("https:"):
        assert url == value


@pytest.mark.parametrize(
    "value",
    [
        "https://evil.com/epz/order/notice/ok20/view/common-info.html?regNumber=0372200172326000015",
        "https://zakupki.gov.ru.evil.com/epz/order/notice/ok20/view/common-info.html?regNumber=0372200172326000015",
        "https://attacker@zakupki.gov.ru/epz/order/notice/ok20/view/common-info.html?regNumber=0372200172326000015",
        "http://zakupki.gov.ru/epz/order/notice/ok20/view/common-info.html?regNumber=0372200172326000015",
        "https://zakupki.gov.ru@evil.com/epz/order/notice/ok20/view/common-info.html?regNumber=0372200172326000015",
        "https://zakupki.gov.ru/epz/order/notice/ok20/view/common-info.html?regNumber=bad",
        "https://zakupki.gov.ru/epz/order/notice/ok20/view/common-info.html?regNumber=0372200172326000015&regNumber=1111111111111111111",
        "https://zakupki.gov.ru/sneaky?regNumber=0372200172326000015",
        "123456789",
    ],
)
def test_strict_eis_reference_denies_unsafe_inputs(value):
    with pytest.raises(ValueError):
        service.parse_eis_reference(value)


def test_workspace_auth_html_assets_and_no_demo_handoffs(client, auth):
    assert client.get("/pilot/tender-agent/workspace").status_code == 401
    assert client.get("/pilot/tender-agent/workspace/assets/workspace.js").status_code == 401
    assert client.get("/api/demo/tender-agent/workspace/registry").status_code == 401

    html = client.get("/pilot/tender-agent/workspace", headers=auth)
    assert html.status_code == 200
    assert "База закупок" in html.text
    assert "Новый анализ" in html.text
    assert "Cache-Control" in html.headers
    for suffix, media in (("workspace.css", "text/css"), ("workspace.js", "text/javascript")):
        res = client.get("/pilot/tender-agent/workspace/assets/" + suffix, headers=auth)
        assert res.status_code == 200
        assert media in res.headers["content-type"]
        assert "no-store" in res.headers.get("cache-control", "")
    assert client.get("/pilot/tender-agent/workspace/assets/../router.py", headers=auth).status_code in {404, 405}


def test_workspace_denies_disabled_or_incomplete_auth_configuration(client, auth, monkeypatch):
    monkeypatch.setattr(operator_router, "get_settings", lambda: Settings(pilot_auth_enabled=False))
    assert client.get("/pilot/tender-agent/workspace", headers=auth).status_code == 503
    assert client.get("/api/demo/tender-agent/workspace/registry", headers=auth).status_code == 503
    monkeypatch.setattr(
        operator_router, "get_settings",
        lambda: Settings(
            pilot_auth_enabled=True,
            pilot_auth_username="test-operator",
            pilot_auth_password="test-secret-unique-12345",
            pilot_auth_protected_prefixes="/pilot/tender-agent",
        ),
    )
    assert client.get("/pilot/tender-agent/workspace", headers=auth).status_code == 503


def test_api_import_rejects_invalid_and_delegates_valid_reference(client, auth, monkeypatch):
    seen = []
    def fake_import(value):
        seen.append(value)
        return {"run_id": "real-corpus-run-1", "status": "ready_to_analyze"}
    monkeypatch.setattr(operator_router, "import_eis_reference", fake_import)
    bad = client.post("/api/demo/tender-agent/workspace/import", json={"reference": "https://malicious.example/223"}, headers=auth)
    assert bad.status_code == 400
    assert seen == []
    good = client.post("/api/demo/tender-agent/workspace/import", json={"reference": "0372200172326000015"}, headers=auth)
    assert good.status_code == 200
    assert seen == ["0372200172326000015"]
    assert client.post("/api/demo/tender-agent/workspace/import", json={"reference": "abc"}, headers=auth).status_code == 422


@pytest.fixture
def fake_db(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    ProcurementTender.__table__.create(engine)
    ProcurementTenderDocument.__table__.create(engine)
    with Session(engine) as session:
        tender = ProcurementTender(
            source="eis", external_id="notice-1", registry_number="0372200172326000015",
            law_type="44fz", title="Разработка сайта музея", customer_name="Музей хлеба",
            nmck_amount=450000, currency="RUB", status="published",
        )
        session.add(tender)
        session.flush()
        path = tmp_path / "original.pdf"
        path.write_bytes(b"%PDF-1.5 valid-test-attachment")
        outside = tmp_path.parent / "other-secret.pdf"
        outside.write_bytes(b"SECRET")
        doc = ProcurementTenderDocument(
            tender_id=tender.id, file_name="original.pdf", local_path=str(path),
            download_status="downloaded", text_extraction_status="done",
        )
        bad_doc = ProcurementTenderDocument(
            tender_id=tender.id, file_name="outside.pdf", local_path=str(outside),
            download_status="downloaded", text_extraction_status="failed",
        )
        session.add_all([doc, bad_doc])
        session.commit()
        ids = tender.id, doc.id, bad_doc.id
    @contextmanager
    def session_factory():
        with Session(engine) as session:
            yield session
    monkeypatch.setattr(service, "read_session", session_factory)
    monkeypatch.setattr(service, "get_settings", lambda: Settings(arvectum_data_dir=str(tmp_path)))
    yield ids
    engine.dispose()


def test_readonly_registry_search_detail_and_scoped_download(fake_db, client, auth):
    tender, good, bad = fake_db
    res = client.get("/api/demo/tender-agent/workspace/registry?query=музея", headers=auth)
    assert res.status_code == 200
    assert res.json()["total"] == 1
    assert res.json()["items"][0]["title"] == "Разработка сайта музея"
    assert "raw_payload" not in res.json()["items"][0]
    assert client.get("/api/demo/tender-agent/workspace/registry?query=other", headers=auth).json()["total"] == 0
    details = client.get(f"/api/demo/tender-agent/workspace/registry/{tender}", headers=auth)
    assert details.status_code == 200
    assert len(details.json()["documents"]) == 2
    assert {entry["local_download"] for entry in details.json()["documents"]} == {True, False}
    download = client.get(f"/api/demo/tender-agent/workspace/registry/{tender}/documents/{good}/download", headers=auth)
    assert download.status_code == 200
    assert download.content.startswith(b"%PDF-")
    assert client.get(f"/api/demo/tender-agent/workspace/registry/{tender}/documents/{bad}/download", headers=auth).status_code == 404
    assert client.get(f"/api/demo/tender-agent/workspace/registry/{'a'*36}", headers=auth).status_code == 404
    assert client.get("/api/demo/tender-agent/workspace/registry?limit=999", headers=auth).status_code == 422



def test_registry_missing_schema_is_unavailable_not_empty_or_500(client, auth, monkeypatch, tmp_path):
    # Fresh isolated staging intentionally has no migrated canonical tables.
    # Never turn a broken registry into zero search results or a raw SQL 500.
    empty_db = tmp_path / "unmigrated.sqlite"
    monkeypatch.setattr(
        service, "get_settings",
        lambda: Settings(database_url=f"sqlite:///{empty_db}"),
    )
    tender_id = "31d2bc23-a5ba-4c09-9c9e-f6ae1c6c5db5"
    document_id = "57869227-eccc-4529-9a44-e68b0a65b37b"
    for path in (
        "/api/demo/tender-agent/workspace/registry",
        f"/api/demo/tender-agent/workspace/registry/{tender_id}",
        f"/api/demo/tender-agent/workspace/registry/{tender_id}/documents/{document_id}/download",
    ):
        assert client.get(path).status_code == 401
        response = client.get(path, headers=auth)
        assert response.status_code == 503
        assert response.json() == {"detail": "База закупок временно недоступна"}
        assert "sql" not in response.text.lower()


def test_duplicate_sql_wildcards_are_treated_as_literal(fake_db):
    assert service.registry_records(query="%")["total"] == 0
    assert service.registry_records(query="_")["total"] == 0


def test_document_path_cannot_escape_data_root(tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "secret.pdf"
    outside.write_bytes(b"private")
    (root / "shortcut.pdf").symlink_to(outside)
    monkeypatch.setattr(service, "get_settings", lambda: Settings(arvectum_data_dir=str(root)))
    assert service._allowed_document_path(str(outside)) is None
    assert service._allowed_document_path(str(root / "shortcut.pdf")) is None


def test_price01_private_readonly_archive_price_projection(client, auth):
    url = "/api/demo/tender-agent/workspace/competitive-prices/0158300034526000388"
    assert client.get(url).status_code == 401
    result = client.get(url, headers=auth)
    assert result.status_code == 200
    assert "no-store" in result.headers.get("cache-control", "")
    payload = result.json()
    assert payload["state"] == "VERIFIED_ARCHIVED_SINGLE_PROCEDURE"
    assert payload["admitted_count"] == 45
    assert payload["rejected_count"] == 10
    assert payload["winner_price_rub"] == "28400.0"
    assert payload["company_price_rub"] == "119000.0"
    assert payload["company_rank_admitted"] == 38
    assert payload["admitted_only_prices_rub"]["median"] == "74000.0"
    assert payload["evidence"]["bid_rows_crosschecked_with_original"] == 55
    assert len(payload["evidence"]["eis_original_zip_sha256"]) == 64
    assert payload["cross_procurement_comparison_state"] == "INSUFFICIENT_EVIDENCE"
    assert payload["cost_scenarios"] is None
    assert payload["company_go"] is False
    assert payload["forecast_or_bid_recommendation"] is False
    assert "bids" not in payload
    assert "application_id" not in result.text
    assert "rejection_reason_original" not in result.text


@pytest.mark.parametrize("number", [
    "0187200001726001304",  # another original procurement is NOT comparable automatically
    "0372200172326000015",  # Museum Bread was not given source-verified final prices
    "0000000000000000000",
    "0158300034526000389",
    "01",
    "0158300034526000388%2Fother",
])
def test_price01_missing_priced_protocol_fails_closed_without_aksay_substitution(
    client, auth, number,
):
    url = "/api/demo/tender-agent/workspace/competitive-prices/" + number
    assert client.get(url).status_code == 401
    result = client.get(url, headers=auth)
    assert result.status_code in {404, 405}
    assert "28400" not in result.text
    assert "74000" not in result.text


def test_price01_tampered_or_missing_aggregate_does_not_create_fake_pricing(
    client, auth, tmp_path, monkeypatch,
):
    import json

    from src.modules.tender_operator_agent_demo import (
        operator_price_context as price_context,
    )

    url = "/api/demo/tender-agent/workspace/competitive-prices/0158300034526000388"
    original = json.loads(price_context._AGGREGATE_PATH.read_text())
    p = tmp_path / "price.json"
    monkeypatch.setattr(price_context, "_AGGREGATE_PATH", p)

    p.write_text("not json")
    assert client.get(url, headers=auth).status_code == 503
    p.write_text(json.dumps({**original, "original_eis_zip_sha256": "0" * 64}))
    assert client.get(url, headers=auth).status_code == 503
    p.write_text(json.dumps({**original, "winner": {**original["winner"], "price_rub": "1"}}))
    assert client.get(url, headers=auth).status_code == 503
    p.write_text(json.dumps(original))
    response = client.get(url, headers=auth)
    assert response.status_code == 200

    p.unlink()
    assert client.get(url, headers=auth).status_code == 503


def test_price01_operator_tab_link_to_existing_arv057_without_auto_bid(client, auth):
    res = client.get("/pilot/tender-agent/workspace", headers=auth)
    assert res.status_code == 200
    html = res.text
    assert 'id="pane-prices"' in html
    assert 'id="price-registry"' in html
    assert 'id="price-historical-btn"' in html
    assert 'data-tab="prices"' in html
    assert "Конкурентная ставка не равна себестоимости" in html
    js = client.get("/pilot/tender-agent/workspace/assets/workspace.js", headers=auth).text
    assert "/workspace/competitive-prices/" in js
    assert "/api/tender-research/historical-prices/" in js
    assert "cross_procurement_comparison_state!=='INSUFFICIENT_EVIDENCE'" in js
    assert "data.forecast_or_bid_recommendation!==false" in js
    assert "data.company_go!==false" in js
    assert "НМЦК не являются ценами победителей" in html
    assert "fetch('/api/demo/tender-agent/workspace/bid" not in js


def test_price01_six_original_website_history_is_private_not_a_single_pool(client, auth):
    url = "/api/demo/tender-agent/workspace/website-price-cohort"
    assert client.get(url).status_code == 401
    result = client.get(url, headers=auth)
    assert result.status_code == 200
    data = result.json()
    assert data["schema_version"] == "ta-price01-website-cohort-private-projection-v1"
    assert data["state"] == "INDEPENDENT_HISTORICAL_WEBSITE_CASES_NOT_POOLED"
    assert data["verified_original_procedures"] == 6
    assert data["same_basket_procurements_as_aksay"] == 1
    assert data["additional_equivalent_procurements"] == 0
    assert data["market_aggregated_price_rub"] is None
    assert data["owner_commercial_go"] is False
    assert data["forecast_or_bid_recommendation"] is False
    assert len(data["cases"]) == 6
    assert sum(c["admitted"] for c in data["cases"]) == 124
    assert sum(c["rejected"] for c in data["cases"]) == 16
    assert "application_id" not in result.text
    assert "appNumber" not in result.text
    assert "rejection_reason_original" not in result.text
    assert "company_price_rub" not in result.text
    assert len(data["source_cohort_receipt_sha256"]) == 64
    case = {x["registry_number"]: x for x in data["cases"]}
    assert case["0119200000126013647"]["sub_ruble_source_bid_observed"] is True
    assert case["0119200000126013647"]["admitted_price_low_rub"] == "0.01"
    assert case["0132300001726000686"]["admitted"] == 1
    assert case["0372200203126000012"]["admitted_price_status"] == (
        "MISSING_FINAL_PRICE_IN_ORIGINAL_EOK_PROTOCOL"
    )
    assert case["0372200203126000012"]["admitted_price_low_rub"] is None
    assert case["0372200203126000012"]["admitted_price_median_rub"] is None


def test_price01_legacy_aksay_only_per_case_endpoint_does_not_auto_admit_other_websites(
    client, auth,
):
    for number in (
        "0132300001726000686",
        "0119200000126013647",
        "0377100005726000128",
        "0372200203126000012",
        "0884200000526000012",
    ):
        res = client.get(
            f"/api/demo/tender-agent/workspace/competitive-prices/{number}",
            headers=auth,
        )
        assert res.status_code == 404
        assert "28400" not in res.text


def test_price01_website_cohort_fails_closed_if_source_receipt_is_altered(
    client, auth, monkeypatch, tmp_path,
):
    import json

    from src.modules.tender_operator_agent_demo import (
        operator_price_context as price_context,
    )

    original = price_context._COHORT_REPORT_PATH.read_bytes()
    p = tmp_path / "original-price-cohort.json"
    monkeypatch.setattr(price_context, "_COHORT_REPORT_PATH", p)
    url = "/api/demo/tender-agent/workspace/website-price-cohort"

    p.write_bytes(b'{"schema_version":"fake"}')
    assert client.get(url, headers=auth).status_code == 503

    altered = json.loads(original)
    altered["new_admitted_same_basket_procurements"] = 5
    p.write_text(json.dumps(altered))
    assert client.get(url, headers=auth).status_code == 503

    altered = json.loads(original)
    altered["cases"][4]["admitted_price_low_rub"] = "0"
    p.write_text(json.dumps(altered))
    assert client.get(url, headers=auth).status_code == 503

    p.write_bytes(original)
    assert client.get(url, headers=auth).status_code == 200
    p.unlink()
    assert client.get(url, headers=auth).status_code == 503


def test_price01_six_original_sites_render_only_inside_existing_prices_tab(client, auth):
    html = client.get("/pilot/tender-agent/workspace", headers=auth).text
    assert 'id="price-cohort-btn"' in html
    assert 'id="price-cohort"' in html
    assert "НЕЛЬЗЯ смешивать цены" in html
    js = client.get("/pilot/tender-agent/workspace/assets/workspace.js", headers=auth).text
    assert "/workspace/website-price-cohort" in js
    assert "async function loadWebsiteCohort()" in js
    assert "data.market_aggregated_price_rub!==null" in js
    assert "data.additional_equivalent_procurements!==0" in js
    assert "ставка менее 1 ₽" in js
    assert "нет конечных цен допущенных" in js
    assert "price-cohort-btn" in js


def test_price01_attested_three_original_tz_normalization_is_private_not_bid(client, auth):
    uri = "/api/demo/tender-agent/workspace/website-workload-normalization"
    assert client.get(uri).status_code == 401
    r = client.get(uri, headers=auth)
    assert r.status_code == 200
    assert "no-store" in r.headers.get("cache-control", "")
    data = r.json()
    assert data["state"] == "ATTESTED_CONTRACT_WORKLOAD_NOT_PRICE_NORMALIZATION"
    assert data["source_cases_count"] == 3
    assert data["comparable_basket_procurements_count"] == 1
    assert data["additional_equivalent_projects"] == 0
    assert data["work_unit_rate_rub"] is None
    assert data["cross_tender_normalized_price_rub"] is None
    assert data["estimated_company_labor_hours"] is None
    assert data["bid_recommendation"] is False
    assert data["owner_approved"] is False
    assert len(data["receipt_sha256"]) == 64
    cases = {case["case_key"]: case for case in data["cases"]}
    assert set(cases) == {"AKSAY", "KRASNOYARSK", "CHEMAL"}
    for case in cases.values():
        assert len(case["original_technical_scope_docx_sha256"]) == 64
        assert case["costs_or_labor_hours_known"] is False
        assert case["actual_content_pages_known"] is False
        assert all(
            len(d["source_line_sha256"]) == 64 and d["source_quote"] and d["reviewed_interpretation"]
            for d in case["verified_dimensions"]
        )

    def get(case, dimension):
        return next(
            item["source_value"]
            for item in cases[case]["verified_dimensions"]
            if item["dimension"] == dimension
        )

    assert [get(key, "delivery_working_days") for key in ("AKSAY", "KRASNOYARSK", "CHEMAL")] == [
        14, 10, 21,
    ]
    assert get("AKSAY", "postacceptance_obligation") == "ROUTINE_SUPPORT_EXCLUDED"
    assert get("KRASNOYARSK", "postacceptance_obligation") == "ONGOING_SUPPORT_12_MONTHS_WITH_SLA"
    assert get("CHEMAL", "postacceptance_obligation") == "DEFECT_WARRANTY_12_MONTHS"
    assert cases["AKSAY"]["initial_content_pages_cap"] is None
    assert cases["KRASNOYARSK"]["initial_content_pages_cap"] is None
    assert cases["CHEMAL"]["initial_content_pages_cap"] == 40
    assert "application_id" not in r.text
    assert "appNumber" not in r.text
    assert "28400" not in r.text


def test_price01_workload_matrix_source_sha_alter_or_missing_is_503(client, auth, tmp_path, monkeypatch):
    import json

    from src.modules.tender_operator_agent_demo import operator_price_context as context

    original = context._WORKLOAD_REPORT_PATH.read_bytes()
    dest = tmp_path / "workload.json"
    monkeypatch.setattr(context, "_WORKLOAD_REPORT_PATH", dest)
    uri = "/api/demo/tender-agent/workspace/website-workload-normalization"

    dest.write_bytes(b"{}")
    assert client.get(uri, headers=auth).status_code == 503

    altered = json.loads(original)
    altered["new_equivalent_website_contracts"] = 2
    dest.write_text(json.dumps(altered))
    assert client.get(uri, headers=auth).status_code == 503

    altered = json.loads(original)
    altered["cases"][0]["unknown_inputs"]["actual_labor_cost_rub"] = 0
    dest.write_text(json.dumps(altered))
    assert client.get(uri, headers=auth).status_code == 503

    dest.write_bytes(original)
    assert client.get(uri, headers=auth).status_code == 200
    dest.unlink()
    assert client.get(uri, headers=auth).status_code == 503


def test_price01_workload_matrix_button_is_real_ui_not_second_console(client, auth):
    html = client.get("/pilot/tender-agent/workspace", headers=auth).text
    js = client.get("/pilot/tender-agent/workspace/assets/workspace.js", headers=auth).text
    assert 'id="price-workload-btn"' in html
    assert 'id="price-workload"' in html
    assert "НЕТ коэффициентов стоимости" in html
    assert "website-workload-normalization" in js
    assert "async function loadWorkloadNormalization()" in js
    assert "work_unit_rate_rub!==null" in js
    assert "additional_equivalent_projects!==0" in js
    assert "loadWorkloadNormalization());" in js
    assert "Нормализация рублёвой цены НЕ ВЫПОЛНЕНА" in js
    assert "/workspace/competitive-prices/" in js  # Aksay still isolated


_COST_SAMPLE = {
    "external_direct_rub": "100.00",
    "labor_rub": "200.00",
    "reserve_rub": "20.00",
    "fixed_platform_fees_rub": "5.00",
    "revenue_tax_percent": "6",
    "variable_platform_fee_percent": "2",
    "target_profit_rub": "50",
    "accept_hypothetical_assumptions_only": True,
}


def test_price01_private_explicit_cost_post_is_not_price_recommendation(client, auth):
    url = "/api/demo/tender-agent/workspace/price-scenario/calculate"
    assert client.post(url, json=_COST_SAMPLE).status_code == 401
    result = client.post(url, json=_COST_SAMPLE, headers=auth)
    assert result.status_code == 200, result.text
    assert "no-store" in result.headers.get("cache-control", "")
    data = result.json()
    assert data["state"] == "EXPLICIT_USER_ASSUMPTION_BREAK_EVEN_ONLY"
    assert (data["cash_break_even_rub"], data["full_economic_break_even_rub"],
            data["full_cost_plus_explicit_target_rub"]) == ("135.87", "353.27", "407.61")
    assert data["inputs_stored"] is False
    assert data["assumptions_independently_verified"] is False
    assert data["is_procurement_bid_recommendation"] is False
    assert data["commercial_owner_go"] is False
    assert data["automatic_submission_or_payment"] is False
    assert "external_direct_rub" not in data
    assert "revenue_tax_percent" not in data


@pytest.mark.parametrize("change", [
    {"revenue_tax_percent": "100"},
    {"variable_platform_fee_percent": "94"},
    {"external_direct_rub": "-1"},
    {"external_direct_rub": "1.999"},
    {"revenue_tax_percent": ""},
    {"accept_hypothetical_assumptions_only": False},
])
def test_price01_protected_cost_post_invalid_scenarios_422(client, auth, change):
    result = client.post(
        "/api/demo/tender-agent/workspace/price-scenario/calculate",
        headers=auth,
        json={**_COST_SAMPLE, **change},
    )
    assert result.status_code == 422


def test_price01_cost_request_explicit_inputs_required_and_no_extra_fields(client, auth):
    url = "/api/demo/tender-agent/workspace/price-scenario/calculate"
    for missing in _COST_SAMPLE:
        payload = {k: v for k, v in _COST_SAMPLE.items() if k != missing}
        assert client.post(url, json=payload, headers=auth).status_code == 422
    assert client.post(
        url, json={**_COST_SAMPLE, "company_inn": "0000000000"}, headers=auth,
    ).status_code == 422
    # POST does not store a durable historical quote: no GET view exists.
    assert client.get(url, headers=auth).status_code == 405


def test_price01_explicit_cost_form_no_default_values_or_automatic_submission(client, auth):
    html = client.get("/pilot/tender-agent/workspace", headers=auth).text
    assert 'id="price-cost-form" method="post"' in html
    assert 'action="/api/demo/tender-agent/workspace/price-scenario/calculate"' in html
    for element in (
        "cost-external", "cost-labor", "cost-reserve", "cost-fixed",
        "cost-tax", "cost-variable", "cost-target",
    ):
        assert f'id="{element}"' in html
    assert 'id="cost-scenario-confirm"' in html
    assert 'id="cost-clear-btn"' in html
    assert "Данные не сохраняются" in html
    js = client.get("/pilot/tender-agent/workspace/assets/workspace.js", headers=auth).text
    assert "/workspace/price-scenario/calculate" in js
    assert "async function calculateExplicitPriceCostScenario(event)" in js
    assert "JSON.stringify(payload)" in js
    assert "accept_hypothetical_assumptions_only" in js
    assert "result.inputs_stored!==false" in js
    assert "result.is_procurement_bid_recommendation!==false" in js
    assert "Нормализация рублёвой цены НЕ ВЫПОЛНЕНА" in js
