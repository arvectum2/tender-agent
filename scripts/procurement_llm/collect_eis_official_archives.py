"""Bounded owner-only EIS getDocsIP original ZIP -> existing learning corpus.

This records authenticated *transported* official archive provenance and
selected notice XML classification. Not a legal signature, current latest EIS
notice, admissible bid, human-gold or training answer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import tempfile
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from scripts.procurement_llm.collect_public_market_originals import (
    OWNER_PRIVATE,
    PublicOriginalError,
    _preserve_first_observed_payload,
)
from scripts.procurement_llm.import_candidates import _engine_url
from src.modules.procurement_learning_corpus.models import (
    ProcurementLearningObservation,
)
from src.modules.procurement_learning_corpus.service import (
    append_candidate,
    make_manual_candidate,
    validate_candidate,
)
from src.modules.tender_operator_agent_demo.eis_official_procedure import (
    classify_official_eis_archive,
)
from src.modules.tender_operator_agent_demo.settings import get_zakupki_soap_settings
from src.modules.tender_operator_agent_demo.zakupki_soap_client import ZakupkiSoapClient

NUMBERS = ("0163200000326005243", "0332100025426000039", "0148200002426000013")
MAX_ZIP = 8_000_000
NUMBER = re.compile(r"[0-9]{19}\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")


def validate_numbers(numbers: object) -> list[str]:
    if (
        not isinstance(numbers, (tuple, list))
        or not 1 <= len(numbers) <= 4
        or any(not isinstance(n, str) or not NUMBER.fullmatch(n) for n in numbers)
        or len(set(numbers)) != len(numbers)
    ):
        raise PublicOriginalError("explicit unique EIS official 19-digit allowlist required")
    return list(numbers)


def fetch_official_archive(number: str) -> bytes:
    validate_numbers([number])
    settings = replace(get_zakupki_soap_settings(), timeout_seconds=12)
    if (
        not settings.configured
        or not settings.disable_proxy_for_eis
        or not settings.require_direct_ru_route
    ):
        raise PublicOriginalError("configured direct official EIS route required")
    client = ZakupkiSoapClient(settings, runtime_status_enabled=False)
    response = client.get_docs_by_reestr_number(number)
    urls = response.archive_urls or (
        [response.archive_url] if response.archive_url else []
    )
    if response.status != "completed" or len(urls) != 1:
        raise PublicOriginalError("unique official getDocsIP archive unavailable")
    parsed = urlsplit(urls[0])
    query = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "int.zakupki.gov.ru"
        or parsed.path != "/dstore/common/download/compound"
        or parsed.username or parsed.password or parsed.fragment
        or parsed.port not in (None, 443)
        or [key for key, _ in query] != ["docRequestUid", "compoundUid"]
        or not re.fullmatch(r"[A-Fa-f0-9-]{36}", query[0][1])
        or not re.fullmatch(r"[A-Fa-f0-9]{32}", query[1][1])
    ):
        raise PublicOriginalError("official getDocsIP archive host/path not trusted")
    with tempfile.TemporaryDirectory(prefix="ta-owner-eis-archive-") as temp:
        downloaded = client.download_archive(urls[0], Path(temp))
        source = Path(temp) / downloaded.stored_name
        if (
            source.is_symlink() or not source.is_file()
            or not 0 < source.stat().st_size <= MAX_ZIP
            or downloaded.source_url_host != "int.zakupki.gov.ru"
        ):
            raise PublicOriginalError("EIS source archive unavailable or oversized")
        return source.read_bytes()


def classify_archive(number: str, raw: bytes) -> dict:
    validate_numbers([number])
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_ZIP:
        raise PublicOriginalError("bounded ZIP source bytes required")
    with tempfile.TemporaryDirectory(prefix="ta-eis-verify-") as temp:
        path = Path(temp) / "original.zip"
        path.write_bytes(raw)
        classification = classify_official_eis_archive(path, number)
    if (
        classification.get("status") not in {"ATTESTED_COMPETITIVE", "ATTESTED_SPECIAL"}
        or classification.get("source_purchase_number") != number
        or classification.get("archive_sha256") != hashlib.sha256(raw).hexdigest()
        or not SHA.fullmatch(classification.get("notice_xml_sha256") or "")
        or not isinstance(classification.get("source_version"), int)
        or classification.get("source_version") < 1
        or classification.get("current_live_eis_verified") is not False
        or classification.get("business_go_eligible") is not False
    ):
        raise PublicOriginalError("official source XML version/identity not verified")
    return classification


def _original_path(root: Path, number: str, raw: bytes) -> Path:
    validate_numbers([number])
    if root.is_symlink() or not root.is_dir():
        raise PublicOriginalError("private EIS original root missing")
    return (
        root / "original-snapshots" / "eis" / number
        / (hashlib.sha256(raw).hexdigest() + ".zip")
    )


def _write_zip(path: Path, raw: bytes, root: Path) -> bool:
    if (
        path.is_symlink() or root.resolve() not in path.resolve().parents
        or path.name != hashlib.sha256(raw).hexdigest() + ".zip"
    ):
        raise PublicOriginalError("private original ZIP path is untrusted")
    for parent in (root / "original-snapshots", path.parent.parent, path.parent):
        if parent.is_symlink():
            raise PublicOriginalError("EIS snapshot symlink ancestor")
        parent.mkdir(mode=0o700, exist_ok=True)
        if stat.S_IMODE(parent.stat().st_mode) & 0o077:
            raise PublicOriginalError("EIS private directory too permissive")
    if path.exists():
        if path.read_bytes() != raw or stat.S_IMODE(path.stat().st_mode) & 0o077:
            raise PublicOriginalError("immutable official original mismatch")
        return False
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return True


def make_eis_candidate(number: str, raw: bytes, observed: datetime, path: Path) -> dict:
    facts = classify_archive(number, raw)
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise PublicOriginalError("official archive observation requires timezone")
    zip_sha = facts["archive_sha256"]
    event = {
        "event_id": "ta-eis-zip:" + hashlib.sha256(
            f"{number}:{zip_sha}:{facts['notice_xml_sha256']}".encode()
        ).hexdigest()[:40],
        "procurement_ref": number,
        "participation": "reviewed_only",
        "review_state": "source_documented",
        "source_role": "development_exposed",
        "event_type": "official_eis_getdocsip_archived_original",
        "source_platform": "eis_getdocsip",
        "official_archive_sha256": zip_sha,
        "official_archive_original_bytes": len(raw),
        "selected_notice_xml_sha256": facts["notice_xml_sha256"],
        "selected_archived_notice_version": facts["source_version"],
        "archived_notice_type": facts["notice_type"],
        "archived_notice_procedure_class": facts["procedure_kind"],
        "archived_classification_status": facts["status"],
        "original_zip_owner_private_path": str(path),
        "source_observed_at_utc": observed.astimezone(UTC).isoformat(),
        "source_gate": "EIS_SOAP_ARCHIVED_XML_SHA_NOT_LIVE_LEGAL_STATUS",
        "current_live_eis_verified": False,
        "current_latest_notice_version_verified": False,
        "original_attached_documents_fully_read": False,
        "owner_bid_go": False,
        "human_verified_interpretation": False,
        "training_labels": "NOT_REVIEWED",
        "raw_archive_bytes_in_db": False,
    }
    candidate = make_manual_candidate(event)
    validate_candidate(candidate)
    return candidate


def collect(numbers: list[str], *, fetch=fetch_official_archive,
            root: Path = OWNER_PRIVATE, apply: bool = False,
            observed: datetime | None = None, engine_factory=None) -> dict:
    numbers = validate_numbers(numbers)
    observed = observed or datetime.now(UTC)
    prepared = []
    # Must attest EVERY original before writing any source or SQL data.
    for number in numbers:
        raw = fetch(number)
        facts = classify_archive(number, raw)
        path = _original_path(root, number, raw)
        candidate = make_eis_candidate(number, raw, observed, path)
        assert facts["archive_sha256"] == candidate["payload_json"]["official_archive_sha256"]
        prepared.append((candidate, path, raw))
    if not apply:
        return {
            "mode": "dry_run", "official_archives_verified": len(prepared),
            "bytes_verified": sum(len(raw) for _, _, raw in prepared),
            "new_private_snapshots": 0, "db_mutations": 0,
            "training_gold_created": False,
        }
    new_files = []
    try:
        for _, path, raw in prepared:
            if _write_zip(path, raw, root):
                new_files.append(path)
        engine = (engine_factory or (lambda: create_engine(_engine_url(), future=True)))()
        try:
            if not inspect(engine).has_table(ProcurementLearningObservation.__tablename__):
                raise RuntimeError("existing canonical migration 107 missing")
            with Session(engine) as session, session.begin():
                inserted = sum(append_candidate(
                    session, _preserve_first_observed_payload(session, candidate)
                ) for candidate, _, _ in prepared)
        finally:
            engine.dispose()
    except BaseException:
        for path in new_files:
            path.unlink(missing_ok=True)
        raise
    return {
        "mode": "canonical_arvectum_applied",
        "source_versions": len(prepared),
        "inserted": inserted,
        "existing": len(prepared) - inserted,
        "new_private_original_zip_snapshots": len(new_files),
        "live_legal_status_verified": False,
        "training_gold_created": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--numbers", nargs="+", default=list(NUMBERS))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-database", choices=["arvectum"])
    args = parser.parse_args()
    if args.apply and args.confirm_database != "arvectum":
        parser.error("explicit --confirm-database arvectum required")
    result = collect(args.numbers, apply=args.apply)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
