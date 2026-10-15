"""Only synthetic independent reviewer keys/labels; no real blind SUT exposure."""
from __future__ import annotations

import base64
import copy
import hashlib
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from scripts.acceptance.freeze_r4_independent_human_cohort import (
    preflight_complete_human_cohort,
    validate_full_cohort_enrollment,
    write_complete_human_cohort,
)
from src.modules.benchmark_pipeline.contract import canonical_sha256, write_artifact
from src.modules.benchmark_pipeline.workflow import prepare_evaluator_bundle
from src.modules.tender_operator_agent_demo.r4_external_gold_intake import (
    attestation_payload,
)
from tests.test_freeze_r4_independent_human_gold import (
    signed_synthetic_fixture,
)
from tests.test_r4_external_gold_intake import P0, P2, P3


def prepare_two_synthetic_independent_signers(tmp_path: Path) -> dict:
    p1, p2 = tmp_path / "synthetic-1", tmp_path / "synthetic-2"
    p1.mkdir(parents=True)
    p2.mkdir(parents=True)
    first = signed_synthetic_fixture(p1)
    second = signed_synthetic_fixture(p2)

    # Both fixtures use intentionally synthetic 999... notice numbers; the
    # real R4 case-id convention is enforced even for these artificial tests.
    import json

    roster = {}
    for index, fixture in enumerate((first, second)):
        notice = f"999999999999999999{9 - index}"
        case_id = "R4-BLIND-" + notice
        reviewer_id = f"outside-synthetic-{index + 1}"
        path = fixture["bundle_dir"]
        manifest = json.loads((path / "case_manifest.json").read_text())
        manifest["case_id"] = case_id
        manifest["procurement"]["notice_number"] = notice
        bundle = prepare_evaluator_bundle(manifest, prepared_at=P0)
        write_artifact(path / "case_manifest.json", manifest, "case_manifest")
        write_artifact(path / "evaluator_bundle.json", bundle, "evaluator_bundle")
        sub = fixture["submission"]
        sub["case_id"] = case_id
        sub["source_bundle_sha256"] = bundle["source_bundle_sha256"]
        sub["blind_discovery_label"]["case_id"] = case_id
        sub["blind_document_truth"]["case_id"] = case_id
        sub["blind_discovery_label"]["evaluator"] = reviewer_id
        sub["blind_document_truth"]["evaluator"] = reviewer_id
        key = Ed25519PrivateKey.generate()
        sub["external_human_reviewer_attestation"]["reviewer_id"] = reviewer_id
        sub["external_human_reviewer_attestation"]["ed25519_signature_b64"] = base64.b64encode(
            key.sign(attestation_payload(
                bundle,
                sub["blind_discovery_label"],
                sub["blind_document_truth"],
                reviewer_id=reviewer_id,
                attested_at=P2,
            ))
        ).decode()
        roster[reviewer_id] = {
            "role": "QUALIFIED_INDEPENDENT_LEGAL_EXPERT",
            "owner_identity_verified": True,
            "ed25519_public_key_b64": base64.b64encode(
                key.public_key().public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw,
                )
            ).decode(),
        }
        source_lock = fixture["immutable_holdout_lock"]
        source_lock["cases"][0]["registry_number"] = notice
        source_lock["cases"][0]["official_zip_sha256"] = hashlib.sha256(
            f"synthetic zip {index}".encode()
        ).hexdigest()
        source_lock["cases"][0]["official_xml_sha256"] = hashlib.sha256(
            f"synthetic xml {index}".encode()
        ).hexdigest()
        source_lock["case_evidence_sha256"] = canonical_sha256(source_lock["cases"])
        source_lock["immutable_lock_sha256"] = canonical_sha256({
            k: v for k, v in source_lock.items() if k != "immutable_lock_sha256"
        })
    first["trusted_reviewer_roster"] = roster
    second["trusted_reviewer_roster"] = roster
    locks = [first["immutable_holdout_lock"], second["immutable_holdout_lock"]]
    cases = [{
        "case_id": a["submission"]["case_id"],
        "lock_index": i,
        "evaluator_bundle_dir": str(a["bundle_dir"]),
        "original_source_root": str(a["original_source_root"]),
        "submission": a["submission"],
    } for i, a in enumerate((first, second))]
    summary = {
        "blind_lock_sha256": [l["immutable_lock_sha256"] for l in locks],
        "blind_cohort_sizes": [1, 1],
        "source_blind_cases_total": 2,
    }
    return {
        "immutable_locks": locks,
        "published_summary": summary,
        "case_inputs": cases,
        "trusted_reviewer_roster": first["trusted_reviewer_roster"],
        "frozen_at": P3,
    }


def test_complete_two_synthetic_reviewers_freeze_atomically(tmp_path):
    kwargs = prepare_two_synthetic_independent_signers(tmp_path)
    checked = preflight_complete_human_cohort(**kwargs)
    assert checked["cohort_receipt"]["source_blind_cases_total"] == 2
    assert checked["cohort_receipt"]["sut_run_authorized_by_this_tool"] is False
    out = tmp_path / "gold-complete-only"
    result = write_complete_human_cohort(validated=checked, private_output=out)
    assert result["aggregate_label_set_sha256"]
    for row in result["signed_case_label_receipts"]:
        directory = out / row["case_id"]
        assert (directory / "frozen_label.json").is_file()
        assert (directory / "blind_discovery_label.json").is_file()
        assert (directory / "blind_document_truth.json").is_file()
    assert (out / "full-cohort-freeze-receipt.json").is_file()
    with pytest.raises(ValueError, match="overwrite"):
        write_complete_human_cohort(validated=checked, private_output=out)


def test_one_missing_external_submission_blocks_whole_cohort(tmp_path):
    kwargs = prepare_two_synthetic_independent_signers(tmp_path)
    kwargs["case_inputs"] = kwargs["case_inputs"][:1]
    with pytest.raises(ValueError, match="All signed cases"):
        preflight_complete_human_cohort(**kwargs)
    assert not (tmp_path / "gold-complete-only").exists()


def test_duplicate_or_wrong_blind_case_prevents_any_freeze(tmp_path):
    kwargs = prepare_two_synthetic_independent_signers(tmp_path)
    kwargs["case_inputs"][1]["case_id"] = kwargs["case_inputs"][0]["case_id"]
    with pytest.raises(ValueError, match="duplicate"):
        preflight_complete_human_cohort(**kwargs)


@pytest.mark.parametrize("mutation", [
    lambda kwargs: kwargs["case_inputs"][1]["submission"].update(draft_status="TEMPLATE_ONLY_NOT_HUMAN_GOLD"),
    lambda kwargs: kwargs["case_inputs"][1]["submission"].update(sut_inference_allowed=True),
    lambda kwargs: kwargs["case_inputs"][1]["submission"]["external_human_reviewer_attestation"].update(
        ed25519_signature_b64=base64.b64encode(b"INVALID" * 10 + b"ABCD").decode()
    ),
    lambda kwargs: kwargs["case_inputs"][1]["submission"]["blind_document_truth"]["facts"][0].update(
        value="Tampered unsigned legal outcome"
    ),
    lambda kwargs: kwargs["trusted_reviewer_roster"].pop("outside-synthetic-2"),
])
def test_second_expert_failure_blocks_first_case_too(tmp_path, mutation):
    kwargs = prepare_two_synthetic_independent_signers(tmp_path)
    mutation(kwargs)
    with pytest.raises(ValueError):
        preflight_complete_human_cohort(**kwargs)
    assert not list(tmp_path.rglob("frozen_label.json"))


def test_published_source_hash_or_group_assignment_cannot_be_replaced(tmp_path):
    kwargs = prepare_two_synthetic_independent_signers(tmp_path)
    kwargs["published_summary"]["blind_lock_sha256"][0] = "0" * 64
    with pytest.raises(ValueError, match="published external audit"):
        preflight_complete_human_cohort(**kwargs)
    kwargs = prepare_two_synthetic_independent_signers(tmp_path / "different")
    kwargs["case_inputs"][1]["lock_index"] = 0
    with pytest.raises(ValueError, match="wrong immutable"):
        preflight_complete_human_cohort(**kwargs)


def test_case_set_and_published_quota_are_not_expandable(tmp_path):
    kwargs = prepare_two_synthetic_independent_signers(tmp_path)
    modified = copy.deepcopy(kwargs["published_summary"])
    modified["source_blind_cases_total"] = 3
    with pytest.raises(ValueError, match="unique source-locked"):
        validate_full_cohort_enrollment(
            immutable_locks=kwargs["immutable_locks"],
            published_summary=modified,
            case_inputs=kwargs["case_inputs"],
        )


def test_tamper_between_preflight_and_write_does_not_create_partial_gold(tmp_path):
    kwargs = prepare_two_synthetic_independent_signers(tmp_path)
    checked = preflight_complete_human_cohort(**kwargs)
    checked["case_artifacts"][1]["truth"]["facts"][0]["value"] = "Altered after signed verification"
    destination = tmp_path / "no-mutated-gold"
    with pytest.raises(ValueError, match="changed after trusted preflight"):
        write_complete_human_cohort(validated=checked, private_output=destination)
    assert not destination.exists()


def test_tampering_canonical_receipt_cannot_claim_owner_go(tmp_path):
    kwargs = prepare_two_synthetic_independent_signers(tmp_path)
    checked = preflight_complete_human_cohort(**kwargs)
    checked["cohort_receipt"]["owner_legal_go_granted"] = True
    destination = tmp_path / "no-fake-owner-go"
    with pytest.raises(ValueError, match="cannot authorize"):
        write_complete_human_cohort(validated=checked, private_output=destination)
    assert not destination.exists()


def test_second_case_disk_write_failure_cleans_staging_without_partial_gold(
    tmp_path, monkeypatch,
):
    from scripts.acceptance import freeze_r4_independent_human_cohort as implementation

    kwargs = prepare_two_synthetic_independent_signers(tmp_path)
    checked = preflight_complete_human_cohort(**kwargs)
    writer = implementation.write_artifact
    calls = 0

    def controlled_failure(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 4:
            raise OSError("synthetic disk write interrupted at second case")
        return writer(*args, **kwargs)

    monkeypatch.setattr(implementation, "write_artifact", controlled_failure)
    destination = tmp_path / "no-partial-freeze"
    with pytest.raises(OSError, match="synthetic disk write interrupted"):
        write_complete_human_cohort(validated=checked, private_output=destination)
    assert calls == 4
    assert not destination.exists()
    assert not list(tmp_path.glob(".full-independent-gold-*"))
    assert not list(tmp_path.rglob("frozen_label.json"))
