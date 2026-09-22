from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.modules.hermes_agent.schemas import (
    HermesAnalysisRequest,
    HermesAnalysisResponse,
    HermesContextRequest,
    HermesEvalCaseCreateRequest,
    HermesEvalCaseResponse,
    HermesFeedbackCreateRequest,
    HermesMemoryCreateRequest,
    HermesMemorySearchRequest,
    HermesQualityCheck,
    HermesRuntimeAnalysisRequest,
    HermesRuntimeAnalysisResult,
)
from src.modules.hermes_agent.service import HermesProcurementAnalysisService
from fastapi import Depends
from sqlalchemy.orm import Session

from src.shared.api.dependencies import DBSession, get_db_session

router = APIRouter(prefix="/internal/hermes", tags=["internal-hermes"])


def get_service(session: DBSession) -> HermesProcurementAnalysisService:
    return HermesProcurementAnalysisService(session)


@router.get("/tenders/{tender_id}/context")
def get_tender_context(tender_id: str, session: DBSession) -> dict:
    service = get_service(session)
    try:
        return service.build_context(tender_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/documents/{document_id}/text")
def get_document_text(document_id: str, session: DBSession) -> dict:
    service = get_service(session)
    try:
        text = service.get_document_text(document_id)
        return {"document_id": document_id, "text": text, "chars": len(text)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/documents/{document_id}/tables")
def get_document_tables(document_id: str, session: DBSession) -> dict:
    service = get_service(session)
    try:
        tables = service.get_document_tables(document_id)
        return {"document_id": document_id, "tables": tables, "count": len(tables)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/tenders/{tender_id}/analysis")
def run_hermes_analysis(tender_id: str, payload: HermesAnalysisRequest, session: DBSession) -> HermesAnalysisResponse:
    if payload.tender_id != tender_id:
        raise HTTPException(status_code=400, detail="tender_id mismatch")

    service = get_service(session)

    context = service.build_context(tender_id)

    analysis = HermesAnalysisResponse(
        tender_id=tender_id,
        document_roles=context.get("document_roles", []),
        summary={
            "subject": context["tender"].get("title", ""),
            "customer": context["tender"].get("customer_name", ""),
            "nmck": str(context["tender"].get("nmck_amount", "")),
        },
    )

    result = service.run_analysis(analysis)

    service.persist_analysis_with_evidence(tender_id, result)

    return result


@router.post("/memory")
def create_memory(payload: HermesMemoryCreateRequest, session: DBSession) -> dict:
    service = get_service(session)
    memory = service.create_memory(payload)
    return {
        "id": memory.id,
        "memory_type": memory.memory_type,
        "scope": memory.scope,
        "category": memory.category,
        "source_tender_id": memory.source_tender_id,
        "created_at": str(memory.created_at),
    }


@router.get("/memory/search")
def search_memory(
    session: DBSession,
    memory_type: str | None = Query(None),
    scope: str | None = Query(None),
    category: str | None = Query(None),
    source_tender_id: str | None = Query(None),
    customer_id: str | None = Query(None),
    project_id: str | None = Query(None),
    procurement_case_id: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
) -> list[dict]:
    service = get_service(session)
    request = HermesMemorySearchRequest(
        memory_type=memory_type,
        scope=scope,
        category=category,
        source_tender_id=source_tender_id,
        customer_id=customer_id,
        project_id=project_id,
        procurement_case_id=procurement_case_id,
        limit=limit,
    )
    try:
        memories = service.search_memory(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [
        {
            "id": m.id,
            "memory_type": m.memory_type,
            "scope": m.scope,
            "category": m.category,
            "payload_json": m.payload_json,
            "source_tender_id": m.source_tender_id,
            "created_at": str(m.created_at),
        }
        for m in memories
    ]


@router.post("/feedback")
def create_feedback(payload: HermesFeedbackCreateRequest, session: DBSession) -> dict:
    service = get_service(session)
    try:
        fb = service.save_feedback_as_memory(payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Scoped analysis context not found") from exc

    eval_case = service.create_eval_case_from_feedback(payload.tender_id, fb)

    return {
        "feedback_id": fb.id,
        "eval_case_id": eval_case.id,
        "tender_id": fb.tender_id,
        "field_path": fb.field_path,
        "feedback_type": fb.feedback_type,
        "message": "Feedback saved and eval case created.",
    }


@router.post("/tenders/{tender_id}/runtime-analysis", response_model=HermesRuntimeAnalysisResult)
def run_hermes_runtime_analysis(
    tender_id: str,
    payload: HermesRuntimeAnalysisRequest,
    session: Session = Depends(get_db_session),
) -> HermesRuntimeAnalysisResult:
    if payload.tender_id != tender_id:
        raise HTTPException(status_code=400, detail="tender_id mismatch")

    service = get_service(session)
    try:
        result = service.run_runtime_analysis(tender_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger = __import__("logging").getLogger(__name__)
        logger.exception("Runtime analysis failed for tender %s", tender_id)
        raise HTTPException(status_code=500, detail="Runtime analysis failed.")


@router.get("/quality-checks")
def run_quality_checks(
    tender_id: str = Query(..., description="Tender ID to analyze"),
    session: Session = Depends(get_db_session),
) -> list[HermesQualityCheck]:
    from src.modules.hermes_agent.quality import run_all_quality_gates
    from src.modules.hermes_agent.schemas import HermesAnalysisResponse

    service = get_service(session)
    context = service.build_context(tender_id)
    analysis = HermesAnalysisResponse(
        tender_id=tender_id,
        document_roles=context.get("document_roles", []),
        summary={
            "subject": context["tender"].get("title", ""),
            "customer": context["tender"].get("customer_name", ""),
            "nmck": str(context["tender"].get("nmck_amount", "")),
        },
    )
    return run_all_quality_gates(analysis)
