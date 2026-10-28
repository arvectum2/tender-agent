import json
from pathlib import Path

import pytest

from src.modules.market_intelligence.pq_project_links import resolve


def _fixture(tmp_path: Path):
    nums = ["32615969197", "32616103025", "32616474682"]
    cases = [
        {"canonical_id": f"223fz:{n}:lot1", "procedure_id": n,
         "scope": "design" if n != "32616474682" else "supply_components",
         "family": "ukrm"} for n in nums
    ] + [{"canonical_id": "223fz:32616474682:lot2",
          "procedure_id": "32616474682", "scope": "supply_components",
          "family": "capacitor_components"}]
    leads = tmp_path / "leads.json"
    leads.write_text(json.dumps({"records": cases}))
    queue = tmp_path / "queue"
    queue.mkdir()
    legs = []
    for idx, number in enumerate(nums[:2]):
        queue_id = f"{number}-" + str(idx) * 24
        sha = str(idx + 1) * 64
        quote = "Лот № 26-004167 «ПИР на установку УКРМ 10кВ Пионерская"
        result = "несостоявшейся в связи с отсутствием коммерческих предложений"
        (queue / (queue_id + ".json")).write_text(json.dumps({
            "schema_version": "pq-review-queue/1", "id": queue_id,
            "state": "reviewed", "packet": {
                "registry_number": number,
                "documents": [{"sha256": sha, "method": "docx",
                               "text": quote + " " + result}],
            },
        }))
        legs.append({
            "canonical_id": f"223fz:{number}:lot1",
            "queue_id": queue_id, "sha256": sha, "quote": quote,
            "outcome_quote": result,
        })
    links = tmp_path / "links.json"
    links.write_text(json.dumps({
        "schema_version": "pq-reviewed-project-links/1",
        "links": [{
            "link_id": "test-reissued", "relation": "same_lot_reissued_no_bids",
            "same_lot_code": "26-004167", "left": legs[0],
            "right": legs[1], "signed_contract_verified": False,
        }],
    }))
    return leads, links, queue


def test_exact_original_same_lot_reissue_merges_need_not_tender(tmp_path: Path):
    leads, links, queue = _fixture(tmp_path)
    result = resolve(leads=leads, links=links, queue=queue)
    assert result["candidate_rows"] == 4
    assert result["candidate_need_groups_after_only_proven_reissue_merges"] == 3
    assert result["source_verified_relation_edges"] == 1
    assert result["same_lot_reissue_links"] == 1
    assert result["national_unique_project_count"] is None
    duo = next(x for x in result["project_need_groups"] if len(x["member_candidate_ids"]) == 2)
    assert duo["group_relation"] == "one_need_two_unsuccessful_notices"
    assert result["same_notice_distinct_lot_groups"] == [{
        "registry_number": "32616474682", "candidate_lot_ids": [
            "223fz:32616474682:lot1", "223fz:32616474682:lot2"],
        "collapse_lots": False,
    }]


def test_forged_quote_and_unsigned_claim_refused(tmp_path: Path):
    leads, links, queue = _fixture(tmp_path)
    data = json.loads(links.read_text())
    data["links"][0]["left"]["quote"] = "Несуществующее описание другой подстанции"
    links.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Source SHA or quoted"):
        resolve(leads=leads, links=links, queue=queue)
    data["links"][0]["left"]["quote"] = data["links"][0]["right"]["quote"]
    data["links"][0]["signed_contract_verified"] = True
    links.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="cannot assert signed"):
        resolve(leads=leads, links=links, queue=queue)


def test_shared_program_link_does_not_merge_contracts(tmp_path: Path):
    leads, links, queue = _fixture(tmp_path)
    data = json.loads(links.read_text())
    edge = data["links"][0]
    edge["relation"] = "shared_parent_program_distinct_contract_scope"
    edge["shared_title_anchor"] = "ПИР на установку УКРМ"
    edge.pop("same_lot_code")
    links.write_text(json.dumps(data))
    result = resolve(leads=leads, links=links, queue=queue)
    assert result["candidate_need_groups_after_only_proven_reissue_merges"] == 4
    assert result["shared_parent_program_edges_no_contract_merge"] == 1
    assert result["relation_edges"][0]["association_only_not_contract_identity"] is True
