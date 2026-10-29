"""Read-only client report from the PQ research corpus; never infer market TAM."""

from __future__ import annotations

import argparse
import collections
import html
import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlsplit

from scripts.market_intelligence.append_pq_delta_20261029 import psql

REPORT = Path("docs/market_intelligence/POWER_QUALITY_CLIENT_PREVIEW_20261024.html")
HOSTS = {
    "zakupki.gov.ru",
    "www.b2b-center.ru",
    "bidzaar.com",
    "etpgpb.ru",
    "www.tektorg.ru",
    "zakaz.etp-region.ru",
    "www.roseltorg.ru",
    "sibur.ru",
    "www.sibur.ru",
    "uds-group.ru",
    "synapsenet.ru",
    "zakupki.kontur.ru",
    "rostender.info",
    "energybase.ru",
    "www.tender.pro",
    "tender.pro",
    "zakupki.tochka.com",
    "vsem-podryad.ru",
    "b2b.house",
    "www.dv-tender.ru",
    "www.tenderguru.ru",
    "kontendus.ru",
    "tender.lot-online.ru",
}
FAMILIES = {
    "ukrm": "УКРМ",
    "capacitor_bank": "БСК",
    "statcom": "STATCOM / SVG",
    "svc": "SVC / СТК",
    "svc_thyristor": "SVC / СТК",
    "harmonic_filter": "Фильтры гармоник",
    "harmonic_filters": "Фильтры гармоник",
    "capacitor_components": "Конденсаторы",
    "capacitor_bank_component": "Конденсаторы",
    "capacitor_blocks": "Конденсаторы",
    "pq_components": "Комплектующие",
    "harmonic_filter_reactor": "Реакторы",
    "filter_compensation": "ФКУ",
    "dynamic_reactive_compensation": "Динамическая компенсация",
    "reactive_compensation_system": "Системы компенсации",
    "hybrid_reactive_power_source": "Гибридные установки",
}
SUPPLY = {
    "supply",
    "equipment_supply_new",
    "equipment_supply_request",
    "supply_candidate",
    "signed_equipment_supply",
    "supply_with_mixed_work",
    "three_year_supply_framework_not_finished_PQ_equipment",
}
COMPONENT = {"supply_components", "component_supply_voltage_unknown"}
DESIGN = {"design", "engineering_design_only", "design_harmonic_filtration"}
EPC = {
    "epc",
    "mixed_epc",
    "adjacent_epc",
    "mixed_epc_repair_services",
    "mixed_supply_install_pnr",
    "electrical_auxiliary_works",
}
SERVICE = {"maintenance", "modernization_existing_equipment"}
SURVEY = {
    "market_sounding",
    "mixed_MTR_market_sounding_with_PQ_component",
    "request_for_quotation",
}
GROUPS = [
    "Поставка / запрос",
    "Компоненты",
    "EPC / СМР",
    "Проектирование",
    "Сервис / модернизация",
    "Мониторинг цен / КП",
    "Другое",
]
SELECTED = [
    (
        "223fz:32616435269:lot1",
        "МПУ 10 кВ, 30 Мвар + БСК 110 кВ",
        "НМЦ 452,02 млн ₽ за весь смешанный комплект; оборудование 10 кВ не оценено отдельно.",
    ),
    (
        "223fz:32615614821:lot1",
        "Реконструкция с УКРМ 6 кВ, 200 квар",
        "Первичная смета содержит УКРМ; EPC/СМР не равны цене одной установки.",
    ),
    (
        "223fz:32514476448:lot1",
        "ПС Уфимка — БСК 10 кВ, 2 × 0,9 Мвар",
        "Строительные и монтажные работы; контрактная стоимость не выделяет БСК.",
    ),
    (
        "223fz:32413764701:lot1",
        "Югорск — контейнерная УКРМ 10 кВ, 150 квар",
        "Реестровая цена 4,08 млн ₽; публичный подписант не установлен.",
    ),
    (
        "223fz:32616296475:lot1",
        "Мелеуз — компенсация в сети 6 кВ",
        "ТЗ: тиристорный реактор ≥500 квар и фильтрация гармоник; победитель не установлен.",
    ),
    (
        "commercial:2128160-1:lot1",
        "Проектирование трёх БСК 6 кВ",
        "Запрос ПИР, не поставка трёх установок.",
    ),
    (
        "commercial:4643332:lot1",
        "Конденсатор КЭП3 10,5 кВ",
        "Один компонент, не комплект STATCOM.",
    ),
    (
        "223fz:32616065155:lot7",
        "Татнефть: конденсаторные установки, 1 комплект",
        "НМЦ лота 3,172 млн ₽; напряжение 6–35 кВ не подтверждено.",
    ),
    (
        "commercial:281-705:lot1",
        "Русагро: фильтры гармоник для 7 заводов",
        "Одна процедура проектирования с семью позициями; в большинстве ТЗ указан класс 0,4 кВ.",
    ),
]


def esc(value: object) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def safe_url(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > 2000:
        return None
    parsed = urlsplit(value)
    if (
        parsed.scheme == "https"
        and parsed.hostname in HOSTS
        and not parsed.username
        and not parsed.password
    ):
        return value
    return None


def rows_live() -> list[dict]:
    sql = """BEGIN READ ONLY;
SELECT jsonb_build_object('id',r.external_id,'data',d.data,'review',d.review_status)::text
FROM dp_resources r JOIN dp_records d USING(resource_id)
WHERE r.collection_id='arvectum-market-pq-6-35kv' ORDER BY r.external_id;
COMMIT;"""
    return [json.loads(line) for line in psql(sql).splitlines() if line.startswith("{")]


def validate(rows: list[dict]) -> None:
    ids = [r["id"] for r in rows]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("Empty corpus or duplicate canonical lot identity")
    for r in rows:
        if r["data"].get("canonical_id") != r["id"]:
            raise ValueError("Database canonical-id mismatch")


def buyer(row: dict) -> str:
    c = row["data"].get("customer") or {}
    name = c.get("name") if isinstance(c, dict) else c
    return str(name or "Не установлен")


def year(row: dict) -> str:
    v = row["data"].get("publication_date") or ""
    return str(v)[:4] if re.fullmatch(r"20\d\d-\d\d-\d\d", str(v)) else "неизв."


def group(row: dict) -> str:
    scope = row["data"].get("scope", "")
    for scopes, label in [
        (SUPPLY, GROUPS[0]),
        (COMPONENT, GROUPS[1]),
        (EPC, GROUPS[2]),
        (DESIGN, GROUPS[3]),
        (SERVICE, GROUPS[4]),
        (SURVEY, GROUPS[5]),
    ]:
        if scope in scopes:
            return label
    return GROUPS[6]


def price(raw: object) -> str:
    try:
        n = Decimal(str(raw))
        return (
            (f"{n:,.2f}".replace(",", " ").replace(".", ",") + " ₽") if n > 0 else "—"
        )
    except (InvalidOperation, TypeError, ValueError):
        return "—"


def links(row: dict) -> list[str]:
    found = []
    for item in row["data"].get("evidence") or []:
        url = safe_url(item.get("url")) if isinstance(item, dict) else None
        if url and url not in found:
            found.append(url)
    return found[:2]


STYLE = """
:root{color-scheme:light;--ink:#27303a;--mute:#667383;--teal:#116b72;--purple:#614a83;--orange:#ce7936;--bg:#f5f6f7;--line:#e1e7ea}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.65 system-ui,-apple-system,'Segoe UI',sans-serif}
.wrap{max-width:1290px;margin:auto;padding:32px 25px 88px}
header{background:linear-gradient(120deg,#26313c,#253540 65%,#165c66);color:#fff;border-radius:16px;padding:43px 46px}
.kicker{font-size:12px;letter-spacing:.17em;color:#9de2dc;font-weight:650;margin-bottom:10px}
h1{font-size:clamp(25px,3vw,38px);line-height:1.17;letter-spacing:-.025em;margin:0 0 16px}
h2{font-size:22px;line-height:1.3;margin:40px 0 14px;letter-spacing:-.015em}
h3{font-size:17px;margin:2px 0 8px;line-height:1.35}
header p{max-width:850px;margin:8px 0;color:#dfebee}
.metas{font-size:13px;margin-top:21px;color:#b9d2d6}
.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:13px;margin:20px 0}
.metric,.surface{background:#fff;border:1px solid var(--line);border-radius:12px}
.metric{padding:19px 19px 16px}.metric strong{font-size:31px;line-height:1.1;font-weight:700;display:block;color:#24303b}
.metric span{display:block;color:var(--mute);font-size:12px;margin-top:8px}
p{margin:10px 0}small,.sub{color:var(--mute);font-size:12px}
.callout{background:#fff;border-left:4px solid var(--orange);padding:17px 22px;margin:18px 0;line-height:1.65;border-radius:0 8px 8px 0}
.callout strong{color:#864912}
.split{display:grid;grid-template-columns:1fr 1fr;gap:16px}.surface{padding:22px 25px}
dl{margin:0}.fact{display:flex;justify-content:space-between;gap:16px;border-bottom:1px solid var(--line);padding:9px 0;font-size:14px}
.fact:last-child{border:0}.fact b{font-variant-numeric:tabular-nums}
.leads{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
.lead{border:1px solid var(--line);border-radius:12px;padding:18px 21px;background:white}
.lead h3{font-size:15px}.lead .info{font-size:13px;color:var(--mute);margin:7px 0 11px}
.pill{display:inline-block;border-radius:30px;padding:3px 10px;background:#e9f4f4;color:#176b71;font-size:11px;letter-spacing:.015em}
.pill.warn{background:#fff1e4;color:#94571f}.pill.soft{background:#eeeaf5;color:#64518b}
a{color:var(--teal);text-underline-offset:2px;overflow-wrap:anywhere}a:hover{color:#694a9a}
table{border-collapse:collapse;width:100%;font-size:12.5px}thead th{text-align:left;background:#eaf0f1;color:#334653;font-size:12px;position:sticky;top:0;z-index:2}
th,td{border-bottom:1px solid #e4eaed;padding:11px 10px;vertical-align:top}
tbody tr[hidden]{display:none}tbody tr:nth-child(even){background:#fbfcfc}tbody tr:hover{background:#f0f6f7}
td:first-child{font-family:ui-monospace,Consolas,monospace;color:#3e5665;white-space:normal;word-break:break-word}
td.price{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
.tablewrap{overflow:auto;max-height:730px;border:1px solid var(--line);border-radius:11px;background:white}
.filters{display:flex;flex-wrap:wrap;gap:12px;align-items:end;margin-bottom:13px}
.filters label{font-size:12px;color:var(--mute);display:flex;flex-direction:column;gap:4px}
input,select{font:inherit;border:1px solid #cbd6dc;border-radius:8px;padding:9px 11px;min-width:145px;background:#fff;color:var(--ink)}
input{min-width:270px;max-width:410px;width:100%}
.counter{color:var(--mute);font-size:13px;margin-left:auto}
.note{color:var(--mute);font-size:12px}ul{padding-left:21px}li{margin:8px 0}
footer{border-top:1px solid #dce3e5;margin-top:38px;padding-top:19px;color:var(--mute);font-size:12px}
@media(max-width:850px){.metrics{grid-template-columns:repeat(2,1fr)}.split,.leads{grid-template-columns:1fr}header{padding:28px}.wrap{padding:18px 14px}.tablewrap{max-height:none}}
@media print{body{background:white;font-size:11px}.wrap{max-width:none;padding:0}header{background:white;color:#1d363f;border-bottom:2px solid #116b72;border-radius:0;padding:0 0 20px}header p,.metas,.kicker{color:#516773}h1{font-size:24px}.metrics,.split{gap:7px}.metric{padding:9px}.metric strong{font-size:21px}.leads{grid-template-columns:1fr 1fr}.lead{break-inside:avoid;padding:10px}.filters{display:none}.tablewrap{max-height:none;overflow:visible}table{font-size:8.5px}th,td{padding:4px}thead th{position:static}.surface{padding:10px}a{color:#1b5964}}
"""


def count_tag(v: object) -> str:
    return f"{int(v):,}".replace(",", " ")


def selected_cards(rows: list[dict]) -> str:
    by_id = {r["id"]: r for r in rows}
    blocks = []
    for cid, title, caveat in SELECTED:
        r = by_id.get(cid)
        if r is None:
            continue
        all_links = links(r)
        source = (
            (
                f'<a href="{esc(all_links[0])}" target="_blank" rel="noopener noreferrer">'
                "Открыть источник</a>"
            )
            if all_links
            else "Оригинал требует проверки"
        )
        category = group(r)
        blocks.append(
            '<article class="lead"><span class="pill">'
            + esc(tech_label(r))
            + '</span> <span class="pill soft">'
            + esc(category)
            + "</span>"
            "<h3>"
            + esc(title)
            + '</h3><div class="info">'
            + esc(buyer(r))
            + " · "
            + esc(cid)
            + "</div><p>"
            + esc(caveat)
            + "</p>"
            '<div class="note">' + source + "</div></article>"
        )
    return "\n".join(blocks)


def tech_label(row: dict) -> str:
    return FAMILIES.get(str(row["data"].get("family") or ""), "Прочее PQ")


def row_html(row: dict) -> str:
    d = row["data"]
    evid = links(row)
    src = (
        " · ".join(
            f'<a href="{esc(u)}" target="_blank" rel="noopener noreferrer">[{i + 1}]</a>'
            for i, u in enumerate(evid)
        )
        if evid
        else "—"
    )
    desc = str(d.get("description") or d.get("project") or "Описание не опубликовано")
    if len(desc) > 220:
        desc = desc[:217].rstrip() + "…"
    st = str(d.get("status") or "").lower()
    state = (
        "Без заявок / отмена"
        if any(x in st for x in ("no_bids", "zero_bids", "cancelled"))
        else "Договор указан*"
        if any(x in st for x in ("signed", "registered_contract"))
        else "Итог скрыт"
        if "hidden" in st
        else "Требует сверки"
    )
    type_name = group(row)
    y = year(row)
    return (
        f'<tr data-year="{esc(y)}" data-group="{esc(type_name)}" '
        f'data-search="{esc((row["id"] + " " + buyer(row) + " " + desc + " " + tech_label(row)).lower())}">'
        "<td>"
        + esc(row["id"])
        + "</td><td>"
        + esc(y)
        + "</td><td>"
        + esc(buyer(row))
        + "</td><td>"
        + esc(tech_label(row))
        + "</td><td>"
        + esc(type_name)
        + "</td><td>"
        + esc(desc)
        + '</td><td class="price">'
        + esc(price(d.get("nmck_rub")))
        + "</td><td>"
        + esc(state)
        + "</td><td>"
        + src
        + "</td></tr>"
    )


def fact_line(name: str, value: object) -> str:
    return f'<div class="fact"><span>{esc(name)}</span><b>{esc(value)}</b></div>'


def render(rows: list[dict], as_of: str) -> str:
    validate(rows)
    total = len(rows)
    proc = len({r["id"].split(":")[1] for r in rows if ":" in r["id"]})
    eis = [r for r in rows if re.fullmatch(r"223fz:\d{11}:lot\d+", r["id"])]
    eis_unique = len({r["id"].split(":")[1] for r in eis})
    per_year = collections.Counter(year(r) for r in rows)
    per_group = collections.Counter(group(r) for r in rows)
    per_buyer = collections.Counter(buyer(r) for r in rows)
    assert sum(per_year.values()) == total == sum(per_group.values())
    cards = selected_cards(rows)
    allrows = "\n".join(row_html(r) for r in rows)
    metrics = "".join(
        '<div class="metric"><strong>'
        + esc(v)
        + "</strong><span>"
        + esc(k)
        + "</span></div>"
        for k, v in [
            ("Уникальных лотов", total),
            ("ID процедур", proc),
            ("Лотов ЕИС 223-ФЗ", len(eis)),
            ("Извещений ЕИС 223-ФЗ", eis_unique),
        ]
    )
    scope = "".join(fact_line(k, per_group[k]) for k in GROUPS)
    years = "".join(
        fact_line(k, per_year[k]) for k in ("2023", "2024", "2025", "2026", "неизв.")
    )
    buyers = "".join(fact_line(k, v) for k, v in per_buyer.most_common(9))
    opts = "".join(
        '<option value="' + esc(v) + '">' + esc(v) + "</option>" for v in GROUPS
    )
    linked = sum(bool(links(r)) for r in rows)
    provisional = sum(r.get("review") == "unreviewed" for r in rows)
    page = f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'">
<meta name="description" content="Arvectum Market Intelligence: закупочный спрос на Power Quality 6–35 кВ в России.">
<title>Power Quality 6–35 кВ — исследование рынка · Арвектум</title><style>{STYLE}</style></head>
<body><main class="wrap">
<header><div class="kicker">ARVECTUM / MARKET INTELLIGENCE</div>
<h1>Power Quality 6–35 кВ<br>Карта закупочного спроса в России</h1>
<p>УКРМ, БСК, STATCOM/SVG, СТК/SVC, фильтры гармоник и проекты реконструкции электросетей. Анализ публичных торгов, технических документов и предварительных сведений о договорах.</p>
<div class="metas">Россия · срез {esc(as_of)} · записи 2023–2026 · предварительная версия для заказчика</div></header>
<section class="metrics" aria-label="Размер исследовательской базы">{metrics}</section>
<div class="callout"><strong>Ограничение данных.</strong> {total} — число уникальных карточек лотов в исследовании, а не количество состоявшихся продаж. В выборке есть коммерческие запросы цен, проектирование, сервис, смешанные EPC-проекты и процедуры с неизвестным номинальным напряжением. Полнота рынка РФ, фактический оборот оборудования, доли производителей и национальная динамика <strong>не установлены</strong>. НМЦ не равна цене договора.</div>
<h2>01 / Структура найденного спроса</h2>
<div class="split"><div class="surface"><h3>По предмету закупки</h3>
<p class="note">Группировка типа работ, а не результатов контрактов.</p>{scope}</div>
<div class="surface"><h3>По году в источнике</h3><p class="note">Часть дат из вторичных карточек или требует уточнения.</p>{years}</div></div>
<p class="note">Из {total} лотов {len(eis)} имеют числовой номер ЕИС 223-ФЗ ({eis_unique} извещений); остальные {total - len(eis)} — коммерческие или нестандартные карточки. {linked} записей содержат минимум одну публичную ссылку, {provisional} пока находятся в исследовательской проверке.</p>
<h2>02 / Технически интересные проекты</h2>
<p>Отобраны конкретные случаи для квалификации оборудования и участников цепочки поставок. Это не рейтинг по стоимости и не перечень выигранных заказов.</p>
<div class="leads">{cards}</div>
<h2>03 / Карта заказчиков и действия</h2>
<div class="split"><div class="surface"><h3>Часто встречающиеся наименования</h3>
{buyers}<p class="note">Число упоминаний, а не уникальных ИНН или фактических покупателей; корпоративный организатор может не быть заказчиком.</p></div>
<div class="surface"><h3>Рекомендуемые шаги</h3><ul>
<li><b>Энергосети:</b> проверять ПС и линии 6–35 кВ, проектировщика, ведомость оборудования и допустимость аналогов.</li>
<li><b>Горнорудные и нефтегазовые компании:</b> отделять закупку новой установки от модернизации, обслуживания и запросов КП.</li>
<li><b>EPC и проектировщики:</b> изучать технические приложения крупных проектов, не принимать весь EPC-бюджет за оборудование PQ.</li>
<li><b>Компоненты:</b> КЭП, фильтр-реакторы и конденсаторные блоки учитывать отдельно от готовых установок.</li>
</ul></div></div>
"""
    return page + tail(rows, opts, allrows, as_of)


def tail(rows: list[dict], opts: str, allrows: str, as_of: str) -> str:
    total = len(rows)
    return f"""
<h2>04 / Полный реестр найденных закупок</h2>
<p>Одна строка соответствует одному каноническому лоту. Используйте локальный поиск и фильтры: никакие запросы с отчёта не отправляются на сервер. НМЦ не суммируется в оценку объёма рынка.</p>
<div class="filters">
<label>Поиск по заказчику, предмету, номеру<input id="search" type="search" placeholder="10 кВ, СТАТКОМ, Россети" aria-label="Поиск по реестру"></label>
<label>Год<select id="year"><option value="">Все годы</option><option>2023</option><option>2024</option><option>2025</option><option>2026</option><option>неизв.</option></select></label>
<label>Тип закупки<select id="group"><option value="">Все типы</option>{opts}</select></label>
<span class="counter" id="showing">Показано {total} из {total}</span></div>
<div class="tablewrap"><table id="registry"><thead><tr>
<th>Номер / лот</th><th>Год*</th><th>Заказчик / организатор</th><th>Технология</th><th>Пакет</th><th>Предмет</th><th>НМЦ / лимит*</th><th>Статус*</th><th>Источники</th>
</tr></thead><tbody>{allrows}</tbody></table></div>
<p class="note">*Для части записей дата публикации не подтверждена. Лимит и НМЦ могут включать весь смешанный пакет. «Договор указан» не означает верифицированного подписанта. Пустое значение цены означает отсутствие данных, а не 0 ₽.</p>
<h2>05 / Пределы доказательной базы</h2>
<div class="surface"><ul>
<li><b>Размер рынка / TAM.</b> Нет проверенного полного знаменателя всех закупок по месяцам и ЭТП — выводы об общем объёме и темпах роста рынка не делаются.</li>
<li><b>Победители / EPC / проектировщики.</b> Протоколы и договоры изучены выборочно; весь реестр из {total} лотов не прошёл проверку подписантов и производителей. Не приравнивать победителя комиссии к фактическому поставщику или производителю.</li>
<li><b>Цены.</b> НМЦ, предложение участника, общая цена договора ПИР/СМР и цена поставленного оборудования — разные показатели. Их нельзя складывать или считать подтверждённой выручкой.</li>
<li><b>Диапазон 6–35 кВ.</b> Сама подстанция 110/10 кВ либо упоминание РУ-6 не доказывает номинальное напряжение PQ-оборудования. МПУ 10 кВ в составе комплекса с БСК 110 кВ учитывается как смешанный проект.</li>
<li><b>Повторы.</b> Повторные запросы на один объект и лоты одного конкурса юридически различны, но не обязательно означают независимый спрос.</li></ul></div>
<h2>06 / План дальнейшей верификации</h2>
<p>Сначала — первичные ТЗ, номинальное напряжение и состав позиций. Затем — оригинальные протоколы, победители с ИНН и заключённые договоры. После этого — отделение цены оборудования от EPC и связка повторных процедур по объектам. Только после проверки покрытия возможно строить статистику реализованных поставок по отрасли, EPC, дистрибьюторам и OEM.</p>
<footer>ООО «Арвектум» · предварительный клиентский отчёт · данные на {esc(as_of)}. Изначальный пилот от 24 октября 2026 г. сохранён в истории Git. Реестр — {total} карточек из PostgreSQL; версия не является подтверждением наличия открытой закупки или заключённого договора.</footer>
</main>
<script>
(function(){{const q=document.getElementById('search'),y=document.getElementById('year'),g=document.getElementById('group'),rs=[...document.querySelectorAll('#registry tbody tr')],n=document.getElementById('showing');
function update(){{const s=q.value.trim().toLocaleLowerCase('ru');let k=0;for(const r of rs){{const ok=(!s||r.dataset.search.includes(s))&&(!y.value||r.dataset.year===y.value)&&(!g.value||r.dataset.group===g.value);r.hidden=!ok;if(ok)k++}}n.textContent='Показано '+k+' из '+rs.length}}
[q,y,g].forEach(c=>c.addEventListener('input',update));update();}})();
</script></body></html>
"""


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, default=REPORT)
    p.add_argument("--as-of", type=str, default=date.today().isoformat())
    p.add_argument("--snapshot", type=Path, help="Offline JSON array in live-row shape")
    a = p.parse_args()
    if not re.fullmatch(r"20\d\d-\d\d-\d\d", a.as_of):
        raise ValueError("Invalid as-of date")
    rows = (
        json.loads(a.snapshot.read_text(encoding="utf8")) if a.snapshot else rows_live()
    )
    html_data = render(rows, a.as_of)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(html_data, encoding="utf8")
    print(
        json.dumps(
            {
                "output": str(a.output),
                "unique_lots": len(rows),
                "distinct_procedures": len({r["id"].split(":")[1] for r in rows}),
                "bytes": a.output.stat().st_size,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
