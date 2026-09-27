from __future__ import annotations

import csv
import io
import subprocess
from dataclasses import dataclass
from pathlib import Path

_TESSERACT_CANDIDATES = (
    Path('/opt/homebrew/bin/tesseract'),
    Path('/usr/local/bin/tesseract'),
    Path('/usr/bin/tesseract'),
)
_TESSERACT_TIMEOUT_SECONDS = 30
_ALLOWED_LANGUAGES = frozenset({'rus', 'eng', 'rus+eng', 'eng+rus'})


@dataclass(frozen=True)
class OcrWord:
    text: str
    confidence: float
    left: int
    top: int
    width: int
    height: int


@dataclass(frozen=True)
class OcrResult:
    engine: str
    words: tuple[OcrWord, ...]
    text: str
    mean_confidence: float | None
    needs_review: bool


def resolve_tesseract() -> Path | None:
    """Resolve only fixed, repository-approved executable locations."""
    return next((path for path in _TESSERACT_CANDIDATES if path.is_file()), None)


def extract_image_with_tesseract(
    image_path: str | Path,
    *,
    language: str = 'rus+eng',
    review_below_confidence: float = 70.0,
) -> OcrResult | None:
    """Evaluate a local image with Tesseract TSV output.

    This is a replaceable, local-only adapter. It does not render PDFs or wire OCR
    into production ingestion. Missing engine, invalid input, timeout, or malformed
    output fails closed to ``None``.
    """
    if language not in _ALLOWED_LANGUAGES:
        raise ValueError('unsupported OCR language')
    path = Path(image_path)
    if not path.is_file():
        return None
    executable = resolve_tesseract()
    if executable is None:
        return None
    try:
        completed = subprocess.run(
            [str(executable), str(path), 'stdout', '-l', language, 'tsv'],
            capture_output=True,
            check=False,
            timeout=_TESSERACT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    try:
        rows = csv.DictReader(io.StringIO(completed.stdout.decode('utf-8')),
                              delimiter='\t')
        required = {'text', 'conf', 'left', 'top', 'width', 'height'}
        if not rows.fieldnames or not required.issubset(rows.fieldnames):
            return None
        words: list[OcrWord] = []
        for row in rows:
            text = (row.get('text') or '').strip()
            if not text:
                continue
            confidence = float(row['conf'])
            if confidence < 0:
                continue
            words.append(OcrWord(
                text=text,
                confidence=confidence,
                left=int(row['left']), top=int(row['top']),
                width=int(row['width']), height=int(row['height']),
            ))
    except (KeyError, TypeError, ValueError, UnicodeDecodeError):
        return None
    if not words:
        return OcrResult('tesseract', (), '', None, True)
    mean_confidence = sum(word.confidence for word in words) / len(words)
    return OcrResult(
        engine='tesseract',
        words=tuple(words),
        text=' '.join(word.text for word in words),
        mean_confidence=mean_confidence,
        needs_review=mean_confidence < review_below_confidence,
    )
