"""Offline reviewer portability checks use only artificial original binaries."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from src.modules.benchmark_pipeline.contract import (
    source_bundle_sha256,
    write_artifact,
)
from src.modules.benchmark_pipeline.workflow import prepare_evaluator_bundle
from src.modules.tender_operator_agent_demo.r4_blind_reviewer_assignment import (
    build_source_only_assignment,
    human_label_input_template,
)
from src.modules.tender_operator_agent_demo.r4_offline_expert_package import (
    write_source_only_reviewer_package,
)


def synthetic_reviewer_source(tmp_path: Path):
    root = tmp_path / "raw"
    source = root / "9000000000000000042" / "originals" / "official-primary.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"Independent primary source binary for synthetic case.")
    docs = [{
        "path": str(source.relative_to(root)),
        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "source_url": "https://zakupki.gov.ru/api/anonymous-official-source",
    }]
    manifest = {
        "schema_version": "1.1.0",
        "case_id": "R4-BLIND-9000000000000000042",
        "procurement": {"notice_number": "9000000000000000042"},
        "source_urls": ["https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=9000000000000000042"],
        "acquired_at": "2026-10-15T00:00:00+00:00",
        "documents": docs,
        "source_scope": "Independently sourced synthetic evidence, not a legal analysis",
        "source_bundle_sha256": source_bundle_sha256(docs),
        "source_conflict": False,
        "provenance_sufficient": True,
    }
    bundle = prepare_evaluator_bundle(manifest, prepared_at="2026-10-15T01:00:00+00:00")
    pack = tmp_path / "review-packs" / bundle["case_id"]
    write_artifact(pack / "case_manifest.json", manifest, "case_manifest")
    write_artifact(pack / "evaluator_bundle.json", bundle, "evaluator_bundle")
    (pack / "independent-reviewer-worksheet.md").write_text(
        build_source_only_assignment(bundle), encoding="utf8",
    )
    (pack / "human-labels-BLANK-template.json").write_text(
        json.dumps(human_label_input_template(bundle), ensure_ascii=False), encoding="utf8",
    )
    return root, pack, docs[0]


def test_offline_package_contains_exact_primary_binaries_and_only_blank_answers(tmp_path):
    source_root, reviewer_pack, source = synthetic_reviewer_source(tmp_path)
    output = tmp_path / "offline" / "one.zip"
    receipt = write_source_only_reviewer_package(
        reviewer_bundle_dir=reviewer_pack,
        original_source_root=source_root,
        private_output=output,
    )
    assert receipt["original_count"] == 1
    assert receipt["signed_expert_gold_count"] == 0
    assert receipt["sut_run_authorized"] is False
    with ZipFile(output) as archive:
        names = set(archive.namelist())
        assert names == {
            "review/case_manifest.json",
            "review/evaluator_bundle.json",
            "review/independent-reviewer-worksheet.md",
            "review/human-labels-BLANK-template.json",
            "handoff-integrity.json",
            "sources/" + source["path"],
        }
        assert archive.read("sources/" + source["path"]) == (
            source_root / source["path"]
        ).read_bytes()
        proof = json.loads(archive.read("handoff-integrity.json"))
        assert proof["original_count"] == 1
        assert proof["purpose"] == "INDEPENDENT_HUMAN_BLIND_REVIEW_ONLY_NO_MODEL_GOLD"
        assert proof["entries_sha256"]["sources/" + source["path"]] == source["sha256"]
        template = json.loads(archive.read("review/human-labels-BLANK-template.json"))
        assert template["blind_discovery_label"]["label"] is None
        assert template["blind_document_truth"]["facts"] == []
        assert template["sut_inference_allowed"] is False
    with pytest.raises(ValueError, match="overwrite"):
        write_source_only_reviewer_package(
            reviewer_bundle_dir=reviewer_pack,
            original_source_root=source_root,
            private_output=output,
        )


def test_source_tampering_is_rejected_without_creating_handoff(tmp_path):
    source_root, reviewer_pack, doc = synthetic_reviewer_source(tmp_path)
    (source_root / doc["path"]).write_bytes(b"tampered source bytes")
    target = tmp_path / "offline" / "one.zip"
    with pytest.raises(ValueError, match="hash"):
        write_source_only_reviewer_package(
            reviewer_bundle_dir=reviewer_pack, original_source_root=source_root,
            private_output=target,
        )
    assert not target.exists()


@pytest.mark.parametrize("mutate", [
    lambda d: d["blind_discovery_label"].update(label="RELEVANT"),
    lambda d: d["blind_document_truth"].update(facts=[{"fake": "already rated"}]),
    lambda d: d.update(draft_status="EXPERT_SUBMITTED"),
    lambda d: d["external_human_reviewer_attestation"].update(ed25519_signature_b64="forged"),
])
def test_prefilled_gold_or_signature_cannot_enter_source_only_archive(tmp_path, mutate):
    source_root, reviewer_pack, _ = synthetic_reviewer_source(tmp_path)
    f = reviewer_pack / "human-labels-BLANK-template.json"
    template = json.loads(f.read_text())
    mutate(template)
    f.write_text(json.dumps(template, ensure_ascii=False))
    target = tmp_path / "offline" / "one.zip"
    with pytest.raises(ValueError, match="blank|unsigned"):
        write_source_only_reviewer_package(
            reviewer_bundle_dir=reviewer_pack, original_source_root=source_root,
            private_output=target,
        )
    assert not target.exists()


def test_model_answer_contamination_in_bundle_is_rejected(tmp_path):
    source_root, reviewer_pack, _ = synthetic_reviewer_source(tmp_path)
    path = reviewer_pack / "evaluator_bundle.json"
    model = json.loads(path.read_text())
    model["analysis"] = {"supplier": "model prefilled"}
    path.write_text(json.dumps(model))
    with pytest.raises(ValueError):
        write_source_only_reviewer_package(
            reviewer_bundle_dir=reviewer_pack, original_source_root=source_root,
            private_output=tmp_path / "offline" / "one.zip",
        )


def test_symlink_metadata_and_original_are_rejected(tmp_path):
    source_root, reviewer_pack, doc = synthetic_reviewer_source(tmp_path)
    original = source_root / doc["path"]
    data = original.read_bytes()
    original.unlink()
    elsewhere = tmp_path / "not-in-original-sources.bin"
    elsewhere.write_bytes(data)
    original.symlink_to(elsewhere)
    with pytest.raises(ValueError, match="symlink|escapes source root"):
        write_source_only_reviewer_package(
            reviewer_bundle_dir=reviewer_pack, original_source_root=source_root,
            private_output=tmp_path / "offline" / "one.zip",
        )
