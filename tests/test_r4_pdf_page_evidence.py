"""A quote on page X cannot be used to attest a claim about page Y."""
from __future__ import annotations

import hashlib
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from reportlab.pdfgen.canvas import Canvas

from src.modules.benchmark_pipeline.contract import BenchmarkContractError
from src.modules.tender_operator_agent_demo.r4_external_gold_intake import (
    _quotes_exactly_grounded,
)
from src.modules.tender_operator_agent_demo.r4_original_text_extract import (
    verified_pdf_citation_pages,
)

FIRST = "Exclusive rights to the completed software transfer only after acceptance."
SECOND = "Warranty repair of the delivered software shall be performed in thirty days."


def original_pdf() -> bytes:
    stream = BytesIO()
    canvas = Canvas(stream, pagesize=(612, 792), pageCompression=1)
    canvas.setFont("Helvetica", 10)
    canvas.drawString(30, 700, FIRST)
    canvas.showPage()
    canvas.drawString(30, 700, SECOND)
    canvas.showPage()
    canvas.save()
    return stream.getvalue()


def verify_quote(tmp_path, raw, *, filename="source.pdf", page="PAGE-2", quote=SECOND):
    file = tmp_path / filename
    file.write_bytes(raw)
    payload = {"documents": [{
        "path": filename,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "source_url": "https://example.org/source-original",
    }]}
    discovery = {"label": "RELEVANT", "evidence": [{
        "source_ref": filename, "quote": quote, "locator": page,
    }]}
    _quotes_exactly_grounded(payload, discovery, {"facts": []}, tmp_path)


def test_page_locator_and_verbatim_source_are_both_required(tmp_path):
    raw = original_pdf()
    pages = verified_pdf_citation_pages(raw, "source.pdf")
    assert len(pages) == 2
    assert FIRST in pages[0]
    assert SECOND in pages[1]
    verify_quote(tmp_path, raw)
    with pytest.raises(BenchmarkContractError, match="claimed page"):
        verify_quote(tmp_path, raw, page="PAGE-1", quote=SECOND)
    with pytest.raises(BenchmarkContractError, match="claimed page"):
        verify_quote(tmp_path, raw, page="PAGE-9", quote=SECOND)
    with pytest.raises(BenchmarkContractError, match="PAGE-N"):
        verify_quote(tmp_path, raw, page="Chapter VI", quote=SECOND)
    with pytest.raises(BenchmarkContractError, match="verbatim"):
        verify_quote(tmp_path, raw, quote="The software supplier must transfer all ownership upon signing the agreement.")


def test_single_original_pdf_in_zip_keeps_page_locator(tmp_path):
    raw = original_pdf()
    zipped = BytesIO()
    with ZipFile(zipped, "w", compression=ZIP_DEFLATED) as output:
        output.writestr("contract.pdf", raw)
    assert len(verified_pdf_citation_pages(zipped.getvalue(), "archive.zip")) == 2
    verify_quote(tmp_path, zipped.getvalue(), filename="archive.zip")
    with pytest.raises(BenchmarkContractError, match="claimed page"):
        verify_quote(tmp_path, zipped.getvalue(), filename="archive.zip", quote=FIRST, page="PAGE-2")


def test_unsupported_original_does_not_claim_pdf_page_evidence():
    assert verified_pdf_citation_pages(b"not pdf", "contract.docx") is None
