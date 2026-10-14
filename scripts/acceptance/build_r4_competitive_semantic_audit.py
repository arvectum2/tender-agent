"""Reproduce twenty first-party historical competitive EIS original reviews.

Read-only private pinned input originals; separate customer prose and internal
machine evidence. No current procurement status, legal eligibility or GO.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))

from src.modules.tender_operator_agent_demo.r4_official_competitive_cohort import (
    validate_cohort,verify_original_notice,
)
from src.modules.tender_operator_agent_demo.r4_original_claim_audit import (
    audit_claims,index_binary_receipts,
)

_PINS={
    "selection":"93f72ba5127f21c9b7744688da2b375d80779a49d64243155e6657ff4d436da1",
    "claims":"eb30969ac4bd421094a09573119e3710962ead7649c3bbe2fe72e579e257bd2e",
    "binaries":"4f453e12c0013a200422990bf65a96fdfc476be6eda2b69065d18115391d9822",
}


def _pinned(path:Path,pin:str)->dict:
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=pin:
        raise ValueError("historical source proof is not byte-identical to pinned original")
    return json.loads(raw)


def build_review(originals:Path)->dict:
    ai=originals/"ai-expert-20261012"
    selected=_pinned(
        ai/"positive-eis-replacements-20261012/verified-competitive-20-plus-four-negative.json",
        _PINS["selection"],
    )
    expert=_pinned(ai/"rdc-expert-packet-20261012.json",_PINS["claims"])
    filestore=_pinned(originals/"independent-20261012/official-filestore-72-attachment-audit.json",_PINS["binaries"])
    cohort=validate_cohort(selected)
    official=[]
    for item in selected["positive_cases"]:
        base=(
            ai/"positive-eis-replacements-20261012"
            if item["role"]=="NEW_OFFICIAL_POSITIVE_REPLACEMENT"
            else originals/"independent-20261012"
        )
        packet=verify_original_notice(item,base/item["reg_number"]/"documentation-archive.zip")
        packet["source_class"]="COMPETITIVE_HISTORIC_ORIGINAL"
        official.append(packet)
    special=next(i for i in selected["negative_cases"] if i.get("notice"))
    negative_archive=verify_original_notice(
        special,originals/"independent-20261012"/special["reg_number"]/"documentation-archive.zip"
    )
    source_binary=index_binary_receipts(filestore)
    claims=audit_claims(
        expert,ai/"tender_operator_demo",source_binary,
        {item["reg_number"] for item in selected["positive_cases"]},
    )
    negatives=[{"registry_number":n["reg_number"],
                "reason":n["noncompetitive_reason"],
                "bid_ready":False} for n in selected["negative_cases"]]
    report={
        "scope":"HISTORIC_FIRST_PARTY_OFFICIAL_20_COMPETITIVE_4_NEGATIVE_NOT_LIVE",
        "methodology":"Original ZIP and notice XML exact SHA+type; historic model source quotes only; legal interpretation not attested",
        "source_cohort":cohort,
        "official_source_verified":len(official)+1,
        "competitive_notices":sorted(official,key=lambda v:v["registry_number"]),
        "special_noncompetitive_original":negative_archive,
        "negative_controls":sorted(negatives,key=lambda v:v["registry_number"]),
        "separate_official_reserve":selected["reserve_case"]["reg_number"],
        "saved_model_claims":claims,
        "current_official_EIS_state_verified":False,
        "full_contract_semantic_review_signed":0,
        "human_gold_review_signed":0,
        "bid_ready":False,
    }
    return report


def readable_review(review:dict)->str:
    items=review["competitive_notices"]
    claim_map={c["registry_number"]:c for c in review["saved_model_claims"]["cases"]}
    lines=[
        "# Независимая проверка 20 конкурентных закупок по документам ЕИС",
        "",
        "**Основа:** ранее сохранённые оригиналы официальных извещений и отдельные исходные вложения. "
        "Проверены целостность документов, вид процедуры и буквальная доказательная опора сохранённых цитат. "
        "Это анализ архивных редакций, не подтверждение действующего приёма заявок.",
        "",
        "## Существенные результаты",
        "",
        "- Из исходной выборки исключены три запроса ценовой информации и одна специальная закупка у единственного поставщика. "
        "Для полноценной двадцатки добавлены четыре независимо подтверждённых конкурентных извещения ЕИС.",
        "- Исходные архивы и тексты извещений проверены по контрольным суммам для всех 20 конкурентных процедур, "
        "а также отдельно для специальной закупки.",
        "- Наличие цитаты в тексте ещё не доказывает правильность юридического вывода модели. "
        "Поэтому ни одна процедура не получила автоматического разрешения на участие.",
        "",
        "## По каждой конкурентной процедуре",
        "",
        "| № | Номер извещения | Способ определения поставщика | Последняя выбранная архивная редакция | Срок из архива | Состояние выводов |",
        "|---:|---|---|---:|---|---|",
    ]
    methods={
        "COMPETITIVE_ELECTRONIC_AUCTION":"Электронный аукцион",
        "COMPETITIVE_ELECTRONIC_QUOTATIONS":"Электронный запрос котировок",
        "COMPETITIVE_OPEN_ELECTRONIC_COMPETITION":"Открытый конкурс в электронной форме",
    }
    for i,case in enumerate(items,1):
        n=case["registry_number"]
        saved=claim_map.get(n)
        state=("Сохранённые цитаты проверены, смысл и полнота требуют экспертизы"
               if saved else "Нет проверенного анализа содержания по этой записи")
        deadline=case["archived_submission_end"] or "В исходной редакции не подтверждён"
        lines.append(
            f"| {i} | {n} | {methods[case['method']]} | {case['archived_version']} | {deadline} | {state} |"
        )
    lines.extend([
        "",
        "## Выявленные ограничения и необходимые проверки",
        "",
        "- Даты в таблице относятся исключительно к сохранённым архивам. "
        "У двух старых модельных отчётов сроки подачи противоречили позднейшей архивной редакции "
        "(0158300034526000388 и 0348100024426000039). До новой проверки ЕИС сроки нельзя использовать.",
        "- Для части закупок отдельные DOC/DOCX/PDF не входят в ZIP извещения. "
        "Контрольная сумма XML не заменяет проверку исходного проекта контракта и полного ТЗ.",
        "- Проверка буквального совпадения фрагмента с документом не устанавливает, что вывод о гарантиях, "
        "ответственности, лицензиях, трудоёмкости или допускающих условиях юридически корректен.",
        "- Для каждой закупки необходимы актуальная официальная редакция, полный набор документов, "
        "проверка существенных условий договора и независимое утверждение экспертного заключения.",
        "",
        "## Записи, исключённые из конкурентной выборки",
        "",
        "- 0148300050426000047 — официальный запрос ценовой информации.",
        "- 0318200087026000163 — официальный запрос ценовой информации.",
        "- 0348100024426000052 — официальный запрос ценовой информации.",
        "- 0349500000226000003 — специальная закупка у единственного поставщика.",
        "",
        "**Итог:** исторический источник проверен. Юридическая готовность, право участия, актуальный срок "
        "подачи заявок и коммерческое решение не удостоверены ни для одной из 20 процедур.",
        "",
    ])
    text="\n".join(lines)
    for forbidden in ("no_data","getDocsIP","Traceback","UNKNOWN/DEFER","HTTP 409","fallback_deterministic_adapter"):
        if forbidden in text:
            raise ValueError("technical diagnostics present in customer source review")
    return text


def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--source-root",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    args=parser.parse_args()
    packet=build_review(args.source_root)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    (args.output_dir/"r4-20-competitive-original-source-audit.json").write_text(
        json.dumps(packet,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf8"
    )
    (args.output_dir/"r4-20-competitive-independent-client-review.md").write_text(
        readable_review(packet),encoding="utf8"
    )
    print(json.dumps({"official_verified":packet["official_source_verified"],
        "competitive":packet["source_cohort"]["competitive"],
        "negative":packet["source_cohort"]["negative"],
        "claim_checks":packet["saved_model_claims"]["claims"],
        "human_signed":packet["human_gold_review_signed"]},sort_keys=True))


if __name__=="__main__":
    main()
