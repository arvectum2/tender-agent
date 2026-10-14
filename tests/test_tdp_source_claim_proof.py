"""Source-bound claims: exact span, historical XML typing, and fail closed."""
from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from src.modules.tender_operator_agent_demo.full_corpus_research import research_full_corpus
from src.modules.tender_operator_agent_demo.source_claim_proof import (
    bind_source_span,
    check_typed_original_facts,
)


def d(fid: str, role: str, text: str, **kwargs):
    return SimpleNamespace(file_id=fid, role=role, display_name=fid+".txt", text=text, **kwargs)


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def purchase_xml(price: str, deadline: str, registry: str = "0372200172326000015"):
    return (
        "<export><purchaseNumber>" + registry + "</purchaseNumber>"
        "<maxPrice>" + price + "</maxPrice>"
        "<endDT>" + deadline + "</endDT>"
        "<publishDTInEIS>2026-10-08T10:53:46+03:00</publishDTInEIS>"
        "</export>"
    )


def test_unicode_span_exact_hash_or_rejected_without_silent_repair():
    source = "Пункт 3.8: Цена 1 000 000 ₽. Условие о праве на изменение."
    original = d("c", "contract_draft", source)
    corpus = research_full_corpus([original])
    quote = "Цена 1 000 000 ₽"
    start = source.index(quote)
    correct = bind_source_span(
        [original], corpus, file_id="c", start=start,
        end=start+len(quote), quote=quote, expected_text_sha256=sha(source),
    )
    assert correct["status"] == "EXACT_NORMALIZED_SOURCE_TEXT"
    assert correct["quote_sha256"] == sha(quote)
    assert correct["source_ref"] == f"normalized:c:{start}-{start+len(quote)}"
    assert correct["semantic_verification"] == "NOT_PERFORMED"
    assert correct["physical_locator_status"] == "PAGE_OR_CELL_NOT_ATTESTED"

    def attempt(**changes):
        return bind_source_span(
            [original], corpus,
            **({"file_id":"c","start":start,"end":start+len(quote),
                "quote":quote,"expected_text_sha256":sha(source)} | changes),
        )
    assert attempt(quote="Цена 2 000 000 ₽")["status"] == "SOURCE_SPAN_UNVERIFIED"
    assert attempt(start=start+1)["status"] == "SOURCE_SPAN_UNVERIFIED"
    assert attempt(expected_text_sha256="0"*64)["status"] == "SOURCE_SPAN_UNVERIFIED"


def test_page_locator_cannot_be_inferred_from_unicode_offset_or_unsupported_proof():
    source = "2.2.3.5.1. Таблица требований к оказанию услуг."
    doc = d("d", "technical_spec", source)
    r = research_full_corpus([doc])
    options={"file_id":"d","start":0,"end":len(source),"quote":source,"expected_text_sha256":sha(source)}
    loose = bind_source_span([doc],r,**options,physical_locator={"kind":"pdf_page","label":"17"})
    assert loose["physical_locator"] is None
    assert loose["physical_locator_status"] == "PAGE_OR_CELL_NOT_ATTESTED"
    checked = bind_source_span(
        [doc],r,**options,physical_locator={
            "kind":"pdf_page","label":"17","extraction_attested":True,
            "normalized_span_map":{
                "file_id":"d","source_sha256":sha(source),
                "start":0,"end":len(source),
            },
        },
    )
    assert checked["physical_locator"] == {"kind":"pdf_page","label":"17"}
    assert checked["physical_locator_status"] == "EXPLICIT_SOURCE_MAPPING_REVIEW"
    assert checked["semantic_verification"] == "NOT_PERFORMED"


def test_tampered_source_does_not_appear_as_verified_evidence():
    text=purchase_xml("1000000","2026-10-16T10:00:00+03:00")
    d1=d("n","notice",text)
    r=research_full_corpus([d1],manifest=[{"file_id":"n","text_sha256":"0"*64}])
    out=bind_source_span([d1],r,file_id="n",start=0,end=5,quote="<expo",expected_text_sha256=sha(text))
    assert out["status"] == "SOURCE_SPAN_UNVERIFIED"
    claims=check_typed_original_facts(r,[{"field":"nmck","value":1000000}])
    assert claims["claims"][0]["status"] == "SOURCE_CORPUS_OR_REVISION_UNRESOLVED"
    assert claims["bid_ready"] is False


def test_source_defined_eis_facts_match_and_contradict_without_live_claim():
    xml=purchase_xml("1000000.00","2026-10-16T10:00:00+03:00")
    report=research_full_corpus([d("n","notice",xml)])
    out=check_typed_original_facts(report,[
        {"field":"nmck","value":"1 000 000,00"},
        {"field":"submission_deadline","value":"2026-10-16T10:00:00+03:00"},
        {"field":"nmck","value":"1 200 000"},
        {"field":"submission_deadline","value":"2026-10-17T10:00:00+03:00"},
        {"field":"evaluation_criteria","value":"Quality is scored 60%"},
    ])
    status=[c["status"] for c in out["claims"]]
    assert status==[
        "MATCHES_HISTORICAL_EIS_SOURCE",
        "MATCHES_HISTORICAL_EIS_SOURCE",
        "CONTRADICTED_BY_HISTORICAL_EIS_SOURCE",
        "CONTRADICTED_BY_HISTORICAL_EIS_SOURCE",
        "UNKNOWN_NOT_ATTESTED",
    ]
    assert all(not c["current_official_revision_attested"] for c in out["claims"])
    assert all(not c["semantic_entailment_verified"] for c in out["claims"])
    assert out["bid_ready"] is False


def test_contradictory_notices_unknown_regardless_of_file_sort_order():
    originals=[
        d("old","notice",purchase_xml("1000000","2026-10-16T10:00:00+03:00")),
        d("new","notice",purchase_xml("900000","2026-10-17T10:00:00+03:00")),
    ]
    for docs in (originals, originals[::-1]):
        r=research_full_corpus(docs)
        checked=check_typed_original_facts(r,[{"field":"nmck","value":900000}])
        assert checked["claims"][0]["status"]=="SOURCE_CORPUS_OR_REVISION_UNRESOLVED"


def test_synthetic_223_fz_and_b2b_procedures_never_inherit_eis_authority():
    for text in (
        "223-ФЗ: Открытый запрос предложений, критерий цена 40%, качество 60%.",
        "B2B: коммерческий запрос предложений, NMC 800000 рублей.",
    ):
        r=research_full_corpus([d("business","supporting",text)])
        result=check_typed_original_facts(r,[
            {"field":"nmck","value":800000},
            {"field":"evaluation_criteria","value":"40%/60%"},
        ])
        assert all(c["status"]=="UNKNOWN_NOT_ATTESTED" for c in result["claims"])
        assert all(not c["semantic_entailment_verified"] for c in result["claims"])


def test_archived_real_eis_source_matches_registered_values():
    root=Path("/tmp/ta-apr03b-archived-local-llm-20261014/runs/toa-run-20261012200402-7249ed/normalized")
    if not root.is_dir():
        return  # external read-only original replay is exercised separately on Mac mini
    real=(root/"file-01-notice.txt").read_text(encoding="utf-8")
    report=research_full_corpus([d("FILE-01","notice",real)])
    verified=check_typed_original_facts(report,[
        {"field":"nmck","value":"1000000.00"},
        {"field":"submission_deadline","value":"2026-10-16T10:00:00+03:00"},
    ])
    assert [x["status"] for x in verified["claims"]]==[
        "MATCHES_HISTORICAL_EIS_SOURCE", "MATCHES_HISTORICAL_EIS_SOURCE",
    ]
    assert all(not x["current_official_revision_attested"] for x in verified["claims"])
