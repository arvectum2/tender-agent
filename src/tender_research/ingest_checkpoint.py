from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from src.tender_research.errors import IngestCheckpointConflictError


@dataclass(frozen=True)
class IngestCheckpoint:
    version: int
    key: str
    source: str
    input_fingerprint: str
    total_items: int
    next_index: int = 0
    status: str = "in_progress"
    last_external_id: str | None = None
    last_error: str | None = None
    updated_at: str = ""


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


def _fingerprint(items: list[str]) -> str:
    payload = json.dumps(items, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _safe_key(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._")[:64] or "sync"
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"{slug}-{digest}.json"


class IngestCheckpointStore:
    """Atomic file-backed restart state for deterministic bounded ingest batches."""

    def __init__(self, data_dir: str | Path):
        self._root = Path(data_dir) / "ingest_checkpoints"

    def path_for(self, key: str) -> Path:
        return self._root / _safe_key(key)

    def load(self, key: str) -> IngestCheckpoint | None:
        path = self.path_for(key)
        if not path.is_file():
            return None
        return IngestCheckpoint(**json.loads(path.read_text(encoding="utf-8")))

    def begin(
        self, *, key: str, source: str, items: list[str], resume: bool = True
    ) -> IngestCheckpoint:
        fingerprint = _fingerprint(items)
        existing = self.load(key)
        if existing is not None:
            if (
                existing.source != source
                or existing.input_fingerprint != fingerprint
                or existing.total_items != len(items)
            ):
                raise IngestCheckpointConflictError(
                    f"Checkpoint {key!r} belongs to a different source/input batch; refusing ambiguous resume"
                )
            if not resume and existing.next_index:
                raise IngestCheckpointConflictError(
                    f"Checkpoint {key!r} already contains progress; explicit reset is required before restart"
                )
            if existing.status == "blocked":
                existing = replace(
                    existing,
                    status="in_progress",
                    last_error=None,
                    updated_at=_utcnow(),
                )
                self._write(existing)
            return existing
        checkpoint = IngestCheckpoint(
            version=1,
            key=key,
            source=source,
            input_fingerprint=fingerprint,
            total_items=len(items),
            updated_at=_utcnow(),
        )
        self._write(checkpoint)
        return checkpoint

    def advance(
        self, checkpoint: IngestCheckpoint, *, next_index: int, external_id: str | None
    ) -> IngestCheckpoint:
        status = "completed" if next_index >= checkpoint.total_items else "in_progress"
        updated = replace(
            checkpoint,
            next_index=next_index,
            status=status,
            last_external_id=external_id,
            last_error=None,
            updated_at=_utcnow(),
        )
        self._write(updated)
        return updated

    def fail(
        self, checkpoint: IngestCheckpoint, *, external_id: str | None, error: str
    ) -> IngestCheckpoint:
        updated = replace(
            checkpoint,
            status="blocked",
            last_external_id=external_id,
            last_error=error,
            updated_at=_utcnow(),
        )
        self._write(updated)
        return updated

    def _write(self, checkpoint: IngestCheckpoint) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        path = self.path_for(checkpoint.key)
        staged = path.with_suffix(path.suffix + ".tmp")
        payload = (
            json.dumps(asdict(checkpoint), ensure_ascii=False, sort_keys=True, indent=2)
            + "\n"
        )
        with staged.open("w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(staged, path)
