from __future__ import annotations

from src.modules.tender_connectors import text_extraction
from src.modules.tender_connectors.text_extraction import (
    extract_attachment_urls,
    extract_text_from_attachment_bytes,
    quality_gate_text,
)
from src.shared.document_processing import ProcessedDocument


class TestQualityGate:
    def test_accepts_valid_text(self):
        result = quality_gate_text("Поставка картриджей HP для офисной техники в количестве 50 штук")
        assert result.accepted is True
        assert result.reason == "accepted"

    def test_rejects_empty(self):
        result = quality_gate_text("")
        assert result.accepted is False
        assert result.reason == "empty"

    def test_rejects_none(self):
        result = quality_gate_text(None)
        assert result.accepted is False

    def test_rejects_too_short(self):
        result = quality_gate_text("короткий")
        assert result.accepted is False
        assert result.reason == "too_short"

    def test_rejects_noise_only(self):
        result = quality_gate_text("!@#$%^&*()_+" * 10)
        assert result.accepted is False

    def test_rejects_repetitive_noise(self):
        result = quality_gate_text("а " * 50)
        assert result.accepted is False


class TestExtractUrls:
    def test_finds_direct_urls(self):
        urls = extract_attachment_urls({
            "attachments": [{"url": "https://example.com/doc.pdf"}],
        })
        assert "https://example.com/doc.pdf" in urls

    def test_finds_urls_in_text(self):
        urls = extract_attachment_urls({
            "description": "Скачать: https://example.com/file.txt",
        })
        assert len(urls) == 1

    def test_deduplicates(self):
        urls = extract_attachment_urls({
            "files": [
                {"url": "https://example.com/a.pdf"},
                {"url": "https://example.com/a.pdf"},
            ],
        })
        assert len(urls) == 1

    def test_returns_empty_for_no_urls(self):
        assert extract_attachment_urls({"name": "test"}) == []


class TestExtractBytes:
    def test_delegates_to_data_platform_processing(self, monkeypatch):
        calls = []

        def fake_process(**kwargs):
            calls.append(kwargs)
            return ProcessedDocument(
                extraction_status="extracted",
                text="Привет мир",
                chunks=(),
            )

        monkeypatch.setattr(text_extraction, "process_document_bytes", fake_process)

        text = extract_text_from_attachment_bytes(
            "https://example.com/file.txt",
            b"ignored",
        )

        assert text == "Привет мир"
        assert calls[0]["filename"] == "file.txt"
        assert calls[0]["canonical_uri"] == "https://example.com/file.txt"

    def test_non_extracted_status_returns_none(self, monkeypatch):
        monkeypatch.setattr(
            text_extraction,
            "process_document_bytes",
            lambda **_kwargs: ProcessedDocument(
                extraction_status="unsupported",
                text="",
                chunks=(),
            ),
        )

        assert extract_text_from_attachment_bytes("file.bin", b"bytes") is None
