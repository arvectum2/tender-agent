"""The existing twenty-case R4 source matrix must be complete or fail closed."""
from __future__ import annotations

import csv
import io
from pathlib import Path

import pytest

from src.modules.tender_operator_agent_demo.r4_case_source_coverage import (
    build_r4_20_case_source_coverage,
)

_ACCEPTANCE = Path(__file__).resolve().parents[1] / "docs" / "acceptance"


def originals() -> dict[str, str]:
    return {
        "protocol_markdown": (_ACCEPTANCE / "TDP_R4_R5_HUMAN_GOLD_PROTOCOL_2026-10-12.md").read_text(),
        "independent_cases_csv": (_ACCEPTANCE / "TDP_R5_INDEPENDENT_20_CASES_2026-10-12.csv").read_text(),
        "independent_files_csv": (_ACCEPTANCE / "TDP_R5_INDEPENDENT_168_FILES_2026-10-12.csv").read_text(),
        "persisted_facts_csv": (_ACCEPTANCE / "TDP_R5_INDEPENDENT_PERSISTED_FACTS_20_2026-10-12.csv").read_text(),
        "human_queue_csv": (_ACCEPTANCE / "TDP_R5_20_CASE_HUMAN_REVIEW_QUEUE_2026-10-11.csv").read_text(),
    }


def rewrite_csv(raw: str, field: str, needle: str, value: str, *, registry: str = "0372200172326000015") -> str:
    reader = csv.DictReader(io.StringIO(raw))
    rows = list(reader)
    headers = reader.fieldnames
    assert headers
    targets = [r for r in rows if r["reg_number"] == registry]
    assert len(targets) == 1
    assert targets[0][field] == needle
    targets[0][field] = value
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=headers)
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def test_real_independent_20_case_originals_are_conservative_and_complete():
    packet = build_r4_20_case_source_coverage(**originals())
    assert packet["summary"] == {
        "total_r4_cases": 20,
        "archived_official_zip": 17,
        "official_soap_no_data": 3,
        "stale_archived_notice_receipts": 3,
        "historic_file_sha_matched": 168,
        "official_original_xml_matched": 96,
        "non_xml_attached_binary_count": 72,
        "independent_binary_retransfers_matched_in_this_audit": 0,
        "saved_historical_reports": 9,
        "persisted_deadline_archive_mismatches": 2,
        "persisted_price_archive_mismatches": 0,
        "human_gold_reviews_completed": 0,
        "live_eis_accepted": 0,
        "arv001_releases": 0,
    }
    assert len(packet["source_matrix_sha256"]) == 64
    assert not packet["human_gold_attested"]
    assert not packet["bid_ready"]
    rows = {x["reg_number"]: x for x in packet["cases"]}
    for registry in ("0158300034526000388", "0348100024426000039", "0360600005326000018"):
        assert rows[registry]["source_receipt_status"] == "STALE_NOTICE_RECEIPT"
        assert "RECEIPT_OUTDATED_VS_LATEST_ARCHIVED_NOTICE" in rows[registry]["blockers"]
    for registry in ("0148300050426000047", "0348100024426000052", "0318200087026000163"):
        assert rows[registry]["official_archive_status"] == "NO_DATA"
        assert rows[registry]["source_case_file_count"] == 0
        assert rows[registry]["expert_gold"] is False
        assert "OFFICIAL_ARCHIVE_NO_DATA_NOT_NONEXISTENCE" in rows[registry]["blockers"]
    for registry in ("0158300034526000388", "0348100024426000039"):
        assert rows[registry]["persisted_deadline_check"] == "MISMATCH"
        assert "PERSISTED_REPORT_DEADLINE_CONTRADICTS_ARCHIVE" in rows[registry]["blockers"]
    bread = rows["0372200172326000015"]
    assert bread["archived_deadline"] == "2026-10-16T10:00:00+03:00"
    assert bread["archived_max_price_rub"] == "1000000.00"
    assert bread["source_case_file_count"] == 6
    assert bread["independent_original_binary_transfers_verified"] == 0
    assert bread["bid_ready"] is False
    assert all(r["human_signature"] is None and r["human_reviewer"] is None for r in rows.values())
    assert packet == build_r4_20_case_source_coverage(**originals())


def test_missing_or_duplicate_case_fails_instead_of_degrading_silently():
    data = originals()
    data["independent_cases_csv"] = "\n".join(data["independent_cases_csv"].splitlines()[:-1]) + "\n"
    with pytest.raises(ValueError, match="case IDs"):
        build_r4_20_case_source_coverage(**data)
    data = originals()
    lines = data["independent_cases_csv"].splitlines()
    data["independent_cases_csv"] = "\n".join([*lines, lines[1]]) + "\n"
    with pytest.raises(ValueError, match="duplicate"):
        build_r4_20_case_source_coverage(**data)


def test_tampered_historic_sha_fails_hard():
    data = originals()
    data["independent_files_csv"] = data["independent_files_csv"].replace(
        "ed5c742b554913c65d9001b658aa23619df418b2d19e6f6d6754a1bc70141bba",
        "NOT_REAL_SHA",
        1,
    )
    with pytest.raises(ValueError, match="SHA256"):
        build_r4_20_case_source_coverage(**data)


def test_cached_source_hash_mismatch_and_duplicate_file_fails_hard():
    data = originals()
    # per-file receipt mutation: duplicate the exact Museum file line.
    lines = data["independent_files_csv"].splitlines()
    match = next(x for x in lines[1:] if x.startswith("0372200172326000015,FILE-01,"))
    data["independent_files_csv"] += match + "\n"
    with pytest.raises(ValueError, match="duplicate file"):
        build_r4_20_case_source_coverage(**data)


def test_mutated_deadline_matrix_label_cannot_override_original_values():
    data = originals()
    data["persisted_facts_csv"] = rewrite_csv(
        data["persisted_facts_csv"],
        "deadline_match", "EXACT", "MISMATCH",
        registry="0372200172326000015",
    )
    with pytest.raises(ValueError, match="deadline"):
        build_r4_20_case_source_coverage(**data)


def test_missing_human_approval_is_never_auto_filled():
    data = originals()
    data["human_queue_csv"] = rewrite_csv(
        data["human_queue_csv"], "human_go_no_go_defer", "", "GO",
        registry="0372200172326000015",
    )
    with pytest.raises(ValueError, match="human signoff"):
        build_r4_20_case_source_coverage(**data)


def test_archive_no_data_is_never_reinterpreted_as_source_verified():
    data = originals()
    data["independent_cases_csv"] = rewrite_csv(
        data["independent_cases_csv"],
        "official_SOAP_status", "no_data", "completed",
        registry="0148300050426000047",
    )
    with pytest.raises(ValueError):
        build_r4_20_case_source_coverage(**data)


def test_deterministic_machine_only_json_and_human_queue_csv_export(tmp_path):
    import json

    from scripts.acceptance.build_r4_20_source_coverage import export_matrix

    first = export_matrix(tmp_path)
    json_out = tmp_path / "r4-20-historical-source-coverage.json"
    csv_out = tmp_path / "r4-20-historical-source-coverage.csv"
    initial_bytes = (json_out.read_bytes(), csv_out.read_bytes())
    second = export_matrix(tmp_path)
    assert first == second
    assert initial_bytes == (json_out.read_bytes(), csv_out.read_bytes())
    assert len(list(csv.DictReader(io.StringIO(csv_out.read_text())))) == 20
    decoded = json.loads(json_out.read_text())
    assert decoded["summary"]["archived_official_zip"] == 17
    assert decoded["summary"]["human_gold_reviews_completed"] == 0
    assert all(not row["bid_ready"] for row in decoded["cases"])
    assert all(row["human_reviewer"] is None for row in decoded["cases"])
