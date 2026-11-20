"""Complete one exact existing daily analysis without preparation or discovery."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import runpy
import sys
from pathlib import Path
from uuid import uuid4

from scripts.ops.recover_daily_index import (
    LAUNCHER,
    SYSTEM_ID,
    identity_digest,
    journal,
    pending_journal,
    private_directory,
)

JOURNAL_ROOT = Path(
    "/Volumes/ArvectumSSD/Arvectum/private/tender-agent/daily-analysis-recovery"
)


def persist_report(root: Path, registry: str, markdown: str):
    if len(registry) != 19 or not registry.isascii() or not registry.isdigit():
        raise ValueError("invalid report notice identity")
    if not markdown.strip():
        raise ValueError("empty analysis report")
    root.mkdir(parents=True, exist_ok=True)
    if root.resolve() != root or root.is_symlink():
        raise ValueError("unsafe report directory")
    path = root / f"analyze_tender_{registry}_recovery_{uuid4().hex}.md"
    content = markdown.encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return path, hashlib.sha256(content).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for k in ("run", "registry", "deal", "fingerprint"):
        p.add_argument("--" + k, required=True)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--confirm-release")
    p.add_argument("--expected-identity-sha")
    args = p.parse_args()
    daily = runpy.run_path(str(LAUNCHER))
    release = daily["RELEASE"]
    if (
        Path(__file__).resolve().parents[2] != release / "source"
        or Path(sys.prefix).resolve() != (release / "venv").resolve()
    ):
        raise RuntimeError("run from approved active release")
    if args.apply and (
        args.confirm_release != daily["SHA"] or not args.expected_identity_sha
    ):
        raise ValueError("exact release and plan confirmation required")
    fd = None
    try:
        if args.apply:
            fd = daily["acquire_daily_lock"]()
        env = daily["preflight"]()
        os.environ.clear()
        os.environ.update(env)
        os.chdir("/Users/master")
        return execute(args, daily["SHA"])
    finally:
        if fd is not None:
            os.close(fd)


def execute(args, release):
    from dataclasses import asdict

    from sqlalchemy import create_engine, select, text

    from scripts.ops.daily_index_recovery_host import admit_index_batch
    from src.modules.daily_tender_run.analysis_recovery import (
        complete_indexed_analysis,
        profile_for_target,
    )
    from src.modules.daily_tender_run.index_reconciliation import reconcile
    from src.modules.daily_tender_run.index_snapshot import PostgresIndexReader
    from src.modules.daily_tender_run.manager_synthesis import synthesize_manager_brief
    from src.modules.daily_tender_run.models import DailyTenderRunItem
    from src.modules.daily_tender_run.recovery_plan import RecoveryTarget, plan_target
    from src.modules.daily_tender_run.service import _run_execution_guard
    from src.shared.db import models as _models  # noqa: F401
    from src.shared.db.session import SessionLocal, engine
    from src.tender_research.config import load_config
    from src.tender_research.rag.analysis_service import analyze_tender
    from src.tender_research.repository import TenderRepository

    target = RecoveryTarget(args.run, args.registry, args.deal, args.fingerprint)
    platform = create_engine(engine.url.set(database="arvectum_data"))
    reader = PostgresIndexReader(platform, SYSTEM_ID)
    try:
        with SessionLocal() as session:
            repo = TenderRepository(session)

            def scope():
                session.expire_all()
                plan = plan_target(session, target)
                if (
                    plan["status"] != "candidate_for_reviewed_recovery"
                    or not plan["collection_id"]
                ):
                    raise RuntimeError("not an exact indexed recovery candidate")
                chunks = repo.list_chunks_by_tender(plan["tender_id"])
                snapshot = reader(plan["collection_id"])
                if not reconcile(chunks, list(snapshot.rows), snapshot.contract)[
                    "complete"
                ]:
                    raise RuntimeError("index not independently complete")
                profile = profile_for_target(session, target)
                item = session.scalars(
                    select(DailyTenderRunItem).where(
                        DailyTenderRunItem.run_id == target.run_id,
                        DailyTenderRunItem.registry_number == target.registry_number,
                    )
                ).one()
                attributes = {
                    "registry_number": item.registry_number,
                    "title": item.title,
                    "customer_name": item.customer_name,
                    "nmck_amount": item.nmck_amount,
                    "deadline_text": item.deadline_at.isoformat()
                    if item.deadline_at
                    else None,
                }
                payload = {
                    "release": release,
                    "target": asdict(target),
                    "collection_id": snapshot.collection_id,
                    "contract": asdict(snapshot.contract),
                    "profile": profile.model_dump(mode="json"),
                    "notice": attributes,
                    "chunks": sorted(
                        (str(c.id), hashlib.sha256(c.text.encode()).hexdigest())
                        for c in chunks
                    ),
                }
                return profile, identity_digest(payload), len(chunks), attributes

            session.execute(text("SET TRANSACTION READ ONLY"))
            profile, digest, count, attributes = scope()
            session.rollback()
            if not args.apply:
                print(
                    json.dumps(
                        {
                            "status": "read_only",
                            "target": asdict(target),
                            "identity_sha256": digest,
                            "verified_chunks": count,
                            "analysis_mode": profile.analysis_mode,
                            "analysis_use_llm": profile.analysis_use_llm,
                            "synthesis_use_llm": profile.synthesis_use_llm,
                        }
                    )
                )
                return 0
            if digest != args.expected_identity_sha:
                raise RuntimeError("analysis plan identity changed")
            if JOURNAL_ROOT.exists():
                private_directory(JOURNAL_ROOT)
                pending_journal(JOURNAL_ROOT, target.registry_number)
            with (
                _run_execution_guard(session, target.run_id),
                admit_index_batch() as (_, receipt),
                journal(
                    JOURNAL_ROOT,
                    target.registry_number,
                    {"identity_sha256": digest, "prewrite": receipt},
                ) as record,
            ):
                session.execute(text("SET TRANSACTION READ ONLY"))
                if scope()[1] != digest:
                    raise RuntimeError("analysis evidence changed after admission")
                record("analysis_started", {"verified_chunks": count})
                result = analyze_tender(
                    registry_number=target.registry_number,
                    use_llm=profile.analysis_use_llm,
                    analysis_mode=profile.analysis_mode,
                    session=session,
                    save_report=False,
                    record_history=False,
                )
                if (
                    result.status not in {"completed", "completed_with_warnings"}
                    or not result.sources_count
                    or result.errors
                    or (profile.analysis_use_llm and not result.used_llm)
                ):
                    raise RuntimeError("source-grounded analysis did not complete")
                synthesis = synthesize_manager_brief(
                    result,
                    **attributes,
                    selection_policy=profile.decision_policy.model_dump(mode="json"),
                    use_llm=profile.synthesis_use_llm,
                )
                if scope()[1] != digest:
                    raise RuntimeError("analysis evidence changed during generation")
                session.rollback()
                report, report_hash = persist_report(
                    Path(load_config().data_dir).resolve() / "rag" / "reports",
                    target.registry_number,
                    result.report_markdown,
                )
                record("report_persisted", {"path": str(report), "sha256": report_hash})
                saved = complete_indexed_analysis(
                    session,
                    target=target,
                    analysis=result,
                    synthesis=synthesis,
                    report=report,
                    expected_profile=profile,
                    index_identity_sha256=digest,
                    report_sha256=report_hash,
                )
                session.commit()
                session.expire_all()
                row = session.scalars(
                    select(DailyTenderRunItem).where(
                        DailyTenderRunItem.run_id == target.run_id,
                        DailyTenderRunItem.registry_number == target.registry_number,
                    )
                ).one()
                if (
                    row.analysis_run_id != saved["analysis_run_id"]
                    or row.status != "MANAGER_READY"
                ):
                    raise RuntimeError("committed recovery could not be verified")
                session.rollback()
                record("verified_batch", saved)
                print(json.dumps(saved))
                return 0
    finally:
        platform.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
