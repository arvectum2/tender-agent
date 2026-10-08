from fastapi import APIRouter, status

from src.modules.application_package_generator.schemas import (
    ApplicationDraftFieldProvenanceResponse,
    ApplicationDraftGenerationResponse,
    GenerateApplicationDraftRequest,
)
from src.modules.application_package_generator.service import (
    generate_application_draft,
    get_application_draft,
    list_application_drafts,
)
from src.shared.api.dependencies import DBSession

router = APIRouter(prefix="/api/application-drafts", tags=["application-drafts"])


def _response(generation, artifact, fields) -> ApplicationDraftGenerationResponse:
    return ApplicationDraftGenerationResponse(
        generation_id=generation.id,
        deal_id=generation.deal_id,
        template_artifact_ref=generation.template_artifact_ref,
        output_artifact_ref=generation.output_artifact_ref,
        output_file_name=generation.output_file_name,
        output_storage_uri=generation.output_storage_uri,
        document_role=generation.document_role,
        output_format=generation.output_format,
        lineage_key=generation.lineage_key,
        template_version_no=generation.template_version_no,
        generation_version_no=generation.generation_version_no,
        template_sha256=generation.template_sha256,
        output_sha256=generation.output_sha256,
        review_state=generation.review_state,
        signature_performed=generation.signature_performed,
        submission_performed=generation.submission_performed,
        external_delivery_performed=generation.external_delivery_performed,
        created_at=generation.created_at,
        field_provenance=[
            ApplicationDraftFieldProvenanceResponse(
                source_type=item.source_type,
                source_ref=item.source_ref,
                target_locator=item.target_locator,
                original_value=item.original_value_json,
                generated_value=item.generated_value_json,
            )
            for item in fields
        ],
    )


@router.post(
    "/generate",
    response_model=ApplicationDraftGenerationResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_application_draft_route(
    payload: GenerateApplicationDraftRequest,
    session: DBSession,
) -> ApplicationDraftGenerationResponse:
    return _response(*generate_application_draft(session, payload))


@router.get("/{generation_id}", response_model=ApplicationDraftGenerationResponse)
def get_application_draft_route(
    generation_id: str,
    session: DBSession,
) -> ApplicationDraftGenerationResponse:
    return _response(*get_application_draft(session, generation_id))


@router.get("", response_model=list[ApplicationDraftGenerationResponse])
def list_application_drafts_route(
    session: DBSession,
    deal_id: str | None = None,
    document_role: str | None = None,
) -> list[ApplicationDraftGenerationResponse]:
    return [
        _response(*item)
        for item in list_application_drafts(
            session,
            deal_id=deal_id,
            document_role=document_role,
        )
    ]
