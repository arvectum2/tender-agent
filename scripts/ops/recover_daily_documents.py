"""Bounded exact-source daily document recovery, one step per invocation."""

from __future__ import annotations

import argparse
import json
import os
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

from scripts.ops.recover_daily_index import (
    LAUNCHER,
    SYSTEM_ID,
    identity_digest,
    journal,
    pending_journal,
    private_directory,
)

JOURNAL_ROOT = Path(
    "/Volumes/ArvectumSSD/Arvectum/private/tender-agent/daily-document-recovery"
)


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


def collection_exists(engine, cid):
    from sqlalchemy import text

    with engine.connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        try:
            row = conn.execute(
                text(
                    "SELECT current_database(),system_identifier::text FROM pg_control_system()"
                )
            ).one()
            if tuple(row) != ("arvectum_data", SYSTEM_ID):
                raise ValueError("Data Platform database identity mismatch")
            return conn.execute(
                text(
                    "SELECT EXISTS(SELECT 1 FROM dp_collections WHERE collection_id=:cid)"
                ),
                {"cid": cid},
            ).scalar_one()
        finally:
            conn.rollback()


def execute(args, release):
    from dataclasses import asdict

    from sqlalchemy import create_engine, text

    from scripts.ops.daily_index_recovery_host import admit_index_batch
    from src.modules.daily_tender_run.document_recovery import (
        fetch_docx,
        next_document_stage,
        save_original,
        source_inventory,
    )
    from src.modules.daily_tender_run.index_reconciliation import reconcile
    from src.modules.daily_tender_run.index_snapshot import PostgresIndexReader
    from src.modules.daily_tender_run.recovery_plan import RecoveryTarget, plan_target
    from src.modules.daily_tender_run.service import _run_execution_guard
    from src.shared.db import models as _models  # noqa: F401
    from src.shared.db.session import SessionLocal, engine
    from src.tender_research.config import load_config
    from src.tender_research.document_store import _tender_doc_dir
    from src.tender_research.providers.public_44fz_search import (
        Public44FzSearchProvider,
    )
    from src.tender_research.rag.data_platform import (
        DataPlatformDocumentProjector,
        build_data_platform_client,
        build_tender_collection_id,
    )
    from src.tender_research.rag.missing_attachments import (
        _official_url,
        recover_missing_attachments,
    )
    from src.tender_research.repository import TenderRepository

    target = RecoveryTarget(args.run, args.registry, args.deal, args.fingerprint)
    config = load_config()
    config.rag_data_platform_timeout_seconds = max(
        config.rag_data_platform_timeout_seconds, 180
    )
    platform = create_engine(engine.url.set(database="arvectum_data"))
    reader = PostgresIndexReader(platform, SYSTEM_ID)
    provider = Public44FzSearchProvider(
        bypass_proxy=True, timeout_seconds=12, delay_seconds=0
    )
    try:
        with SessionLocal() as session:
            repo = TenderRepository(session)

            def scope():
                session.expire_all()
                plan = plan_target(session, target)
                if plan["status"] != "candidate_for_reviewed_recovery":
                    raise ValueError("not an exact document recovery candidate")
                tender = repo.get_tender_by_id(plan["tender_id"])
                card = tender.raw_payload["public_detail"]["card_url"]
                if not _official_url(card, registry=target.registry_number):
                    raise ValueError("unbound public card")
                detail = provider.fetch_detail(
                    registry_number=target.registry_number, card_url=card
                )
                source = source_inventory(tender, detail)
                base = _tender_doc_dir(
                    config.data_dir, tender.source, tender.external_id
                )
                folder = (base / "documents" / "original").resolve()
                stage, doc, evidence = next_document_stage(repo, tender, folder)
                cid = None
                counts = None
                if stage == "ensure_collection":
                    cid = build_tender_collection_id(repo, tender.id)
                    if not cid:
                        raise ValueError("no complete local document projection")
                    if collection_exists(platform, cid):
                        snapshot = reader(cid)
                        result = reconcile(
                            repo.list_chunks_by_tender(tender.id),
                            list(snapshot.rows),
                            snapshot.contract,
                        )
                        if result["requires_review"]:
                            raise ValueError(
                                "existing collection requires reconciliation"
                            )
                        stage = (
                            "index_complete"
                            if result["complete"]
                            else "ready_for_index"
                        )
                        counts = result["counts"]
                identity = identity_digest(
                    {
                        "release": release,
                        "target": asdict(target),
                        "source": source,
                        "stage": stage,
                        "document_id": str(doc.id) if doc else None,
                        "evidence": evidence,
                        "tender_id": tender.id,
                        "collection_id": cid,
                    }
                )
                return SimpleNamespace(
                    tender=tender,
                    detail=detail,
                    folder=folder,
                    stage=stage,
                    doc=doc,
                    digest=identity,
                    source=source,
                    cid=cid,
                    counts=counts,
                )

            def result(plan):
                return {
                    "stage": plan.stage,
                    "identity_sha256": plan.digest,
                    "registry": target.registry_number,
                    "document_id": str(plan.doc.id) if plan.doc else None,
                    "document_count": len(plan.source["links"]),
                    "collection_id": plan.cid,
                    "counts": plan.counts,
                }

            session.execute(text("SET TRANSACTION READ ONLY"))
            before = scope()
            initial = result(before)
            session.rollback()
            if not args.apply:
                print(json.dumps(initial))
                return 0
            if initial["identity_sha256"] != args.expected_identity_sha:
                raise ValueError("document recovery plan changed")
            if JOURNAL_ROOT.exists():
                private_directory(JOURNAL_ROOT)
                pending_journal(JOURNAL_ROOT, target.registry_number)
            if initial["stage"] in {"index_complete", "ready_for_index"}:
                print(json.dumps(initial))
                return 0
            with (
                _run_execution_guard(session, target.run_id),
                admit_index_batch() as (_, receipt),journal(
                JOURNAL_ROOT,
                target.registry_number,
                {"plan": initial, "prewrite": receipt},
            ) as record
            ):
                current = scope()
                if current.digest != initial["identity_sha256"]:
                    raise ValueError("document scope changed after admission")
                record("step_started", result(current))
                if current.stage == "register_inventory":
                    frozen = SimpleNamespace(
                        fetch_detail=lambda **_: current.detail
                    )
                    count = recover_missing_attachments(
                        repo, current.tender, provider=frozen
                    )
                    if count != len(current.source["links"]):
                        raise RuntimeError("inventory registration incomplete")
                    session.commit()
                elif current.stage == "download_document":
                    doc = current.doc
                    content = fetch_docx(doc.file_url, config)
                    path, sha = save_original(current.folder, doc, content)
                    record("original_persisted", {"id": str(doc.id), "sha256": sha})
                    doc.local_path = str(path)
                    doc.sha256 = sha
                    doc.size_bytes = len(content)
                    doc.download_status = "downloaded"
                    doc.error_message = None
                    session.commit()
                elif current.stage == "project_document":
                    with build_data_platform_client(config) as client:
                        summary = DataPlatformDocumentProjector(
                            repo, client, config
                        ).build_for_tender(
                            current.tender, document_ids={current.doc.id}
                        )
                    if (
                        summary.documents_processed != 1
                        or summary.extracted_documents != 1
                        or not summary.chunks_projected
                    ):
                        raise RuntimeError("document extraction incomplete")
                elif current.stage == "ensure_collection":
                    with build_data_platform_client(config) as client:
                        client.ensure_collection(
                            collection_id=current.cid,
                            name=f"Tender {target.registry_number}",
                        )
                else:
                    raise RuntimeError("unsupported document stage")
                session.rollback()
                session.execute(text("SET TRANSACTION READ ONLY"))
                after = scope()
                final = result(after)
                session.rollback()
                if final["identity_sha256"] == initial["identity_sha256"]:
                    raise RuntimeError("no independently verified stage progress")
                record("verified_batch", final)
                print(json.dumps(final))
                return 0
    finally:
        platform.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
