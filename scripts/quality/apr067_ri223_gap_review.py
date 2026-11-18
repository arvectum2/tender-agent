"""Post-baseline source-led review, not independent gold."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.modules.tender_operator_agent_demo.evidence_document_search import (
    checked_search_run,
)
from src.modules.tender_operator_agent_demo.evidence_ri223_archive import (
    ri223_archive_observation,
)
from src.modules.tender_operator_agent_demo.ri223_review_dossier import (
    verified_inventory,
)
from src.modules.tender_operator_agent_demo.verified_original_quote import (
    verify_operator_run_quote,
)

_BASELINE_SHA = "850f7b0f9a77661d8fa9800c2fc8f568d239dcc807dfbb9efaf69831125a1e37"
_BASELINE = Path("docs/quality/APR067_RI223_DOMAIN_COVERAGE_2026-11-18.json")
_DOCS = {
    "32616445632": "066252cac6ba7d9bfc876c9ac9a5e5425df31497fe37683dd7cdc5bdf4fa2558",
    "32616445866": "a8645964df2203e09abb34dd9d64b88c8bea607031ebde80ff89362914979550",
    "32616447910": "297e426b920b361ec90b323fdf1444eeb3d709b858216ef14a2aabdb6f07b908",
}
_QUOTES = {
    "32616445632": {
        "notice": "Настоящее извещение информируют о заключении договора с единственным поставщиком и не предназначено для приглашения исполнителей подавать заявки на участие в закупке, участниками закупки могут быть только субъекты малого и среднего предпринимательства.",
    },
    "32616445866": {
        "notice": "Размещение настоящего Извещения носит уведомительный характер – договор заключается с единственным поставщиком (подрядчиком, исполнителем), без проведения конкурен тных процедур, согласно Положению о закупке,",
        "subject": "Предмет договора Выполнение работ по проектированию, разработке, адаптации и тестированию клиентской части (Frontend) веб -интерфейса программного продукта UP EASM",
        "sme": "Закупка проводится только для субъектов малого и среднего предпринимательства",
        "schedule": "Сроки поставки товара, выполнения работ, оказания услуг В соответствии с условиями договора",
        "no_docs": "Документация не предоставляется. Размещение настоящего Извещения носит уведомительный характер.",
    },
    "32616447910": {
        "notice": "Извещение носит уведомительный характер и не предполагает при его размещении в ЕИС подачу со стороны участников закупки каких-либо заявок, документов, сведений,",
        "subject": "Наименование и описание предмета закупки: В соответствии с условиями договора.",
        "contract": "Возможность заказчика изменить условия договора: В соответствии с условиями договора. Информация о возможности одностороннего отказа от исполнения договора: В соответствии с условиями договора.",
        "funding": "Источник финансирования Оплата производится за счет средств, полученных от предпринимательской деятельности.",
    },
}
_PLAN = {
    "32616444788": {"evaluation": ("EXTERNAL_REGULATION_REFERENCE_ONLY", "xml")},
    "32616445632": {"evaluation": ("NOTICE_NOT_INVITATION_REVIEW", "notice")},
    "32616445866": {
        "technical_scope": ("SUBJECT_ONLY", "subject"),
        "qualification": ("SME_ONLY_NOT_FULL_QUALIFICATION", "sme"),
        "application": ("NOTICE_NOT_COMPETITIVE_REVIEW", "notice"),
        "evaluation": ("NOTICE_NOT_COMPETITIVE_REVIEW", "notice"),
        "schedule": ("CONTRACT_REFERENCE_ONLY", "schedule"),
        "payment": ("TERMS_UNKNOWN_DOCUMENTATION_NOT_PROVIDED", "no_docs"),
        "security": ("TERMS_UNKNOWN_DOCUMENTATION_NOT_PROVIDED", "no_docs"),
    },
    "32616447910": {
        "technical_scope": ("CONTRACT_REFERENCE_ONLY", "subject"),
        "qualification": ("UNKNOWN_NO_REQUIREMENT_ATTESTED", None),
        "application": ("NOTICE_NOT_INVITATION_REVIEW", "notice"),
        "evaluation": ("NOTICE_NOT_INVITATION_REVIEW", "notice"),
        "contract": ("CONTRACT_REFERENCE_ONLY", "contract"),
        "participation": ("UNKNOWN_NO_REQUIREMENT_ATTESTED", None),
        "payment": ("FUNDING_ONLY_PAYMENT_TERMS_UNKNOWN", "funding"),
    },
}


def baseline_gaps():
    raw = _BASELINE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != _BASELINE_SHA:
        raise ValueError("Frozen baseline changed")
    data = json.loads(raw)
    gaps = {(r["case"],d) for r in data["cases"] for d,n in r["counts"].items() if n == 0}
    if gaps != {(n,d) for n,plan in _PLAN.items() for d in plan} or len(gaps) != 16:
        raise ValueError("Frozen gap denominator mismatch")
    return gaps


def observe(run_id):
    run,meta=checked_search_run(run_id)
    n=meta.get("procurement_id")
    if n not in _PLAN:
        return []
    inventory=verified_inventory(run,meta)
    notice=ri223_archive_observation(run,meta)
    if not inventory["archived_bytes_complete"] or not inventory["projection_complete"] or notice["status"]!="PINNED_RI223_ARCHIVED_NOTICE":
        raise ValueError("Verified complete archived originals required")
    result=[]
    cache={}
    for domain,(label,key) in _PLAN[n].items():
        if key not in cache:
            ev=None
            if key=="xml":
                field="archived_summingup_order"
                matches=[c for c in notice["citations"] if c["source_ref"].endswith(":"+field) and c["excerpt"]==notice["fields"].get(field)]
                if len(matches)==1 and "18.6." in matches[0]["excerpt"] and "Положения о закупке" in matches[0]["excerpt"]:
                    ev=matches[0]
            elif key:
                sha=_DOCS[n];quote=_QUOTES[n][key]
                matches=[f for f in meta["files"] if f.get("source")=="ri223_attachment" and f.get("data_platform_source",{}).get("canonical_uri")=="tender-upload://"+sha]
                if len(matches)==1:
                    checked=verify_operator_run_quote(run_id=run_id,file_id=matches[0]["file_id"],exact_quote=quote)
                    candidate=checked.get("evidence")
                    if checked.get("status")=="literal_quote_found_in_extracted_original_only" and isinstance(candidate,dict) and candidate.get("original_sha256")==sha and candidate.get("quote")==quote:
                        ev=candidate
            cache[key]=ev
        ev=cache[key]
        result.append({"case":n,"domain":domain,"status":label if ev or key is None else "UNKNOWN_SOURCE_QUOTE_UNVERIFIED",
                       "evidence":ev,"requirements_verified":False,"legal_applicability_attested":False})
    current,latest=checked_search_run(run_id)
    if current!=run or latest!=meta or verified_inventory(run,meta)!=inventory or ri223_archive_observation(run,meta)!=notice:
        raise ValueError("Source changed during gap review")
    return result


def summarize(rows):
    if {(r["case"],r["domain"]) for r in rows}!=baseline_gaps() or len(rows)!=16:
        raise ValueError("Gap rows incomplete or duplicated")
    if any(r["requirements_verified"] or r["legal_applicability_attested"] for r in rows):
        raise ValueError("Improper promotion")
    return {"scope":"POST_BASELINE_SOURCE_LED_GAP_REVIEW_ONLY","frozen_baseline_cited":29,"frozen_baseline_total":45,
            "gaps_reviewed":16,"gaps_with_contextual_source":sum(bool(r["evidence"]) for r in rows),
            "rows_without_source":sum(not r["evidence"] for r in rows),"rows":rows,
            "changed_baseline":False,"semantic_precision":None,"semantic_recall":None,
            "independent_gold":False,"commercial_acceptance":False,"go_eligible":False}
