from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response

from src.modules.commercial_core.run_service import (
    evaluate_run_commercial_core,
    get_run_commercial_core,
)
from src.modules.commercial_core.schemas import CommercialCoreResponse
from src.modules.tender_operator_agent_demo.pilot_wizard_ui import (
    render_tender_operator_pilot_wizard_html,
)
from src.modules.tender_operator_agent_demo.procurement_discovery import (
    build_public_search_url,
    get_procurement_details,
    get_supplier_profile,
    list_procurement_sources,
    reset_supplier_profile,
    search_procurements,
    search_public_44fz,
)
from src.modules.tender_operator_agent_demo.procurement_intake_service import (
    create_run_from_eis_docs_archive,
    create_run_from_procurement,
    create_run_from_search_result,
    get_procurement_for_run,
)
from src.modules.tender_operator_agent_demo.procurement_schemas import (
    ProcurementDetails,
    ProcurementSourceStatus,
    PublicProcurementSearchResponse,
)
from src.modules.tender_operator_agent_demo.procurement_schemas import (
    ProcurementSearchRequest as ProcurementSearchRequestV2,
)
from src.modules.tender_operator_agent_demo.procurement_schemas import (
    ProcurementSearchResult as ProcurementSearchResultV2,
)
from src.modules.tender_operator_agent_demo.report_export_service import (
    export_demo_agent_report_docx,
    export_demo_agent_report_pdf,
)
from src.modules.tender_operator_agent_demo.schemas import (
    EisDocsArchiveRunRequest,
    ProcurementRunCreateRequest,
    ProcurementRunDetailsResponse,
    ProcurementRunResponse,
    ProcurementSearchResponse,
    PublicSearchUrlResponse,
    SearchResultHandoffRequest,
    SearchResultHandoffResponse,
    TenderOperatorDemoReportResponse,
    TenderOperatorDemoRunResponse,
    TenderOperatorDemoStepsResponse,
    TenderOperatorRunEventFeedItem,
    TenderOperatorUploadedRunAnalyzeResponse,
    TenderOperatorUploadedRunCreateResponse,
    TenderOperatorUploadedRunListResponse,
    TenderOperatorUploadedRunResponse,
    TenderOperatorUploadedRunStepsResponse,
)
from src.modules.tender_operator_agent_demo.service import (
    ASSET_MAP,
    get_demo_asset_response,
    get_tender_operator_demo_report,
    get_tender_operator_demo_report_download,
    get_tender_operator_demo_run,
    get_tender_operator_demo_steps,
    render_tender_operator_demo_report_html,
)
from src.modules.tender_operator_agent_demo.ui import (
    render_tender_operator_console_html,
)
from src.modules.tender_operator_agent_demo.upload_service import (
    analyze_uploaded_demo_run,
    append_files_to_demo_run,
    create_uploaded_demo_run,
    get_uploaded_demo_archive_download,
    get_uploaded_demo_report,
    get_uploaded_demo_report_download,
    get_uploaded_demo_report_html,
    get_uploaded_demo_run,
    get_uploaded_demo_run_steps,
    get_uploaded_demo_source_file_download,
    list_uploaded_demo_runs,
    load_demo_run_events,
)

router = APIRouter(tags=["tender-operator-agent-demo"])


@router.get("/demo/tender-agent", response_class=HTMLResponse)
def tender_operator_demo_page() -> str:
    return render_tender_operator_console_html()


@router.get("/pilot/tender-agent", response_class=HTMLResponse)
def tender_operator_pilot_wizard_page() -> str:
    return render_tender_operator_pilot_wizard_html()


@router.get("/demo/tender-agent/wizard", response_class=HTMLResponse)
def tender_operator_pilot_wizard_demo_alias_page() -> str:
    return render_tender_operator_pilot_wizard_html()


@router.get("/demo/tender-agent/runs/{run_id}", response_class=HTMLResponse)
def tender_operator_uploaded_run_page(run_id: str) -> str:
    return render_tender_operator_console_html(selected_run_id=run_id)


@router.get("/demo/tender-agent/report", response_class=HTMLResponse)
def tender_operator_demo_report_page() -> str:
    return render_tender_operator_demo_report_html()


@router.get("/demo/tender-agent/runs/{run_id}/report", response_class=HTMLResponse)
def tender_operator_uploaded_run_report_page(run_id: str) -> str:
    return get_uploaded_demo_report_html(run_id)


@router.get("/demo/tender-agent/assets/{asset_name}")
def tender_operator_demo_asset(asset_name: str):
    if asset_name not in ASSET_MAP:
        raise HTTPException(status_code=404, detail="Asset was not found")
    return get_demo_asset_response(asset_name)


@router.get("/api/demo/tender-agent/run", response_model=TenderOperatorDemoRunResponse)
def tender_operator_demo_run() -> TenderOperatorDemoRunResponse:
    return get_tender_operator_demo_run()


@router.get("/api/demo/tender-agent/steps", response_model=TenderOperatorDemoStepsResponse)
def tender_operator_demo_steps() -> TenderOperatorDemoStepsResponse:
    return get_tender_operator_demo_steps()


@router.get("/api/demo/tender-agent/report", response_model=TenderOperatorDemoReportResponse)
def tender_operator_demo_report() -> TenderOperatorDemoReportResponse:
    return get_tender_operator_demo_report()


@router.get("/api/demo/tender-agent/report/download")
def tender_operator_demo_report_download() -> Response:
    file_name, payload = get_tender_operator_demo_report_download()
    return Response(
        content=payload,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )


@router.get("/api/demo/tender-agent/procurements/search", response_model=ProcurementSearchResponse)
def search_tender_operator_procurements(
    query: str = "",
    source: str = "demo_local",
    max_results: int = 10,
    date_from: str | None = None,
    date_to: str | None = None,
    customer_name: str | None = None,
    region: str | None = None,
    price_from: float | None = None,
    price_to: float | None = None,
) -> ProcurementSearchResponse:
    try:
        return search_procurements(
            query=query,
            source=source,
            max_results=max_results,
            date_from=date_from,
            date_to=date_to,
            customer_name=customer_name,
            region=region,
            price_from=price_from,
            price_to=price_to,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/demo/tender-agent/procurement/sources", response_model=list[ProcurementSourceStatus])
def list_tender_operator_procurement_sources() -> list[ProcurementSourceStatus]:
    return list_procurement_sources()


@router.get("/api/demo/tender-agent/supplier-profile")
def get_supplier_profile_endpoint():
    return get_supplier_profile().model_dump(mode="json")


@router.post("/api/demo/tender-agent/supplier-profile/reset")
def reset_supplier_profile_endpoint():
    return reset_supplier_profile().model_dump(mode="json")


@router.get("/api/demo/tender-agent/procurement/public-search-url", response_model=PublicSearchUrlResponse)
def get_tender_operator_public_search_url(
    query: str,
    law: str = "44fz",
    region: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> PublicSearchUrlResponse:
    return build_public_search_url(query=query, law=law, region=region, date_from=date_from, date_to=date_to)


@router.post("/api/demo/tender-agent/procurement/public-44fz-search", response_model=PublicProcurementSearchResponse)
def search_tender_operator_public_44fz(
    query: str | None = Form(None),
    law: str | None = Form(None),
    region: str | None = Form(None),
    date_from: str | None = Form(None),
    date_to: str | None = Form(None),
    price_from: float | None = Form(None),
    price_to: float | None = Form(None),
    deadline_from: str | None = Form(None),
    deadline_to: str | None = Form(None),
    status_filter: str | None = Form(None),
    procedure_type: str | None = Form(None),
    page: int | None = Form(None),
    page_size: int | None = Form(None),
    max_results: int | None = Form(None),
    cursor: str | None = Form(None),
    seen_registry_numbers: str | None = Form(None),
    query_q: str | None = Query(None, alias="query"),
    law_q: str | None = Query(None, alias="law"),
    region_q: str | None = Query(None, alias="region"),
    date_from_q: str | None = Query(None, alias="date_from"),
    date_to_q: str | None = Query(None, alias="date_to"),
    price_from_q: float | None = Query(None, alias="price_from"),
    price_to_q: float | None = Query(None, alias="price_to"),
    deadline_from_q: str | None = Query(None, alias="deadline_from"),
    deadline_to_q: str | None = Query(None, alias="deadline_to"),
    status_filter_q: str | None = Query(None, alias="status_filter"),
    procedure_type_q: str | None = Query(None, alias="procedure_type"),
    page_q: int | None = Query(None, alias="page"),
    page_size_q: int | None = Query(None, alias="page_size"),
    max_results_q: int | None = Query(None, alias="max_results"),
    cursor_q: str | None = Query(None, alias="cursor"),
    seen_registry_numbers_q: str | None = Query(None, alias="seen_registry_numbers"),
):
    query = query if query is not None else query_q or ""
    law = law if law is not None else law_q or "44fz"
    region = region if region is not None else region_q
    date_from = date_from if date_from is not None else date_from_q
    date_to = date_to if date_to is not None else date_to_q
    price_from = price_from if price_from is not None else price_from_q
    price_to = price_to if price_to is not None else price_to_q
    deadline_from = deadline_from if deadline_from is not None else deadline_from_q
    deadline_to = deadline_to if deadline_to is not None else deadline_to_q
    status_filter = status_filter if status_filter is not None else status_filter_q
    procedure_type = procedure_type if procedure_type is not None else procedure_type_q
    page = page if page is not None else page_q or 1
    page_size = page_size if page_size is not None else page_size_q or 10
    max_results = max_results if max_results is not None else max_results_q or 10
    cursor = cursor if cursor is not None else cursor_q
    seen_registry_numbers = seen_registry_numbers if seen_registry_numbers is not None else seen_registry_numbers_q
    parsed_seen: list[str] = []
    if seen_registry_numbers:
        try:
            import json
            parsed_seen = json.loads(seen_registry_numbers)
            if not isinstance(parsed_seen, list):
                parsed_seen = []
        except (json.JSONDecodeError, ValueError):
            parsed_seen = []
    try:
        return search_public_44fz(
            query=query,
            law=law,
            region=region,
            date_from=date_from,
            date_to=date_to,
            price_from=price_from,
            price_to=price_to,
            deadline_from=deadline_from,
            deadline_to=deadline_to,
            status_filter=status_filter,
            procedure_type=procedure_type,
            page=page,
            page_size=page_size,
            max_results=max_results,
            cursor=cursor,
            seen_registry_numbers=parsed_seen,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/demo/tender-agent/procurement/search", response_model=list[ProcurementSearchResultV2])
def search_tender_operator_procurements_v2(payload: ProcurementSearchRequestV2) -> list[ProcurementSearchResultV2]:
    try:
        results = search_procurements(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if not isinstance(results, list):
        raise HTTPException(status_code=500, detail="Unexpected procurement search response")
    return results


@router.get(
    "/api/demo/tender-agent/procurement/{source}/{procurement_id}",
    response_model=ProcurementDetails,
)
def get_tender_operator_procurement_details(source: str, procurement_id: str) -> ProcurementDetails:
    try:
        return get_procurement_details(source, procurement_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/api/demo/tender-agent/runs/from-procurement", response_model=ProcurementRunResponse)
def create_tender_operator_run_from_procurement(payload: ProcurementRunCreateRequest) -> ProcurementRunResponse:
    return create_run_from_procurement(payload)


@router.post("/api/demo/tender-agent/runs/from-eis-docs-archive", response_model=ProcurementRunResponse)
def create_tender_operator_run_from_eis_docs_archive(payload: EisDocsArchiveRunRequest) -> ProcurementRunResponse:
    return create_run_from_eis_docs_archive(payload)


@router.post("/api/demo/tender-agent/runs/from-search-result", response_model=SearchResultHandoffResponse)
def create_tender_operator_run_from_search_result(payload: SearchResultHandoffRequest) -> SearchResultHandoffResponse:
    return create_run_from_search_result(payload)


@router.post("/api/demo/tender-agent/runs", response_model=TenderOperatorUploadedRunCreateResponse)
async def create_tender_operator_uploaded_run(
    tender_title: str = Form(...),
    tender_category: str = Form(default="Электротехническое оборудование"),
    customer_name: str = Form(default="Промышленный заказчик"),
    notes: str | None = Form(default=None),
    target_margin_percent: float = Form(default=15),
    logistics_reserve_percent: float = Form(default=3),
    risk_reserve_percent: float = Form(default=5),
    payment_delay_days: int = Form(default=45),
    files: Annotated[list[UploadFile], File()] = ...,
) -> TenderOperatorUploadedRunCreateResponse:
    uploads: list[tuple[str, str, bytes]] = []
    for item in files:
        uploads.append((item.filename or "upload.bin", item.content_type or "application/octet-stream", await item.read()))
    return create_uploaded_demo_run(
        tender_title=tender_title,
        tender_category=tender_category,
        customer_name=customer_name,
        notes=notes,
        target_margin_percent=target_margin_percent,
        logistics_reserve_percent=logistics_reserve_percent,
        risk_reserve_percent=risk_reserve_percent,
        payment_delay_days=payment_delay_days,
        uploads=uploads,
    )


@router.post("/api/demo/tender-agent/runs/{run_id}/files", response_model=TenderOperatorUploadedRunCreateResponse)
async def append_tender_operator_uploaded_files(
    run_id: str,
    files: Annotated[list[UploadFile], File()] = ...,
) -> TenderOperatorUploadedRunCreateResponse:
    uploads: list[tuple[str, str, bytes]] = []
    for item in files:
        uploads.append((item.filename or "upload.bin", item.content_type or "application/octet-stream", await item.read()))
    return append_files_to_demo_run(run_id=run_id, uploads=uploads)


@router.get("/api/demo/tender-agent/runs", response_model=TenderOperatorUploadedRunListResponse)
def list_tender_operator_uploaded_runs() -> TenderOperatorUploadedRunListResponse:
    return list_uploaded_demo_runs()


@router.get("/api/demo/tender-agent/runs/{run_id}", response_model=TenderOperatorUploadedRunResponse)
def get_tender_operator_uploaded_run(run_id: str) -> TenderOperatorUploadedRunResponse:
    return get_uploaded_demo_run(run_id)


@router.get("/api/demo/tender-agent/runs/{run_id}/events", response_model=list[TenderOperatorRunEventFeedItem])
def get_tender_operator_uploaded_run_events(run_id: str) -> list[TenderOperatorRunEventFeedItem]:
    return [
        TenderOperatorRunEventFeedItem(
            timestamp=item.timestamp or item.created_at,
            event_type=item.event_type,
            message_ru=item.message_ru or item.message,
            step=item.step,
            severity=item.severity,
        )
        for item in load_demo_run_events(run_id)
    ]


@router.get("/api/demo/tender-agent/runs/{run_id}/procurement", response_model=ProcurementRunDetailsResponse)
def get_tender_operator_procurement_for_run(run_id: str) -> ProcurementRunDetailsResponse:
    return get_procurement_for_run(run_id)


@router.post("/api/demo/tender-agent/runs/{run_id}/analyze", response_model=TenderOperatorUploadedRunAnalyzeResponse)
def analyze_tender_operator_uploaded_run(run_id: str) -> TenderOperatorUploadedRunAnalyzeResponse:
    return analyze_uploaded_demo_run(run_id)


@router.post(
    "/api/demo/tender-agent/runs/{run_id}/commercial-core",
    response_model=CommercialCoreResponse,
)
async def evaluate_tender_operator_commercial_core(
    run_id: str,
    catalog_file: Annotated[UploadFile, File()] = ...,
    default_currency: str | None = Form(default=None),
    target_bid_amount: float | None = Form(default=None),
) -> CommercialCoreResponse:
    return evaluate_run_commercial_core(
        run_id,
        catalog_filename=catalog_file.filename or "catalog",
        catalog_content=await catalog_file.read(),
        default_currency=default_currency,
        target_bid_amount=target_bid_amount,
    )


@router.get(
    "/api/demo/tender-agent/runs/{run_id}/commercial-core",
    response_model=CommercialCoreResponse,
)
def get_tender_operator_commercial_core(run_id: str) -> CommercialCoreResponse:
    return get_run_commercial_core(run_id)


@router.get("/api/demo/tender-agent/runs/{run_id}/steps", response_model=TenderOperatorUploadedRunStepsResponse)
def get_tender_operator_uploaded_run_steps(run_id: str) -> TenderOperatorUploadedRunStepsResponse:
    return get_uploaded_demo_run_steps(run_id)


@router.get("/api/demo/tender-agent/runs/{run_id}/report", response_model=TenderOperatorDemoReportResponse)
def get_tender_operator_uploaded_run_report(run_id: str) -> TenderOperatorDemoReportResponse:
    return get_uploaded_demo_report(run_id)


@router.get("/api/demo/tender-agent/runs/{run_id}/report/download")
def download_tender_operator_uploaded_run_report(run_id: str):
    return get_uploaded_demo_report_download(run_id)


@router.get("/api/demo/tender-agent/runs/{run_id}/files/{file_id}/download")
def download_tender_operator_uploaded_run_source_file(run_id: str, file_id: str):
    return get_uploaded_demo_source_file_download(run_id, file_id)


@router.get("/api/demo/tender-agent/runs/{run_id}/archive/download")
def download_tender_operator_uploaded_run_archive(run_id: str):
    return get_uploaded_demo_archive_download(run_id)


@router.get("/api/demo/tender-agent/runs/{run_id}/export/docx")
def export_tender_operator_uploaded_run_docx(run_id: str) -> FileResponse:
    try:
        exported = export_demo_agent_report_docx(run_id)
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to export DOCX report") from exc
    return FileResponse(
        exported.file_path,
        media_type=exported.content_type,
        filename=exported.file_name,
    )


@router.get("/api/demo/tender-agent/runs/{run_id}/export/pdf")
def export_tender_operator_uploaded_run_pdf(run_id: str) -> FileResponse:
    try:
        exported = export_demo_agent_report_pdf(run_id)
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to export PDF report") from exc
    return FileResponse(
        exported.file_path,
        media_type=exported.content_type,
        filename=exported.file_name,
    )
