"""Bilingual 16:9 Arvectum client-deck PDF source with every research case."""
from __future__ import annotations

import argparse
import collections
import decimal
import html
import json
import subprocess
from functools import lru_cache
from pathlib import Path

from scripts.market_intelligence.audit_fgi_report_fields import audit as audit_fields

SNAP = Path("data/market_intelligence/power_quality/fgi_client_deck_snapshot_20261030_v2.json")
SCOPE = {
 "supply":"supply","equipment_supply_new":"supply","equipment_supply_request":"supply",
 "signed_equipment_supply":"supply","supply_candidate":"supply",
 "supply_with_mixed_work":"supply","three_year_supply_framework_not_finished_PQ_equipment":"supply",
 "supply_components":"components","capacitor_component_supply_spares":"components","component_supply_voltage_unknown":"components",
 "design":"design","design_and_survey_only":"design","engineering_design_only":"design","design_harmonic_filtration":"design",
 "epc":"epc","mixed_epc":"epc","adjacent_epc":"epc","mixed_epc_repair_services":"epc",
 "mixed_supply_install_pnr":"epc","electrical_auxiliary_works":"epc",
 "maintenance":"service","commissioning_service_existing_ukrm":"service",
 "modernization_existing_equipment":"service","market_sounding":"sounding",
 "request_for_quotation":"sounding","mixed_MTR_market_sounding_with_PQ_component":"sounding"}
GROUPS = [
 ("supply","Поставка / запрос","Supply / requests"),
 ("epc","EPC / СМР","EPC / construction"),
 ("design","Проектирование","Design"),
 ("sounding","Мониторинг цен / КП","Market sounding"),
 ("service","Сервис / модернизация","Service / modernization"),
 ("components","Компоненты","Components"),
 ("other","Другое / требует проверки","Other / needs review")]
FAM = {
 "ukrm":("УКРМ","UKRM capacitor compensation"),"bsk":("БСК","Capacitor banks"),
 "capacitor_bank":("БСК / КУ","Capacitor banks"),"statcom":("STATCOM / SVG","STATCOM / SVG"),
 "svc":("СТК / SVC","SVC / TCR"),"svc_thyristor":("Тиристорная компенсация","Thyristor compensation"),
 "harmonic_filter":("Фильтры гармоник","Harmonic filters"),
 "harmonic_filters":("Фильтры гармоник","Harmonic filters"),
 "reactive_compensation_system":("Система компенсации","Reactive-power compensation"),
 "capacitor_components":("Конденсаторные компоненты","Capacitor components"),
 "capacitor_blocks":("Конденсаторные блоки","Capacitor modules")}
@lru_cache(maxsize=1)
def official_logo():
    """Return original Arvectum Block paths, with approved color only."""
    source = Path("src/modules/tender_operator_agent_demo/assets/arvectum-logo-block.svg")
    content = source.read_text(encoding="utf8")
    if "BRAND__Ok----Block" not in content or "#41b599" not in content:
        raise RuntimeError("Brand logo source changed; inspect official artwork")
    content = content.replace("#41b599", "#00C8A0")
    return content.replace("<svg ", '<svg class="official-logo" role="img" aria-label="Arvectum" ', 1)

def esc(v): return html.escape(str(v) if v is not None and v!="" else "—", quote=True)
def short(s,n=470):
    s=" ".join(str(s or "").split())
    return s if len(s)<=n else s[:n-1].rsplit(" ",1)[0]+"…"
def priced(s,english=False):
    try:
        x=decimal.Decimal(str(s))
        if x<=0:return "—"
        if x>=1000000:
            return (f"{x/1000000:,.2f}".replace(","," ").replace(".","," )+" млн ₽") if not english else f"RUB {x/1000000:,.2f}m"
        return (f"{x:,.2f}".replace(","," ").replace(".",",")+" ₽") if not english else f"RUB {x:,.2f}"
    except (decimal.InvalidOperation,ValueError,TypeError):return "—"
def priced_full(value, english=False):
    try:
        n=decimal.Decimal(str(value))
        if n<=0:return "—"
        z=f"{n:,.2f}"
        return "RUB "+z if english else z.replace(","," ").replace(".",",")+" ₽"
    except (decimal.InvalidOperation, ValueError, TypeError):
        return "—"

def readable_status(raw, lang):
    s=str(raw or "").lower()
    if "rad_official_failed_single_application" in s:
        return tr("Не состоялась: одна заявка, договор рекомендован",
                  "Unsuccessful: sole bid, contract recommended", lang)
    if "cancel" in s:return tr("Отменено", "Cancelled", lang)
    if "no_bid" in s or "zero_bid" in s:return tr("Без заявок", "No bids", lang)
    if "signed" in s or "registered_contract" in s:
        return tr("Договор указан в источнике", "Contract reported by source", lang)
    if "closed" in s or "finished" in s or "completed" in s:
        return tr("Процедура завершена (по источнику)", "Procedure closed in source", lang)
    if "active" in s or "open" in s or "accept" in s:
        return tr("Приём заявок по исходной карточке", "Bids accepted per source card", lang)
    return tr("Итог не подтверждён", "Outcome not verified", lang)

def firstparty(s):
    return any("primary" in x.get("tier","").lower() or "first_party" in x.get("tier","").lower() or "original" in x.get("tier","").lower() for x in s)
def tr(ru,en,lang):return ru if lang=="ru" else en
def family(s,lang):
    return FAM.get(s,(s.replace("_"," "),s.replace("_"," ")))[0 if lang=="ru" else 1]
def group(s,lang):
    k=SCOPE.get(s,"other")
    return next((x[1 if lang=="ru" else 2] for x in GROUPS if x[0]==k),k)
def wrap(section, inner, n, sectiontitle,lang):
    return f'''<section class="slide">
    <div class="brand">{official_logo()}</div><div class="site">arvectum.com</div>
    <div class="top">{esc(section)}</div><div class="rail">{esc(sectiontitle)}</div>
    <main>{inner}</main><footer><b>POWER QUALITY</b> / 30.10.2026
    <span>{tr("ООО Арвектум • исследование рынка","Arvectum • market research",lang)} &nbsp; <strong>{n:03d}</strong></span></footer></section>'''
CSS = """
@page{size:13.333333in 7.5in;margin:0}
*{box-sizing:border-box}html,body{margin:0;padding:0;font-family:"PT Sans",Arial,sans-serif;color:#283246}
body{-webkit-print-color-adjust:exact!important;print-color-adjust:exact!important}
.slide{position:relative;width:1280px;height:720px;background:#f6f8fa;overflow:hidden;page-break-after:always}
.slide:last-child{page-break-after:auto}
.brand{position:absolute;top:24px;left:40px;width:195px;height:35px}.brand svg{width:195px;height:auto;max-height:35px;display:block}
 .site{position:absolute;top:65px;left:40px;font-size:13px;color:#76919d}
.top{position:absolute;right:40px;top:32px;font-size:12px;letter-spacing:1.2px;color:#63808f;text-transform:uppercase;font-weight:700}
.rail{position:absolute;left:39px;top:138px;width:230px;white-space:pre-line;font-size:21px;font-weight:800;line-height:1.17;color:#142e45;text-transform:uppercase}
.slide main{position:absolute;left:306px;right:44px;top:119px;bottom:68px;overflow:hidden}
footer{position:absolute;left:39px;right:32px;bottom:18px;border-top:1px solid #d5dfe5;padding-top:11px;display:flex;justify-content:space-between;color:#768999;font-size:12px}
footer b{color:#132c43}footer strong{color:#00aa91}
h1{font-size:42px;color:#132d43;letter-spacing:-.7px;line-height:1.14;margin:0}
h2{font-size:28px;line-height:1.17;margin:0;color:#132d43;overflow-wrap:anywhere}
h3{font-size:18px;margin:0}
p{margin:8px 0 0;line-height:1.37}
.sub{font-size:17px;color:#627887;line-height:1.3;margin-top:10px}
.muted{color:#687f8c}
.teal{color:#00a991}
.box{border:1px solid #dbe5eb;border-radius:12px;background:white;padding:21px 22px}
.soft{background:#eaf8f5}.warm{background:#fff6eb}
.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:13px;margin:37px 0 15px}
.metric{border-radius:12px;border:1px solid #dce5e8;background:white;padding:20px;min-height:122px}
.metric strong{font-size:40px;display:block;color:#00ae97;line-height:1.2}
.metric span{font-size:14px;color:#5d7685;display:block;margin-top:9px}
.dual{display:grid;grid-template-columns:1fr 1fr;gap:17px;margin-top:22px}
.panel{background:white;border-radius:12px;border:1px solid #dce5e9;padding:19px 23px}
.key{font-size:13px;color:#5e7785;letter-spacing:.5px;font-weight:700;text-transform:uppercase}
.value{font-size:22px;color:#152f45;font-weight:800;margin-top:6px}
.call{margin-top:23px;background:#001432;padding:25px 29px;color:white;border-radius:11px;font-size:18px;line-height:1.4}
.list{margin-top:22px;display:grid;gap:12px}
.listitem{display:flex;align-items:center;gap:12px}
.listitem b{width:265px;font-size:15px}
.listitem .track{height:18px;background:#e5ecef;flex:1;border-radius:11px;overflow:hidden}
.listitem i{display:block;height:100%;background:linear-gradient(90deg,#00b699,#28aac3);border-radius:11px}
.listitem em{font-style:normal;color:#276a78;font-weight:800;width:55px;text-align:right}
table{border-collapse:collapse;width:100%;margin-top:27px;font-size:14px;background:white}
th{text-align:left;background:#001432;color:white;padding:11px;font-size:13px}
td{padding:10px 11px;border-bottom:1px solid #e0e8ee;vertical-align:top;line-height:1.3}
tr:nth-child(even) td{background:#f8fafb}
.stamp{font-size:12px;font-weight:800;letter-spacing:.8px;color:#00ad9d;margin-bottom:11px}
.cover{background:#001432;color:#fff}
.cover .brand{top:35px;left:56px;width:245px;height:45px}.cover .brand svg{width:245px;max-height:45px}
.cover .site{top:91px;left:60px;color:#8baab8}
.cover .tag{position:absolute;left:60px;top:140px;color:#40ddc4;letter-spacing:2px;font-size:13px;font-weight:800}
.cover h1{position:absolute;top:225px;left:62px;color:white;font-size:71px;line-height:1.01}
.cover .dek{position:absolute;left:65px;top:420px;width:660px;color:#c7dbe1;font-size:20px;line-height:1.4}
.cover .date{position:absolute;bottom:57px;left:65px;color:#5bd7c5;font-size:15px;font-weight:800}
.cover > svg{position:absolute;right:0;top:255px;width:580px;height:230px}
.case .rail{top:135px;font-size:18px}
.case main{top:105px;bottom:58px}
.case .number{font-family:"JetBrains Mono","PT Mono",Menlo,monospace;font-size:15px;font-weight:800;color:#048c85;letter-spacing:.3px}
.case h2{font-size:32px;margin-top:13px;max-height:76px;overflow:hidden}
.chips{display:flex;gap:9px;margin-top:11px;align-items:center;flex-wrap:wrap}
.chip{background:#e8f7f3;border-radius:30px;color:#058b77;font-size:12px;font-weight:800;padding:5px 11px}
.chip.alt{background:#fff0df;color:#9b642e}
.case .subject{margin-top:16px;padding:15px 17px;border-radius:0 10px 10px 0;border-left:4px solid #00bfa9;background:white;font-size:17px;line-height:1.32;min-height:82px;max-height:124px;overflow:hidden}
.case .subject.small{font-size:15px}
.case .grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-top:13px}
.case .datum{border-radius:10px;background:white;border:1px solid #d9e5ea;padding:12px 15px;min-height:68px;overflow:hidden}
.case .datum .k{font-size:11px;color:#6c8490;font-weight:800;text-transform:uppercase}
.case .datum .v{font-size:17px;font-weight:800;color:#173246;margin-top:5px;line-height:1.24;overflow-wrap:anywhere}
.case .datum .v.sm{font-size:12.5px}.case .grid:not(.two) .datum .v{font-family:"JetBrains Mono","PT Mono",monospace;font-size:14px}
.case .grid.two{grid-template-columns:1fr 1fr;margin-top:12px}
.case .grid.two .datum{min-height:70px}
.case .remark{margin-top:13px;background:#eff4f7;padding:12px 16px;border-radius:9px;font-size:13.4px;line-height:1.3;color:#36596c;max-height:140px;overflow:hidden}
.case .sources{margin-top:12px;font-size:12.5px;color:#6c8290;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.case a{color:#008977;border-bottom:1px solid #00aa98;text-decoration:none}
.index{display:grid;grid-template-columns:1fr 1fr;gap:10px 15px;margin-top:27px}
.index a{display:block;border:1px solid #dbe4ea;border-radius:7px;background:white;padding:10px 13px;text-decoration:none;color:#163349;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.index b{color:#00a98e;margin-right:7px}
.smallnote{font-size:13px;color:#637d89;line-height:1.35;margin-top:15px}
.case-evidence main{top:93px;bottom:51px}
.case-evidence .buyer-short{font-size:22px;line-height:1.13;font-weight:800;margin:7px 0 8px}
.case-evidence .cols{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:10px}
.case-evidence .panel{padding:10px 14px}
.case-evidence .panel h3{font-size:15px;color:#005d58;margin-bottom:8px}
.case-evidence .kv{display:grid;grid-template-columns:47% 53%;gap:3px 8px;border-bottom:1px solid #dbe5ea;padding:3px 0;font-size:12px;line-height:1.13;min-height:24px}
.case-evidence .kv:last-child{border-bottom:0}
.case-evidence .kv b{font-weight:600;color:#4a6b77;overflow-wrap:anywhere}
.case-evidence .kv span{font-weight:700;color:#172f44;overflow-wrap:anywhere}
.case-evidence .proofs{background:white;border:1px solid #dbe5eb;border-radius:9px;padding:9px 14px;margin-top:8px}
.case-evidence .proofs h3{font-size:14px;color:#076f6a;margin:0 0 6px}
.case-evidence .proofs a{font-size:12px;display:inline-block;margin:3px 12px 3px 0;text-decoration:underline;color:#007d75;overflow-wrap:anywhere}
.case-evidence .backlog{background:#eaf8f5;border-radius:8px;padding:8px 12px;font-size:11.5px;color:#265868;margin-top:6px;line-height:1.25}
.case-evidence .mono{font-family:"JetBrains Mono","PT Mono",Menlo,monospace;font-size:12px}
"""
def metric(v,t):return f'<div class="metric"><strong>{esc(v)}</strong><span>{esc(t)}</span></div>'
def line(k,v):return f'<div class="listitem"><b>{esc(k)}</b><span class="track"><i style="width:{v[1]:.2f}%"></i></span><em>{v[0]}</em></div>'
def box(k,v,n=""):return f'<div class="panel"><div class="key">{esc(k)}</div><div class="value">{esc(v)}</div><p class="muted">{esc(n)}</p></div>'
def table(headers,rows):
    return '<table><thead><tr>'+''.join('<th>'+esc(x)+'</th>' for x in headers)+'</tr></thead><tbody>'+''.join(
        '<tr>'+''.join('<td>'+esc(x)+'</td>' for x in r)+'</tr>' for r in rows
    )+'</tbody></table>'
def cover(d,lang):
    n=d["unique_lots"];p=d["distinct_procedures"]
    title=tr("РОССИЯ · 6–35 КВ","RUSSIA · 6–35 KV",lang)
    desc=tr(f"Полный корпус Power Quality: {n} уникальных закупочных лотов и {p} процедур. Обзор, экономика, участники рынка и детальные карточки каждой закупки.",
            f"Full Power Quality corpus: {n} unique procurement lots and {p} procedure IDs. Market overview, economics, participants, and a source-linked dossier for every lot.",lang)
    return f'''<section class="slide cover"><div class="brand">{official_logo()}</div>
<div class="site">arvectum.com</div><div class="tag">{tr("ОБЗОР РЕАЛЬНЫХ ЗАКУПОК","REAL PROCUREMENT REVIEW",lang)}</div>
<h1>POWER QUALITY<br>{title}</h1><p class="dek">{esc(desc)}</p>
<div class="date">2023–2026 / {tr("Срез 30 октября 2026","As of 30 October 2026",lang)}</div>
<svg viewBox="0 0 580 230" xmlns="http://www.w3.org/2000/svg" fill="none" stroke="#03bfa5" stroke-width="2.4">
<path d="M0 85 C110 32 160 155 277 104 S460 160 580 90"/>
<path d="M0 108 C110 55 160 178 277 127 S460 183 580 113"/>
<path d="M0 131 C110 78 160 201 277 150 S460 206 580 136"/></svg></section>'''

def groups(rows):
    return collections.Counter(SCOPE.get(r["scope"], "other") for r in rows)

def years(rows):
    return collections.Counter((r["date"][:4] if r["date"] else "н/д") for r in rows)

def summary_pages(d,lang):
    rows=d["items"];n=len(rows);p=d["distinct_procedures"]
    ek=d["eis_223_lots"];en=d["eis_223_notices"]
    pages=[]
    head=tr("Документально выявлен спрос на 6, 10 и 35 кВ","Evidence confirms demand at 6, 10 and 35 kV",lang)
    intro=tr("Обновление исходного 10-слайдового обзора: все закупки доступны в индивидуальных досье. Корпус не равен рынку исполненных контрактов.",
             "Expanded original ten-slide overview: every lot now has its own dossier. A research corpus is not a registry of executed contracts.",lang)
    numbers=metric(n,tr("Уникальные лоты","Unique lots",lang))+metric(p,tr("ID процедур","Procedure IDs",lang))+metric(ek,tr("Лоты ЕИС 223-ФЗ","EIS 223-FZ lots",lang))+metric(en,tr("Извещения ЕИС","EIS notices",lang))
    inn=f'<h1>{esc(head)}</h1><p class="sub">{esc(intro)}</p><div class="metrics">{numbers}</div>'
    inn+=f'<div class="call">{tr("Ключевое ограничение: запросы КП, сервис, проектирование и EPC учитываются как закупочные кейсы, но не как продажи PQ-устройств. НМЦ, предложение участника и сумма договора нельзя складывать в общий оборот.","Important boundary: RFQs, service, engineering and EPC count as research cases, not completed PQ hardware sales. Initial prices, bids and contract values are not additive market revenue.",lang)}</div>'
    pages.append(("01 / "+tr("Выводы","Evidence",lang),tr("ВЫВОДЫ","EVIDENCE",lang),inn))
    g=groups(rows); m=max(g.values())
    bar=''.join(line(x[1 if lang=="ru" else 2],(g[x[0]],100*g[x[0]]/m)) for x in GROUPS)
    inn=f'<h1>{tr("Структура исследовательского корпуса","Structure of the research corpus",lang)}</h1><p class="sub">{tr("Группировка по предмету, не по подписанным договорам.","Grouping by procurement subject, not by signed contracts.",lang)}</p><div class="list">{bar}</div>'
    pages.append(("02 / "+tr("Структура","Structure",lang),tr("СТРУКТУРА","STRUCTURE",lang),inn))
    fam=collections.Counter(x["family"] or "unknown" for x in rows)
    ftop=fam.most_common(8); fm=max(v for _,v in ftop)
    bar=''.join(line(family(k,lang),(v,100*v/fm)) for k,v in ftop)
    inn=f'<h1>{tr("Технологии в закупках","Technologies found in procurements",lang)}</h1><p class="sub">{tr("Классы оборудования извлечены из карточек и ТЗ; их наличие не означает технического допуска продукции FGI.","Equipment categories are extracted from cards and technical documents; category presence does not mean FGI product approval.",lang)}</p><div class="list">{bar}</div>'
    pages.append(("03 / "+tr("Технологии","Technology",lang),tr("ТЕХНОЛОГИИ","TECHNOLOGY",lang),inn))
    yrs=years(rows);bys=collections.Counter(x["buyer"] or tr("Неизвестно","Unknown",lang) for x in rows)
    ftab=table([tr("Год","Year",lang),tr("Лотов","Lots",lang)],[[k,yrs.get(k,0)] for k in ["2023","2024","2025","2026","н/д"]])
    cust=table([tr("Организация (как указана в карточках)","Organization name in source cards",lang),tr("Лотов","Lots",lang)],
        [[short(k,49),v] for k,v in bys.most_common(7)])
    inn=f'<h1>{tr("География заказчиков и динамика выявлений","Buyer landscape and discovery timeline",lang)}</h1><p class="sub">{tr("Годы — годы публикаций в корпусе, не оценка динамики всего рынка.","Years reflect publication dates in the corpus, not nationwide market growth.",lang)}</p><div class="dual"><div>{ftab}</div><div>{cust}</div></div>'
    pages.append(("04 / "+tr("Заказчики","Customers",lang),tr("ЗАКАЗЧИКИ","BUYERS",lang),inn))
    src=sum(bool(x["source_urls"]) for x in rows)
    orig=sum(firstparty(x["source_urls"]) for x in rows)
    nmc=sum(bool(x["nmck"]) for x in rows)
    cp=sum(bool(x["contract_price"]) for x in rows)
    win=sum(bool(x["winner"]) for x in rows)
    boxes=''.join([box(tr("Ссылки","Source links",lang),f"{src} / {n}",tr("Публичные URL в карточках","Public URLs attached",lang)),
        box(tr("Первичные источники","First-party sources",lang),str(orig),tr("Первый уровень доказательств","Direct evidence tier",lang)),
        box(tr("НМЦ / лимит","NMC / ceiling",lang),str(nmc),tr("Это не суммы подписанных договоров","Not signed contract prices",lang)),
        box(tr("Цены договоров","Contract-price entries",lang),str(cp),tr("Включая смешанные / вторичные значения","Includes mixed and secondary signals",lang))])
    inn=f'<h1>{tr("Качество и полнота фактов","Evidence completeness",lang)}</h1><p class="sub">{tr(f"Состояние полей в {n} карточках; пустое поле означает «не подтверждено», а не ноль.",f"Field coverage across {n} cases; an empty field means unverified, not zero.",lang)}</p><div class="dual">{boxes}</div><p class="smallnote">{tr(f"Имя участника торгов или поставщика встречается в {win} карточках; это не перечень подписанных поставщиков. Все {n} записей остаются на исследовательской проверке.",f"A named bid participant or supplier is present in {win} cases; this is not a signed-supplier census. All {n} cases remain under research review.",lang)}</p>'
    pages.append(("05 / "+tr("Проверка","Evidence",lang),tr("ДОКАЗАТЕЛЬСТВА","EVIDENCE",lang),inn))
    contracts=[q for q in rows if q["contract_price"]]
    contracts.sort(key=lambda q:float(q["contract_price"]),reverse=True)
    trs=[[short(q["id"],43),short(q["buyer"],42),priced(q["contract_price"],lang!="ru"),
          tr("Да" if q["signed_supplier_verified"] else "Не доказан",
             "Verified" if q["signed_supplier_verified"] else "Unverified",lang)] for q in contracts[:5]]
    inn=f'<h1>{tr("Цены зарегистрированных и заявленных договоров","Reported and registered contract prices",lang)}</h1>'
    inn+=f'<p class="sub">{tr("Включены только поля цен из карточек; нельзя трактовать общую сумму EPC как выручку от устройств PQ.","Only recorded price signals are shown; do not treat total EPC amounts as PQ device revenue.",lang)}</p>'
    inn+=table([tr("Номер / лот","Case / lot",lang),tr("Заказчик","Customer",lang),
                tr("Цена в источнике","Reported price",lang),tr("Подписант","Signatory",lang)],trs)
    inn+=f'<div class="call">{tr("В корпусе есть цены ПИР, сервиса, реконструкции и поставок. Даже указанная цена договора не доказывает фактическую оплату и принадлежность оборудования к 6–35 кВ.","The corpus includes design, service, reconstruction and supply amounts. A reported contract price does not prove payment or the rated voltage of PQ equipment.",lang)}</div>'
    pages.append(("06 / "+tr("Договоры","Contracts",lang),tr("ДОГОВОРЫ","CONTRACTS",lang),inn))
    picked=[
      ("223fz:32616435269:lot1","МПУ 10 кВ / 30 Мвар + БСК 110 кВ","10 kV / 30 Mvar modular source + 110 kV bank"),
      ("223fz:32616497692:lot1","Вяртсиля: 10 кВ / 3 Мвар","Vyartsilya: 10 kV / 3 Mvar"),
      ("223fz:32616433248:lot1","Кяппесельга: 35 кВ / ≥3,5 Мвар","Kyappeselga: 35 kV / ≥3.5 Mvar"),
      ("223fz:32413764701:lot1","ЮТЭК: 10 кВ / 150 квар","YUTEK: 10 kV / 150 kvar"),
      ("223fz:32615614821:lot1","Нагорная: 6,3 кВ / 200 квар","Nagornaya: 6.3 kV / 200 kvar"),
      ("223fz:32616296475:lot1","Тиристорный реактор и фильтры, Мелеуз","Thyristor reactor and filters, Meleuz")]
    by_id={q["id"]:q for q in rows}
    tab=[]
    for cid,ru,en in picked:
        q=by_id.get(cid)
        if q:tab.append([tr(ru,en,lang),short(q["buyer"],39),
                         priced(q["nmck"],lang!="ru"),
                         tr("ТЗ и договор проверены","Spec & contract verified",lang)
                         if cid=="223fz:32616296475:lot1" and q.get("signed_contract_verified")
                         else tr("Проверить ТЗ","Check source spec",lang)])
    inn=f'<h1>{tr("Технический спрос: 6–35 кВ","Technical demand at 6–35 kV",lang)}</h1>'
    inn+=f'<p class="sub">{tr("Технически значимые объекты; цены могут включать EPC, проектирование и вспомогательные работы.","Technically significant cases; amounts may include EPC, design and auxiliary works.",lang)}</p>'
    inn+=table([tr("Объект","Facility",lang),tr("Заказчик","Buyer",lang),
               tr("НМЦ / лимит","NMC / ceiling",lang),tr("Действие","Next action",lang)],tab)
    pages.append(("07 / "+tr("Технический спрос","Technical demand",lang),tr("ТЕХНИКА","ENGINEERING",lang),inn))
    cases=[
      ("commercial:106044-ТТ:lot1","СТАТКОМ 6,3 кВ","6.3 kV STATCOM"),
      ("commercial:306-644:lot35","Монтаж УКРМ 6 кВ","6 kV UKRM installation"),
      ("223fz:32616065155:lot7","Конденсаторные установки, напряжение не доказано","Capacitor units, rated voltage unverified"),
      ("223fz:judicial-contract-03-34-24:lot1","Поставка УКРМ 10,5 кВ / 13 Мвар","10.5 kV / 13 Mvar supplied UKRM")]
    tab=[]
    for cid,ru,en in cases:
        q=by_id.get(cid)
        if q:tab.append([short(q["buyer"],49),tr(ru,en,lang),short(q["status"],44)])
    inn=f'<h1>{tr("Промышленный спрос и исходы","Industrial procurement demand",lang)}</h1>'
    inn+=f'<p class="sub">{tr("Одна юридическая процедура может содержать несколько физических установок. Состав закупки и договор — разные уровни фактов.","One legal procedure may include several physical devices. Demand and signed delivery are different evidence levels.",lang)}</p>'
    inn+=table([tr("Заказчик","Customer",lang),tr("Предмет","Subject",lang),
                tr("Статус карточки","Source status",lang)],tab)
    inn+=f'<div class="call">{tr("Монтаж 6-кВ УКРМ и поставка конденсаторных элементов не означают подписанную покупку новых установок STATCOM.","Installation of a 6 kV UKRM and purchase of capacitor components do not establish a signed delivery of new STATCOM units.",lang)}</div>'
    pages.append(("08 / "+tr("Промышленность","Industry",lang),tr("ПРОМЫШЛЕННЫЙ СПРОС","INDUSTRIAL DEMAND",lang),inn))
    named=[q for q in rows if q["winner"]]
    tab=[[short(q["id"],42),short(q["winner"],60),
          tr("Имя из источника; проверить подписанта","Named in source; signatory to verify",lang)]
          for q in named[:8]]
    inn=f'<h1>{tr("Участники и разграничение ролей","Participants and documented roles",lang)}</h1>'
    inn+=f'<p class="sub">{tr("Победитель комиссии, исполнитель EPC, поставщик по договору и OEM — не одно лицо по умолчанию.","Commission bidder, EPC contractor, signed supplier and OEM are not interchangeable roles.",lang)}</p>'
    if tab:inn+=table([tr("Закупка","Procurement",lang),tr("Названная компания","Named entity",lang),
                       tr("Доказательность","Evidence",lang)],tab)
    inn+=f'<div class="call">{tr("Для большинства карточек подписант публично не установлен. Рейтинг поставщиков требует сверки ИНН, протоколов, договоров и паспортов изделий.","For most rows the signatory is not established. Supplier rankings require tax IDs, protocols, contracts and equipment documents.",lang)}</div>'
    pages.append(("09 / "+tr("Участники","Participants",lang),tr("УЧАСТНИКИ РЫНКА","PARTICIPANTS",lang),inn))
    tech=[
      ("6–6,6 кВ","УКРМ / БСК","UKRM / capacitor banks","SVG и ступенчатая БСК не взаимозаменяемы автоматически","SVG and switched banks are not automatic equivalents"),
      ("10 кВ","SVG / STATCOM","SVG / STATCOM","Проверить гармоники, SCADA, климат и допуск аналога","Verify harmonics, SCADA, climate and admissibility"),
      ("33–35 кВ","Высоковольтные решения","High-voltage systems","Сверить типоисполнение и требования проекта","Validate models against original specifications"),
      ("400/690 В","FGAPF","FGAPF","Не представлять как отдельный фильтр 6–35 кВ","Not a stand-alone 6–35 kV filter")]
    tab=[[a,b if lang=="ru" else c,d if lang=="ru" else e] for a,b,c,d,e in tech]
    inn=f'<h1>{tr("Класс FGI ≠ технический допуск","FGI voltage class ≠ tender compliance",lang)}</h1>'
    inn+=f'<p class="sub">{tr("Точки входа существуют, но соответствие требует инженерной проверки по каждому ТЗ.","Potential entry points exist, but engineering compliance requires case-by-case review.",lang)}</p>'
    inn+=table([tr("Класс","Voltage",lang),tr("Технология","Technology",lang),
                tr("Условие допуска","Compliance condition",lang)],tab)
    pages.append(("10 / "+tr("Оборудование FGI","FGI equipment",lang),tr("ОБОРУДОВАНИЕ FGI","FGI EQUIPMENT",lang),inn))
    topics=[
      (tr("Один лот","One lot",lang),
       tr("Канонический ключ юридической процедуры. Несколько установок внутри одного лота не становятся несколькими лотами.","A canonical legal procurement lot; several physical devices within one lot do not become several lots.",lang)),
      (tr("Разделение цен","Price types",lang),
       tr("НМЦ ≠ предложение участника ≠ стоимость договора ≠ выплата. EPC и ПИР не являются прямой ценой оборудования.","NMC ≠ bid ≠ registered contract ≠ payment. EPC and design budgets are not hardware-only value.",lang)),
      (tr("Поставщики","Suppliers",lang),
       tr("Имя по протоколу нельзя автоматически объявлять поставщиком по подписанному договору или изготовителем.","A bidder named in a protocol cannot automatically be named a signed supplier or manufacturer.",lang)),
      (tr("Источники","Sources",lang),
       tr("Оригинальные ссылки включены в карточки, когда они содержатся в базе. Неподтверждённые сведения показываются явно.","Original source URLs appear where stored in the database. Unverified fields are explicitly labeled.",lang))]
    inn=f'<h1>{tr("Источники, определения и ограничения","Sources, definitions and limitations",lang)}</h1>'
    inn+=f'<p class="sub">{tr("Полный реестр закупочных карточек приложен постранично: это и есть доказательная база, а не только десять красивых примеров.","Every procurement record follows as its own slide: this is the underlying evidence, not merely ten selected examples.",lang)}</p>'
    inn+=''.join(f'<div class="panel" style="margin-top:13px;padding:14px 19px"><b>{esc(k)}</b><div class="muted" style="font-size:15px;line-height:1.3;margin-top:4px">{esc(v)}</div></div>' for k,v in topics)
    pages.append(("11 / "+tr("Методология","Methodology",lang),tr("ИСТОЧНИКИ И ВЫВОДЫ","SOURCES / LIMITS",lang),inn))
    return pages
def dossier(item,idx,total,lang,page):
    en=lang!="ru"
    key=esc(item["id"]); buyer=esc(item["buyer"])
    fam=esc(family(item["family"],lang)); scp=esc(group(item["scope"],lang))
    number=f"{idx:03d} / {total:03d}"
    head=tr("ДОСЬЕ ЗАКУПКИ","PROCUREMENT DOSSIER",lang)
    extra_inn=(" &nbsp; · &nbsp; "+tr("ИНН","TIN",lang)+" "+esc(item["buyer_inn"])) if item["buyer_inn"] else ""
    header=f'<div class="number">{number} &nbsp; · &nbsp; {key}{extra_inn}</div><h2>{buyer}</h2>'
    chips=(f'<div class="chips"><span class="chip">{fam}</span><span class="chip">{scp}</span>'
           f'<span class="chip alt">{esc(item["date"] or tr("Дата неизвестна","Unknown date",lang))}</span></div>')
    status_tag=short(readable_status(item["status"],lang),55)
    chips=chips.replace("</div>",f'<span class="chip alt" title="{esc(item["status"])}">{tr("СТАТУС","STATUS",lang)}: {esc(status_tag)}</span></div>')
    desc=item["description"] or item["project"] or tr("Предмет не указан в карточке","Subject not populated in the source row",lang)
    # English deck preserves the original Russian procurement source wording.
    pref=tr("ПРЕДМЕТ ЗАКУПКИ","ORIGINAL RUSSIAN PROCUREMENT SUBJECT",lang)
    desc_class="small" if len(desc)>240 else ""
    description=(f'<div class="subject {desc_class}"><div class="key" style="font-size:11px;color:#008a7b">'
                 f'{esc(pref)}</div>{esc(desc)}</div>')
    def field(label,val,sm=False):
        return (f'<div class="datum"><div class="k">{esc(label)}</div>'
                f'<div class="v{" sm" if sm else ""}">{esc(val)}</div></div>')
    finance='<div class="grid">'
    finance+=field(tr("НМЦ / лимит","NMC / ceiling",lang),priced_full(item["nmck"],en))
    finance+=field(tr("Предложение / протокол","Bid / protocol",lang),priced_full(item["bid"],en))
    contract_text=priced_full(item["contract_price"],en)
    if item["contract_no"]:
        contract_text+=(" · №"+short(item["contract_no"],32))
    finance+=field(tr("Цена договора в источнике*","Reported contract price*",lang),contract_text,len(contract_text)>29)
    finance+='</div>'
    tech=[]
    if item["voltage_kv"]:tech.append(f'{tr("Напряжение","Voltage",lang)}: {item["voltage_kv"]} kV')
    if item["power"]:tech.append(f'{tr("Мощность","Power",lang)}: {item["power"]}')
    if item["quantity"]:tech.append(f'{tr("Количество","Quantity",lang)}: {item["quantity"]} {item["quantity_unit"]}')
    if not tech:
        tech.append(tr("Номинальные параметры не подтверждены в структурированных полях",
                       "Rated parameters not verified in structured fields",lang))
    winner=item["winner"] or tr("Не указан / требует проверки","Not stated / verification pending",lang)
    facts='<div class="grid two">'
    facts+=field(tr("Технические характеристики","Technical parameters",lang),' · '.join(tech),True)
    facts+=field(tr("Участник / поставщик из источника","Bidder / supplier named in source",lang),winner,True)
    facts+='</div>'
    note=item["notes"] or item["market_scope"] or item["status"] or ""
    if not note:note=tr("Дополнительных сведений нет","No additional notes available",lang)
    note=short(note,500)
    disclaimer=(f'<div class="remark"><b>{tr("ОГОВОРКА /","RESEARCH CAVEAT / SOURCE NOTE",lang)}</b>'
                f' {esc(note)}</div>')
    sources=item["source_urls"]
    if sources:
        links=''.join(f'<a href="{esc(s["url"])}">[{i+1}] {esc(short(s["tier"] or tr("Ссылка","Source",lang),40))}</a>'
                      for i,s in enumerate(sources[:4]))
    else:
        links=tr("Публичный URL не закреплён за карточкой; требуется проверка.",
                 "No public source URL attached; original to be obtained.",lang)
    src=f'<div class="sources"><b>{tr("ИСТОЧНИКИ","SOURCES",lang)}:</b>{links}</div>'
    body=header+chips+description+finance+facts+disclaimer+src
    page_html=wrap("RESEARCH REGISTER · "+number,body,page,head,lang)
    return page_html.replace('<section class="slide">',
                             f'<section id="case-{idx}" class="slide case" data-case-id="{key}">',1)

def dossier_evidence(item, idx, total, lang, page, review):
    """Second fixed-layout page: independent legal, technical and source evidence."""
    en=lang!="ru"
    unknown=tr("Не установлено","Not verified",lang)
    case_id=esc(item["id"])
    def kv(label,value,monospace=False):
        value=short(str(value or unknown),95 if not monospace else 68)
        return (f'<div class="kv"><b>{esc(label)}</b>'
                f'<span{" class=mono" if monospace else ""}>{esc(value)}</span></div>')
    def pval(key):
        return priced_full(item.get(key),en)
    left=[
        (tr("Юридический режим","Regime",lang),item.get("regime")),
        (tr("Номер процедуры","Notice / procedure",lang),item.get("procedure")),
        (tr("ЭТП / источник","Marketplace",lang),item.get("platform")),
        (tr("Объект / проект","Facility / project",lang),short(item.get("project"),72)),
        (tr("НМЦ / лимит","NMC / ceiling",lang),pval("nmck")),
        (tr("Предложение комиссии","Commission bid",lang),pval("bid")),
        (tr("Цена договора по источнику","Reported contract value",lang),pval("contract_price")),
        (tr("Доля PQ-оборудования","Equipment-only amount",lang),pval("equipment_only_price")),
        (tr("Фактически оплачено","Payment confirmed",lang),
         pval("paid_amount") if item.get("paid_verified") else unknown),
        (tr("Номер договора","Contract number",lang),item.get("contract_no")),
        (tr("Реестровый номер","Registry number",lang),item.get("contract_registry_number")),
    ]
    right=[
        (tr("Номинал изделия (кВ)","Equipment rated kV",lang),item.get("voltage_kv")),
        (tr("Мощность","Capacity",lang),item.get("power")),
        (tr("Количество","Quantity",lang),
         f'{item["quantity"]} {item["quantity_unit"]}' if item.get("quantity") else ""),
        (tr("Заказчик / ИНН","Customer TIN",lang),item.get("buyer_inn")),
        (tr("Победитель / участник","Bidder / winner",lang),item.get("winner")),
        (tr("Подписанный поставщик","Signed supplier",lang),item.get("contract_signatory")),
        (tr("ИНН поставщика","Supplier TIN",lang),item.get("supplier_inn")),
        (tr("EPC / подрядчик","EPC contractor",lang),item.get("epc")),
        (tr("Проектировщик","Designer",lang),item.get("designer")),
        (tr("Изготовитель OEM","Equipment OEM",lang),item.get("oem")),
    ]
    left_html=''.join(kv(k,v,i in (1,9)) for i,(k,v) in enumerate(left))
    right_html=''.join(kv(k,v) for k,v in right)
    sources=item.get("source_urls") or []
    link_html=''.join(
        f'<a href="{esc(src["url"])}">[{i+1}] {esc(short(src["tier"] or "source",50))}'
        f'{" · SHA" if src.get("sha") else ""}</a>'
        for i,src in enumerate(sources[:4])
    ) or esc(tr("Публичный первоисточник ещё не прикреплён","Public original not attached",lang))
    missing=review["missing_fields"]
    miss=[f for section in ("identity","technical","financial","participants","outcome")
          for f in missing[section]]
    priority=review["next_priority"]
    known=f'{sum(len(a) for a in review["filled_fields"].values())}/{sum(len(a) for a in review["filled_fields"].values())+len(miss)}'
    miss_display=", ".join(miss[:8])
    if len(miss)>8: miss_display+=f" … +{len(miss)-8}"
    grade=review["source_grade"]
    caption=(f'{tr("ДОКАЗАТЕЛЬСТВА И РОЛИ","EVIDENCE AND ROLES",lang)} '
             f'· {idx:03d}/{total:03d} · {case_id}')
    head=(f'<div class="number">{caption}</div>'
          f'<div class="buyer-short">{esc(short(item["buyer"],85))}</div>')
    cols=(f'<div class="cols"><div class="panel"><h3>'
          f'{tr("Идентичность и финансы","Identity and financial terms",lang)}</h3>'
          f'{left_html}</div><div class="panel"><h3>'
          f'{tr("Техника и участники","Technical data and counterparties",lang)}</h3>'
          f'{right_html}</div></div>')
    proof=(f'<div class="proofs"><h3>'
           f'{tr("Первоисточники и проверка","Sources and verification",lang)}'
           f' · {tr("класс","grade",lang)} {grade}'
           f' · {tr("полей заполнено","fields populated",lang)} {known}'
           f'</h3>{link_html}</div>')
    backlog=(f'<div class="backlog">'
             f'<b>{tr("ДАЛЬНЕЙШАЯ ПРОВЕРКА","NEXT EVIDENCE TASK",lang)}:</b> '
             f'{esc(priority)} · {tr("Не установлено","Missing",lang)}: {esc(miss_display or "—")}'
             f'</div>')
    body=head+cols+proof+backlog
    output=wrap("SOURCE EVIDENCE · "+f"{idx:03d}/{total:03d}",body,page,
                tr("ПОЛЯ И СТАТУС","FIELDS / STATUS",lang),lang)
    return output.replace('<section class="slide">',
        f'<section id="case-{idx}-evidence" class="slide case-evidence" data-evidence-id="{case_id}">',1)

def index_pages(items,lang,startpage):
    pages=[]
    for start in range(0,len(items),16):
        sub=items[start:start+16]
        links=''.join(f'<a href="#case-{start+i+1}"><b>{start+i+1:03d}</b>'
                      f' {esc(short(row["buyer"],38))} — {esc(short(row["id"],39))}</a>'
                      for i,row in enumerate(sub))
        n=1+start//16
        body=(f'<h1>{tr("Содержание полного корпуса","Complete register contents",lang)} · {n:02d}</h1>'
              f'<p class="sub">{tr("Каждый пункт ведёт к отдельному закупочному досье с номером лота, ценами, участниками и ссылками.","Each link leads to a complete individual procurement dossier with its lot key, prices, participants and sources.",lang)}</p>'
              f'<div class="index">{links}</div>')
        pages.append(wrap("REGISTER INDEX",body,startpage+len(pages),
                          tr("НАВИГАЦИЯ","INDEX",lang),lang))
    return pages

def render(data,lang):
    items=data["items"];n=data["unique_lots"]
    if n != len(items) or len({x["id"] for x in items}) != n:
        raise ValueError("Lot cardinality drift")
    assessment=audit_fields(data)
    audit_by_id={q["id"]:q for q in assessment["cases"]}
    slides=[cover(data,lang)]
    for sec,rail,body in summary_pages(data,lang):
        slides.append(wrap(sec,body,len(slides)+1,rail,lang))
    coverage=assessment["field_coverage"]
    grade=assessment["source_grades"]
    field_table=table([
        tr("Поле","Field",lang),tr("Заполнено (из "+str(n)+")","Populated (of "+str(n)+")",lang)
    ],[
        (tr("НМЦ","Initial ceiling",lang),coverage.get("nmck",0)),
        (tr("Номинальное напряжение изделия","Equipment rated voltage",lang),coverage.get("voltage_kv",0)),
        (tr("Номинальная мощность","Rated reactive power",lang),coverage.get("power",0)),
        (tr("Предложение по протоколу","Commission bid amount",lang),coverage.get("bid",0)),
        (tr("Цена подписанного/заявленного договора","Reported contract price",lang),coverage.get("contract_price",0)),
        (tr("Стоимость PQ-оборудования","Equipment-only price",lang),coverage.get("equipment_only_price",0)),
        (tr("Изготовитель OEM","Equipment OEM",lang),coverage.get("oem",0)),
    ])
    quality=(f'<h1>{tr("Прогресс верификации полей","Field verification progress",lang)}</h1>'
             f'<p class="sub">{tr("Заполнение поля не равно первичной верификации. Оценка по текущему срезу юридических лотов.","Populated fields do not imply first-party verification. Frozen current-corpus field coverage.",lang)}</p>'
             +field_table+
             f'<p class="smallnote">{tr("Источники по уровню доказательности","Source evidence grades",lang)}: '
             f'A={grade.get("A",0)} · B={grade.get("B",0)} · C={grade.get("C",0)} · D={grade.get("D",0)}. '
             f'{tr("Индивидуальные пробелы и следующий шаг — на второй странице каждого досье.","Individual missing fields and the next research step appear on every second case page.",lang)}</p>')
    slides.append(wrap("FIELD COMPLETENESS",quality,len(slides)+1,
                 tr("ПОЛНОТА ДАННЫХ","FIELD COVERAGE",lang),lang))
    slides.extend(index_pages(items,lang,len(slides)+1))
    for i,item in enumerate(items,1):
        slides.append(dossier(item,i,n,lang,len(slides)+1))
        slides.append(dossier_evidence(item,i,n,lang,len(slides)+1,audit_by_id[item["id"]]))
    footer=(f'<h1>{tr("Выводы и следующий этап","Conclusions and next steps",lang)}</h1>'
            f'<div class="metrics">{metric(n,tr("Лотов","Lots",lang))}'
            f'{metric(data["distinct_procedures"],tr("Процедур","Procedures",lang))}'
            f'{metric(data["eis_223_notices"],tr("Извещений ЕИС","EIS notices",lang))}'
            f'{metric(sum(bool(x["contract_price"]) for x in items),tr("Полей цен договоров","Contract-price fields",lang))}</div>'
            f'<div class="call">{tr("Все закупки теперь представлены индивидуально. Следующий этап — оригинальные протоколы, ИНН подписантов, выделение цены оборудования и привязка повторных закупок к конкретным объектам.","Every procurement is now individually documented. Next: obtain original award protocols, signatory tax IDs, equipment-only pricing and deduplication by physical project.",lang)}</div>')
    slides.append(wrap("CONCLUSION",footer,len(slides)+1,
                       tr("РЕЗУЛЬТАТ","CONCLUSION",lang),lang))
    for pos,s in enumerate(slides,1):
        if s.count('<section ') != 1:
            raise ValueError(f"Malformed slide {pos}")
    report_date = data["snapshot_date"]
    date_label = ".".join(reversed(report_date.split("-")))
    body = "".join(slides).replace("POWER QUALITY</b> / 30.10.2026",
                                  "POWER QUALITY</b> / " + esc(date_label))
    return '<!doctype html><html lang="'+lang+'"><head><meta charset="utf-8"><style>'+CSS+'</style></head><body>'+body+'</body></html>',len(slides)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--snapshot",type=Path,default=SNAP)
    p.add_argument("--outdir",type=Path,default=Path("docs/market_intelligence"))
    p.add_argument("--html-only",action="store_true")
    p.add_argument("--version",default="V2",choices=["V2","V3","V4","V5","V6","V7","V8","V9","V10","V11","V12","V13","V14","V15","V16"])
    args=p.parse_args()
    data=json.loads(args.snapshot.read_text(encoding="utf8"))
    args.outdir.mkdir(parents=True,exist_ok=True)
    for lang in ("ru","en"):
        html_deck,pages=render(data,lang)
        stem=f"ARVECTUM_FGI_PQ_FULL_{lang.upper()}_{data['snapshot_date'].replace('-','')}_{args.version}"
        hp=args.outdir/(stem+".html")
        hp.write_text(html_deck,encoding="utf-8")
        print(f"{lang}: {pages} slide sections, {len(html_deck)} chars")
        if args.html_only:continue
        output=(args.outdir/(stem+".pdf")).resolve()
        profile="/tmp/fgi-deck-"+lang+"-"+str(__import__("os").getpid())
        cmd=["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
             "--headless=new","--disable-gpu","--no-first-run",
             "--no-default-browser-check",f"--user-data-dir={profile}",
             "--print-to-pdf-no-header",f"--print-to-pdf={output}",
             hp.resolve().as_uri()]
        r=subprocess.run(cmd,check=False,text=True,capture_output=True,timeout=150)
        if r.returncode or not output.is_file():
            raise RuntimeError("Browser PDF generation failed "+r.stderr[-700:])
        print(f"PDF: {output}, {output.stat().st_size} bytes")
if __name__=="__main__":
    main()
