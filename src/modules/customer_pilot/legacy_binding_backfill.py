"""Explicit, fail-closed conversion of pre-096 immutable canonical bindings."""

from __future__ import annotations

import hashlib
import json
import stat
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select

from src.modules.customer_pilot.artifact_snapshot import (
    VERIFICATION_POLICY_VERSION as ARTIFACT_POLICY_VERSION,
)
from src.modules.customer_pilot.artifact_snapshot import (
    FinalPdfArtifactError,
    derive_final_pdf_artifact_identity,
    verify_final_pdf_generation,
)
from src.modules.customer_pilot.canonical_snapshot import (
    EXACT_FILE_SET,
    SOURCE_GRAPH_HASH_ALGORITHM,
    VERIFICATION_POLICY_VERSION,
)
from src.modules.procurement_analysis.canonical_persistence import (
    verify_canonical_bytes,
)


@dataclass(frozen=True)
class LegacyBackfillResult:
    status: str
    changed_fields: tuple[str, ...]
    verified_identities: dict[str, str]
    error_category: str | None
    mutation_performed: bool


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _regular(path: Path) -> bytes:
    value = path.lstat()
    if stat.S_ISLNK(value.st_mode) or not stat.S_ISREG(value.st_mode):
        raise ValueError("unsafe_filesystem")
    return path.read_bytes()


def _directory(path: Path) -> None:
    value = path.lstat()
    if stat.S_ISLNK(value.st_mode) or not stat.S_ISDIR(value.st_mode):
        raise ValueError("unsafe_filesystem")


def _result(status: str, error: str | None = None, identities: dict | None = None):
    return LegacyBackfillResult(status, (), identities or {}, error, False)


def backfill_legacy_run_binding(*, session, run, case, run_result, artifact, data_root):
    """Stable entrypoint: keep original runtime helper patch points."""
    from src.modules.customer_pilot.legacy_binding_backfill_orchestrator import (
        run_immutable_backfill,
    )

    return run_immutable_backfill(
        session=session,
        run=run,
        case=case,
        run_result=run_result,
        artifact=artifact,
        data_root=data_root,
        select=select,
        _result=_result,
        Path=Path,
        _directory=_directory,
        EXACT_FILE_SET=EXACT_FILE_SET,
        _regular=_regular,
        verify_canonical_bytes=verify_canonical_bytes,
        json=json,
        _sha=_sha,
        SOURCE_GRAPH_HASH_ALGORITHM=SOURCE_GRAPH_HASH_ALGORITHM,
        VERIFICATION_POLICY_VERSION=VERIFICATION_POLICY_VERSION,
        derive_final_pdf_artifact_identity=derive_final_pdf_artifact_identity,
        verify_final_pdf_generation=verify_final_pdf_generation,
        FinalPdfArtifactError=FinalPdfArtifactError,
        ARTIFACT_POLICY_VERSION=ARTIFACT_POLICY_VERSION,
        LegacyBackfillResult=LegacyBackfillResult,
    )
