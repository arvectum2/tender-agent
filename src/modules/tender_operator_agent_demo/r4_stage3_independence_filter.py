"""Deterministic source SHA conflict exclusion after official EIS acquisition.

Never replace rejected candidates by later visible items. No legal source
content, model outputs, training labels, bid decisions or expert signatures.
"""
from __future__ import annotations

import re

_SHA = re.compile(r"[0-9a-f]{64}\Z")


def filter_attested_candidates_by_independence(
    *, immutable_discovery: dict,
    official_cases: list[dict],
    previously_protected_numbers: set[str],
    previously_protected_original_sha256: set[str],
    previously_protected_zip_sha256: set[str],
    previously_protected_xml_sha256: set[str],
    expected_candidate_count: int = 8,
) -> dict:
    selected = immutable_discovery.get("selected_discovery_only")
    if not 1 <= expected_candidate_count <= 40:
        raise ValueError("Invalid preregistered candidate quota")
    if (
        not isinstance(selected, list)
        or len(selected) != expected_candidate_count
        or len(official_cases) != len(selected)
    ):
        raise ValueError("All preregistered source-ranked entries must be accounted for")
    if [x["registry_number"] for x in selected] != [x["registry_number"] for x in official_cases]:
        raise ValueError("Order or membership altered after prospective source preregistration")
    accepted: list[dict] = []
    rejected: list[dict] = []
    seen_binary = set(previously_protected_original_sha256)
    seen_xml = set(previously_protected_xml_sha256)
    seen_zip = set(previously_protected_zip_sha256)
    seen_notice = set(previously_protected_numbers)
    for source, case in zip(selected, official_cases):
        no = case["registry_number"]
        rank = (source["source_rank"], source["source_card_rank"])
        if no in seen_notice:
            raise ValueError("Candidate number was already evaluated or repeated")
        seen_notice.add(no)
        if case.get("status") != "ALL_OFFICIAL_EIS_ORIGINALS_VERIFIED":
            rejected.append({"registry_number": no, "source_rank":rank[0],
                "source_card_rank":rank[1], "reason":"UNATTESTED_OFFICIAL_EIS_ORIGINALS"})
            continue
        docs = case.get("documents")
        if not isinstance(docs, list) or not docs:
            raise ValueError("Official verified candidate has no source documents")
        shas = [item["sha256"] for item in docs]
        if any(not isinstance(s, str) or not _SHA.fullmatch(s) for s in shas):
            raise ValueError("Candidate source digest is not SHA-256")
        zip_sha = case.get("official_zip_sha256")
        xml_sha = case.get("official_xml_sha256")
        if not all(isinstance(x, str) and _SHA.fullmatch(x) for x in (zip_sha,xml_sha)):
            raise ValueError("Original EIS ZIP/XML SHA missing")
        if len(set(shas)) != len(shas) or any(s in seen_binary for s in shas):
            rejected.append({"registry_number":no,"source_rank":rank[0],
                "source_card_rank":rank[1],"reason":"REPEATED_ORIGINAL_BINARY_WITH_PREVIOUS_OR_EARLIER_CASE"})
            continue
        if zip_sha in seen_zip or xml_sha in seen_xml:
            rejected.append({"registry_number":no,"source_rank":rank[0],
                "source_card_rank":rank[1],"reason":"REUSED_OFFICIAL_ZIP_OR_XML_WITH_PREVIOUS_OR_EARLIER_CASE"})
            continue
        seen_binary.update(shas)
        seen_xml.add(xml_sha)
        seen_zip.add(zip_sha)
        accepted.append(case)
    return {
        "source_selection_intent_sha256": immutable_discovery["source_intent_sha256"],
        "source_candidate_count": len(selected),
        "accepted_source_only_cases": accepted,
        "excluded_cases_in_source_order": rejected,
        "replacements_added": 0,
        "human_gold": 0,
        "sut_inference_permitted": False,
        "bid_ready": False,
    }
