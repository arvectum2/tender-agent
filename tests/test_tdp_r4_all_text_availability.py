"""Original 96-file text-readiness must not equate empty or tampered text to evidence."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from src.modules.tender_operator_agent_demo.r4_all_original_text_coverage import (
    _verify_text_location,
)

REGISTRY = "0372200172326000015"


def test_original_source_text_sha_and_length_are_checked(tmp_path: Path):
    folder = tmp_path / REGISTRY
    folder.mkdir()
    text = "PARAGRAPH-0001: Срок оказания услуг указан в официальном документе."
    original = folder / "attachment-01.txt"
    original.write_text(text, encoding="utf8")
    digest = hashlib.sha256(text.encode("utf8")).hexdigest()
    _verify_text_location(tmp_path, REGISTRY, original.name, digest, len(text))
    original.write_text(text + " изменено", encoding="utf8")
    with pytest.raises(ValueError, match="modified"):
        _verify_text_location(tmp_path, REGISTRY, original.name, digest, len(text))


def test_original_text_does_not_pass_with_blank_or_short_content(tmp_path: Path):
    folder = tmp_path / REGISTRY
    folder.mkdir()
    path = folder / "file.txt"
    path.write_text("ТЗ", encoding="utf8")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="not trustworthy"):
        _verify_text_location(tmp_path, REGISTRY, path.name, digest, len("ТЗ"))


def test_untrusted_source_locator_fails_without_reading_foreign_files(tmp_path: Path):
    with pytest.raises(ValueError, match="not trustworthy"):
        _verify_text_location(tmp_path, REGISTRY, "../other.txt", "0" * 64, 100)
    with pytest.raises(ValueError, match="not found"):
        _verify_text_location(tmp_path, REGISTRY, "missing.txt", "0" * 64, 100)
