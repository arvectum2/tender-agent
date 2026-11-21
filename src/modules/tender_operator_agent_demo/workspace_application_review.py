"""Bounded archive-only application review for the private operator workspace."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, StrictBool

from src.modules.company_profile_store.application_checklist import (
    Signatory,
    _rows,
    observe_application,
)


class ApplicationReviewRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    signatory: Signatory = 'UNKNOWN'
    goods_used: StrictBool | None = None


class ReviewFragment(BaseModel):
    group: str
    file_id: str
    chunk_id: str
    original_sha256: str
    quote: str


class ReviewRow(BaseModel):
    code: str
    title: str
    category: str
    applicability: str
    citations: list[ReviewFragment]


class ApplicationReviewResponse(BaseModel):
    contract: Literal['archived_application_review_v1'] = 'archived_application_review_v1'
    run_id: str
    procurement_number: str | None
    status: Literal['UNKNOWN','INCOMPLETE_REVIEWED_SOURCE','ARCHIVED_QUOTATION_CHECKLIST_REVIEW_ONLY','ARCHIVED_NOTIFICATION_NOT_APPLICATION']
    signatory: Signatory
    goods_used: StrictBool | None
    rows: list[ReviewRow]
    notification_sources: list[ReviewFragment]
    current_revision_attested: Literal[False] = False
    whole_application_requirements_complete: Literal[False] = False
    company_profile_checked: Literal[False] = False
    application_ready: Literal[False] = False
    recommendation: Literal['DEFER'] = 'DEFER'
    external_action_allowed: Literal[False] = False


def _fragments(groups):
    return [ReviewFragment(group=key,file_id=f['file_id'],chunk_id=f['chunk_id'],
                           original_sha256=f['original_sha256'],quote=f['quote'])
            for key,fragments in groups.items() for f in fragments]


def review_workspace_application(run_id, request):
    packet=observe_application(run_id)
    rows=[]
    notifications=[]
    if packet['status']=='ARCHIVED_QUOTATION_CHECKLIST_REVIEW_ONLY':
        for row in _rows(packet,request.signatory,request.goods_used):
            rows.append(ReviewRow(code=row['code'],title=row['title'],category=row['category'],
                                  applicability=row['applicability'],citations=_fragments(row['source'])))
    elif packet['status']=='ARCHIVED_NOTIFICATION_NOT_APPLICATION':
        notifications=[f for groups in packet['source_groups'].values() for f in _fragments(groups)]
    return ApplicationReviewResponse(run_id=run_id,procurement_number=packet['procurement_number'],
            status=packet['status'],signatory=request.signatory,goods_used=request.goods_used,
            rows=rows,notification_sources=notifications)
