"""Four-section, read-only, source-verified Gemma evidence acceptance probe.

This does NOT write to canonical PostgreSQL, the learning corpus, or a
TenderAnalysisRun. It verifies actual original EIS SHA, runs Data Platform
retrieval and produces a strictly private JSON evidence-check receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import time
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from scripts.procurement_llm.analysis_queue_worker import (
    QUALITY_GEMMA_LLAMA_BASE_URL,
    QUALITY_GEMMA_LLAMA_MODEL,
    readiness,
)
from scripts.procurement_llm.import_candidates import _engine_url
from scripts.procurement_llm.source_quality_rerun import NUMBER, source_for_case
from src.tender_research.config import load_config
from src.tender_research.rag.analysis_service import build_section_context
from src.tender_research.rag.data_platform import (
    DataPlatformRagRetriever,
    build_data_platform_client,
)
from src.tender_research.rag.llm import LocalChatLlmClient
from src.tender_research.rag.official_eis_priority import prioritize_original_eis_hits
from src.tender_research.rag.schemas import analysis_sections_for_regime
from src.tender_research.repository import TenderRepository

IDS = ("subject", "customer_requirements", "evaluation_criteria", "contract_terms")
OUT = Path("/Volumes/ArvectumSSD/Arvectum/private/tender-agent/quality-benchmarks/gemma-four-retry-20261019")


def _save_once(payload: dict) -> Path:
    OUT.mkdir(parents=True, exist_ok=True, mode=0o700)
    if OUT.is_symlink() or stat.S_IMODE(OUT.stat().st_mode) != 0o700:
        raise ValueError("private output folder cannot be verified")
    if payload["mode"] != "source_only_local_gemma":
        name = "evidence.json"
    elif payload.get("experiment_variant") == "repair3":
        name = "retry3-result.json"
    elif tuple(payload["selected_section_ids"]) == IDS:
        name = "result.json"
    else:
        name = "retry2-result.json"
    destination = OUT / name
    descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    return destination


def actual_probe(
    *, invoke_llm: bool, selected_section_ids: tuple[str, ...] = IDS,
    experiment_variant: str = "baseline",
) -> dict:
    if not selected_section_ids or any(i not in IDS for i in selected_section_ids):
        raise ValueError("only supported pinned four sections")
    engine = create_engine(_engine_url())
    result = {
        "schema": "smolensk_original_eis_four_section_repair_v1",
        "mode": "source_only_local_gemma" if invoke_llm else "evidence_only_readonly",
        "procurement_ref": NUMBER,
        "model": QUALITY_GEMMA_LLAMA_MODEL,
        "backend": "llama.cpp",
        "canonical_database_modified": False,
        "saved_run": False,
        "gold_promoted": False,
        "legal_bid_go": False,
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "sections": [],
        "selected_section_ids": list(selected_section_ids),
        "experiment_variant": experiment_variant,
    }
    try:
        with Session(engine) as session:
            session.execute(text("SET TRANSACTION READ ONLY"))
            source = source_for_case(session, NUMBER)
            health = readiness(
                session, source, require_services=True,
                llm_base_url=QUALITY_GEMMA_LLAMA_BASE_URL,
                llm_model=QUALITY_GEMMA_LLAMA_MODEL,
            )
            if not health["ready_for_actual_llm"]:
                raise RuntimeError("canonically indexed originals not ready for test")
            repo = TenderRepository(session)
            tender = repo.get_tender_by_registry_number(NUMBER)
            assert tender is not None
            client = build_data_platform_client(load_config())
            llm = LocalChatLlmClient(
                base_url=QUALITY_GEMMA_LLAMA_BASE_URL,
                model_name=QUALITY_GEMMA_LLAMA_MODEL,
                timeout_seconds=420,
                max_context_chars=22000,
            )
            try:
                available = {
                    section["id"]: section
                    for section in analysis_sections_for_regime(tender.law_type)
                }
                for section_id in selected_section_ids:
                    section = available[section_id]
                    started = time.perf_counter()
                    hits = DataPlatformRagRetriever(repo, client).search_documents(
                        section["question"], registry_number=NUMBER, limit=18
                    )
                    selected = prioritize_original_eis_hits(
                        repo, hits, registry_number=NUMBER, section_id=section_id,
                        max_chunks=18
                    )
                    context = build_section_context(
                        selected,max_chunks=18,max_context_chars=22000,
                        max_chunk_chars=2500,max_preview_chars=1200
                    ).hits
                    evidence = [
                        {
                            "file_name": h.file_name,
                            "chunk_id": h.chunk_id,
                            "sha256_text": hashlib.sha256(h.text.encode("utf-8")).hexdigest(),
                            "registry_number": h.registry_number,
                            "tender_id": h.tender_id,
                        }
                        for h in context
                    ]
                    record = {
                        "id": section_id,
                        "source_chunks": len(context),
                        "source_evidence": evidence,
                        "percent_numeric_guard_active": True,
                        "source_citation_guard_active": True,
                        "model_called": invoke_llm,
                    }
                    if invoke_llm:
                        answer = llm.generate_answer(
                            section["question"], context,
                            registry_number=NUMBER, analysis_mode="detailed"
                        )
                        record.update({
                            "duration_seconds": round(time.perf_counter()-started,2),
                            "attempts": answer.attempt_count,
                            "accepted": answer.error is None and bool(answer.answer),
                            "error": answer.error,
                            "answer": answer.answer if answer.error is None else None,
                            "answer_sha256": (
                                hashlib.sha256(answer.answer.encode()).hexdigest()
                                if answer.answer and answer.error is None else None
                            ),
                        })
                    else:
                        record["duration_seconds"] = round(time.perf_counter()-started,2)
                    result["sections"].append(record)
            finally:
                client.close()
            session.rollback()
    finally:
        engine.dispose()
    result["sections_accepted"] = sum(s.get("accepted",False) for s in result["sections"])
    result["sections_total"] = len(result["sections"])
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--llm", action="store_true")
    parser.add_argument("--only", nargs="+", choices=IDS)
    parser.add_argument("--variant", choices=["baseline", "repair3"], default="baseline")
    args = parser.parse_args()
    outcome = actual_probe(
        invoke_llm=args.llm,
        selected_section_ids=tuple(args.only) if args.only else IDS,
        experiment_variant=args.variant,
    )
    destination = _save_once(outcome)
    print(json.dumps({
        "status": "completed", "result_path": str(destination),
        "sections_total": outcome["sections_total"],
        "sections_accepted": outcome["sections_accepted"],
        "real_llm": args.llm,
        "database_modified": False,
        "gold": False,
        "duration_per_section": [
            (item["id"],item["duration_seconds"],
             item.get("attempts"),item.get("error"))
            for item in outcome["sections"]
        ],
    },ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
