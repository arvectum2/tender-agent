from enum import StrEnum


class DealStatus(StrEnum):
    NEW = "NEW"
    CANDIDATE = "CANDIDATE"
    DOCS_ANALYSIS = "DOCS_ANALYSIS"
    SUPPLIER_SOURCING = "SUPPLIER_SOURCING"
    ECONOMICS_REVIEW = "ECONOMICS_REVIEW"
    WAITING_CEO_APPROVAL_TO_BID = "WAITING_CEO_APPROVAL_TO_BID"
    BID_PREPARATION = "BID_PREPARATION"
    PRE_SUBMISSION = "PRE_SUBMISSION"
    SUBMISSION = "SUBMISSION"
    POST_SUBMISSION = "POST_SUBMISSION"
    OUTCOME_CAPTURE = "OUTCOME_CAPTURE"
    DECLINED_TO_BID = "DECLINED_TO_BID"
    REJECTED_EARLY = "REJECTED_EARLY"


class TransitionType(StrEnum):
    AUTO = "AUTO"
    HUMAN = "HUMAN"
    BOTH = "BOTH"


class ChangedByType(StrEnum):
    SYSTEM = "SYSTEM"
    HUMAN = "HUMAN"
    MODULE = "MODULE"
    AGENT = "AGENT"


class ArtifactType(StrEnum):
    TENDER_DOC = "TENDER_DOC"
    SUPPLIER_QUOTE = "SUPPLIER_QUOTE"
    GENERATED_DOC = "GENERATED_DOC"
    RECEIPT_DOC = "RECEIPT_DOC"
    MEMO_ARTIFACT = "MEMO_ARTIFACT"
    ATTACHMENT = "ATTACHMENT"
    OTHER = "OTHER"


class EventSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DecisionByType(StrEnum):
    HUMAN = "HUMAN"
    SYSTEM = "SYSTEM"
    MODULE = "MODULE"


class ProcurementChannel(StrEnum):
    ETP = "ETP"
    PORTAL = "PORTAL"
    EMAIL = "EMAIL"
    MANUAL = "MANUAL"
    OTHER = "OTHER"


class DirectionType(StrEnum):
    SUPPLY = "SUPPLY"
    SERVICE = "SERVICE"
    WORK = "WORK"
    MIXED = "MIXED"
    OTHER = "OTHER"


class InitialSourceType(StrEnum):
    PORTAL_INGEST = "portal_ingest"
    EMAIL_INGEST = "email_ingest"
    MANUAL_ENTRY = "manual_entry"
    API_IMPORT = "api_import"
    OTHER = "other"

