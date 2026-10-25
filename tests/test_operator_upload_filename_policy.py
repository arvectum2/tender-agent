import pytest
from fastapi import HTTPException

from src.modules.tender_operator_agent_demo import upload_service_legacy as old
from src.modules.tender_operator_agent_demo.operator_upload_filenames import (
    ALLOWED_EXTENSIONS,
    sanitize_demo_filename,
)


def test_upload_legacy_filename_policy_facade():
    assert old.sanitize_demo_filename is sanitize_demo_filename
    assert old.ALLOWED_EXTENSIONS is ALLOWED_EXTENSIONS


@pytest.mark.parametrize(("filename", "index", "expected"), [
    ("Техническое задание.DOCX", 1, ("Техническое задание.DOCX", "01-file-1.docx")),
    ("Contract Draft.PDF", 7, ("Contract Draft.PDF", "07-contract-draft.pdf")),
    ("notes.txt", 2, ("notes.txt", "02-notes.txt")),
])
def test_filename_policy_preserves_existing_normalization(filename, index, expected):
    assert sanitize_demo_filename(filename, index) == expected


def test_extension_is_rejected_before_storage():
    with pytest.raises(HTTPException) as exc:
        sanitize_demo_filename("installer.exe", 1)
    assert exc.value.status_code == 400
