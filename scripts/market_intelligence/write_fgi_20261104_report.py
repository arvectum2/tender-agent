"""Textual source ledger and per-case field backlog for client reporting."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path

ROOT=Path("docs/market_intelligence")
SNAP=Path("data/market_intelligence/power_quality/fgi_full_corpus_20261104.v1.json")
FIELDS={
 "identity":("id","notice","regime","platform","date","buyer","buyer_inn","organizer","beneficiary","project"),
 "technical":("family","scope","description","voltage_kv","rated_power","quantity","model"),
 "financial":("nmck","bid","contract_price","equipment_only_price","paid_amount","contract_no","contract_date"),
 "participants":("bidder","bidder_inn","signed_supplier","epc","designer","oem","protocol_bidders"),
 "outcome":("status","contract_signed_verified","signed_supplier_verified","oem_verified","paid_verified"),
 "sources":("sources",),
}
def clean(x,limit=100):
    s=" ".join(str(x or "—").split()).replace("|","/")
    return s if len(s)<=limit else s[:limit-1].rsplit(" ",1)[0]+"…"
def audit(d):
    cases=[];counts=collections.Counter()
    for r in d["items"]:
        gaps={}
        for group,fields in FIELDS.items():
            gaps[group]=[]
            for key in fields:
                value=r.get(key)
                if value in (None,"",[],{},False):gaps[group].append(key)
                else:counts[key]+=1
        if gaps["identity"] or r["evidence_grade"]=="C":stage="P1: оригиналы, заказчик, даты"
        elif gaps["technical"]:stage="P2: ТЗ, номинал и комплектация"
        elif gaps["participants"]:stage="P3: протокол, роли сторон"
        elif gaps["financial"]:stage="P4/P5: договор, исполнение, оплата"
        else:stage="Редакторская проверка"
        cases.append({"id":r["id"],"buyer":r["buyer"],
           "grade":r["evidence_grade"],
           "present_fields":sum(len(x) for x in FIELDS.values())-sum(len(x) for x in gaps.values()),
           "total_fields":sum(len(x) for x in FIELDS.values()),
           "missing_fields":gaps,"priority":stage,
           "url_count":len(r["sources"]),"case_status":r["status"]})
    return {"schema":"arvectum-fgi-client-evidence-audit/20261104",
            "as_of":d["as_of"],"lots":len(d["items"]),
            "fields":{k:list(v) for k,v in FIELDS.items()},
            "field_counts":dict(sorted(counts.items())),
            "case_coverage":cases,"grade_counts":d["grade_counts"],
            "caveat":"A populated field is not proof of source verification; unknown does not mean zero."}
def header(d,assessment):
    rows=d["items"];n=len(rows);g=d["grade_counts"];c=assessment["field_counts"]
    source=json.dumps(d,ensure_ascii=False,sort_keys=True,indent=2)+"\n"
    sha=hashlib.sha256(source.encode()).hexdigest()
    lines=[
        "# ARVECTUM — полный отчёт Power Quality",
        "",
        "Дата исследования: 4 ноября 2026 года. Исторический диапазон: 2023–2026.",
        "",
        f"Корпус: {n} уникальных лотов; {d['distinct_procedures']} ID процедур;",
        f"{d['eis_223_notices']} извещений ЕИС 223-ФЗ ({d['eis_223_lots']} лотов).",
        "",
        f"Уровни источников (по лоту): A={g.get('A',0)}, B={g.get('B',0)}, C={g.get('C',0)}, D={g.get('D',0)}.",
        "Оригинал одного документа не подтверждает все поля сделки.",
        "",
        "Материалы:",
        "",
        "- [Русский PDF — 406 слайдов](ARVECTUM_FGI_PQ_EXHAUSTIVE_RU_20261104.pdf)",
        "- [English PDF — 406 slides](ARVECTUM_FGI_PQ_EXHAUSTIVE_EN_20261104.pdf)",
        "- [Неизменяемый JSON-корпус](../../data/market_intelligence/power_quality/fgi_full_corpus_20261104.v1.json)",
        "- [Аудит заполненности](ARVECTUM_FGI_PQ_AUDIT_20261104.json)",
        "- [Все сохранённые адреса источников](ARVECTUM_FGI_PQ_SOURCE_LEDGER_20261104.md)",
        "",
        "SHA-256 исходного JSON: "+sha,
        "",
        "## Интерпретация",
        "",
        "Спрос включает УКРМ, БСК, STATCOM/SVG, SVC/тиристорную компенсацию, фильтры гармоник, компоненты и EPC.",
        "Это НЕ реестр завершённых контрактов и не полный рынок России. НМЦ, предложение, договор, цена устройства и оплата не складываются в единую выручку.",
        "",
        "## Сегменты",
        "",
        "| Вид работ | Лотов |","|---|---:|",
    ]
    for k,v in sorted(d["scope_counts"].items(),key=lambda x:x[1],reverse=True):
        lines.append(f"| {k} | {v} |")
    lines.extend(["", "## Полнота важных полей", "", "| Поле | Заполнено / всего |", "|---|---:|"])
    for k in ("buyer_inn","nmck","bid","contract_price","equipment_only_price",
        "contract_signed_verified","signed_supplier_verified","paid_verified",
        "voltage_kv","rated_power","quantity","model","oem_verified","bidder","protocol_bidders"):
        lines.append(f"| {k} | {c.get(k,0)} / {n} |")
    return lines,sha
def append_rows(lines,d):
    rows=d["items"]
    lines.extend(["","## Реестр всех уникальных закупок","","Одна строка = один канонический лот. Порядок совпадает с PDF-приложениями.",
       "",
       "| № | Канонический ID | Заказчик | Предмет / технология | Вид | НМЦ ₽ | Договор ₽ | Класс |",
       "|---:|---|---|---|---|---:|---:|:---:|"])
    for i,r in enumerate(rows,1):
        first=r["sources"][0]["url"] if r["sources"] else None
        linked=f"[{clean(r['id'],62)}]({first})" if first else clean(r["id"],62)
        lines.append("| "+" | ".join([
          str(i),linked,clean(r["buyer"],47),
          clean(r["description"] or r["project"],78),
          clean(r["scope_group"],28),clean(r["nmck"],21),
          clean(r["contract_price"],21),r["evidence_grade"]])+" |")
    lines.extend(["", "## Границы использования", "",
       "- Нет права выводить подписавшего поставщика из одного протокольного победителя.",
       "- Без выделенной номенклатуры цена комплексного EPC не равна цене УКРМ/STATCOM.",
       "- Отсутствие строки оплаты или OEM — не доказательство отсутствия факта.",
       "- Существующие URL могут стать недоступны после выгрузки; исторический SHA не подтверждает их доступность на текущую дату.",
       "- Каждый из 123 лотов представлен на трёх отдельных страницах PDF; шесть случаев с исходными списками участников дополнены отдельными страницами протоколов.",
       ""])
def source_ledger(d):
    lines=["# ARVECTUM — исходные URL полного корпуса на 4 ноября 2026 года","",
       "Сохранённый источник может быть оригиналом, агрегатором или исторической архивной ссылкой. URL не гарантирует доступность страницы сегодня.",
       ""]
    count=0
    for i,row in enumerate(d["items"],1):
        lines.extend([f"## {i:03d}. {row['id']} — {clean(row['buyer'],95)}",
                      "",
                      f"Категория: {row['scope_group']}; уровень записи: {row['evidence_grade']}.",
                      "",
                      "| № | Класс исходной карточки | URL | SHA-256 |",
                      "|---:|---|---|---|"])
        if not row["sources"]:
            lines.append("| — | — | Первичный URL не сохранён | — |")
        for j,s in enumerate(row["sources"],1):
            count+=1
            url=s["url"]
            lines.append("| "+" | ".join([str(j),clean(s["tier"],65),
                  "[Открыть источник]("+url+")",str(s["sha256"] or "Не сохранён")])+" |")
        lines.append("")
    return "\n".join(lines).rstrip()+"\n",count
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--snapshot",type=Path,default=SNAP)
    parser.add_argument("--outdir",type=Path,default=ROOT)
    args=parser.parse_args()
    d=json.loads(args.snapshot.read_text(encoding="utf8"))
    assert d["unique_lots"]==len(d["items"])==len({r["id"] for r in d["items"]})
    results=audit(d)
    args.outdir.mkdir(parents=True,exist_ok=True)
    report_lines,sha=header(d,results);append_rows(report_lines,d)
    (args.outdir/"ARVECTUM_FGI_PQ_FULL_REPORT_20261104.md").write_text(
        "\n".join(report_lines).rstrip()+"\n",encoding="utf8")
    (args.outdir/"ARVECTUM_FGI_PQ_AUDIT_20261104.json").write_text(
        json.dumps(results,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    ledger,nsource=source_ledger(d)
    (args.outdir/"ARVECTUM_FGI_PQ_SOURCE_LEDGER_20261104.md").write_text(ledger,encoding="utf8")
    print(json.dumps({"lots":len(d["items"]),"audit_cases":len(results["case_coverage"]),
      "source_links":nsource,"sha256":sha},ensure_ascii=False))
if __name__=="__main__":
    main()
