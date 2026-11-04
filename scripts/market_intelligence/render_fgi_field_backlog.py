"""Human-readable, stable 117-lot source-enrichment queue from field-audit JSON."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

DEFAULT=Path("docs/market_intelligence/ARVECTUM_FGI_PQ_FIELD_AUDIT_20261030_v2.json")
def md_escape(s):
    return str(s).replace("|","/").replace("\n"," ")[:100]

def render(d):
    lines=[
        "# ARVECTUM — очередь доказательного заполнения карточек",
        "",
        f"Срез: {d['snapshot_date']}; {d['lots']} юридических лотов. Стандарт: [v1.0](ARVECTUM_CLIENT_REPORT_STANDARD_V1.md).",
        "",
        "**Важно:** наличие значения в исходной карточке не означает независимую проверку. Не заменять неизвестное нулём. Все изменения полей основывать на конкретном источнике и SHA оригинала.",
        "",
        "## 1. Сводка обязательных полей",
        "",
        "| Поле | Заполнено | Требует проверки / дополнения |",
        "|---|---:|---:|",
    ]
    for key,n in sorted(d["field_coverage"].items(),key=lambda kv:(kv[1],kv[0])):
        lines.append(f"| `{key}` | {n} | {d['lots']-n} |")
    lines.extend(["","## 2. Приоритеты", "",
                  "| Источник A | Источник B | Источник C | Источник D |",
                  "|---:|---:|---:|",
                  f"| {d['source_grades'].get('A',0)} | {d['source_grades'].get('B',0)} | {d['source_grades'].get('C',0)} | {d['source_grades'].get('D',0)} |",
                  "",
                  "P0/P1: первичные документы, заказчик/ИНН, дата, номер и результат.",
                  "P2: номинал оборудования, реактивная мощность, количество и модель по ТЗ.",
                  "P3: комиссия и победитель с ИНН, включая реквизиты протокола.",
                  "P4: подписанный договор, цена всего объекта и оборудования отдельно.",
                  "P5: изготовитель, поставка, факт оплаты.",
                  "",
                  "## 3. Досье по каждому лоту",
                  "",
                  "| № | Канонический ID | Заказчик | Класс источника | Заполнено | Следующий шаг | Все неизвестные поля |",
                  "|---:|---|---|:---:|---:|---|---|"])
    for idx,r in enumerate(d["cases"],1):
        missing=[k for v in r["missing_fields"].values() for k in v]
        filled=sum(len(v) for v in r["filled_fields"].values())
        lines.append("| "+" | ".join([
            str(idx),f'`{md_escape(r["id"])}`',md_escape(r["buyer"]),
            r["source_grade"],str(filled)+"/"+str(d["fields_expected_each"]),
            md_escape(r["next_priority"]),", ".join(f"`{md_escape(k)}`" for k in missing),
        ])+" |")
    lines.extend(["","## 4. Запреты","",
                  "- Не ставить `verified` в отсутствие первичного документа именно данного факта.",
                  "- Не считать сумму EPC, ПИР или сервиса ценой самого STATCOM/УКРМ.",
                  "- Не объявлять победителя комиссии договорным поставщиком или изготовителем.",
                  "- Не обновлять старый источник без версионного backup, точного lot-ID и readback.",
                  "- Не выдавать 117 лотов за 117 подписанных контрактов.",""])
    return "\n".join(lines)+"\n"

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--audit",type=Path,default=DEFAULT)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    d=json.loads(a.audit.read_text(encoding="utf8"))
    a.out.write_text(render(d),encoding="utf8")
    print(f"Written {a.out}, {len(d['cases'])} case rows")
if __name__=="__main__":main()
