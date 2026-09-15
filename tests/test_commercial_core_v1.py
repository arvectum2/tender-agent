from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook

from src.modules.commercial_core.schemas import (
    CatalogMatchStatus,
    CommercialFeasibilityStatus,
)
from src.modules.commercial_core.service import (
    COMMERCIAL_CORE_CONTRACT_VERSION,
    build_commercial_core,
    import_catalog,
)


def _model(*, lines: list[dict] | None = None, nmck: float = 100_000) -> dict:
    return {
        "nmck": nmck,
        "currency": "RUB",
        "line_items": lines
        or [
            {
                "stable_item_id": "line-1",
                "official_name": "Автоматический выключатель ВА47-29 16А",
                "quantity": 10,
                "unit_normalized": "шт",
                "article": "MVA20-1-016-C",
                "brand": "IEK",
            },
            {
                "stable_item_id": "line-2",
                "official_name": "Контактор КМИ-10910 9А 230В",
                "quantity": 5,
                "unit_normalized": "шт",
                "article": "KKM11-009-230-10",
                "brand": "IEK",
            },
        ],
    }


def _csv(rows: str) -> bytes:
    return rows.strip().encode("utf-8")


def _xlsx(headers: list[str], rows: list[list[object]], *, sheet: str = "Прайс") -> bytes:
    workbook = Workbook()
    ws = workbook.active
    ws.title = sheet
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = BytesIO()
    workbook.save(buf)
    return buf.getvalue()


def test_csv_exact_matches_are_source_bound_and_economics_known() -> None:
    catalog = _csv(
        """
Артикул;Бренд;Наименование;Ед.;Цена;Валюта
MVA20-1-016-C;IEK;Автоматический выключатель ВА47-29 16А;шт;1200;RUB
KKM11-009-230-10;IEK;Контактор КМИ-10910 9А 230В;шт;2100;RUB
"""
    )
    result = build_commercial_core(_model(), catalog_filename="price.csv", catalog_content=catalog)

    assert result.contract_version == COMMERCIAL_CORE_CONTRACT_VERSION
    assert result.catalog.status == "READY"
    assert [item.status for item in result.matches] == [CatalogMatchStatus.EXACT, CatalogMatchStatus.EXACT]
    assert result.coverage.matched_coverage_ratio == 1.0
    assert result.coverage.costed_coverage_ratio == 1.0
    assert result.economics.known_catalog_cost == 22_500.0
    assert result.economics.nmck_headroom_amount == 77_500.0
    assert result.feasibility_status == CommercialFeasibilityStatus.FEASIBLE
    assert result.external_action_allowed is False
    assert result.safety["bid_submission_allowed"] is False
    assert result.matches[0].evidence == [
        {"source_file": "price.csv", "sheet": "CSV", "row": 2, "catalog_row_id": "catalog:CSV:2"}
    ]


def test_xlsx_import_detects_header_and_preserves_sheet_row_provenance() -> None:
    payload = _xlsx(
        ["Код товара", "Производитель", "Наименование товара", "Единица измерения", "Цена за ед", "Валюта"],
        [["A-1", "Test Factory", "Кабель ВВГнг-LS 3x2.5", "м", 95.5, "RUB"]],
        sheet="Каталог 2026",
    )
    imported = import_catalog("catalog.xlsx", payload)

    assert imported.status == "READY"
    assert len(imported.rows) == 1
    row = imported.rows[0]
    assert row.sku == "A-1"
    assert row.manufacturer == "Test Factory"
    assert row.price == 95.5
    assert row.sheet_name == "Каталог 2026"
    assert row.row_number == 2


def test_ambiguous_duplicate_price_columns_fail_closed_to_review() -> None:
    payload = _csv(
        """
Артикул;Наименование;Цена;Price;Валюта
A-1;Кабель ВВГнг-LS 3x2.5;95;96;RUB
"""
    )
    result = build_commercial_core(_model(), catalog_filename="ambiguous.csv", catalog_content=payload)

    assert result.catalog.status == "NEEDS_REVIEW"
    assert any("ambiguous_columns:price" in item for item in result.catalog.unknowns)
    assert result.feasibility_status == CommercialFeasibilityStatus.NEEDS_REVIEW
    assert result.matches == []


def test_missing_price_never_becomes_known_economics() -> None:
    payload = _csv(
        """
Артикул;Бренд;Наименование;Ед.;Валюта
MVA20-1-016-C;IEK;Автоматический выключатель ВА47-29 16А;шт;RUB
KKM11-009-230-10;IEK;Контактор КМИ-10910 9А 230В;шт;RUB
"""
    )
    result = build_commercial_core(_model(), catalog_filename="noprice.csv", catalog_content=payload)

    assert all(item.status == CatalogMatchStatus.EXACT for item in result.matches)
    assert result.economics.status != "KNOWN"
    assert result.economics.known_catalog_cost is None
    assert result.feasibility_status == CommercialFeasibilityStatus.NEEDS_REVIEW


def test_duplicate_exact_sku_is_uncertain_instead_of_silent_selection() -> None:
    model = _model(lines=[{
        "stable_item_id": "line-1",
        "official_name": "Автоматический выключатель ВА47-29 16А",
        "quantity": 10,
        "unit_normalized": "шт",
        "article": "MVA20-1-016-C",
        "brand": "IEK",
    }])
    payload = _csv(
        """
Артикул;Бренд;Наименование;Ед.;Цена;Валюта
MVA20-1-016-C;IEK;Автоматический выключатель ВА47-29 16А;шт;1200;RUB
MVA20-1-016-C;IEK;Автоматический выключатель ВА47-29 16А;шт;1250;RUB
"""
    )
    result = build_commercial_core(model, catalog_filename="dupe.csv", catalog_content=payload)

    assert any(item.startswith("duplicate_sku:") for item in result.catalog.warnings)
    assert result.matches[0].status == CatalogMatchStatus.UNCERTAIN
    assert result.matches[0].catalog_row_id is None
    assert result.feasibility_status == CommercialFeasibilityStatus.NEEDS_REVIEW


def test_unit_conflict_for_strong_match_is_uncertain() -> None:
    model = _model(lines=[{
        "stable_item_id": "line-1",
        "official_name": "Кабель ВВГнг-LS 3x2.5",
        "quantity": 100,
        "unit_normalized": "м",
        "article": "CABLE-1",
    }])
    payload = _csv(
        """
Артикул;Наименование;Ед.;Цена;Валюта
CABLE-1;Кабель ВВГнг-LS 3x2.5;шт;95;RUB
"""
    )
    result = build_commercial_core(model, catalog_filename="unit.csv", catalog_content=payload)

    assert result.matches[0].status == CatalogMatchStatus.UNCERTAIN
    assert any(reason.startswith("unit_conflict") for reason in result.matches[0].rationale)
    assert result.economics.known_catalog_cost is None


def test_likely_analog_and_partial_never_produce_unconditional_feasible() -> None:
    model = _model(lines=[
        {
            "stable_item_id": "analog",
            "official_name": "Контактор КМИ-10910 9А 230В",
            "quantity": 2,
            "unit_normalized": "шт",
            "brand": "IEK",
        },
        {
            "stable_item_id": "partial",
            "official_name": "Автоматический выключатель трехполюсный 16А",
            "quantity": 3,
            "unit_normalized": "шт",
        },
    ])
    payload = _csv(
        """
Артикул;Бренд;Наименование;Ед.;Цена;Валюта
K1;IEK;Контактор КМИ-10910 9А 230В исполнение;шт;2100;RUB
B1;EKF;Автоматический выключатель 16А;шт;900;RUB
"""
    )
    result = build_commercial_core(model, catalog_filename="analog.csv", catalog_content=payload)

    assert result.matches[0].status in {CatalogMatchStatus.LIKELY_ANALOG, CatalogMatchStatus.PARTIAL}
    assert result.matches[1].status in {CatalogMatchStatus.PARTIAL, CatalogMatchStatus.UNCERTAIN}
    assert result.feasibility_status == CommercialFeasibilityStatus.NEEDS_REVIEW


def test_no_match_is_explicit() -> None:
    model = _model(lines=[{
        "stable_item_id": "line-1",
        "official_name": "Силовой трансформатор 1000 кВА",
        "quantity": 1,
        "unit_normalized": "шт",
    }])
    payload = _csv(
        """
Артикул;Наименование;Ед.;Цена;Валюта
X1;Офисное кресло;шт;5000;RUB
"""
    )
    result = build_commercial_core(model, catalog_filename="nomatch.csv", catalog_content=payload)

    assert result.matches[0].status == CatalogMatchStatus.NO_MATCH
    assert result.coverage.no_match == 1
    assert result.feasibility_status == CommercialFeasibilityStatus.NEEDS_REVIEW


def test_target_bid_below_known_catalog_cost_is_not_feasible_at_current_price() -> None:
    payload = _csv(
        """
Артикул;Бренд;Наименование;Ед.;Цена;Валюта
MVA20-1-016-C;IEK;Автоматический выключатель ВА47-29 16А;шт;1200;RUB
KKM11-009-230-10;IEK;Контактор КМИ-10910 9А 230В;шт;2100;RUB
"""
    )
    result = build_commercial_core(
        _model(), catalog_filename="price.csv", catalog_content=payload, target_bid_amount=20_000
    )

    assert result.economics.known_catalog_cost == 22_500.0
    assert result.economics.gross_margin_amount == -2_500.0
    assert result.feasibility_status == CommercialFeasibilityStatus.NOT_FEASIBLE_AT_CURRENT_CATALOG_PRICE


def test_missing_quantity_keeps_economics_unknown_even_with_exact_sku() -> None:
    model = _model(lines=[{
        "stable_item_id": "line-1",
        "official_name": "Автоматический выключатель ВА47-29 16А",
        "quantity": None,
        "unit_normalized": "шт",
        "article": "MVA20-1-016-C",
    }])
    payload = _csv(
        """
Артикул;Наименование;Ед.;Цена;Валюта
MVA20-1-016-C;Автоматический выключатель ВА47-29 16А;шт;1200;RUB
"""
    )
    result = build_commercial_core(model, catalog_filename="price.csv", catalog_content=payload)

    assert result.matches[0].status == CatalogMatchStatus.EXACT
    assert result.economics.status == "UNKNOWN"
    assert result.economics.known_catalog_cost is None
    assert result.feasibility_status == CommercialFeasibilityStatus.NEEDS_REVIEW


def test_commercial_core_api_persists_customer_safe_result_and_rerenders_report(
    client, monkeypatch, tmp_path
) -> None:
    runs_root = tmp_path / "tender_operator_demo_runs"
    monkeypatch.setenv("AI_CORP_TENDER_OPERATOR_DEMO_RUNS_DIR", str(runs_root))
    run_id = "commercial-core-integration"
    output_dir = runs_root / run_id / "output"
    output_dir.mkdir(parents=True)
    canonical = {
        "procurement_number": "0123456789012345678",
        "procurement_title": "Поставка электротехнических товаров",
        "customer_name": "Промышленный заказчик",
        "publication_datetime_display": "15.09.2026 10:00",
        "application_deadline_display": "30.09.2026 12:00",
        "nmck": 50_000,
        "currency": "RUB",
        "delivery_place": "Москва",
        "metadata": {
            "document_set_summary": {
                "status": "complete",
                "logical_documents": [],
                "logical_document_count": 0,
                "physical_file_count": 0,
            }
        },
        "customer_decision": {
            "recommendation": "NEEDS_REVIEW",
            "reasons": ["Требуется коммерческий расчёт"],
            "confirmed": [],
            "not_evaluated": [],
            "next_action": "Загрузить прайс-лист",
        },
        "line_items": [
            {
                "stable_item_id": "line-1",
                "sequence": 1,
                "official_name": "Гофра 16 мм",
                "original_name": "Гофра 16 мм",
                "quantity": 400,
                "quantity_display": "400",
                "unit_normalized": "шт",
                "unit_original": "шт",
                "characteristics": [],
                "evidence_ids": [],
                "source_row": "строка 1",
            },
            {
                "stable_item_id": "line-2",
                "sequence": 2,
                "official_name": "Кабель-канал 20х24 мм",
                "original_name": "Кабель-канал 20х24 мм",
                "quantity": 200,
                "quantity_display": "200",
                "unit_normalized": "м",
                "unit_original": "м",
                "characteristics": [],
                "evidence_ids": [],
                "source_row": "строка 2",
            },
        ],
        "evidence_map": [],
        "risks": [],
        "customer_questions": [],
        "corpus_limitations": [],
        "requirements": [],
    }
    import json

    (output_dir / "canonical_report.json").write_text(
        json.dumps(canonical, ensure_ascii=False), encoding="utf-8"
    )
    (output_dir / "report.json").write_text(
        json.dumps({"run_id": run_id}, ensure_ascii=False), encoding="utf-8"
    )

    catalog = _csv(
        """
Артикул;Наименование;Ед.;Цена;Валюта
G-16;Гофра 16 мм;шт;20;RUB
KK-2024;Кабель-канал 20х24 мм;м;100;RUB
"""
    )
    evaluated = client.post(
        f"/api/demo/tender-agent/runs/{run_id}/commercial-core",
        data={"target_bid_amount": "50000"},
        files={"catalog_file": ("customer-price.csv", catalog, "text/csv")},
    )
    assert evaluated.status_code == 200, evaluated.text
    payload = evaluated.json()
    assert payload["contract_version"] == COMMERCIAL_CORE_CONTRACT_VERSION
    assert payload["coverage"]["exact"] == 2
    assert payload["coverage"]["matched_coverage_ratio"] == 1.0
    assert payload["economics"]["known_catalog_cost"] == 28000.0
    assert payload["economics"]["gross_margin_amount"] == 22000.0
    assert payload["feasibility_status"] == "FEASIBLE"
    assert payload["human_control_required"] is True
    assert payload["external_action_allowed"] is False

    fetched = client.get(f"/api/demo/tender-agent/runs/{run_id}/commercial-core")
    assert fetched.status_code == 200
    assert fetched.json() == payload

    persisted = json.loads((output_dir / "commercial_core.json").read_text(encoding="utf-8"))
    canonical_after = json.loads((output_dir / "canonical_report.json").read_text(encoding="utf-8"))
    customer_report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert persisted["catalog"]["stored_source"]["file_name"].endswith("customer-price.csv")
    assert canonical_after["commercial_core"]["catalog"]["stored_source"]["sha256"] == payload["catalog"]["source_sha256"]
    assert customer_report["commercial_core"]["catalog"]["source_file"] == "customer-price.csv"
    assert "stored_source" not in str(customer_report["commercial_core"])
    assert "source_sha256" not in customer_report["commercial_core"]["catalog"]
    assert "position_id" not in str(customer_report["commercial_core"]["matches"])

    report_html = (output_dir / "report.html").read_text(encoding="utf-8")
    assert "Commercial Core" in report_html
    assert "FEASIBLE" in report_html
    assert "EXACT" in report_html
    assert "customer-price.csv / CSV / строка 2" in report_html
    assert "28000" in report_html
    assert "внешние действия не разрешены" in report_html


def test_commercial_core_api_requires_analyzed_run(client, monkeypatch, tmp_path) -> None:
    runs_root = tmp_path / "tender_operator_demo_runs"
    monkeypatch.setenv("AI_CORP_TENDER_OPERATOR_DEMO_RUNS_DIR", str(runs_root))
    created = client.post(
        "/api/demo/tender-agent/runs",
        data={
            "tender_title": "Not analyzed",
            "tender_category": "Электротехническое оборудование",
            "customer_name": "Промышленный заказчик",
        },
        files=[("files", ("notice.txt", b"notice", "text/plain"))],
    )
    assert created.status_code == 200
    run_id = created.json()["run_id"]
    response = client.post(
        f"/api/demo/tender-agent/runs/{run_id}/commercial-core",
        files={"catalog_file": ("catalog.csv", b"SKU;Name\nA;B\n", "text/csv")},
    )
    assert response.status_code == 409
    assert "Analyze the tender run" in response.json()["detail"]


def test_conflicting_sku_never_becomes_exact_from_same_title() -> None:
    model = _model(lines=[{
        "stable_item_id": "line-1",
        "official_name": "Автоматический выключатель ВА47-29 16А",
        "quantity": 10,
        "unit_normalized": "шт",
        "article": "TENDER-SKU",
    }])
    payload = _csv(
        """
Артикул;Наименование;Ед.;Цена;Валюта
CATALOG-SKU;Автоматический выключатель ВА47-29 16А;шт;1200;RUB
"""
    )
    result = build_commercial_core(model, catalog_filename="conflict.csv", catalog_content=payload)

    assert result.matches[0].status == CatalogMatchStatus.NO_MATCH
    assert "article_conflict" in result.matches[0].rationale
    assert result.economics.known_catalog_cost is None
    assert result.feasibility_status == CommercialFeasibilityStatus.NEEDS_REVIEW


def test_unknown_catalog_unit_blocks_exact_costing() -> None:
    model = _model(lines=[{
        "stable_item_id": "line-1",
        "official_name": "Автоматический выключатель ВА47-29 16А",
        "quantity": 10,
        "unit_normalized": "шт",
        "article": "MVA20-1-016-C",
    }])
    payload = _csv(
        """
Артикул;Наименование;Цена;Валюта
MVA20-1-016-C;Автоматический выключатель ВА47-29 16А;1200;RUB
"""
    )
    result = build_commercial_core(model, catalog_filename="unit-unknown.csv", catalog_content=payload)

    assert result.matches[0].status == CatalogMatchStatus.UNCERTAIN
    assert "catalog_unit_unknown" in result.matches[0].rationale
    assert result.economics.known_catalog_cost is None
    assert result.feasibility_status == CommercialFeasibilityStatus.NEEDS_REVIEW
