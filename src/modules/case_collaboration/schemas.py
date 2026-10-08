from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from src.shared.types.common import APIModel

EntryType = Literal["COMMENT", "DECISION"]


class EvidenceLinkIn(APIModel):
    source_type: str = Field(min_length=1, max_length=64)
    source_ref: str = Field(min_length=1)


class AppendCaseJournalEntryRequest(APIModel):
    entry_type: EntryType
    actor_type: str = Field(min_length=1, max_length=32)
    actor_ref: str = Field(min_length=1, max_length=256)
    body: str = Field(min_length=1)
    decision_code: str | None = Field(default=None, max_length=128)
    supersedes_entry_id: str | None = None
    mention_refs: list[str] = Field(default_factory=list)
    evidence_links: list[EvidenceLinkIn] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_decision(self):
        if self.entry_type == "DECISION" and not self.decision_code:
            raise ValueError("decision_code is required for DECISION entries")
        if self.entry_type == "COMMENT" and self.decision_code:
            raise ValueError("decision_code is only valid for DECISION entries")
        return self


class CaseJournalMentionResponse(APIModel):
    mention_ref: str
    notification_state: str
    created_at: datetime


class CaseJournalEvidenceResponse(APIModel):
    source_type: str
    source_ref: str
    created_at: datetime


class CaseJournalEntryResponse(APIModel):
    id: str
    customer_id: str
    project_id: str
    procurement_case_id: str
    entry_type: EntryType
    actor_type: str
    actor_ref: str
    body: str
    decision_code: str | None
    supersedes_entry_id: str | None
    created_at: datetime
    mentions: list[CaseJournalMentionResponse] = Field(default_factory=list)
    evidence_links: list[CaseJournalEvidenceResponse] = Field(default_factory=list)
