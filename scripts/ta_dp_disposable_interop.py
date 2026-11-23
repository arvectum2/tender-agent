"""Explicit opt-in TA <-> Data Platform disposable HTTP+PG17 integration.

Requires a separate candidate Data Platform worktree; never touches live
services, their databases, Qwen, or the tender-agent production checkout.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import secrets
import socket
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.shared.data_platform import DataPlatformClient
from src.shared.db import models as _models  # noqa: F401 - ORM registry/foreign-key targets
from src.shared.db.base import Base
from src.tender_research.rag.data_platform import DataPlatformRagRetriever
from src.tender_research.rag.two_mode_ingest import (
    AsyncTenderIndexPending,
    TwoModeTenderIndexer,
)
from src.tender_research.repository import TenderRepository

LABEL = "arvectum.ta.dp.disposable_interop"


def checked(*args: str, cwd: Path | None = None, env: dict | None = None) -> str:
    try:
        result = subprocess.run(
            args,
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            timeout=80,
            check=True,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        # CLI arguments may contain disposable DB credentials. Never expose
        # argv or subprocess output, including through exception chaining.
        raise RuntimeError("disposable interop subprocess failed") from None
    return result.stdout.strip()


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def seed_repo() -> tuple[TenderRepository, str, set[str]]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    repo = TenderRepository(sessionmaker(bind=engine)())
    tender = repo.upsert_tender(
        {
            "source": "eis",
            "external_id": "synthetic-disposable-interop",
            "registry_number": "SYNTHETIC-DP-TA",
            "title": "Synthetic trial",
        }
    )
    doc = repo.upsert_document({"tender_id": tender.id, "file_name": "synthetic.txt"})
    chunk_ids = set()
    for i in range(9):
        content = (
            f"Синтетический кабельный монтаж: этап {i:03d}. "
            "Документы подтверждают приёмку кабеля. " * 4
        )
        chunk = repo.upsert_document_chunk(
            {
                "tender_id": tender.id,
                "document_id": doc.id,
                "chunk_index": i,
                "text": content,
                "text_hash": hashlib.sha256(content.encode()).hexdigest(),
                "char_start": i * 550,
                "char_end": (i + 1) * 550,
                "token_estimate": 70,
                "source_file_name": "synthetic.txt",
            }
        )
        chunk_ids.add(chunk.id)
    repo._session.commit()
    return repo, str(tender.id), chunk_ids


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dp-worktree", type=Path, required=True)
    parser.add_argument("--execute-disposable-test", action="store_true")
    args = parser.parse_args()
    if not args.execute_disposable_test:
        parser.error("explicit --execute-disposable-test required")
    dp = args.dp_worktree.expanduser().resolve()
    if not (dp / "migrations/versions/0014_async_ingest_jobs.py").is_file():
        parser.error("candidate DP worktree missing migration 0014")
    if (dp / ".env").exists():
        parser.error("refusing DP worktree containing .env")
    dp_python = dp / ".venv/bin/python"
    if not dp_python.exists():
        parser.error("isolated DP candidate interpreter missing")
    if not hasattr(DataPlatformClient, "enqueue_ingest_document_bytes"):
        parser.error("updated candidate Data Platform SDK must be on PYTHONPATH")

    name = f"ta-dp-disposable-{uuid.uuid4().hex[:10]}"
    dbport, apiport = free_port(), free_port()
    assert dbport != apiport
    username = f"interop_{uuid.uuid4().hex[:10]}"
    passwd = secrets.token_urlsafe(22)
    dsn = f"postgresql+psycopg://{username}:{passwd}@127.0.0.1:{dbport}/{username}"
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("ARVECTUM_DATA_", "E2E_"))
    }
    env.update(
        E2E_DB=dsn,
        E2E_KEY=secrets.token_urlsafe(25),
        E2E_CONSUMER=secrets.token_urlsafe(25),
        E2E_PORT=str(apiport),
        PYTHONPATH=str(dp / "src"),
    )
    worker_env = dict(
        env,
        ARVECTUM_DATA_DATABASE_URL=dsn,
        ARVECTUM_DATA_ASYNC_INGEST_ENABLED="true",
        ARVECTUM_DATA_EMBEDDING_PROVIDER="hashing",
        ARVECTUM_DATA_EMBEDDING_MODEL="e2e-hash-v1",
        ARVECTUM_DATA_EMBEDDING_DIMENSION="64",
        ARVECTUM_DATA_CROSS_ENCODER_PROVIDER="disabled",
        ARVECTUM_DATA_REASONING_POLICY="disabled",
        ARVECTUM_DATA_VISION_POLICY="disabled",
    )
    container_created = False
    server = None
    api = f"http://127.0.0.1:{apiport}"
    with tempfile.TemporaryDirectory(prefix="ta-dp-interop-") as scratch:
        try:
            checked(
                "docker",
                "run",
                "-d",
                "--name",
                name,
                "--label",
                f"{LABEL}=true",
                "--memory",
                "384m",
                "--cpus",
                "1",
                "-p",
                f"127.0.0.1:{dbport}:5432",
                "-e",
                f"POSTGRES_USER={username}",
                "-e",
                f"POSTGRES_PASSWORD={passwd}",
                "-e",
                f"POSTGRES_DB={username}",
                "--health-cmd",
                f"pg_isready -U {username} -d {username}",
                "--health-interval",
                "1s",
                "--health-timeout",
                "1s",
                "--health-retries",
                "30",
                "pgvector/pgvector:pg17",
            )
            container_created = True
            for _ in range(80):
                if (
                    checked("docker", "inspect", "-f", "{{.State.Health.Status}}", name)
                    == "healthy"
                ):
                    break
                time.sleep(0.25)
            else:
                raise AssertionError("disposable PG17 did not become healthy")
            checked(
                str(dp_python),
                "-m",
                "alembic",
                "-c",
                str(dp / "alembic.ini"),
                "upgrade",
                "head",
                cwd=dp,
                env=worker_env,
            )

            stage = dp / "scripts/disposable_http_e2e.py"
            spec = importlib.util.spec_from_file_location("dp_stage_reference", stage)
            assert spec and spec.loader
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            log = Path(scratch) / "api.log"
            with log.open("w") as log_file:
                server = subprocess.Popen(
                    [str(dp_python), "-c", module.SERVER],
                    cwd=dp,
                    env=env,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                )
            with httpx.Client(base_url=api, timeout=3) as http:
                for _ in range(80):
                    if server.poll() is not None:
                        raise AssertionError("disposable API exited early")
                    try:
                        if http.get("/health").status_code == 200:
                            break
                    except httpx.RequestError:
                        pass
                    time.sleep(0.2)
                else:
                    raise AssertionError("disposable API did not become healthy")
            repo, tender_id, expected_chunks = seed_repo()
            with DataPlatformClient(base_url=api, api_key=env["E2E_KEY"]) as client:
                plan = TwoModeTenderIndexer(repo, client, async_enabled=True)
                assert plan.mode(tender_id) == "background"
                first = plan.start(tender_id)
                assert first.next_offset == 8
                second = plan.start(tender_id, offset=first.next_offset)
                assert second.next_offset is None
                try:
                    plan.require_ready(tender_id, [first, second])
                except AsyncTenderIndexPending:
                    pass
                else:
                    raise AssertionError("TA accepted incomplete async index")
                # A single explicit, finite worker process against disposable DB.
                script = (
                    "from arvectum_data.api.config import Settings;"
                    "from arvectum_data.api.service import DataPlatformService;"
                    "from arvectum_data.api.ingest_worker import run_one;"
                    "service=DataPlatformService(Settings(_env_file=None));"
                    "n=0\n"
                    "while run_one(service):\n n+=1\n"
                    "assert n==9,n"
                )
                checked(str(dp_python), "-c", script, cwd=dp, env=worker_env)
                assert (
                    plan.require_ready(tender_id, [first, second])
                    == first.collection_id
                )
                retriever = DataPlatformRagRetriever(repo, client)
                hits = plan.search_when_ready(
                    tender_id,
                    [first, second],
                    retriever,
                    query="кабель",
                    limit=9,
                )
                if not hits or not {hit.chunk_id for hit in hits} <= expected_chunks:
                    raise AssertionError(
                        "TA failed source-faithful RAG after background indexing"
                    )
                print(
                    json.dumps(
                        {
                            "status": "PASS",
                            "stage": "disposable Pg17 + real HTTP + hashing model",
                            "submitted_jobs": 9,
                            "completed_jobs": 9,
                            "verified_tender_search_hits": len(hits),
                            "pending_search_blocked": True,
                            "production_mutation": False,
                        },
                        ensure_ascii=False,
                    )
                )
        finally:
            if server and server.poll() is None:
                server.terminate()
                try:
                    server.wait(timeout=7)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=3)
            if container_created:
                label = checked(
                    "docker",
                    "inspect",
                    "-f",
                    '{{index .Config.Labels "' + LABEL + '"}}',
                    name,
                )
                if label != "true":
                    raise AssertionError("refusing cleanup of unknown container")
                checked("docker", "rm", "-f", name)


if __name__ == "__main__":
    main()
