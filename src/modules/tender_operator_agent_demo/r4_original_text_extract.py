"""Read-only PDF/DOCX/ZIP source extraction, no legal text interpretation.

For scanned PDFs or unsupported spreadsheets, fail closed: the model must
never fabricate text or silently skip relevant source material.
"""
from __future__ import annotations

import io
import subprocess
import tempfile
import zipfile
from pathlib import Path

from docx import Document


def _pdf_text(data: bytes) -> str:
    with tempfile.TemporaryDirectory() as temporary:
        p = Path(temporary) / "source.pdf"
        p.write_bytes(data)
        run = subprocess.run(
            ["pdftotext", "-layout", "-enc", "UTF-8", str(p), "-"],
            capture_output=True, check=True, timeout=40,
        )
    text = run.stdout.decode("utf8", errors="strict")
    if len(text.strip()) < 80:
        raise ValueError("PDF source requires separate visual/OCR review")
    return text


def verified_document_text(raw: bytes, filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return _pdf_text(raw)
    if suffix == ".docx":
        doc = Document(io.BytesIO(raw))
        lines = [
            f"PARAGRAPH-{index:04d}: {part.text}"
            for index, part in enumerate(doc.paragraphs, 1)
            if part.text.strip()
        ]
        for table_id, table in enumerate(doc.tables, 1):
            for row_id, row in enumerate(table.rows, 1):
                for cell_id, cell in enumerate(row.cells, 1):
                    if cell.text.strip():
                        lines.append(
                            f"TABLE-{table_id:04d} ROW-{row_id:04d} "
                            f"CELL-{cell_id:04d}: {cell.text}"
                        )
        if sum(len(line) for line in lines) < 80:
            raise ValueError("DOCX source insufficient for text comparison")
        return "\n".join(lines)
    if suffix != ".zip":
        raise ValueError("Unsupported official original document format")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = [info for info in archive.infolist() if not info.is_dir()]
        if len(entries) != 1 or entries[0].file_size > 20_000_000:
            raise ValueError("Ambiguous/oversize official nested document ZIP")
        info = entries[0]
        inner_path = Path(info.filename)
        if info.flag_bits & 1 or inner_path.is_absolute() or ".." in inner_path.parts:
            raise ValueError("Unsafe ZIP inner original document")
        if inner_path.suffix.lower() not in {".docx", ".pdf"}:
            raise ValueError("Unsupported inner original source document")
        return verified_document_text(archive.read(info), info.filename)
