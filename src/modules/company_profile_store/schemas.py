from datetime import datetime
from typing import Literal

from pydantic import Field

from src.shared.types.common import APIModel

FactGroup = Literal[
    "IDENTITY",
    "REQUISITE",
    "CONTACT",
    "LICENSE",
    "CERTIFICATE",
    "EXPERIENCE",
    "OTHER",
]
CompanyDocumentType = Literal[
    "STATUTORY",
    "LICENSE",
    "CERTIFICATE",
    "EXPERIENCE",
    "REQUISITES",
    "TEMPLATE",
]


class AppendCompanyProfileFactRequest(APIModel):
    fact_group: FactGroup
    value: object | None = None
    source_type: str = Field(min_length=1, max_length=64)
    source_ref: str = Field(min_length=1)
    expires_at: datetime | None = None


class CompanyProfileFactVersionResponse(APIModel):
    id: str
    customer_id: str
    fact_key: str
    fact_group: FactGroup
    version_no: int
    value: object | None
    source_type: str
    source_ref: str
    expires_at: datetime | None
    created_at: datetime
    is_current: bool
    is_expired: bool
    state: Literal["ACTIVE", "EXPIRED", "SUPERSEDED"]


class CreateCompanyDocumentRequest(APIModel):
    document_key: str = Field(min_length=1, max_length=128)
    document_type: CompanyDocumentType
    display_name: str = Field(min_length=1)
    artifact_ref: str = Field(min_length=1)
    artifact_version_no: int = Field(ge=1)
    document_number: str | None = None
    issued_at: datetime | None = None
    expires_at: datetime | None = None
    source_type: str = Field(min_length=1, max_length=64)
    source_ref: str = Field(min_length=1)


class AppendCompanyDocumentVersionRequest(APIModel):
    artifact_version_no: int = Field(ge=1)
    document_number: str | None = None
    issued_at: datetime | None = None
    expires_at: datetime | None = None
    source_type: str = Field(min_length=1, max_length=64)
    source_ref: str = Field(min_length=1)


class CompanyDocumentVersionResponse(APIModel):
    id: str
    version_no: int
    artifact_ref: str
    artifact_version_no: int
    artifact_storage_uri: str
    artifact_checksum_sha256: str | None
    document_number: str | None
    issued_at: datetime | None
    expires_at: datetime | None
    source_type: str
    source_ref: str
    created_at: datetime
    is_current: bool
    is_expired: bool
    state: Literal["ACTIVE", "EXPIRED", "SUPERSEDED"]


class CompanyDocumentResponse(APIModel):
    id: str
    customer_id: str
    document_key: str
    document_type: CompanyDocumentType
    display_name: str
    artifact_ref: str
    created_at: datetime
    current_version_no: int
    current_state: Literal["ACTIVE", "EXPIRED"]
    versions: list[CompanyDocumentVersionResponse] = Field(default_factory=list)


class AutofillTargetRequest(APIModel):
    fact_key: str = Field(min_length=1, max_length=128)
    target_locator: str = Field(min_length=1)


class ResolveCompanyAutofillRequest(APIModel):
    targets: list[AutofillTargetRequest] = Field(min_length=1)


class AutofillResolvedField(APIModel):
    fact_key: str
    target_locator: str
    value: object | None
    source_type: Literal["COMPANY_PROFILE_FACT"]
    source_ref: str
    fact_version_no: int


class AutofillUnresolvedField(APIModel):
    fact_key: str
    target_locator: str
    reason: Literal["MISSING", "EXPIRED"]


class ResolveCompanyAutofillResponse(APIModel):
    customer_id: str
    resolved: list[AutofillResolvedField] = Field(default_factory=list)
    unresolved: list[AutofillUnresolvedField] = Field(default_factory=list)
    inference_performed: bool = False
    private_document_import_performed: bool = False
