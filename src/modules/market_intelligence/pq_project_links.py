"""Source-verified links between PQ tenders, lots and overarching projects.

Same underlying need (including a failed reissue) is merged ONLY with
specific quoted original protocols. Shared-program edges are NEVER merged
into a single purchasing lot or equipment price. Missing links remain unknown.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

RELATIONS = frozenset({
    "same_lot_reissued_no_bids",
    "shared_parent_program_distinct_contract_scope",
})


def _normalized(text: str) -> str:
    return " ".join(text.split()).casefold()


def _document_leg(leg: dict, *, queue: Path, corpus: dict[str, dict]) -> dict:
    identity = leg.get("canonical_id")
    if not isinstance(identity, str) or identity not in corpus:
        raise ValueError("Unknown canonical source candidate")
    number = str(corpus[identity].get("procedure_id") or "")
    packet_id = leg.get("queue_id")
    sha = leg.get("sha256")
    quote = leg.get("quote")
    if (not re.fullmatch(r"\d{11}", number)
            or not isinstance(packet_id, str)
            or not re.fullmatch(re.escape(number) + r"-[a-f0-9]{24}", packet_id)
            or not isinstance(sha, str)
            or not re.fullmatch(r"[0-9a-f]{64}", sha)
            or not isinstance(quote, str) or len(quote) < 18):
        raise ValueError("Unsafe project-link source identity")
    packet_file = queue / (packet_id + ".json")
    if packet_file.is_symlink():
        raise ValueError("Symlinked source review packet")
    d = json.loads(packet_file.read_text(encoding="utf-8"))
    if (d.get("schema_version") != "pq-review-queue/1"
            or d.get("state") != "reviewed"
            or d.get("packet", {}).get("registry_number") != number):
        raise ValueError("Project link requires reviewed original procurement packet")
    doc = next((x for x in d["packet"]["documents"]
                if x.get("sha256") == sha), None)
    if doc is None or _normalized(quote) not in _normalized(doc.get("text") or ""):
        raise ValueError("Source SHA or quoted project fact missing")
    outcome = leg.get("outcome_quote")
    if outcome is not None and (
            not isinstance(outcome, str)
            or _normalized(outcome) not in _normalized(doc.get("text") or "")):
        raise ValueError("Original commission outcome quote missing")
    return {
        "canonical_id": identity, "procedure_id": number,
        "source_sha256": sha, "source_quote": quote,
        "review_queue_id": packet_id,
        "original_commission_outcome_quote_verified": outcome is not None,
    }


def resolve(*, leads: Path, links: Path, queue: Path) -> dict:
    candidates = json.loads(leads.read_text(encoding="utf-8"))["records"]
    if len(candidates) > 20000:
        raise ValueError("Unbounded project candidate corpus")
    cases = {x.get("canonical_id"): x for x in candidates}
    if len(cases) != len(candidates) or None in cases:
        raise ValueError("Invalid duplicated candidate identities")
    fixtures = json.loads(links.read_text(encoding="utf-8"))
    if (fixtures.get("schema_version") != "pq-reviewed-project-links/1"
            or not isinstance(fixtures.get("links"), list)
            or len(fixtures["links"]) > 200):
        raise ValueError("Invalid bounded project linkage manifest")
    parent = {identity: identity for identity in cases}

    def root(item: str) -> str:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    verified_edges = []
    seen_edges = set()
    shared_program = []
    merge_edges = []
    for link in fixtures["links"]:
        relation = link.get("relation")
        if relation not in RELATIONS or link.get("signed_contract_verified") is not False:
            raise ValueError("Project links cannot assert signed contract")
        left = _document_leg(link["left"], queue=queue, corpus=cases)
        right = _document_leg(link["right"], queue=queue, corpus=cases)
        if left["canonical_id"] == right["canonical_id"]:
            raise ValueError("Project link cannot refer to same candidate twice")
        pair = tuple(sorted([left["canonical_id"], right["canonical_id"]]))
        key = (pair, relation)
        if key in seen_edges:
            raise ValueError("Duplicate project link")
        seen_edges.add(key)
        if relation == "same_lot_reissued_no_bids":
            lot = link.get("same_lot_code")
            if (not isinstance(lot, str) or not re.fullmatch(r"\d{2}-\d{6}", lot)
                    or not all(lot in leg["source_quote"] for leg in (left, right))
                    or not left["original_commission_outcome_quote_verified"]
                    or not right["original_commission_outcome_quote_verified"]):
                raise ValueError("Reissue merge requires exact common lot and two failed originals")
            if cases[left["canonical_id"]].get("scope") != cases[right["canonical_id"]].get("scope"):
                raise ValueError("Reissue cannot merge unlike scope categories")
            a, b = root(left["canonical_id"]), root(right["canonical_id"])
            if a != b:
                parent[max(a, b)] = min(a, b)
            merge_edges.append(link["link_id"])
        else:
            anchor = link.get("shared_title_anchor")
            if (not isinstance(anchor, str) or len(anchor) < 18
                    or not all(_normalized(anchor) in _normalized(
                        leg["source_quote"]) for leg in (left, right))):
                raise ValueError("Cross-contract program edge requires exact shared title")
            shared_program.append(link["link_id"])
        verified_edges.append({
            "link_id": link["link_id"], "relation": relation,
            "left": left, "right": right,
            "same_lot_code": link.get("same_lot_code"),
            "association_only_not_contract_identity": relation != "same_lot_reissued_no_bids",
            "signed_contract_verified": False,
            "pq_equipment_price_attributed": False,
        })
    groups = defaultdict(list)
    notices = defaultdict(list)
    for identity in cases:
        groups[root(identity)].append(identity)
        number = str(cases[identity].get("procedure_id") or "")
        if re.fullmatch(r"\d{11}", number):
            notices[number].append(identity)
    duplicate_notices = [
        {"registry_number": number, "candidate_lot_ids": sorted(identities),
         "collapse_lots": False}
        for number, identities in sorted(notices.items()) if len(identities) > 1
    ]
    return {
        "schema_version": "pq-reviewed-project-links-audit/1",
        "completeness": "known_reviewed_links_only_not_final_project_census",
        "candidate_rows": len(cases),
        "candidate_need_groups_after_only_proven_reissue_merges": len(groups),
        "source_verified_relation_edges": len(verified_edges),
        "same_lot_reissue_links": len(merge_edges),
        "shared_parent_program_edges_no_contract_merge": len(shared_program),
        "same_notice_distinct_lot_groups": duplicate_notices,
        "project_need_groups": [
            {"representative_candidate_id": representative,
             "member_candidate_ids": sorted(members),
             "group_relation": "one_need_two_unsuccessful_notices"
             if len(members) > 1 else "not_proven_duplicate_to_other_candidates",
             "signed_contract_verified": False,
             "equipment_value_rub": None}
            for representative, members in sorted(groups.items())
        ],
        "relation_edges": verified_edges,
        "national_unique_project_count": None,
        "verified_equipment_market_value_rub": None,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--leads", type=Path, required=True)
    p.add_argument("--links", type=Path, required=True)
    p.add_argument("--queue", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = resolve(leads=args.leads, links=args.links, queue=args.queue)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items()
                      if key not in ("project_need_groups", "relation_edges",
                                     "same_notice_distinct_lot_groups")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
