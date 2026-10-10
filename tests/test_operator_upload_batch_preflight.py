"""A rejected batch cannot leave partially stored tender operator attachments."""

import pytest
from fastapi import HTTPException

from src.modules.tender_operator_agent_demo import upload_service_legacy as upload
from src.modules.tender_operator_agent_demo.operator_upload_preflight import (
    validate_operator_upload_batch,
)


def _upload_run(uploads):
    return upload.create_uploaded_demo_run(
        tender_title="Закупка оборудования",
        tender_category="equipment",
        customer_name="Заказчик",
        notes=None,
        target_margin_percent=None,
        logistics_reserve_percent=None,
        risk_reserve_percent=None,
        payment_delay_days=None,
        uploads=uploads,
    )


def test_preflight_rejects_all_before_creating_new_run(tmp_path, monkeypatch):
    root = tmp_path / "isolated-runs"
    monkeypatch.setenv("AI_CORP_TENDER_OPERATOR_DEMO_RUNS_DIR", str(root))

    # Previously, the first document could be written before this second
    # attachment failed validation.
    with pytest.raises(HTTPException) as exc:
        _upload_run([
            ("spec.txt", "text/plain", b"valid first"),
            ("not-supported.exe", "application/octet-stream", b"invalid second"),
        ])
    assert exc.value.status_code == 400
    assert not root.exists()


def test_preflight_rejects_append_without_partial_files_or_events(tmp_path, monkeypatch):
    root = tmp_path / "isolated-runs"
    monkeypatch.setenv("AI_CORP_TENDER_OPERATOR_DEMO_RUNS_DIR", str(root))
    run = _upload_run([("initial.txt", "text/plain", b"initial")])
    folder = root / run.run_id
    metadata = folder / "metadata.json"
    events = folder / "events.jsonl"
    existing_metadata = metadata.read_bytes()
    existing_events = events.read_bytes()
    existing_files = sorted((folder / "input").iterdir())
    with pytest.raises(HTTPException) as exc:
        upload.append_files_to_demo_run(
            run_id=run.run_id,
            uploads=[
                ("good.txt", "text/plain", b"good"),
                ("bad.exe", "application/octet-stream", b"invalid"),
            ],
        )
    assert exc.value.status_code == 400
    assert metadata.read_bytes() == existing_metadata
    assert events.read_bytes() == existing_events
    assert sorted((folder / "input").iterdir()) == existing_files


def test_preflight_rejects_oversized_later_file_without_normalization():
    sanitized = []

    def accept_name(name, index):
        sanitized.append((name, index))
        return name, name

    with pytest.raises(HTTPException, match="File exceeds"):
        validate_operator_upload_batch(
            [("first.txt", "text/plain", b"ok"), ("large.txt", "text/plain", b"123456")],
            existing_file_count=0,
            existing_total_bytes=0,
            max_file_count=16,
            max_file_size_bytes=5,
            max_total_upload_bytes=40,
            sanitize_name=accept_name,
        )
    assert sanitized == [("first.txt", 1)]


def test_preflight_keeps_exact_batch_count_and_total_size_errors():
    kwargs = {
        "existing_file_count": 2,
        "existing_total_bytes": 4,
        "max_file_count": 3,
        "max_file_size_bytes": 20,
        "max_total_upload_bytes": 6,
        "sanitize_name": lambda name, index: (name, name),
    }
    with pytest.raises(HTTPException, match="Too many files"):
        validate_operator_upload_batch(
            [("a.txt", "text/plain", b"1"), ("b.txt", "text/plain", b"2")],
            **kwargs,
        )
    with pytest.raises(HTTPException, match="Total upload size"):
        validate_operator_upload_batch(
            [("a.txt", "text/plain", b"123")],
            **kwargs,
        )


def test_oversized_second_attachment_is_rejected_before_new_run(tmp_path, monkeypatch):
    root = tmp_path / "runs"
    monkeypatch.setenv("AI_CORP_TENDER_OPERATOR_DEMO_RUNS_DIR", str(root))
    monkeypatch.setattr(upload, "MAX_FILE_SIZE_BYTES", 4)
    with pytest.raises(HTTPException, match="File exceeds"):
        _upload_run([
            ("first.txt", "text/plain", b"okay"),
            ("too-large.txt", "text/plain", b"over-limit"),
        ])
    assert not root.exists()
