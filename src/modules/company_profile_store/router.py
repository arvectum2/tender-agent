from fastapi import APIRouter, Query, status

from src.modules.company_profile_store.schemas import (
    AppendCompanyDocumentVersionRequest,
    AppendCompanyProfileFactRequest,
    CompanyDocumentResponse,
    CompanyDocumentVersionResponse,
    CompanyProfileFactVersionResponse,
    CreateCompanyDocumentRequest,
    ResolveCompanyAutofillRequest,
    ResolveCompanyAutofillResponse,
)
from src.modules.company_profile_store.service import (
    append_company_document_version,
    append_company_profile_fact,
    artifact_version_evidence,
    create_company_document,
    document_version_state,
    fact_state,
    get_company_document,
    get_company_profile_fact_history,
    list_company_documents,
    list_current_company_profile_facts,
    resolve_company_autofill,
)
from src.shared.api.dependencies import DBSession

router = APIRouter(
    prefix="/api/company-profile/customers/{customer_id}",
    tags=["company-profile"],
)


def _fact_response(
    record, *, latest_version_no: int
) -> CompanyProfileFactVersionResponse:
    is_current, is_expired, state = fact_state(
        record,
        latest_version_no=latest_version_no,
    )
    return CompanyProfileFactVersionResponse(
        id=record.id,
        customer_id=record.customer_id,
        fact_key=record.fact_key,
        fact_group=record.fact_group,
        version_no=record.version_no,
        value=record.value_json,
        source_type=record.source_type,
        source_ref=record.source_ref,
        expires_at=record.expires_at,
        created_at=record.created_at,
        is_current=is_current,
        is_expired=is_expired,
        state=state,
    )


def _document_response(
    session: DBSession,
    document,
    versions,
) -> CompanyDocumentResponse:
    latest_version_no = versions[-1].version_no
    version_responses = []
    for version in versions:
        evidence = artifact_version_evidence(
            session,
            artifact_ref=document.artifact_ref,
            artifact_version_no=version.artifact_version_no,
        )
        is_current, is_expired, state = document_version_state(
            version,
            latest_version_no=latest_version_no,
        )
        version_responses.append(
            CompanyDocumentVersionResponse(
                id=version.id,
                version_no=version.version_no,
                artifact_ref=document.artifact_ref,
                artifact_version_no=version.artifact_version_no,
                artifact_storage_uri=evidence.storage_uri,
                artifact_checksum_sha256=evidence.checksum_sha256,
                document_number=version.document_number,
                issued_at=version.issued_at,
                expires_at=version.expires_at,
                source_type=version.source_type,
                source_ref=version.source_ref,
                created_at=version.created_at,
                is_current=is_current,
                is_expired=is_expired,
                state=state,
            )
        )
    return CompanyDocumentResponse(
        id=document.id,
        customer_id=document.customer_id,
        document_key=document.document_key,
        document_type=document.document_type,
        display_name=document.display_name,
        artifact_ref=document.artifact_ref,
        created_at=document.created_at,
        current_version_no=latest_version_no,
        current_state=version_responses[-1].state,
        versions=version_responses,
    )


@router.post(
    "/facts/{fact_key}/versions",
    response_model=CompanyProfileFactVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def append_fact_version_route(
    customer_id: str,
    fact_key: str,
    payload: AppendCompanyProfileFactRequest,
    session: DBSession,
) -> CompanyProfileFactVersionResponse:
    record = append_company_profile_fact(
        session,
        customer_id=customer_id,
        fact_key=fact_key,
        payload=payload,
    )
    return _fact_response(record, latest_version_no=record.version_no)


@router.get(
    "/facts/{fact_key}",
    response_model=list[CompanyProfileFactVersionResponse],
)
def get_fact_history_route(
    customer_id: str,
    fact_key: str,
    session: DBSession,
) -> list[CompanyProfileFactVersionResponse]:
    records = get_company_profile_fact_history(
        session,
        customer_id=customer_id,
        fact_key=fact_key,
    )
    latest = records[-1].version_no
    return [_fact_response(record, latest_version_no=latest) for record in records]


@router.get(
    "/facts",
    response_model=list[CompanyProfileFactVersionResponse],
)
def list_current_facts_route(
    customer_id: str,
    session: DBSession,
) -> list[CompanyProfileFactVersionResponse]:
    records = list_current_company_profile_facts(session, customer_id=customer_id)
    return [
        _fact_response(record, latest_version_no=record.version_no)
        for record in records
    ]


@router.post(
    "/documents",
    response_model=CompanyDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_document_route(
    customer_id: str,
    payload: CreateCompanyDocumentRequest,
    session: DBSession,
) -> CompanyDocumentResponse:
    document, _version = create_company_document(
        session,
        customer_id=customer_id,
        payload=payload,
    )
    return _document_response(
        session,
        *get_company_document(
            session,
            customer_id=customer_id,
            document_key=document.document_key,
        ),
    )


@router.post(
    "/documents/{document_key}/versions",
    response_model=CompanyDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def append_document_version_route(
    customer_id: str,
    document_key: str,
    payload: AppendCompanyDocumentVersionRequest,
    session: DBSession,
) -> CompanyDocumentResponse:
    document, _version = append_company_document_version(
        session,
        customer_id=customer_id,
        document_key=document_key,
        payload=payload,
    )
    return _document_response(
        session,
        *get_company_document(
            session,
            customer_id=customer_id,
            document_key=document.document_key,
        ),
    )


@router.get("/documents/{document_key}", response_model=CompanyDocumentResponse)
def get_document_route(
    customer_id: str,
    document_key: str,
    session: DBSession,
) -> CompanyDocumentResponse:
    return _document_response(
        session,
        *get_company_document(
            session,
            customer_id=customer_id,
            document_key=document_key,
        ),
    )


@router.get("/documents", response_model=list[CompanyDocumentResponse])
def list_documents_route(
    customer_id: str,
    session: DBSession,
    document_type: str | None = Query(default=None),
) -> list[CompanyDocumentResponse]:
    return [
        _document_response(session, *item)
        for item in list_company_documents(
            session,
            customer_id=customer_id,
            document_type=document_type,
        )
    ]


@router.post("/autofill", response_model=ResolveCompanyAutofillResponse)
def resolve_autofill_route(
    customer_id: str,
    payload: ResolveCompanyAutofillRequest,
    session: DBSession,
) -> ResolveCompanyAutofillResponse:
    resolved, unresolved = resolve_company_autofill(
        session,
        customer_id=customer_id,
        payload=payload,
    )
    return ResolveCompanyAutofillResponse(
        customer_id=customer_id,
        resolved=resolved,
        unresolved=unresolved,
        inference_performed=False,
        private_document_import_performed=False,
    )
