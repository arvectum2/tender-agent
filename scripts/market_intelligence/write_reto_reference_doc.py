"""Source-to-field crosswalk and requirements for one benchmark procurement."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

SOURCE=Path("data/market_intelligence/power_quality/exemplars/reto_32616181358_20261031.v1.json")
OUTPUT=Path("docs/market_intelligence/ARVECTUM_RETO_REFERENCE_DOSSIER_20261031.md")

def text(value):
    return str("Не установлено" if value is None else value).replace("|","/").replace("\n"," ")[:210]

def render(case):
    fields=case["field_evidence"]
    summary=Counter(x["status"] for x in fields)
    lines=[
        "# Эталон Arvectum — закупка 32616181358",
        "",
        "Срез 31 октября 2026. Юридический лот 223fz:32616181358:lot1.",
        "",
        "## Материалы",
        "",
        "- [Основной слайд RU](ARVECTUM_RETO_REFERENCE_SLIDE_RU_20261031.pdf) / [EN](ARVECTUM_RETO_REFERENCE_SLIDE_EN_20261031.pdf)",
        "- [Досье RU: 3 слайда](ARVECTUM_RETO_REFERENCE_RU_20261031.pdf) / [EN: 3 slides](ARVECTUM_RETO_REFERENCE_EN_20261031.pdf)",
        "- [Превью RU](ARVECTUM_RETO_REFERENCE_SLIDE_RU_20261031.png) / [EN](ARVECTUM_RETO_REFERENCE_SLIDE_EN_20261031.png)",
        "",
        "## Установлено из первичных документов",
        "",
        "Исходное ТЗ: 10 конденсаторов КЭПФ на 12 кВ, по пять штук на 450 и 600 квар; всего 5,25 Мвар. НМЦ 3 078 500 ₽, включая НДС 22%.",
        "",
        "Оригинальный протокол комиссии №186-2 от 03.08.2026: три заявки, две допущены; победитель — ООО «ЭКСПЕРТ ГРУПП» (ИНН 7720494275), предложение 3 050 000 ₽. Заявка завода «КВАР» (1 960 906 ₽) отклонена из-за отсутствия справки КНД 1120101 и технического несоответствия по току модели на 600 квар.",
        "",
        "Исторический реестр ЕИС: договор №060-26-Р от 19.08.2026, регистрационный №57724646338260000460000, 3 050 000 ₽. Сейчас оригинальная веб-страница ЕИС HTTP 404 — эти значения отмечены как архивные и независимо не переудостоверены.",
        "",
        "Подписант договора, изготовитель, страна фактического изготовления, отгрузка и оплата не установлены. Республика Казахстан в архиве — страна регистрации изготовителя, не доказательство страны происхождения. Компоненты БСК не являются готовым SVG/STATCOM.",
        "",
        "## Источники и SHA оригиналов",
        "",
        "| ID | Источник | Степень | SHA-256 |",
        "|---|---|---|---|",
    ]
    for key,src in case["source_provenance"].items():
        lines.append("| "+ " | ".join([key,
          "["+text(src["label"])+"]("+src["url"]+")",
          src["grade"],src["sha"]])+" |")
    lines.extend([
        "",
        "## Поле → значение → документ",
        "",
        f"Всего {len(fields)} полей: "+", ".join(f"{k}={v}" for k,v in sorted(summary.items())),
        "",
        "| Поле | Значение | Статус | Подтверждает |",
        "|---|---|---|---|",
    ])
    for field in fields:
        lines.append("| "+" | ".join([field["field"],text(field["value"]),
              field["status"],", ".join(field["source_ids"]) or "—"])+" |")
    lines.extend([
       "",
       "## Правила применения к другим закупкам",
       "",
       "- Всегда иметь источник и отдельную доказательность по каждому полю.",
       "- Отдельно отображать НМЦ, предложенную сумму, зарегистрированный договор, оборудование и платеж.",
       "- Победитель протокола, подписавшая сторона, EPC, проектировщик и OEM не подменяют друг друга.",
       "- Номинал оборудования проверять по ТЗ, не по классу подстанции.",
       "- Когда оригинала нет, писать «не установлено» и указывать причину.",
       "- Основной слайд — суть и вывод, страницы приложения — инженерия, экономика, протокол и источники.",
       "- Без выдуманного логотипа, микрошрифтов, скрытого текста и подмены источника.",
       "",
    ])
    return "\n".join(lines)
if __name__=="__main__":
    case=json.loads(SOURCE.read_text(encoding="utf8"))
    OUTPUT.write_text(render(case)+"\n",encoding="utf8")
    print("report",OUTPUT,OUTPUT.stat().st_size)
