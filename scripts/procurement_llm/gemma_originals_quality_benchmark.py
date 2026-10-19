"""Reproducible owner-private Gemma comparison with all real EIS originals.

Benchmark path is direct-source, NOT production DB-backed RAG: explicit
limitation reported. It takes original XML ZIP and five exact DOCX binary
receipts, creates deterministic cited paragraphs, and invokes the same
Tender Agent LocalChatLlmClient section-by-section with reasoning-enabled
llama.cpp quality server. No PDF/ETP/new model/network source or SQL writes.
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
from typing import Any

from docx import Document

from scripts.procurement_llm.analysis_queue_worker import (
    QUALITY_GEMMA_LLAMA_BASE_URL,
    QUALITY_GEMMA_LLAMA_MODEL,
    PinnedSource,
)
from scripts.procurement_llm.collect_public_market_originals import OWNER_PRIVATE
from scripts.procurement_llm.official_eis_xml_context import source_context_blob
from src.tender_research.rag.llm import LocalChatLlmClient
from src.tender_research.rag.schemas import ANALYSIS_SECTIONS
from src.tender_research.rag.search_types import RagSearchHit

NUMBER = "0163200000326005243"
ARCHIVE_SHA = "4cec297f6bd040723105fab5ac03a3d10e986b3c03b03032a7da3c3769389d5d"
ORIGINAL = OWNER_PRIVATE / "original-snapshots" / "eis" / NUMBER / (ARCHIVE_SHA + ".zip")
MANIFEST = OWNER_PRIVATE / "eis-source-documents" / NUMBER / ARCHIVE_SHA / "source-manifest.json"
MODEL = QUALITY_GEMMA_LLAMA_MODEL
SERVER = QUALITY_GEMMA_LLAMA_BASE_URL
MAX_CHARS_PER_SECTION = 22000
MAX_CHARS_PER_CHUNK = 1500

# Includes exactly the same 10 categories as the first saved Gemma report,
# plus one technical-work-scope question essential to B2B IT supplier decisions.
SECTIONS = [*ANALYSIS_SECTIONS, {
    "id": "technical_scope",
    "title": "Технические требования к веб-сайту",
    "question": (
        "Разложи ВСЕ прямо подтвержденные требования изменения сайта по блокам: "
        "технология сайта, dev1 и миграция, адаптивность и слабовидящие, "
        "прокрутка, PHP-ошибки, зарубежные зависимости, главная страница, "
        "4 вкладки поиска депутатов, Метрика и Яндекс.Карты, новости и мероприятия, "
        "URL и редиректы, CSS/таблицы/иконки, согласование дизайн-макетов. "
        "Для каждого блока назови конкретное требование и исходный источник; "
        "не выдумывай исполнение или экономику."
    ),
}]
KEYWORDS = {
    "notice_info": ("извещен", "срок", "публик", "площадк"),
    "subject": ("предмет", "цена", "нмцк", "услуг", "договор"),
    "customer_requirements": ("требован", "квалификац", "участник", "контракт"),
    "application_composition": ("заявк", "декларац", "состав", "част"),
    "evaluation_criteria": ("критер", "оцено", "балл", "квалификац", "договор"),
    "contract_terms": ("срок", "гаранти", "ответствен", "оплат", "декабр", "приёмк"),
    "documentation_requirements": ("документ", "оформлен", "заявк", "декларац"),
    "restrictions_benefits": ("ограничен", "преимуще", "субъект", "реестр"),
    "deadlines": ("дат", "срок", "окончан", "подач", "декабр"),
    "documents_summary": ("документац", "вложен", "разъяснен", "контракт"),
    "technical_scope": ("сайт", "депутат", "дизайн", "поиск", "слабовид", "переход"),
}
# Route original documents to their relevant question (all files included
# in at least one section) before lexical selection, not content hallucination.
PRIORITY_DOCS = {
    "notice_info": ("XML", "Требования"),
    "subject": ("XML", "Описание", "ОБОСНОВАНИЕ"),
    "customer_requirements": ("XML", "Требования", "Критерии"),
    "application_composition": ("XML", "Требования"),
    "evaluation_criteria": ("XML", "Критерии"),
    "contract_terms": ("XML", "Проект"),
    "documentation_requirements": ("XML", "Требования"),
    "restrictions_benefits": ("XML", "Требования", "Критерии"),
    "deadlines": ("XML", "Проект"),
    "documents_summary": ("XML", "Требования", "Описание"),
    "technical_scope": ("XML", "Описание"),
}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _chunks(text: str, *, max_chars: int = MAX_CHARS_PER_CHUNK) -> list[str]:
    """Coalesce full original paragraphs (not only tiny keyword matches)."""
    result: list[str] = []
    current: list[str] = []
    used = 0

    def emit() -> None:
        nonlocal used
        if current:
            result.append("\n".join(current))
            current.clear()
            used = 0

    for paragraph in text.splitlines():
        paragraph = " ".join(paragraph.split())
        if not paragraph:
            continue
        while len(paragraph) > max_chars:
            emit()
            split = paragraph.rfind(" ", 1, max_chars)
            split = split if split > 200 else max_chars
            result.append(paragraph[:split])
            paragraph = paragraph[split:].strip()
        if not paragraph:
            continue
        if used + len(paragraph) + (1 if current else 0) > max_chars:
            emit()
        current.append(paragraph)
        used += len(paragraph) + (1 if len(current) > 1 else 0)
    emit()
    return result


def _hit(text: str, *, file_name: str, blob_sha: str, index: int) -> RagSearchHit:
    token = f"{blob_sha}:{index}:{digest(text.encode())}"
    return RagSearchHit(
        # Stable short SHA-derived opaque IDs are simpler for a 12B model
        # to cite faithfully than a full UUID. Hash provenance unchanged.
        chunk_id="src-" + digest(token.encode())[:16],
        score=0,
        registry_number=NUMBER,
        tender_id="source-original-archive-"+ARCHIVE_SHA[:16],
        tender_title="Оказание услуг по изменению сайта Смоленской областной Думы",
        customer_name="СМОЛЕНСКАЯ ОБЛАСТНАЯ ДУМА",
        document_id=blob_sha[:32],
        file_name=file_name,
        chunk_index=index,
        text=text,
        preview=text[:500],
    )


def load_sources() -> tuple[list[RagSearchHit], dict]:
    if not ORIGINAL.is_file() or digest(ORIGINAL.read_bytes()) != ARCHIVE_SHA:
        raise RuntimeError("official stored getDocsIP ZIP SHA mismatch")
    if stat.S_IMODE(ORIGINAL.stat().st_mode) != 0o600:
        raise RuntimeError("private EIS original ZIP mode not 0600")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if (
        manifest["archived_original_zip_sha256"] != ARCHIVE_SHA
        or manifest["complete_xml_linked_attachment_count"] != 6
        or not manifest["all_original_binaries_saved"]
    ):
        raise RuntimeError("official attachment manifest incomplete/ambiguous")
    src = PinnedSource(
        observation_id=manifest["source_observation_id"],
        procurement_ref=NUMBER, event_kind="manual:ta-eis-zip",
        original_sha256=ARCHIVE_SHA, path=ORIGINAL, platform="eis",
    )
    xml_docx, receipt = source_context_blob(src)
    parsed = Document(__import__("io").BytesIO(xml_docx))
    xml_text = "\n".join(p.text for p in parsed.paragraphs if p.text)
    hits: list[RagSearchHit] = [
        _hit(txt, file_name="XML ЕИС v2: подтверждённые поля/ТЗ (производный)",
             blob_sha=receipt["source_notice_xml_sha256"], index=i)
        for i, txt in enumerate(_chunks(xml_text))
    ]
    original_count = 0
    names: list[str] = []
    total_chars = len(xml_text)
    for source in manifest["attachments"]:
        if source["binary_type"] != "DOCX_MAIN_BODY_OK":
            continue
        p = Path(source["owner_private_original_path"])
        if (
            p.is_symlink() or not p.is_file()
            or stat.S_IMODE(p.stat().st_mode) != 0o600
            or digest(p.read_bytes()) != source["original_binary_sha256"]
        ):
            raise RuntimeError("original DOCX source changed")
        doc = Document(p)
        # Both document paragraphs AND every table cell are read.
        body = "\n".join(
            [line.text for line in doc.paragraphs]
            + [cell.text for table in doc.tables for row in table.rows for cell in row.cells]
        )
        total_chars += len(body)
        for i, txt in enumerate(_chunks(body)):
            hits.append(_hit(txt, file_name=source["original_name"],
                             blob_sha=source["original_binary_sha256"], index=i))
        original_count += 1
        names.append(source["original_name"])
    if original_count != 5 or receipt["characteristics_included"] != 14:
        raise RuntimeError("not all real original documents and XML requirements loaded")
    return hits, {
        "original_archive_sha": ARCHIVE_SHA,
        "original_xml_sha": receipt["source_notice_xml_sha256"],
        "notice_nmc_rub": receipt["source_facts"]["НМЦК РУБ — сумма контракта, НЕ лимит квалификационного опыта"],
        "xml_characteristics": receipt["characteristics_included"],
        "official_docx_count": original_count,
        "original_names": names,
        "source_text_chars_total": total_chars,
        "candidate_chunks": len(hits),
        "excluded_opaque_zip": 1,
        "signed_original_source_attached": True,
        "source_current_legal_status": "NOT_VERIFIED",
    }


def selection(hits: list[RagSearchHit], section_id: str) -> list[RagSearchHit]:
    keywords = KEYWORDS[section_id]
    priority = PRIORITY_DOCS[section_id]

    def rank(item: RagSearchHit) -> tuple[int,int,int,int]:
        file_tag = "XML" if item.file_name.startswith("XML") else item.file_name
        document_order = next(
            (i for i, key in enumerate(priority) if key.lower() in file_tag.lower()),
            len(priority) + 1,
        )
        lower = item.text.lower()
        word_hits = sum(lower.count(keyword) for keyword in keywords)
        xml_important = bool(item.file_name.startswith("XML")
                             and ("НМЦК РУБ" in item.text
                                  or "Окончание приёма" in item.text
                                  or "Способ закупки" in item.text))
        score = (900 if xml_important else 0) + max(0, 240 - 80*document_order) + word_hits*12
        if item.file_name.startswith("XML"):
            if section_id == "technical_scope":
                score += 300
            elif not xml_important:
                # XML numeric facts remain in every section, but entire
                # technical object block should not crowd out contract DOCX.
                score -= 500
        return (-score, document_order, item.chunk_index, len(item.text))

    ordered = sorted(hits, key=rank)
    result: list[RagSearchHit] = []
    used = 0
    for item in ordered:
        # Actual LocalChatLlmClient adds headers/source IDs; reserve 5000 chars.
        span = len(item.text) + 350
        if used + span > MAX_CHARS_PER_SECTION or len(result) >= 18:
            continue
        result.append(item)
        used += span
    if not result or not any(x.file_name.startswith("XML") for x in result):
        raise RuntimeError("mandatory official XML numeric facts missing")
    return result


def _private_write_json(path: Path, value: dict) -> None:
    raw=(json.dumps(value,ensure_ascii=False,indent=2,sort_keys=True)+"\n").encode()
    if path.is_symlink():
        raise RuntimeError("unsafe progress file")
    temporary=path.with_suffix(".next")
    fd=os.open(temporary,os.O_CREAT|os.O_TRUNC|os.O_WRONLY,0o600)
    with os.fdopen(fd,"wb") as f:
        f.write(raw);f.flush();os.fsync(f.fileno())
    os.replace(temporary,path)
    os.chmod(path,0o600)


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-sections",type=int,default=len(SECTIONS))
    parser.add_argument("--output-dir",type=Path,
                        default=OWNER_PRIVATE / "quality-benchmarks" / "gemma-xml-reasoning-20261019")
    args=parser.parse_args()
    if not 1 <= args.max_sections <= len(SECTIONS):
        parser.error("invalid benchmark section count")
    out=args.output_dir
    if out.is_symlink(): raise RuntimeError("output must not be a symlink")
    out.mkdir(mode=0o700,parents=True,exist_ok=True)
    if stat.S_IMODE(out.stat().st_mode) != 0o700: raise RuntimeError("output directory must be private")
    hits, evidence = load_sources()
    progress_path=out/"progress.json"
    report: dict[str,Any] = {
        "schema":"gemma_12b_reasoning_xml_full_source_benchmark_v1",
        "model":MODEL,
        "server":SERVER,
        "analysis_mode":"detailed_direct_original_source",
        "reasoning_configured":"on_1024_token_budget",
        "baseline_report_seconds":249.97,
        "baseline_run_id":"ee8b1140-1cc6-46ef-b1db-661931fac69a",
        "source":evidence,
        "sections":[],
        "no_canonical_db_write":True,
        "no_training_gold":True,
        "same_tender_source_version":True,
        "total_elapsed_seconds":None,
    }
    if progress_path.is_file():
        previous=json.loads(progress_path.read_text())
        if (previous.get("schema")!=report["schema"]
                or previous.get("source")!=evidence
                or previous.get("model")!=MODEL):
            raise RuntimeError("prior incomplete benchmark is not same original/model")
        report=previous
    client=LocalChatLlmClient(base_url=SERVER,model_name=MODEL,
                              timeout_seconds=420,
                              max_context_chars=MAX_CHARS_PER_SECTION)
    total_start=time.monotonic()
    for sec in SECTIONS[:args.max_sections]:
        if any(
            old.get("id") == sec["id"] and old.get("status") == "completed"
            for old in report["sections"]
        ):
            continue
        failed_before = [
            old for old in report["sections"]
            if old.get("id") == sec["id"] and old.get("status") != "completed"
        ]
        prior_cost_seconds = sum(
            float(old.get("model_seconds", 0)) for old in failed_before
        )
        report["sections"] = [
            old for old in report["sections"] if old.get("id") != sec["id"]
        ]
        chunks=selection(hits,sec["id"])
        started=time.monotonic()
        answer=client.generate_answer(sec["question"],chunks,
                                      registry_number=NUMBER,analysis_mode="detailed")
        current={
            "id":sec["id"],"title":sec["title"],
            "answer":answer.answer,
            "status":"completed" if answer.answer and not answer.error else "not_verified",
            "error_kind":(answer.error or "")[:180],
            "originals_referenced":sorted({x.file_name for x in chunks}),
            "original_chunk_count":len(chunks),
            "context_chars":sum(len(x.text) for x in chunks),
            "model_seconds":round(time.monotonic()-started,2),
            "previous_failed_attempt_seconds": round(prior_cost_seconds, 2),
            "attempt_count": len(failed_before) + 1,
            "citation_id_format": "source-sha-short-16",
            "cited_source_ids":sorted({x.chunk_id for x in answer.sources}),
            "source_citation_count":len(answer.sources),
        }
        report["sections"].append(current)
        report["total_elapsed_seconds"]=round(sum(
            x["model_seconds"] + x.get("previous_failed_attempt_seconds", 0)
            for x in report["sections"]),2)
        report["evaluated_at_utc"]=datetime.now(UTC).isoformat()
        _private_write_json(progress_path,report)
        print("SECTION_COMPLETE",sec["id"],current["status"],
              "elapsed_seconds",current["model_seconds"],
              "chunks",len(chunks),"chars",current["context_chars"],
              "error",current["error_kind"],flush=True)
    print("BENCHMARK_END_SECTIONS",len(report["sections"]),
          "TOTAL_MODEL_SECONDS",round(sum(
              s["model_seconds"] + s.get("previous_failed_attempt_seconds", 0)
              for s in report["sections"]),2),
          "TOTAL_THIS_INVOCATION_SECONDS",round(time.monotonic()-total_start,2),
          flush=True)
    return 0 if all(s["status"]=="completed" for s in report["sections"]) else 2


if __name__=="__main__":
    raise SystemExit(main())
