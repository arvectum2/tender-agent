from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from src.shared.types.common import APIModel

DocumentRole = Literal[
    "FORM_2",
    "COMMERCIAL_PROPOSAL",
    "DECLARATION",
    "SPECIFICATION",
    "INVENTORY",
]


class ApplicationDraftFieldMapping(APIModel):
    target_locator: str = Field(min_length=1)
    value: str | int | float | bool | None = None
    source_type: str = Field(min_length=1, max_length=64)
    source_ref: str = Field(min_length=1)


class GenerateApplicationDraftRequest(APIModel):
    deal_id: str = Field(min_length=1)
    template_artifact_ref: str = Field(min_length=1)
    expected_template_version: int = Field(ge=1)
    document_role: DocumentRole
    fields: list[ApplicationDraftFieldMapping] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_targets(self):
        locators = [item.target_locator for item in self.fields]
        if len(locators) != len(set(locators)):
            raise ValueError("target_locator values must be unique")
        return self


class ApplicationDraftFieldProvenanceResponse(APIModel):
    source_type: str
    source_ref: str
    target_locator: str
    original_value: object | None
    generated_value: object | None


class ApplicationDraftGenerationResponse(APIModel):
    generation_id: str
    deal_id: str
    template_artifact_ref: str
    output_artifact_ref: str
    output_file_name: str
    output_storage_uri: str
    document_role: DocumentRole
    output_format: Literal["docx", "xlsx"]
    lineage_key: str
    template_version_no: int
    generation_version_no: int
    template_sha256: str
    output_sha256: str
    review_state: Literal["DRAFT_REVIEW_ONLY"]
    signature_performed: bool
    submission_performed: bool
    external_delivery_performed: bool
    created_at: datetime
    field_provenance: list[ApplicationDraftFieldProvenanceResponse]
