from __future__ import annotations

from src.shared.data_platform import SearchProfile, build_collection_id

ARVECTUM_OS_NAMESPACE = "arvectum-os"

ARVECTUM_OS_KNOWLEDGE_SEARCH_PROFILE: SearchProfile = {
    "mode": "hybrid",
    "lexical_weight": 1.0,
    "vector_weight": 1.0,
    "query_variant_weight": 0.5,
    "collapse_by_canonical_uri": False,
}


def knowledge_collection_id(deal_id: str, revision: str) -> str:
    return build_collection_id(
        ARVECTUM_OS_NAMESPACE,
        "knowledge",
        str(deal_id),
        revision,
    )
