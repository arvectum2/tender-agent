import json
import zipfile
from io import BytesIO
from pathlib import Path

from openpyxl import Workbook

from src.modules.tender_operator_agent_demo import upload_service_legacy
from src.modules.tender_operator_agent_demo.upload_service import (
    AnalyzedDocument,
    _collect_supply_items,
    _extract_supply_items_from_spec_text,
)


def _controlled_llm_result(*, failed_sections: set[str]) -> dict:
    section_names = {"requirements", "supplier_questions", "rfq_draft", "contract_risks"}
    return {
        "analysis_mode": "llm_tender_operator_provider",
        "resolved_provider": "test-provider",
        "requirements": {},
        "supplier_questions": [],
        "rfq_draft": {},
        "contract_risks": [],
        "bid_decision": None,
        "sections": {
            section: {
                "validation_status": "FAILED" if section in failed_sections else "PASSED",
                "trace_id": f"TRACE-{section}",
            }
            for section in sorted(section_names)
        },
        "trace_ids": [f"TRACE-{section}" for section in sorted(section_names)],
    }


def _set_runs_root(monkeypatch, tmp_path: Path) -> Path:
    runs_root = tmp_path / "tender_operator_demo_runs"
    monkeypatch.setenv("AI_CORP_TENDER_OPERATOR_DEMO_RUNS_DIR", str(runs_root))
    return runs_root


def _sample_upload_payload(include_quote: bool = True):
    files = [
        ("files", ("notice.txt", b"NOTICE\nProcurement of electrical equipment for switchgear upgrade.", "text/plain")),
        ("files", ("technical_spec.txt", b"Technical specification. Delivery in 45 days. Certificates required.", "text/plain")),
        ("files", ("contract_draft.txt", b"Draft contract. Penalty for delay. Payment after acceptance.", "text/plain")),
    ]
    if include_quote:
        files.append(
            ("files", ("supplier_quote.txt", b"Supplier quote. Total price 11820000 RUB. Delivery 42 days.", "text/plain"))
        )
    data = {
        "tender_title": "Upload Demo Tender",
        "tender_category": "Электротехническое оборудование",
        "customer_name": "Промышленный заказчик",
        "notes": "Smoke upload run",
    }
    return data, files


def _build_quote_xlsx_bytes(*, supplier_label: str, english: bool = False) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Quote"
    if english:
        sheet.append(["Item", "Description", "Quantity", "Unit", "Unit Price", "Amount", "Delivery", "Currency"])
    else:
        sheet.append(["№", "Наименование", "Кол-во", "Ед. изм.", "Цена", "Сумма", "Срок поставки", "Валюта"])
    sheet.append([1, "Шкаф управления", 2, "шт", 120000, 240000, "35 дней", "RUB"])
    sheet.append([2, "Кабель силовой", 100, "м", 450, 45000, "35 дней", "RUB"])
    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def _build_zip_bytes(entries: list[tuple[str, bytes]]) -> bytes:
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries:
            archive.writestr(name, content)
    return stream.getvalue()


def test_tender_operator_demo_page_shows_both_modes(client):
    response = client.get("/demo/tender-agent")

    assert response.status_code == 200
    assert "Найти закупку" in response.text
    assert "Демо-набор" in response.text
    assert "Загрузка и анализ" in response.text


def test_create_uploaded_run_with_txt_files(client, monkeypatch, tmp_path):
    runs_root = _set_runs_root(monkeypatch, tmp_path)
    data, files = _sample_upload_payload(include_quote=False)

    response = client.post("/api/demo/tender-agent/runs", data=data, files=files)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready_to_analyze"
    assert payload["file_count"] == 3

    metadata_path = runs_root / payload["run_id"] / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["mode"] == "uploaded_demo"
    assert metadata["human_in_the_loop"] is True
    assert metadata["external_actions"] is False
    assert metadata["no_platform_submission"] is True
    assert metadata["files"][0]["stored_name"].startswith("01-")
    assert metadata["economics_inputs"]["target_margin_percent"] == 15.0
    assert metadata["economics_inputs"]["payment_delay_days"] == 45


def test_path_traversal_filename_is_sanitized(client, monkeypatch, tmp_path):
    runs_root = _set_runs_root(monkeypatch, tmp_path)
    data, files = _sample_upload_payload(include_quote=False)
    files[0] = ("files", ("../../notice.txt", b"NOTICE\nSafe name only.", "text/plain"))

    response = client.post("/api/demo/tender-agent/runs", data=data, files=files)

    assert response.status_code == 200
    payload = response.json()
    metadata = json.loads((runs_root / payload["run_id"] / "metadata.json").read_text(encoding="utf-8"))
    stored_name = metadata["files"][0]["stored_name"]
    assert ".." not in stored_name
    assert "/" not in stored_name
    assert "\\" not in stored_name
    assert metadata["warnings"]


def test_unsupported_file_type_is_rejected(client, monkeypatch, tmp_path):
    _set_runs_root(monkeypatch, tmp_path)
    data = {
        "tender_title": "Unsafe",
        "tender_category": "Электротехническое оборудование",
        "customer_name": "Промышленный заказчик",
    }
    files = [("files", ("malware.exe", b"MZ", "application/octet-stream"))]

    response = client.post("/api/demo/tender-agent/runs", data=data, files=files)

    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_analyze_uploaded_run_returns_completed_and_report_endpoints_work(client, monkeypatch, tmp_path):
    runs_root = _set_runs_root(monkeypatch, tmp_path)
    data, files = _sample_upload_payload(include_quote=True)

    create_response = client.post("/api/demo/tender-agent/runs", data=data, files=files)
    run_id = create_response.json()["run_id"]

    analyze = client.post(f"/api/demo/tender-agent/runs/{run_id}/analyze")
    assert analyze.status_code == 200
    analyze_payload = analyze.json()
    assert analyze_payload["status"] in {"completed", "completed_with_warnings"}
    assert analyze_payload["analysis_mode"] == "fallback_deterministic_adapter"

    run_response = client.get(f"/api/demo/tender-agent/runs/{run_id}")
    steps_response = client.get(f"/api/demo/tender-agent/runs/{run_id}/steps")
    report_response = client.get(f"/api/demo/tender-agent/runs/{run_id}/report")
    download_response = client.get(f"/api/demo/tender-agent/runs/{run_id}/report/download")
    report_page = client.get(f"/demo/tender-agent/runs/{run_id}/report")

    assert run_response.status_code == 200
    run_payload = run_response.json()
    assert run_payload["external_actions"] is False
    assert run_payload["human_in_the_loop"] is True
    assert run_payload["report_html_url"].endswith(f"/demo/tender-agent/runs/{run_id}/report")

    assert steps_response.status_code == 200
    steps_payload = steps_response.json()
    assert steps_payload["run_id"] == run_id
    assert len(steps_payload["steps"]) == 9
    assert {step["key"] for step in steps_payload["steps"]} == {
        "documents",
        "requirements",
        "supplier_search",
        "questions",
        "rfq",
        "quotes",
        "economics",
        "risks",
        "decision",
    }

    assert report_response.status_code == 200
    assert report_response.json()["run_id"] == run_id

    assert download_response.status_code == 200
    assert download_response.headers["content-type"].startswith("text/html")
    assert "attachment; filename=" in download_response.headers["content-disposition"]
    assert report_page.status_code == 200
    assert "Отчёт по загруженному прогону тендерного агента" in report_page.text
    assert "Скачано документов" in report_page.text
    assert "Показать документы" in report_page.text

    first_file_download = client.get(f"/api/demo/tender-agent/runs/{run_id}/files/FILE-01/download")
    assert first_file_download.status_code == 200
    assert "attachment; filename=" in first_file_download.headers["content-disposition"]

    assert (runs_root / run_id / "output" / "report.html").exists()


def test_all_failed_controlled_llm_sections_cannot_report_clean_completion(client, monkeypatch, tmp_path):
    runs_root = _set_runs_root(monkeypatch, tmp_path)
    data, files = _sample_upload_payload(include_quote=True)
    monkeypatch.setattr(
        upload_service_legacy,
        "_try_run_llm_workflow",
        lambda **_kwargs: _controlled_llm_result(
            failed_sections={"requirements", "supplier_questions", "rfq_draft", "contract_risks"}
        ),
    )

    create_response = client.post("/api/demo/tender-agent/runs", data=data, files=files)
    run_id = create_response.json()["run_id"]
    analyze = client.post(f"/api/demo/tender-agent/runs/{run_id}/analyze")

    assert analyze.status_code == 200
    assert analyze.json()["analysis_mode"] == "fallback_deterministic_adapter"
    metadata = json.loads((runs_root / run_id / "metadata.json").read_text(encoding="utf-8"))
    provenance = metadata["ai_runtime_provenance"]
    assert provenance["llm_invoked"] is True
    assert provenance["llm_calls_count"] == 4
    assert provenance["fallback_reason"] == "controlled_llm_all_sections_failed"
    events = [json.loads(line) for line in (runs_root / run_id / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert "llm_analysis_completed" not in {event["event_type"] for event in events}
    assert "llm_analysis_validation_failed" in {event["event_type"] for event in events}


def test_partial_controlled_llm_failure_cannot_report_clean_completion(client, monkeypatch, tmp_path):
    runs_root = _set_runs_root(monkeypatch, tmp_path)
    data, files = _sample_upload_payload(include_quote=True)
    monkeypatch.setattr(
        upload_service_legacy,
        "_try_run_llm_workflow",
        lambda **_kwargs: _controlled_llm_result(failed_sections={"contract_risks"}),
    )

    create_response = client.post("/api/demo/tender-agent/runs", data=data, files=files)
    run_id = create_response.json()["run_id"]
    analyze = client.post(f"/api/demo/tender-agent/runs/{run_id}/analyze")

    assert analyze.status_code == 200
    assert analyze.json()["analysis_mode"] == "llm_tender_operator_provider"
    metadata = json.loads((runs_root / run_id / "metadata.json").read_text(encoding="utf-8"))
    provenance = metadata["ai_runtime_provenance"]
    assert provenance["llm_invoked"] is True
    assert provenance["llm_calls_count"] == 4
    assert provenance["fallback_reason"] == "controlled_llm_partial_section_failure:contract_risks"
    events = [json.loads(line) for line in (runs_root / run_id / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert "llm_analysis_completed" not in {event["event_type"] for event in events}
    assert "llm_analysis_completed_with_warnings" in {event["event_type"] for event in events}


def test_analyze_without_quotes_stays_honest_and_needs_review(client, monkeypatch, tmp_path):
    _set_runs_root(monkeypatch, tmp_path)
    data, files = _sample_upload_payload(include_quote=False)

    create_response = client.post("/api/demo/tender-agent/runs", data=data, files=files)
    run_id = create_response.json()["run_id"]

    analyze = client.post(f"/api/demo/tender-agent/runs/{run_id}/analyze")
    assert analyze.status_code == 200
    analyze_payload = analyze.json()
    assert analyze_payload["status"] in {"needs_review", "completed_with_warnings"}
    assert analyze_payload["final_recommendation"]["recommendation"] == "manual_review_required"

    steps_payload = client.get(f"/api/demo/tender-agent/runs/{run_id}/steps").json()
    quotes_step = next(step for step in steps_payload["steps"] if step["key"] == "quotes")
    economics_step = next(step for step in steps_payload["steps"] if step["key"] == "economics")
    assert quotes_step["status"] == "blocked"
    assert economics_step["status"] == "blocked"


def test_fallback_mode_does_not_crash_when_pdf_extraction_is_unavailable(client, monkeypatch, tmp_path):
    _set_runs_root(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "src.modules.tender_operator_agent_demo.upload_service.extract_text_from_attachment_bytes",
        lambda **_kwargs: None,
    )
    data = {
        "tender_title": "PDF fallback demo",
        "tender_category": "Электротехническое оборудование",
        "customer_name": "Промышленный заказчик",
    }
    files = [
        ("files", ("notice.pdf", b"%PDF-1.4 fake", "application/pdf")),
        ("files", ("contract_draft.docx", b"PK\x03\x04fake", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
    ]

    create_response = client.post("/api/demo/tender-agent/runs", data=data, files=files)
    run_id = create_response.json()["run_id"]

    analyze = client.post(f"/api/demo/tender-agent/runs/{run_id}/analyze")

    assert analyze.status_code == 200
    payload = analyze.json()
    assert payload["analysis_mode"] == "fallback_deterministic_adapter"
    assert payload["status"] in {"needs_review", "completed_with_warnings"}


def test_xlsx_quotes_are_normalized_and_report_includes_quote_sections(client, monkeypatch, tmp_path):
    _set_runs_root(monkeypatch, tmp_path)
    data, files = _sample_upload_payload(include_quote=False)
    files.extend(
        [
            ("files", ("ТКП_ПоставщикА.xlsx", _build_quote_xlsx_bytes(supplier_label="Поставщик А"), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")),
            ("files", ("quote_supplier_b.xlsx", _build_quote_xlsx_bytes(supplier_label="Supplier B", english=True), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")),
        ]
    )

    create_response = client.post("/api/demo/tender-agent/runs", data=data, files=files)
    run_id = create_response.json()["run_id"]

    analyze = client.post(f"/api/demo/tender-agent/runs/{run_id}/analyze")
    assert analyze.status_code == 200

    run_payload = client.get(f"/api/demo/tender-agent/runs/{run_id}").json()
    assert run_payload["quote_comparison"]["supplier_quotes_found"] >= 2
    assert run_payload["quote_comparison"]["items_extracted"] >= 2
    assert run_payload["economics_summary"]["economics_status"] in {"conditionally_viable", "insufficient_data"}
    assert run_payload["economics_summary"]["supplier_cost_selected"] is not None

    report_page = client.get(f"/demo/tender-agent/runs/{run_id}/report")
    assert report_page.status_code == 200
    assert "Извлечённые ТКП" in report_page.text
    assert "Сравнение ТКП" in report_page.text
    assert "Экономика" in report_page.text


def test_technical_spec_xlsx_is_not_misclassified_as_supplier_quote(client, monkeypatch, tmp_path):
    _set_runs_root(monkeypatch, tmp_path)
    data, files = _sample_upload_payload(include_quote=False)
    files.append(
        (
            "files",
            (
                "technical_spec_price_table.xlsx",
                _build_quote_xlsx_bytes(supplier_label="ТЗ таблица"),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )
    )

    create_response = client.post("/api/demo/tender-agent/runs", data=data, files=files)
    run_id = create_response.json()["run_id"]

    analyze = client.post(f"/api/demo/tender-agent/runs/{run_id}/analyze")
    assert analyze.status_code == 200

    run_payload = client.get(f"/api/demo/tender-agent/runs/{run_id}").json()
    assert run_payload["quote_comparison"]["supplier_quotes_found"] == 0
    assert run_payload["economics_summary"]["supplier_cost_selected"] is None
    assert run_payload["final_recommendation"]["recommendation"] == "manual_review_required"


def test_report_includes_preliminary_procurement_analysis_from_tz_and_contract(client, monkeypatch, tmp_path):
    _set_runs_root(monkeypatch, tmp_path)
    data = {
        "tender_title": "Обучение по ИБ",
        "tender_category": "Услуги обучения",
        "customer_name": "Администрация города",
    }
    files = [
        ("files", ("notice.txt", "Извещение о закупке образовательных услуг.".encode("utf-8"), "text/plain")),
        (
            "files",
            (
                "technical_spec.txt",
                (
                    "1. Наименование и описание услуг: оказание образовательных услуг по повышению квалификации.\n"
                    "Форма обучения\nОчно-заочная\n"
                    "216 часов\n"
                    "2\n"
                    "3. Место оказания услуг: очное обучение в городе Хабаровске; дистанционная часть на территории Заказчика.\n"
                    "Услуги должны быть согласованы с Федеральной службой по техническому и экспортному контролю.\n"
                ).encode("utf-8"),
                "text/plain",
            ),
        ),
        (
            "files",
            (
                "contract_draft.txt",
                (
                    "Цена Контракта является твердой и не подлежит изменению.\n"
                    "Оплата оказанных Исполнителем Услуг осуществляется Заказчиком в течение 7 рабочих дней после подписания документа о приемке.\n"
                    "Требуется обеспечение исполнения контракта.\n"
                ).encode("utf-8"),
                "text/plain",
            ),
        ),
    ]

    create_response = client.post("/api/demo/tender-agent/runs", data=data, files=files)
    run_id = create_response.json()["run_id"]

    analyze = client.post(f"/api/demo/tender-agent/runs/{run_id}/analyze")
    assert analyze.status_code == 200

    report_page = client.get(f"/demo/tender-agent/runs/{run_id}/report")
    assert report_page.status_code == 200
    assert "Предварительный анализ закупки" in report_page.text
    assert "216 часов" in report_page.text
    assert "Хабаровске" in report_page.text
    assert "7 рабочих дней" in report_page.text
    assert "Ключевые условия договора" in report_page.text
    assert "Подтверждаете ли вы исполнение требований технического задания в полном объеме?" in report_page.text
    assert "Оборудование и товары должны соответствовать заявленной спецификации" not in report_page.text
    assert "Run ID:" not in report_page.text
    assert "Что удалось извлечь из ТЗ и договора" not in report_page.text
    assert report_page.text.count("Программа должна быть согласована с ФСТЭК России.") <= 1


def test_goods_tz_is_rendered_as_table_in_report(client, monkeypatch, tmp_path):
    _set_runs_root(monkeypatch, tmp_path)
    data = {
        "tender_title": "Поставка электротехнических товаров",
        "tender_category": "Электротехническое оборудование",
        "customer_name": "Промышленный заказчик",
    }
    files = [
        ("files", ("notice.txt", "Извещение о поставке товаров.".encode("utf-8"), "text/plain")),
        (
            "files",
            (
                "technical_spec.txt",
                (
                    "1. Описание объекта закупки:\n"
                    "№ п/п Наименование Ед. изм. ОКВЭД2 ОКПД2 КТРУ Кол-во\n"
                    "1 2 3 4 5 6 7 1 Гофра 16 мм шт 27.90 27.90.12.130 - 400\n"
                    "Характеристики объекта закупки:\n"
                    "1 Материал: ПВХ 2 Внешний диаметр, мм: 16 3 Тип: труба гибкая гофрированная\n"
                    "2. Описание объекта закупки:\n"
                    "№ п/п Наименование Ед. изм. ОКВЭД2 ОКПД2 КТРУ Кол-во\n"
                    "1 2 3 4 5 6 7 2 Кабель-канал 20х24 мм м 27.33 27.33.13.130 - 200\n"
                    "Характеристики объекта закупки:\n"
                    "1 Материал: ПВХ 2 Цвет изделия: белый 3 Ширина короба, мм: 24\n"
                    "16. Адрес поставки товара\n"
                    "1 2 1 Московская область, г. Бронницы, Заводской проезд д. 1\n"
                    "17. Сроки поставки товара\n"
                    "1 2 1 В течение 10 рабочих дней с момента подписания контракта.\n"
                ).encode("utf-8"),
                "text/plain",
            ),
        ),
        (
            "files",
            (
                "contract_draft.txt",
                "Оплата осуществляется в течение 7 рабочих дней после подписания документа о приемке.".encode("utf-8"),
                "text/plain",
            ),
        ),
    ]

    create_response = client.post("/api/demo/tender-agent/runs", data=data, files=files)
    run_id = create_response.json()["run_id"]
    analyze = client.post(f"/api/demo/tender-agent/runs/{run_id}/analyze")
    assert analyze.status_code == 200

    report_page = client.get(f"/demo/tender-agent/runs/{run_id}/report")
    assert report_page.status_code == 200
    assert "Состав поставки" in report_page.text
    assert "<table>" in report_page.text
    assert "Гофра 16 мм" in report_page.text
    assert "Кабель-канал 20х24 мм" in report_page.text
    assert "В ТЗ выделена табличная спецификация по товарам." in report_page.text


def test_goods_address_is_not_cut_on_city_abbreviation(client, monkeypatch, tmp_path):
    _set_runs_root(monkeypatch, tmp_path)
    data = {
        "tender_title": "Поставка нефтепродуктов",
        "tender_category": "Нефтепродукты",
        "customer_name": "Промышленный заказчик",
    }
    files = [
        ("files", ("notice.txt", "Извещение о поставке товаров.".encode("utf-8"), "text/plain")),
        (
            "files",
            (
                "technical_spec.txt",
                (
                    "Место поставки товаров : Автозаправочные станции г. Екатеринбург . "
                    "Условия поставки товаров: Заправка осуществляется по электронным картам.\n"
                ).encode("utf-8"),
                "text/plain",
            ),
        ),
        ("files", ("contract_draft.txt", "Оплата в течение 20 рабочих дней после приемки.".encode("utf-8"), "text/plain")),
    ]

    create_response = client.post("/api/demo/tender-agent/runs", data=data, files=files)
    run_id = create_response.json()["run_id"]
    analyze = client.post(f"/api/demo/tender-agent/runs/{run_id}/analyze")
    assert analyze.status_code == 200

    report_page = client.get(f"/demo/tender-agent/runs/{run_id}/report")
    assert report_page.status_code == 200
    assert "Адрес поставки: Автозаправочные станции г. Екатеринбург." in report_page.text
    assert "Адрес поставки: Автозаправочные станции г.</li>" not in report_page.text


def test_realistic_goods_supply_items_are_extracted_from_tz_and_nmck():
    technical_spec_text = (
        "Приложение № 1\n"
        "к техническому заданию\n"
        "Перечень запасных частей\n"
        "№ п/п\n"
        "Наименование\n"
        "Характеристики товара\n"
        "Ед.изм.\n"
        "Кол-во\n"
        "1\n"
        "Кабель силовой АВВГ-П 2х2.5 или эквивалент\n"
        "Номинальное переменное напряжение\n"
        "0,66/1 кВ, частота 50 Гц\n"
        "м\n"
        "200.00\n"
        "Материал\n"
        "алюминий\n"
        "Соответствие\n"
        "ГОСТ 31996-2012\n"
        "2\n"
        "Провод СИП-4 2х16 0.6/1 ГОСТ (намотка на барабане №8) или эквивалент\n"
        "Номинальное переменное напряжение\n"
        "0,6/1 кВ, частота 50 Гц\n"
        "м\n"
        "1300.00\n"
        "Изоляция и оболочка\n"
        "светостабилизированный сшитый полиэтилен\n"
        "Соответствие\n"
        "ГОСТ 31946-2012\n"
        "3\n"
        "Провод СИП-4 4х16 0.6/1 ГОСТ (намотка на барабане №8) или эквивалент\n"
        "Номинальное переменное напряжение\n"
        "0,6/1 кВ, частота 50 Гц\n"
        "м\n"
        "700.00\n"
        "Изоляция\n"
        "светостабилизированный сшитый полиэтилен\n"
        "Соответствие\n"
        "ГОСТ 31946-2012\n"
    )
    nmck_text = (
        "=== Расчет цены ===\n"
        "№ п/п\tНаименование\tЕд. изм\tКоли-чество\tЦена за единицу\tН(М)ЦК\n"
        "1\tКабель силовой АВВГ-П 2х2.5 или эквивалент\tм.\t200\t16.75\t3350\n"
        "2\tПровод СИП-4 2х16 0.6/1 ГОСТ (намотка на барабане №8) или эквивалент\tм.\t1300\t44.35\t57655\n"
        "3\tПровод СИП-4 4х16 0.6/1 ГОСТ (намотка на барабане №8) или эквивалент\tм.\t700\t88.63\t62041\n"
    )

    spec_items = _extract_supply_items_from_spec_text(technical_spec_text, "Техническое задание.doc")
    assert len(spec_items) == 3
    assert spec_items[0].name == "Кабель силовой АВВГ-П 2х2.5"
    assert spec_items[0].unit == "м"
    assert spec_items[0].quantity == "200"
    assert "ГОСТ 31996-2012" in spec_items[0].gost

    merged = _collect_supply_items(
        [
            AnalyzedDocument(
                display_name="Техническое задание.doc",
                extension=".doc",
                role="technical_spec",
                text=technical_spec_text,
                extracted_text_available=True,
                warnings=[],
                source="upload",
                file_id="doc-1",
            ),
            AnalyzedDocument(
                display_name="НМЦК.xlsx",
                extension=".xlsx",
                role="supporting",
                text=nmck_text,
                extracted_text_available=True,
                warnings=[],
                source="upload",
                file_id="doc-2",
            ),
        ]
    )
    assert len(merged) == 3
    assert [item.quantity for item in merged] == ["200", "1300", "700"]
    assert merged[0].unit_price == "16,75"
    assert merged[1].total_price == "57 655,00"
    assert "НМЦК.xlsx" in merged[1].source_documents


def test_goods_report_uses_supply_items_and_goods_economics(client, monkeypatch, tmp_path):
    _set_runs_root(monkeypatch, tmp_path)
    data = {
        "tender_title": "Поставка электротехнической продукции",
        "tender_category": "Электротехническая продукция",
        "customer_name": "МБУ СБСК",
    }
    files = [
        ("files", ("notice.txt", "Извещение о поставке товаров. НМЦК 123046 руб.".encode("utf-8"), "text/plain")),
        (
            "files",
            (
                "technical_spec.txt",
                (
                    "Предмет закупки: Поставка электротехнической продукции\n"
                    "Место поставки товара\n"
                    "Самарская область, г. Кинель, ул. Элеваторная, д. 24.\n"
                    "Срок поставки товара\n"
                    "Поставка Товара осуществляется Поставщиком с даты заключения Контракта по 31.12.2026 г. по заявке Заказчика в течение 15 рабочих дней.\n"
                    "Приложение № 1\n"
                    "Перечень запасных частей\n"
                    "№ п/п\n"
                    "Наименование\n"
                    "Характеристики товара\n"
                    "Ед.изм.\n"
                    "Кол-во\n"
                    "1\n"
                    "Кабель силовой АВВГ-П 2х2.5 или эквивалент\n"
                    "Номинальное переменное напряжение\n"
                    "0,66/1 кВ, частота 50 Гц\n"
                    "м\n"
                    "200.00\n"
                    "Соответствие\n"
                    "ГОСТ 31996-2012\n"
                    "2\n"
                    "Провод СИП-4 2х16 0.6/1 ГОСТ (намотка на барабане №8) или эквивалент\n"
                    "Номинальное переменное напряжение\n"
                    "0,6/1 кВ, частота 50 Гц\n"
                    "м\n"
                    "1300.00\n"
                    "Соответствие\n"
                    "ГОСТ 31946-2012\n"
                    "3\n"
                    "Провод СИП-4 4х16 0.6/1 ГОСТ (намотка на барабане №8) или эквивалент\n"
                    "Номинальное переменное напряжение\n"
                    "0,6/1 кВ, частота 50 Гц\n"
                    "м\n"
                    "700.00\n"
                    "Соответствие\n"
                    "ГОСТ 31946-2012\n"
                ).encode("utf-8"),
                "text/plain",
            ),
        ),
        (
            "files",
            (
                "НМЦК.txt",
                (
                    "=== Расчет цены ===\n"
                    "№ п/п\tНаименование\tЕд. изм\tКоли-чество\tЦена за единицу\tН(М)ЦК\n"
                    "1\tКабель силовой АВВГ-П 2х2.5 или эквивалент\tм.\t200\t16.75\t3350\n"
                    "2\tПровод СИП-4 2х16 0.6/1 ГОСТ (намотка на барабане №8) или эквивалент\tм.\t1300\t44.35\t57655\n"
                    "3\tПровод СИП-4 4х16 0.6/1 ГОСТ (намотка на барабане №8) или эквивалент\tм.\t700\t88.63\t62041\n"
                ).encode("utf-8"),
                "text/plain",
            ),
        ),
        ("files", ("contract_draft.txt", "Оплата осуществляется в течение 7 рабочих дней после подписания документа о приемке.".encode("utf-8"), "text/plain")),
    ]

    create_response = client.post("/api/demo/tender-agent/runs", data=data, files=files)
    run_id = create_response.json()["run_id"]
    analyze = client.post(f"/api/demo/tender-agent/runs/{run_id}/analyze")
    assert analyze.status_code == 200

    report_page = client.get(f"/demo/tender-agent/runs/{run_id}/report")
    assert report_page.status_code == 200
    assert "Кабель силовой АВВГ-П 2х2.5" in report_page.text
    assert "Провод СИП-4 2х16 0.6/1 ГОСТ (намотка на барабане №8)" in report_page.text
    assert "ГОСТ 31946-2012" in report_page.text
    assert "57 655,00" in report_page.text
    assert "цену за единицу и сумму по каждой позиции" in report_page.text
    assert "Ориентир по НМЦК на метр" in report_page.text
    assert "стоимость интеграции СМЭВ/ЕРН" not in report_page.text
    assert "стоимость разработки СЭМД" not in report_page.text


def test_eis_protocol_xml_is_not_misclassified_as_quote(client, monkeypatch, tmp_path):
    _set_runs_root(monkeypatch, tmp_path)
    data = {
        "tender_title": "Поставка нефтепродуктов",
        "tender_category": "Нефтепродукты",
        "customer_name": "Промышленный заказчик",
    }
    files = [
        ("files", ("technical_spec.txt", "Место поставки товаров: АЗС.".encode("utf-8"), "text/plain")),
        ("files", ("contract_draft.txt", "Оплата после приемки.".encode("utf-8"), "text/plain")),
        (
            "files",
            (
                "fcsProposalsResult_0162300005326001258_1.xml",
                "<xml>служебный протокол закупки</xml>".encode("utf-8"),
                "application/xml",
            ),
        ),
    ]

    create_response = client.post("/api/demo/tender-agent/runs", data=data, files=files)
    run_id = create_response.json()["run_id"]
    analyze = client.post(f"/api/demo/tender-agent/runs/{run_id}/analyze")
    assert analyze.status_code == 200

    run_payload = client.get(f"/api/demo/tender-agent/runs/{run_id}").json()
    assert run_payload["quote_comparison"]["supplier_quotes_found"] == 0
    report_page = client.get(f"/demo/tender-agent/runs/{run_id}/report")
    assert "fcsProposalsResult_0162300005326001258_1.xml" not in report_page.text or "Извлечённые ТКП" in report_page.text


def test_zip_with_safe_xlsx_is_processed(client, monkeypatch, tmp_path):
    _set_runs_root(monkeypatch, tmp_path)
    data, files = _sample_upload_payload(include_quote=False)
    zip_payload = _build_zip_bytes(
        [("ТКП_ПоставщикА.xlsx", _build_quote_xlsx_bytes(supplier_label="Поставщик А"))]
    )
    files.append(("files", ("quotes_bundle.zip", zip_payload, "application/zip")))

    create_response = client.post("/api/demo/tender-agent/runs", data=data, files=files)
    run_id = create_response.json()["run_id"]
    analyze = client.post(f"/api/demo/tender-agent/runs/{run_id}/analyze")

    assert analyze.status_code == 200
    run_payload = client.get(f"/api/demo/tender-agent/runs/{run_id}").json()
    assert run_payload["quote_comparison"]["supplier_quotes_found"] >= 1


def test_zip_path_traversal_is_rejected_safely(client, monkeypatch, tmp_path):
    _set_runs_root(monkeypatch, tmp_path)
    data, files = _sample_upload_payload(include_quote=False)
    zip_payload = _build_zip_bytes(
        [
            ("../escape.xlsx", _build_quote_xlsx_bytes(supplier_label="Поставщик А")),
            ("safe/ТКП_ПоставщикБ.xlsx", _build_quote_xlsx_bytes(supplier_label="Поставщик Б")),
        ]
    )
    files.append(("files", ("quotes_bundle.zip", zip_payload, "application/zip")))

    create_response = client.post("/api/demo/tender-agent/runs", data=data, files=files)
    run_id = create_response.json()["run_id"]
    analyze = client.post(f"/api/demo/tender-agent/runs/{run_id}/analyze")

    assert analyze.status_code == 200
    run_payload = client.get(f"/api/demo/tender-agent/runs/{run_id}").json()
    assert any("unsafe path" in warning for warning in run_payload["warnings"])
