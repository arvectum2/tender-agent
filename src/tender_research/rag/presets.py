from __future__ import annotations

from src.shared.data_platform import SearchProfile, build_collection_id

TENDER_NAMESPACE = "tender"
LEGACY_TENDER_NAMESPACE = "tender-agent"

TENDER_SEARCH_PROFILE: SearchProfile = {
    "mode": "hybrid",
    "lexical_weight": 1.0,
    "vector_weight": 4.0,
    "query_variant_weight": 0.5,
    "collapse_by_canonical_uri": False,
}


def tender_collection_id(tender_id: str, revision: str) -> str:
    return build_collection_id(TENDER_NAMESPACE, str(tender_id), revision)


def legacy_tender_collection_id(tender_id: str, revision: str) -> str:
    return build_collection_id(LEGACY_TENDER_NAMESPACE, str(tender_id), revision)


def tender_processing_collection_id(scope: str) -> str:
    return build_collection_id(TENDER_NAMESPACE, str(scope), "processing")


def tender_recovery_processing_collection_id() -> str:
    return build_collection_id(TENDER_NAMESPACE, "recovery", "processing")
