"""Storage-neutral document role classification for the frozen pipeline."""

from __future__ import annotations


def detect_document_role(name: str) -> str:
    """Classify a document name without depending on a delivery contour."""
    lowered = name.lower()
    if lowered.endswith(".xml") and any(
        token in lowered
        for token in (
            "epnotification",
            "epprotocol",
            "fcsplacementresult",
            "fcsproposalsresult",
            "clarification",
            "protocol",
            "протокол",
        )
    ):
        return "notice"
    if any(token in lowered for token in ("tkp", "ткп", "quote", "kp", "коммер", "proposal")):
        return "tkp"
    if any(token in lowered for token in ("contract", "договор", "agreement", "проект гк", "гк.doc", "контракт")):
        return "contract_draft"
    if any(token in lowered for token in ("spec", "специф", "technical", "тз", "техничес", "описание объекта")):
        return "technical_spec"
    if any(token in lowered for token in ("notice", "извещ", "tender", "закуп")):
        return "notice"
    return "supporting"
