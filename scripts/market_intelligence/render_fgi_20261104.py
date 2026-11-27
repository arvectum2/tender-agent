"""Evidence-aware bilingual ARVECTUM FGI 2026-11-04 client report.

123 live research lots. Reuse exactly the official RETO exemplar's brand,
grid and three-page per-lot design. Keep facts from sources, not inference.
"""
from __future__ import annotations

import argparse
import collections
import decimal
import html
import json
import subprocess
from pathlib import Path

from scripts.market_intelligence.render_fgi_full_deck import official_logo
from scripts.market_intelligence.render_reto_reference_slide import CSS as CASE_CSS

SNAP=Path("data/market_intelligence/power_quality/fgi_full_corpus_20261104.v1.json")
OUTPUT=Path("docs/market_intelligence")
BUCKET={
 "supply":("Поставка оборудования","Hardware supply"),
 "components":("Комплектующие","Components"),
 "mixed_supply":("Поставка + работы","Supply plus works"),
 "epc":("EPC / СМР","EPC / construction"),
 "design":("ПИР / проектирование","Engineering design"),
 "service":("Сервис / модернизация","Maintenance and upgrades"),
 "sounding":("Запросы цен / КП","RFQs and market sounding"),
 "other":("Прочее / уточняется","Other / to classify"),
}
FAMILY={
 "ukrm":("УКРМ / конденсаторные установки","UKRM switched capacitor systems"),
 "reactive_compensation_system":("Системы компенсации","Reactive-power systems"),
 "capacitor_bank":("БСК / конденсаторные батареи","Capacitor banks"),
 "capacitor_bank_component":("Компоненты БСК","Capacitor-bank components"),
 "capacitor_components":("Конденсаторные компоненты","Capacitor components"),
 "bsk":("БСК","Capacitor banks"),
 "statcom":("STATCOM / SVG","STATCOM / SVG"),
 "harmonic_filter":("Фильтрация гармоник","Harmonic filtering"),
 "svc":("СТК / SVC","SVC / TCR"),
 "svc_thyristor":("Тиристорная компенсация","Thyristor compensation"),
}
def esc(v):
    return html.escape(str(v) if v is not None and v!="" else "Не установлено",quote=True)
def tr(ru,en,lang):return ru if lang=="ru" else en
def label(key,dictionary,lang):
    return dictionary.get(key,(key or "—",key or "—"))[0 if lang=="ru" else 1]
def cut(s,limit=180):
    if s is None:return None
    a=" ".join(str(s).split())
    return a if len(a)<=limit else a[:limit-1].rsplit(" ",1)[0]+"…"
def missing(lang):return tr("Не установлено","Not established",lang)
def rub(v,lang,compact=False):
    try:
        if v is None:return missing(lang)
        n=decimal.Decimal(str(v).replace(" ","").replace(",","."))
        if n<0:return missing(lang)
        if compact and n>=1_000_000:
            return (f"{n/1_000_000:,.2f}".replace(","," ").replace(".",",")+" млн ₽") if lang=="ru" else f"RUB {n/1_000_000:,.2f}m"
        if lang=="ru":return f"{n:,.2f}".replace(","," ").replace(".",",")+" ₽"
        return f"RUB {n:,.2f}"
    except (ValueError,decimal.InvalidOperation,TypeError):
        return missing(lang)
def integer(v):
    try:return f"{int(v):,}".replace(","," ")
    except (ValueError,TypeError):return "—"
def scope_note(row,lang):
    b=row["scope_group"]
    return {
      "epc":tr("Стоимость процедуры может включать ПИР, оборудование, строительство и ПНР; это не цена отдельной УКРМ.","Total may include design, equipment, works and commissioning; not the device-only price.",lang),
      "design":tr("Проектные работы, не поставка нового оборудования.","Engineering work, not a new hardware sale.",lang),
      "sounding":tr("Ценовой запрос/мониторинг не означает заключённый договор.","Market sounding / RFQ is not a signed purchase.",lang),
      "service":tr("Сервис/ремонт оборудования, не обязательно новая поставка.","Service/repairs, not necessarily new hardware.",lang),
      "components":tr("Поставка компонентов не равна установке завершённого STATCOM/SVG.","Components are not a complete STATCOM/SVG system.",lang),
      "supply":tr("Предмет похож на поставку, но поставщик и исполнение подтверждаются отдельно.","Supply scope; signatory and execution still need independent proof.",lang),
    }.get(b,tr("Не отождествлять запрос, НМЦ и подписанный контракт.","Do not conflate request, initial price and signed contract.",lang))
def entry_label(key):
    labels={
     "type":"Тип оборудования","voltage_kv":"Номинал, кВ","ukrm_voltage_kv":"Номинал УКРМ, кВ",
     "power_kvar":"Реактивная мощность, квар","power_mvar":"Мощность, Мвар",
     "bsk_power_kvar":"Мощность БСК, квар","quantity":"Количество",
     "model1":"Модель 1","model2":"Модель 2","current_a":"Ток, А",
     "frequency_hz":"Частота, Гц","site":"Объект",
     "nominal_voltage_kv":"Номинал изделия, кВ","model":"Маркировка",
     "equipment":"Оборудование","equipment_voltage_kv":"Напряжение изделия",
    }
    return labels.get(key,key.replace("_"," "))
def flatten_technical(row):
    out=[]
    for k in ("voltage_kv","rated_power","quantity","model"):
        v=row.get(k)
        if v:
            suffix=" "+row["rated_power_unit"] if k=="rated_power" and row.get("rated_power_unit") else ""
            out.append((entry_label(k),str(v)+suffix))
    for kind,val in row.get("technical_details",{}).items():
        if isinstance(val,dict):
            for key,value in val.items():
                if value is None or value is False or value=="":continue
                if isinstance(value,(str,int,float,bool)):
                    out.append((entry_label(key),cut(value,95)))
                elif isinstance(value,list) and key=="requirements":
                    out.append((entry_label(key),cut(", ".join(str(z) for z in value),95)))
        elif isinstance(val,list):
            for v in val[:5]:
                if isinstance(v,dict):
                    parts=[str(v[k]) for k in ("model","units","qty","unit_price_rub")
                           if k in v and v[k] is not None]
                    if parts:out.append((kind,cut(" · ".join(parts),90)))
    unique=[];seen=set()
    for key,value in out:
        sig=(key,str(value))
        if sig in seen:continue
        seen.add(sig);unique.append((key,value))
    return unique
def has_source(row):
    return bool(row["sources"])
def case_missing(row):
    p={
     "identity":["buyer","buyer_inn","notice","date","platform"],
     "specification":["description","voltage_kv","rated_power","quantity","model"],
     "finance":["nmck","bid","contract_price","equipment_only_price","paid_amount"],
     "participants":["bidder","bidder_inn","signed_supplier","epc","designer","oem"],
     "evidence":["sources"],
    }
    missing_keys=[key for _,keys in p.items() for key in keys
                  if row.get(key) in (None,"",[],{})]
    # EPC/designer are not applicable to a pure component supply but remain explicit.
    return missing_keys
CSS=CASE_CSS+"""
.cover{background:#001432;color:#fff}
.cover .logo{top:36px;left:60px;width:250px}
.cover .logo svg{width:250px;height:44px}
.cover .logs{position:absolute;left:60px;top:88px;color:#9eb4c3;font-size:13px}
.cover .eyeb{position:absolute;left:62px;top:163px;color:#78FAE6;letter-spacing:2px;font-weight:800}
.cover .bigtitle{position:absolute;left:62px;top:240px;font-size:70px;line-height:1.02;color:#fff;font-weight:800;letter-spacing:-1.9px}
.cover .deke{position:absolute;left:65px;top:420px;width:670px;color:#c8dce2;font-size:20px;line-height:1.4}
.cover .datee{position:absolute;left:64px;bottom:52px;font-size:15px;color:#78FAE6;font-weight:800}
.cover > svg{position:absolute;top:225px;right:0;width:590px;height:250px}
.summary .main{top:111px}
.summary .title{font-size:34px;margin-bottom:8px}
.summary .subtitle{font-size:15px;margin-bottom:13px}
.summary .metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:11px;margin-top:24px}
.summary .metric{padding:17px;min-height:110px}
.summary .metric .big{font-family:"PT Sans";font-size:34px;color:#00a58e}
.summary .metric small{font-size:12px;line-height:1.25}
.analytical-grid{display:grid;grid-template-columns:1fr 1fr;gap:13px;margin-top:18px}
.analytical-grid .panel{padding:15px 17px}
.analytical-grid .panel h3{font-size:16px}
.barlist{margin-top:21px;display:grid;gap:10px}
.barrow{display:grid;grid-template-columns:250px 1fr 62px;gap:12px;align-items:center;font-size:15px}
.barrow .track{height:14px;border-radius:12px;background:#e1ecf1;overflow:hidden}
.barrow .track i{height:100%;display:block;background:#00bfa5;border-radius:12px}
.barrow strong{text-align:right;font-size:17px;color:#006c63}
.summary .call{background:#001432;color:#fff;padding:18px 22px;border-radius:10px;margin-top:19px;font-size:16px;line-height:1.33}
.summary .call b{color:#78FAE6}
.summary table{margin-top:18px;font-size:13px}
.summary table th{font-size:12px}
.summary table td{padding:8px 10px;line-height:1.2}
.summary .small-note{font-size:12px;color:#5a7583;margin-top:11px;line-height:1.35}
.index-list{display:grid;grid-template-columns:1fr 1fr;gap:8px 13px;margin-top:20px}
.index-list a{display:block;background:white;border:1px solid #dee7ed;border-radius:6px;
 padding:9px 12px;font-size:13px;text-decoration:none;color:#253c4a;overflow:hidden;
 text-overflow:ellipsis;white-space:nowrap}
.index-list b{color:#00a58e;margin-right:8px}
.report-case .eyebrow{text-transform:none;font-family:"JetBrains Mono",Menlo,monospace;font-size:10.5px;letter-spacing:0}
.report-case .title{font-size:30px;line-height:1.08}
.report-case .subtitle{font-size:14px}
.report-case .metricgrid{margin-top:12px}
.report-case .metric{min-height:87px}
.report-case .metric .big{font-size:21px;font-family:"JetBrains Mono",Menlo,monospace}
.report-case .metric .big.sm{font-size:15px;overflow-wrap:anywhere}
.report-case .panels{margin-top:9px}
.report-case .panel{padding:13px 16px}
.report-case .insight{font-size:14px;margin-top:9px;line-height:1.26;padding:12px 16px}
.report-case .footnote{font-size:10px;margin-top:4px}
.report-case .timeline .t{padding:8px 10px}
.report-case .price-row{grid-template-columns:1.1fr 2fr}
.report-case .price-row .desc{font-size:12.5px;text-align:right}
.report-case .price-row .m{font-size:12px}
.report-case .smallhead{font-size:12px;color:#008674;font-weight:800}
.report-case .trio-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:14px}
.report-case .trio-grid .panel:nth-child(2) .kv b{font-family:"JetBrains Mono",Menlo,monospace;font-size:11px;overflow-wrap:anywhere;word-break:break-word}
.report-case .kv{padding:5px 0;font-size:12.7px}
.report-case .sourcegrid{margin-top:12px;gap:8px}
.report-case .source{padding:9px 12px;min-height:55px;font-size:11.5px}
.report-case .source a{margin-top:2px}
.report-case .source .sha{font-size:9px;color:#758793}
.report-case .note{margin-top:10px;padding:10px 12px;font-size:12.4px}
.report-case .tech-scroll{max-height:140px;overflow:visible}
.report-case .tech-row{font-size:12px;line-height:1.23;padding:5px 0;border-bottom:1px solid #e1e7ea;display:grid;grid-template-columns:39% 61%;gap:8px}
.report-case .tech-row b{font-weight:600;color:#4e6878}
.report-case .tech-row span{font-weight:700;color:#182e40}
.report-case .more{font-size:11px;color:#68818b;margin-top:7px}
.source-page .main{top:102px;bottom:49px}
.source-page table{margin-top:10px}
.source-page table th{padding:7px 9px}
.source-page table td{padding:6px 9px;line-height:1.17}
.source-page .sourcegrid{margin-top:8px;gap:6px}
.source-page .source{padding:6px 10px;min-height:47px;line-height:1.2}
.source-page .source a{margin-top:2px}
.source-page .note{margin-top:7px;padding:8px 10px;font-size:12px;line-height:1.2}
.source-page .footnote{margin-top:5px}
.index .title{font-size:30px}
"""
def frame(body,lang,page,rail,rail_note="",anchor=None,kind="summary"):
    anc=f' id="{esc(anchor)}"' if anchor else ""
    brand=official_logo()
    text=(f'<section class="slide {kind}"{anc}>'
        f'<div class="logo">{brand}</div><div class="logosub">arvectum.com · Market Intelligence</div>'
        f'<div class="topline">ARVECTUM · PQ · 04.11.2026</div>'
        f'<div class="rail">{esc(rail)}</div>'
        f'<div class="rail-note"><div class="rail-badge">6–35 kV · PQ</div>{esc(rail_note)}</div>'
        f'<main class="main">{body}</main>'
        f'<footer><span><b>ARVECTUM</b> / POWER QUALITY / 04.11.2026</span>'
        f'<span>{tr("Исследовательский корпус — не реестр продаж","Research corpus ≠ completed sales",lang)}'
        f' &nbsp; <strong>{page:03d}</strong></span></footer></section>')
    return text
def title(t,desc="",eyebrow=""):
    return (f'<div class="eyebrow">{esc(eyebrow)}</div>' if eyebrow else "")+\
           f'<div class="title">{esc(t)}</div>'+\
           (f'<div class="subtitle">{esc(desc)}</div>' if desc else "")
def metric(v,k,sub=""):
    return (f'<div class="metric"><div class="mname">{esc(k)}</div>'
            f'<div class="big">{esc(v)}</div><small>{esc(sub) if sub else ""}</small></div>')
def grid_metrics(vals):
    return '<div class="metrics">'+''.join(metric(a,b,c) for a,b,c in vals)+'</div>'
def tab(headers,rows):
    return ('<table><thead><tr>'+''.join('<th>'+esc(h)+'</th>' for h in headers)+
        '</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in r)+
        '</tr>' for r in rows)+'</tbody></table>')
def bars(rows,maxval):
    return '<div class="barlist">'+''.join(
        f'<div class="barrow"><span>{esc(t)}</span><div class="track">'
        f'<i style="width:{max(0,min(100,100*n/maxval)):.1f}%"></i></div>'
        f'<strong>{n}</strong></div>' for t,n in rows
    )+'</div>'
def panel(caption,inner):
    return f'<div class="panel"><h3>{esc(caption)}</h3>{inner}</div>'
def notes(text,lang):
    return f'<div class="call">{esc(text)}</div>'
def business_roles(r):
    return [("buyer",r["buyer"]),("winner",r["bidder"]),
            ("contract",r["signed_supplier"]),("epc",r["epc"]),
            ("designer",r["designer"]),("oem",r["oem"])]
def cover(data,lang):
    title1="POWER QUALITY"
    title2=tr("РОССИЯ · 2023–2026","RUSSIA · 2023–2026",lang)
    desc=tr(
      f"Полный проверяемый срез: {data['unique_lots']} уникальных закупочных лота. Аналитика и отдельное трёхстраничное досье по каждой позиции.",
      f"Complete auditable snapshot: {data['unique_lots']} unique procurement lots. Market analytics and a dedicated three-page dossier per case.",lang)
    return f'''<section class="slide cover"><div class="logo">{official_logo()}</div>
    <div class="logs">arvectum.com · Tender Agent / Data Platform</div>
    <div class="eyeb">{tr("РЫНОЧНОЕ ИССЛЕДОВАНИЕ · 6–35 КВ","MARKET INTELLIGENCE · 6–35 KV",lang)}</div>
    <div class="bigtitle">{title1}<br>{title2}</div><div class="deke">{esc(desc)}</div>
    <div class="datee">{tr("Срез: 4 ноября 2026","As of 4 November 2026",lang)} · ARVECTUM</div>
    <svg viewBox="0 0 590 250" xmlns="http://www.w3.org/2000/svg" fill="none" stroke="#00C8A0" stroke-width="2.8">
      <path d="M0 72 C110 18 172 150 278 102 S470 163 590 98"/>
      <path d="M0 103 C110 49 172 181 278 133 S470 194 590 129"/>
      <path d="M0 134 C110 80 172 212 278 164 S470 225 590 160"/>
    </svg></section>'''
def summary_pages(data,lang):
    rows=data["items"];n=len(rows);pages=[]
    def add(label_ru,label_en,body):
        pages.append((tr(label_ru,label_en,lang),body))
    cov={key:sum(bool(r.get(key)) for r in rows) for key in (
      "nmck","bid","contract_price","contract_no","contract_signed_verified",
      "signed_supplier_verified","equipment_only_price","paid_verified",
      "oem_verified","buyer_inn","voltage_kv","rated_power","quantity","bidder","sources")}
    years=collections.Counter((r.get("date") or "")[:4] or "unknown" for r in rows)
    sc=data["scope_counts"];grade=data["grade_counts"]
    add("РЕЗЮМЕ","EXECUTIVE",
        title(tr("Реальный спрос есть; исполненные поставки не доказаны","Demand found; completed supply revenue unverified",lang),
          tr("Исследовательский корпус: юридические лоты, ценовые запросы, EPC, ПИР и сервис, а не 123 подписанных договора.","A corpus of legal lots, market soundings, EPC, design and services—not 123 executed contracts.",lang))
        +grid_metrics([
          (n,tr("Лотов","Lots",lang),""),
          (data["distinct_procedures"],tr("ID процедур","Procedure IDs",lang),""),
          (data["eis_223_notices"],tr("Извещений ЕИС","EIS notices",lang),""),
          (cov["contract_signed_verified"],tr("Флаг договора","Contract flag",lang),tr("Подписант отдельно","Signatory unverified",lang))])
        +'<div class="call">'+tr(
           "<b>Вывод:</b> УКРМ, БСК, STATCOM, SVC и фильтры встречаются в закупках, но подтвердить точную стоимость оборудования, подписанта, OEM и оплату удаётся далеко не для всех объектов.",
           "<b>Finding:</b> UKRM, capacitor banks, STATCOM, SVC and filtering appear, but equipment-only costs, signatories, OEMs and payment remain sparsely evidenced.",lang)+'</div>')
    b1=panel(tr("Юридический лот","Legal lot",lang),f'<h3>{n}</h3><p>{tr("Ключ notice:lot, не количество устройств и не договоров.","Canonical notice:lot key, not a contract or installed device.",lang)}</p>')
    b2=panel(tr("Процедуры","Procedure IDs",lang),f'<h3>{data["distinct_procedures"]}</h3><p>{tr("Одна процедура может включать несколько лотов.","One procedure can contain multiple lots.",lang)}</p>')
    b3=panel(tr("Что не входит в выборку","Coverage exclusions",lang),tr(
        "Нет доказанной полноты всех ЕИС и коммерческих ЭТП; повторные этапы проекта могут пересекаться с одним объектом.",
        "No guarantee of exhaustive EIS or commercial platform coverage; one facility may have multiple overlapping procedures.",lang))
    b4=panel(tr("Уровень документов","Evidence meaning",lang),tr(
        "Оригинальный документ или SHA подтверждают только указанные в нём факты. Протокол ≠ договор ≠ акт ≠ платёж.",
        "An original or SHA proves only its stated facts. Protocol ≠ contract ≠ acceptance ≠ payment.",lang))
    add("МЕТОДОЛОГИЯ","METHOD",
        title(tr("Лот, процедура, договор и установка — разные сущности","A lot, a procedure, a contract and a device differ",lang),
          tr("Ключевые определения, обязательные для корректного коммерческого отчёта.","Counting rules for commercial integrity.",lang))
        +'<div class="analytical-grid">'+b1+b2+b3+b4+'</div>')
    groups=[(label(k,BUCKET,lang),sc.get(k,0)) for k in
            ("supply","components","mixed_supply","epc","design","service","sounding","other")]
    add("СТРУКТУРА","SCOPE",
        title(tr("Распределение по предмету закупки","Procurement scopes",lang),
          tr("Взаимоисключающие категории для подсчёта; отдельный EPC может содержать разные виды PQ.","Exclusive counting categories; individual EPC packages can contain multiple PQ technologies.",lang))
        +bars(groups,max(n for _,n in groups))
        +'<div class="small-note">'+tr(
          "Запрос на поставку и ценовой мониторинг не доказывают поставку и реализацию оборудования.",
          "A supply request or market sounding is not a completed purchase.",lang)+'</div>')
    families=collections.Counter(x["family"] or "unknown" for x in rows)
    fam=[(label(k,FAMILY,lang),v) for k,v in families.most_common(9)]
    add("ТЕХНОЛОГИИ","TECHNOLOGIES",
        title(tr("Технологический профиль","Technology families",lang),
          tr("Из описаний лотов; наличие класса не означает взаимозаменяемость с техникой FGI.","Derived from lot descriptions; a technology name does not prove FGI substitution compliance.",lang))
        +bars(fam,max(q for _,q in fam)))
    yrs=[(tr("Без даты","Unknown date",lang) if y=="unknown" else y,years.get(y,0))
         for y in ("2023","2024","2025","2026","unknown")]
    add("ГОДЫ ПУБЛИКАЦИИ","YEARS",
        title(tr("Срез 2023–2026: найденные, а не все закупки","Discovery by year, not market growth",lang),
          tr("По дате исходной публикации в карточке; неполнота поиска не позволяет оценить национальную динамику.","Publication dates in available records; coverage is not exhaustive for market-wide growth analysis.",lang))
        +bars(yrs,max(v for _,v in yrs))
        +'<div class="call">'+tr(
          "<b>Не экстраполировать:</b> преобладание 2026 года отражает глубину текущего поиска и доступность источников, а не достоверный скачок спроса.",
          "<b>No extrapolation:</b> 2026 dominates partly because of collection depth and source access, not verified nationwide demand growth.",lang)+'</div>')
    eis_n=data["eis_223_lots"]
    add("ИСТОЧНИКИ","CHANNELS",
        title(tr("ЕИС 223-ФЗ и коммерческие каналы","223-FZ notices and commercial channels",lang),
          tr("Юридический статус и полнота документации отличаются по типу площадки.","Legal status and documentary evidence vary by platform.",lang))
        +grid_metrics([
         (eis_n,tr("Лотов ЕИС 223-ФЗ","223-FZ lots",lang),""),
         (data["eis_223_notices"],tr("Извещений ЕИС","223-FZ notices",lang),""),
         (n-eis_n,tr("Прочих карточек","Other cards",lang),""),
         (cov["sources"],tr("С URL источника","With source URL",lang),"")])
        +tab([tr("Канал","Channel",lang),tr("Число","Lots",lang),tr("Подтверждает","Evidence scope",lang)],
         [[tr("Оригинальный номер 223-ФЗ","Original EIS 223-FZ ID",lang),eis_n,
           tr("Извещение; договор требует отдельного подтверждения","Notice; contract needs independent evidence",lang)],
          [tr("Прочие ЭТП и индексы","Other platforms / indexes",lang),n-eis_n,
           tr("Могут включать ценовые запросы и смежные этапы","Can include price enquiries or adjacent stages",lang)]])
        +'<div class="small-note">'+tr("Вторичная карточка не превращается в официальный реестр контрактов.",
                                       "Third-party index pages cannot establish an official executed contract.",lang)+'</div>')
    buyers={}
    for row in rows:
        key=row["buyer_inn"] or row["buyer"] or "unknown"
        rec=buyers.setdefault(key,[row["buyer"] or "—",0, bool(row["buyer_inn"])])
        rec[1]+=1
        if len(row["buyer"] or "")<len(rec[0]):rec[0]=row["buyer"]
    top=sorted(buyers.values(),key=lambda a:a[1],reverse=True)[:9]
    add("ПОКУПАТЕЛИ","BUYERS",
        title(tr("Наиболее часто встречающиеся заказчики и организаторы","Top recurring buyers / organizers",lang),
          tr("Группировка по ИНН, если он известен; иначе по тексту имени. Одинаковые объекты могут пересекаться.","Grouped by tax ID where available, otherwise by exact name; overlaps are possible.",lang))
        +tab([tr("Организация / отображаемое имя","Organization / source label",lang),
              tr("Лотов","Lots",lang)],[[cut(x[0],64),x[1]] for x in top])
        +'<div class="small-note">'+tr(
          f"ИНН сохранён в {cov['buyer_inn']} из {n} карточек. Корпоративный организатор не всегда конечный владелец объекта.",
          f"Tax ID populated for {cov['buyer_inn']} of {n} rows. An organizer is not necessarily the final beneficiary.",lang)+'</div>')
    def coverage_lines(items):
        return bars([(name,cov[key]) for key,name in items],n)
    add("ПОЛНОТА СВЕДЕНИЙ","DATA COVERAGE",
        title(tr("Ключевые поля заполнены неравномерно","Critical fields are sparsely populated",lang),
          tr("Заполненность ≠ независимая первичная проверка каждой цифры.","Populated does not mean each number was independently verified.",lang))
        +coverage_lines([
           ("buyer_inn",tr("ИНН заказчика","Customer tax ID",lang)),
           ("nmck",tr("НМЦ","Initial price",lang)),
           ("contract_price",tr("Цена договора / сигнал","Contract price / signal",lang)),
           ("voltage_kv",tr("Номинал изделия, кВ","Equipment kV",lang)),
           ("rated_power",tr("Реактивная мощность","Reactive power",lang)),
           ("bid",tr("Предложение комиссии","Bid amount",lang)),
           ("bidder",tr("Названный участник","Named bidder",lang))])
        +'<div class="small-note">'+tr(
          "Пустые поля не означают, что победителя, договора или оплаты не существует; это открытые вопросы исследования.",
          "Missing fields do not mean a winner, signed contract or payment does not exist; they require further evidence.",lang)+'</div>')
    add("ДОГОВОРЫ","CONTRACTS",
        title(tr("Наличие договора и личность поставщика — разные факты","Contract evidence is not supplier identity",lang),
          tr("Агрегированы только явно сохранённые поля; нет подтверждения фактической оплаты или исполнения.","Only stored record fields are counted; cash payment and execution are not established.",lang))
        +grid_metrics([
           (cov["contract_signed_verified"],tr("Признак реестра договора","Contract registry flag",lang),""),
           (cov["contract_no"],tr("Номер договора","Contract ID present",lang),""),
           (cov["signed_supplier_verified"],tr("Подписант подтверждён","Signed supplier proven",lang),""),
           (cov["paid_verified"],tr("Оплата подтверждена","Payment proven",lang),"")])
        +'<div class="call">'+tr(
          "<b>Оговорка:</b> 20 карточек имеют явный признак зарегистрированного договора, но он не доказывает личность подписанта, стоимость только PQ-оборудования или исполнение. Протокольный победитель — отдельная роль.",
          "<b>Qualification:</b> 20 cards carry registered-contract flags; they do not establish the signatory, equipment-only value or performance. A commission winner is a distinct role.",lang)+'</div>')
    add("ФИНАНСЫ","FINANCIAL FIELDS",
        title(tr("НМЦ, предложение, договор, оборудование и оплата — пять разных показателей","Five distinct financial categories",lang),
          tr("Суммирование всех указанных сумм создаёт ложный объём рынка — особенно для EPC и проектирования.","Adding all listed prices creates false market turnover, especially when EPC and design are mixed in.",lang))
        +grid_metrics([
           (cov["nmck"],tr("НМЦ","NMC populated",lang),""),
           (cov["bid"],tr("Протокольная цена","Bid amount",lang),""),
           (cov["contract_price"],tr("Цена договора / сигнал","Contract price field",lang),""),
           (cov["equipment_only_price"],tr("Цена PQ отдельно","Equipment-only field",lang),"")])
        +tab([tr("Показатель","Metric",lang),tr("Интерпретация","How to interpret",lang)],
         [[tr("НМЦ","NMC",lang),tr("Предельная цена закупки, не платёж","Budget ceiling; not a payment",lang)],
          [tr("Предложение","Bid",lang),tr("Комиссия или заявка, не поставка","Bid/protocol; not delivered goods",lang)],
          [tr("Договор","Contract",lang),tr("Проверить состав, подписанта и условия","Check scope, parties and terms",lang)],
          [tr("PQ-оборудование","PQ hardware",lang),tr("Только выделенный предмет и обоснованная цена","Hardware-only price where supported",lang)],
          [tr("Оплата","Payment",lang),tr("Нужны платёжные документы и приёмка","Requires payment and acceptance evidence",lang)]]))
    top_budget=[]
    for r in rows:
        try:
            if r["nmck"] and decimal.Decimal(str(r["nmck"]))>0:
                top_budget.append((decimal.Decimal(str(r["nmck"])),r))
        except decimal.InvalidOperation:pass
    top_budget.sort(reverse=True,key=lambda t:t[0])
    add("КРУПНЫЕ БЮДЖЕТЫ","TOP NMC",
        title(tr("Крупнейшие НМЦ — преимущественно сложные проекты","Largest budgets are not device-only sales",lang),
          tr("Ниже финансовые потолки процедур, а не исполненная выручка производителей PQ.","Ceilings of mixed-scope tenders, NOT OEM sales revenue.",lang))
        +tab([tr("Заказчик / объект","Buyer / facility",lang),
              tr("Класс","Scope",lang),tr("НМЦ","NMC",lang)],
             [[cut(r["buyer"] or r["project"],50),
               label(r["scope_group"],BUCKET,lang),rub(amount,lang,True)]
              for amount,r in top_budget[:7]])
        +'<div class="small-note">'+tr(
           "Сверхкрупные проекты Хани и Лопча — EPC и строительство в сетях 220 кВ, а не только 6–35 кВ оборудование; сравнение с ценой устройства некорректно.",
           "Khani and Lopcha are 220 kV network EPC packages, not solely 6–35 kV PQ hardware; direct price comparison is invalid.",lang)+'</div>')
    tier=[(tr("A — первичка + цифровой след","A — original + SHA/bytes",lang),grade.get("A",0)),
          (tr("B — первичный адрес","B — first-party link",lang),grade.get("B",0)),
          (tr("C — вторичная карточка","C — third-party index",lang),grade.get("C",0)),
          (tr("D — без URL","D — no linked URL",lang),grade.get("D",0))]
    add("ДОКАЗАТЕЛЬСТВА","SOURCE GRADES",
        title(tr("Матрица качества источников","Source provenance by lot",lang),
          tr("Класс относится к наличию исходного документа у лота; он не присваивается автоматически всем полям.","A tier describes available lot-level provenance, not verification of every attribute.",lang))
        +bars(tier,max(q for _,q in tier))
        +'<div class="call">'+tr(
          "<b>Приоритет:</b> сначала получить оригинальные ТЗ и протоколы у 54 карточек класса C, затем заполнить участника, договор, изготовителя и факт исполнения. Для класса A тоже требуется проверять каждое поле.",
          "<b>Priority:</b> obtain original specifications and protocols for the 54 C-grade records, then verify bidders, signed contracts, OEMs and performance. A-grade cases still need field-specific scrutiny.",lang)+'</div>')
    supply=[r for r in rows if r["scope_group"] in ("supply","components","mixed_supply")]
    supply_rank=sorted((r for r in supply if r["nmck"]),
        key=lambda r:decimal.Decimal(str(r["nmck"])) if str(r["nmck"]).replace(".","",1).isdigit() else 0,
        reverse=True)
    add("ПОСТАВКИ","SUPPLY PIPELINE",
        title(tr("Прямые поставки и компоненты: ценовые ориентиры","Hardware supply signals and ceilings",lang),
          tr("Суммы по одному юридическому лоту; статус подписания и исполнение нужно проверять отдельно.","Per-lot amounts; contract signature and execution require independent evidence.",lang))
        +tab([tr("Лот / покупатель","Lot / buyer",lang),tr("Предмет","Equipment subject",lang),
              tr("НМЦ / ограничение","NMC / ceiling",lang)],
            [[cut(r["buyer"],41),cut(r["description"],80),rub(r["nmck"],lang,True)]
             for r in supply_rank[:7]])
        +'<div class="small-note">'+tr(
          "Коммерческие запросы и отменённые процедуры не включать в выручку. Схожие лоты могут быть последовательными этапами одного проекта.",
          "Commercial requests and cancelled tenders are not revenue; similar lots can be different stages of one project.",lang)+'</div>')
    epc=[r for r in rows if r["scope_group"]=="epc" and r["nmck"]]
    epc.sort(key=lambda r:decimal.Decimal(str(r["nmck"])) if str(r["nmck"]).replace(".","",1).isdigit() else 0,reverse=True)
    add("EPC / РЕКОНСТРУКЦИЯ","EPC",
        title(tr("Комплексная модернизация подстанций: PQ внутри EPC","PQ subsystems embedded in EPC packages",lang),
          tr("Большие суммы включают проект, строительство, оборудование и пусконаладку.","Large figures include design, construction, equipment and commissioning.",lang))
        +tab([tr("Процедура","Tender",lang),tr("Объект / содержание","Facility / scope",lang),tr("НМЦ","NMC",lang)],
            [[r["notice"] or cut(r["id"],18),
              cut(r["project"] or r["description"],90),rub(r["nmck"],lang,True)]
             for r in epc[:6]])
        +'<div class="small-note">'+tr(
          "Ни одна из этих сумм не трактуется как цена отдельного устройства без выделенной спецификации оборудования.",
          "None of these totals is treated as a single device price without an equipment-only bill.",lang)+'</div>')
    known=[r for r in rows if r["bidder"]]
    add("УЧАСТНИКИ","BIDDERS",
        title(tr("Победители по протоколам ≠ подписавшие договор","Named commission bidders ≠ contract signatories",lang),
          tr("Перечисляем только имена, реально сохранённые в карточках. Отсутствие имени — пробел исследования.","Only actually recorded names are listed; a missing name is an evidence gap.",lang))
        +tab([tr("Процедура","Procedure",lang),tr("Участник из карточки","Named bidder",lang),
              tr("Предложение / сигнал","Offer",lang)],
             [[cut(r["notice"] or r["id"],24),cut(r["bidder"],56),rub(r["bid"],lang,True)]
              for r in known[:7]])
        +'<div class="call">'+tr(
           "<b>Отдельное правило:</b> ООО «ЭКСПЕРТ ГРУПП» доказан как победитель комиссии РЭТО по протоколу №186-2, но имя подписанта договора и завод-изготовитель не опубликованы в доступной первичке.",
           "<b>Separate roles:</b> EXPERT GROUP is proven as the RETO commission winner in protocol 186-2; the signed contracting supplier and OEM remain unverified.",lang)+'</div>')
    add("НАПРЯЖЕНИЯ","VOLTAGE",
        title(tr("Техническое соответствие: номинал конкретного устройства","Technical fit requires equipment-rated voltage",lang),
          tr("Класс подстанции 110/220 кВ не равен напряжению УКРМ, фильтра или STATCOM внутри проекта.","A 110/220 kV substation rating is NOT the rated voltage of an embedded compensation device.",lang))
        +grid_metrics([
            (cov["voltage_kv"],tr("Номинал в поле","Rated kV populated",lang),""),
            (n-cov["voltage_kv"],tr("Нет номинала","Rated kV missing",lang),""),
            (cov["rated_power"],tr("Мощность в поле","Rated kvar/Mvar known",lang),""),
            (cov["quantity"],tr("Количество в поле","Quantity present",lang),"")])
        +'<div class="analytical-grid">'
        +panel(tr("Что проверять","Validation items",lang),tr(
           "Номинал Uн, мощность kvar/Mvar, ступени, реакторы, гармоники, климат, SCADA, испытания и условия допуска аналога.",
           "Rated kV, kvar/Mvar, steps/reactors, harmonics, climate, SCADA, type tests and substitution rules.",lang))
        +panel(tr("Запрет на подмену","No automatic substitution",lang),tr(
           "IGBT SVG, ступенчатая УКРМ и тиристорный SVC решают близкие задачи, но не взаимозаменяемы без проверки ТЗ.",
           "IGBT SVG, switched UKRM and thyristor SVC address related functions but are not automatically interchangeable.",lang))
        +'</div>')
    add("РЫНОЧНЫЕ РОЛИ","COMMERCIAL ROLES",
        title(tr("Фактическая цепочка поставки пока не установлена","Supply-chain roles require more evidence",lang),
          tr("Отделяем организатора закупки, покупателя, EPC, проектировщика, участника, поставщика и OEM.",
             "Separate procurement organizers, buyers, EPCs, designers, bidders, suppliers and OEMs.",lang))
        +grid_metrics([
          (cov["buyer_inn"],tr("ИНН заказчика","Buyer tax IDs",lang),""),
          (cov["bidder"],tr("Участник назван","Named bidders",lang),""),
          (cov["signed_supplier_verified"],tr("Подписант доказан","Proven signatories",lang),""),
          (cov["oem_verified"],tr("OEM доказан","Proven OEMs",lang),"")])
        +'<div class="call">'+tr(
          "<b>Проблема:</b> без подтверждённого ИНН договорного контрагента и документов на изделие нельзя строить надёжный рейтинг поставщиков, EPC или производителя оборудования.",
          "<b>Gap:</b> supplier rankings or OEM attribution require signed-contract counterparties and original product documents; protocol names alone are insufficient.",lang)+'</div>')
    registered=[r for r in rows if r["contract_price"]]
    registered.sort(key=lambda r:decimal.Decimal(str(r["contract_price"]))
                    if str(r["contract_price"]).replace(".","",1).isdigit() else 0,reverse=True)
    add("ЦЕНЫ ДОГОВОРОВ","REPORTED CONTRACTS",
        title(tr("Договорные суммы: важно проверять их предмет","Reported contract prices need scope scrutiny",lang),
          tr("Цены поля реестра/источника не доказывают расчёт, поставку или производственный OEM.","Registry or secondary price fields do not establish payment, delivery or the manufacturer.",lang))
        +tab([tr("Закупка","Case",lang),tr("Вид","Scope",lang),tr("Цена, ₽","Reported price",lang)],
           [[cut(r["id"],43),label(r["scope_group"],BUCKET,lang),rub(r["contract_price"],lang,True)]
            for r in registered[:7]])
        +'<div class="small-note">'+tr(
          "Для любого EPC сумму договора нельзя без выделения номенклатуры приравнивать к прямым поставкам PQ-оборудования.",
          "Mixed EPC contract values must not be treated as PQ-equipment-only prices.",lang)+'</div>')
    add("FGI / КАНАЛ ПРОДАЖ","FGI / CHANNEL",
        title(tr("Векторы коммерческого развития FGI","FGI go-to-market opportunities",lang),
          tr("Не утверждение о присутствии FGI в сделках, а сегментация проверяемого спроса.","Demand segmentation for due diligence, not evidence of FGI sales.",lang))
        +'<div class="analytical-grid">'
        +panel(tr("Прямые поставки","Direct supply",lang),tr(
          "Изучать действующие УКРМ/БСК, реальные кВ/Мвар, ограничения аналогов и срок поставки; требуются допуск и техника.",
          "Check exact UKRM/bank specifications, kV/Mvar, permissible equivalents, delivery and approval requirements.",lang))
        +panel(tr("Проектировщики и EPC","Designers and EPCs",lang),tr(
          "Ранние ТЗ и ПИР — точки входа для SVG/STATCOM; необходимы типовые решения и расчёты сетевых режимов.",
          "Design/EPC stages enable early SVG/STATCOM positioning; supply engineering studies and compliant design inputs.",lang))
        +panel(tr("Компоненты","Components",lang),tr(
          "Требования к конденсаторам, реакторам, фильтрам не превращать в факт продажи законченного преобразователя.",
          "Capacitor, reactor or filter components are not proof of a completed power-electronics solution sale.",lang))
        +panel(tr("Аттестация","Qualification",lang),tr(
          "Сверять аттестацию «Россетей», стандарты, климатическое исполнение, схему защиты и телемеханику.",
          "Validate Rosseti accreditation, standards, climatic class, protection and telemetry interfaces.",lang))
        +'</div>')
    add("ОЧЕРЕДЬ ВЕРИФИКАЦИИ","RESEARCH BACKLOG",
        title(tr("Последовательное заполнение каждого лота P0–P5","Evidence-enrichment workflow P0–P5",lang),
          tr("Статус «не установлено» означает исследовательскую задачу, а не отсутствие события.","Unknown means a research task, not proof the event never occurred.",lang))
        +tab([tr("Приоритет","Step",lang),tr("Что добавляем","Required evidence",lang),
              tr("Критерий готовности","Done when",lang)],
           [[ "P0",tr("Дедупликация и идентичность","Canonical identity",lang),tr("Один notice:lot","Unique notice:lot",lang)],
            [ "P1",tr("Оригинальное извещение / заказчик / ИНН","Notice + buyer/tax ID",lang),tr("URL + первичный файл","URL + original file",lang)],
            [ "P2",tr("ТЗ: Uн, мощность, количество, модель","Rated equipment spec",lang),tr("Точная строка ТЗ","Exact original specification",lang)],
            [ "P3",tr("Протокол: участники / победитель / ИНН","Bids and winner",lang),tr("Датированный протокол","Dated commission document",lang)],
            [ "P4",tr("Подписанный договор, цену изделия отдельно","Signed contract and item prices",lang),tr("Подписант и состав","Signatory and BOM",lang)],
            [ "P5",tr("OEM, отгрузка, акт, оплачено","OEM, delivery, payment",lang),tr("Акт и платёж","Acceptance and payment proof",lang)]])
        +'<div class="small-note">'+tr(
          "Наиболее уязвимые позиции: 54 карточки класса C и ещё не заполненные поля сумм/технических параметров.",
          "Highest-risk records are 54 source-grade-C entries and missing prices/technical parameters.",lang)+'</div>')
    add("УСЛОВИЯ ИСТОЧНИКОВ","LIMITATIONS",
        title(tr("Как пользоваться результатом без искажения рынка","How to use the report without overclaiming",lang),
          tr("Каждый лот далее сопровождается тремя слайдами: обзор, техника/финансы, участники/источники.","Every lot receives three pages: case overview, technical/financial data and participants/sources.",lang))
        +'<div class="analytical-grid">'
        +panel(tr("Что уже есть","Documented now",lang),tr(
          "Заказчики, предмет, часть первичных файлов и протоколов, отдельные суммы и технические характеристики.",
          "Buyers, descriptions, selected originals/protocols, some prices and equipment specifications.",lang))
        +panel(tr("Что ещё не доказано","Not established yet",lang),tr(
          "Исчерпывающий рынок, большая часть подписантов и OEM, реальная оплата, цена устройства внутри EPC.",
          "Exhaustive market, most signatories/OEMs, actual payment, equipment-only pricing within EPC.",lang))
        +panel(tr("Технические числа","Technical quantities",lang),tr(
          "Номинал берётся из явного поля устройства. Напряжение подстанции само по себе не используется как номинал.",
          "Rated kV must explicitly refer to the device; substation ratings are not substituted.",lang))
        +panel(tr("Источник и дата","Provenance and date",lang),tr(
          "Ссылки отражают сохранённые сведения корпуса на 4.11.2026; недоступный оригинал и исторический архив различаются.",
          "Links reflect frozen records as of 4 Nov 2026; inaccessible originals and historical archives are distinct.",lang))
        +'</div>')
    return pages
def index_pages(rows,lang,start_number):
    pages=[];step=16
    for start in range(0,len(rows),step):
        chunk=rows[start:start+step]
        body=title(tr("Указатель закупочных досье","Procurement dossier index",lang)+
                   f" · {start//step+1:02d}",
             tr("Нажмите на строку, чтобы перейти к трём страницам соответствующего лота.",
                "Select a row to open its three-page individual dossier.",lang))
        text=''.join(f'<a href="#case-{start+i+1}"><b>{start+i+1:03d}</b>'
            f' {esc(cut(r["buyer"],36))} — {esc(cut(r["id"],45))}</a>'
            for i,r in enumerate(chunk))
        body+='<div class="index-list">'+text+'</div>'
        pages.append(frame(body,lang,start_number+len(pages),
                           tr("РЕЕСТР ЛОТОВ","LOT REGISTER",lang),
                           tr("Все записи: 1 ID = 1 юридический лот",
                              "Each case ID appears only once in the register",lang),kind="summary index"))
    return pages

def case_head(r,i,total,lang,section):
    return ('<div class="eyebrow">'
            +esc(f"{tr('ДОСЬЕ','DOSSIER',lang)} {i:03d}/{total:03d} · {r['id']}")
            +'</div>')
def small_rows(pairs,lang,maxrows=7):
    pairs=pairs[:maxrows]
    return ''.join(f'<div class="kv"><span>{esc(k)}</span><b>{esc(v if v else missing(lang))}</b></div>'
                   for k,v in pairs)
def key_value_row(a,b):
    return f'<div class="tech-row"><b>{esc(a)}</b><span>{esc(b)}</span></div>'
def status_label(r,lang):
    if r["contract_signed_verified"]:
        return tr("Договор указан в реестре/источнике","Registered contract reported",lang)
    if r["bidder"]:
        return tr("Участник комиссии назван","Commission bidder named",lang)
    if "cancel" in (r["status"] or "").lower():
        return tr("Отмена по карточке","Cancellation recorded",lang)
    if r["scope_group"]=="sounding":
        return tr("Запрос цен / КП","Market sounding / RFQ",lang)
    return tr("Итог требует проверки","Outcome requires verification",lang)
def case_page1(r,i,total,lang,page):
    site=r["buyer"] or missing(lang)
    sub=site+((" · "+tr("ИНН","TIN",lang)+" "+r["buyer_inn"]) if r["buyer_inn"] else "")
    head=(cut(r["description"],101) or cut(r["project"],101) or tr("Предмет не установлен","Subject not specified",lang))
    head=tr("Закупка: ","Procurement: ",lang)+head
    equipment=missing(lang)
    if r["voltage_kv"]:
        equipment=str(r["voltage_kv"])+" kV"
        if r["rated_power"]:equipment+=" · "+str(r["rated_power"])+" "+(r["rated_power_unit"] or "")
    bidder=r["bidder"] or missing(lang)
    flags=[
      (tr("НМЦ / лимит","Initial price",lang),rub(r["nmck"],lang),tr("Не договор","Not signed value",lang)),
      (tr("Цена договора из источника","Reported contract value",lang),rub(r["contract_price"],lang),
       tr("Состав проверить","Check scope",lang)),
      (tr("Номинал изделия","Equipment rating",lang),equipment,
       tr("Нет номинала по ТЗ","No confirmed rated kV",lang) if not r["voltage_kv"] else ""),
      (tr("Участник комиссии","Commission bidder",lang),cut(bidder,44),""),
    ]
    metric_html=''.join(f'<div class="metric"><div class="mname">{esc(k)}</div>'
        f'<div class="big{" sm" if len(str(v))>16 else ""}">{esc(v)}</div><small>{esc(note)}</small></div>'
        for k,v,note in flags)
    subject=(
      key_value_row(tr("Объект","Facility",lang),cut(r["project"],165) or missing(lang))+
      key_value_row(tr("Тип","Scope",lang),label(r["scope_group"],BUCKET,lang))+
      key_value_row(tr("Технология","Family",lang),label(r["family"],FAMILY,lang))+
      key_value_row(tr("Предмет по исходной записи","Original case subject",lang),
                    cut(r["description"],190) or missing(lang))
    )
    status=(
      key_value_row(tr("Размещение","Published",lang),r["date"] or missing(lang))+
      key_value_row(tr("Срок / дедлайн","Deadline",lang),r["deadline"] or missing(lang))+
      key_value_row(tr("Дата договора","Contract date",lang),r["contract_date"] or missing(lang))+
      key_value_row(tr("Стадия","Stage",lang),status_label(r,lang))
    )
    body=case_head(r,i,total,lang,"case1")
    body+=title(head,sub)
    body+='<div class="metricgrid">'+metric_html+'</div>'
    body+='<div class="panels">'+panel(tr("Что закупалось","Scope and buyer demand",lang),subject)+\
          panel(tr("Хронология и результат","Timeline and reported status",lang),status)+'</div>'
    note=scope_note(r,lang)
    body+='<div class="insight"><b>'+tr("ИНТЕРПРЕТАЦИЯ: ","INTERPRETATION: ",lang)+'</b>'+esc(note)+'</div>'
    body+='<div class="footnote">'+tr(
       "Источники и недостающие сведения — на третьем слайде; оригинальные технические поля — на втором.",
       "Source links and missing facts on page 3; original technical and financial details on page 2.",lang)+'</div>'
    return frame(body,lang,page,tr("КАРТОЧКА ЗАКУПКИ","PROCUREMENT CARD",lang),
                 label(r["scope_group"],BUCKET,lang),anchor=f"case-{i}",kind="report-case")
def case_page2(r,i,total,lang,page):
    tech=flatten_technical(r)
    base=[
       (tr("Модель / тип","Model / type",lang),r["model"]),
       (tr("Номинал устройства","Equipment voltage",lang),
        str(r["voltage_kv"])+" kV" if r["voltage_kv"] else None),
       (tr("Реактивная мощность","Reactive rating",lang),
        str(r["rated_power"])+" "+(r["rated_power_unit"] or "") if r["rated_power"] else None),
       (tr("Количество","Quantity",lang),
        str(r["quantity"])+" "+(r["quantity_unit"] or "") if r["quantity"] else None),
    ]
    for k,v in tech:
        if len(base)>=10:break
        if (k,v) not in base and v:
            base.append((k,cut(v,88)))
    money=[
       (tr("НМЦ / начальный лимит","Initial ceiling / NMC",lang),rub(r["nmck"],lang)),
       (tr("Предложение по протоколу","Commission bid",lang),rub(r["bid"],lang)),
       (tr("Договорная цена из записи","Reported contract amount",lang),rub(r["contract_price"],lang)),
       (tr("Цена только PQ-оборудования*","Equipment-only amount*",lang),rub(r["equipment_only_price"],lang)),
       (tr("Фактически оплачено","Paid amount verified",lang),rub(r["paid_amount"],lang)),
       (tr("Реестровый номер договора","Contract registry number",lang),cut(r["contract_no"],64)),
       (tr("Дата договора","Contract date",lang),r["contract_date"]),
       (tr("Характер суммы","Price source / basis",lang),cut(r["reported_price_kind"],75)),
       (tr("Класс сделки","Procurement scope",lang),label(r["scope_group"],BUCKET,lang)),
    ]
    left='<div class="panel"><h3>'+tr("Номенклатура и параметры","Equipment specification",lang)+'</h3>'
    left+=small_rows(base,lang,10)+'</div>'
    right='<div class="panel"><h3>'+tr("Пять раздельных финансовых величин","Five independent price types",lang)+'</h3>'
    right+=small_rows(money,lang,9)+'</div>'
    subject=cut(r["description"],390) or missing(lang)
    detail=('<div class="note"><b>'+tr("Предмет исходной карточки: ","Original source subject: ",lang)
            +'</b>'+esc(subject)+'</div>')
    if len(r["description"] or "")>390:
        detail+='<div class="footnote">'+tr(
             "Оригинальное более длинное описание без потери сохранено в JSON-срезе, к которому прилагается отчёт.",
             "The full longer source wording is preserved in the accompanying JSON snapshot.",lang)+'</div>'
    body=case_head(r,i,total,lang,"case2")
    body+=title(tr("Техника, спецификация и цены","Engineering, bill of materials and prices",lang),
       tr("Номинал устройства, а не напряжение ПС. Каждая сумма имеет собственное правовое основание.",
          "Equipment-rated kV, not substation voltage. Each price type has a distinct legal meaning.",lang))
    body+='<div class="trio-grid">'+left+right+'</div>'+detail
    body+='<div class="footnote">'+tr(
      "* Значение цены оборудования не интерпретируется как оплаченная выручка; для EPC отделяется от работ только по оригинальной спецификации.",
      "* Equipment-only amount is not paid revenue; EPC hardware must be split from works using an original itemized bill.",lang)+'</div>'
    return frame(body,lang,page,tr("ТЕХНИКА И ЦЕНЫ","TECHNICAL & FINANCIAL",lang),
                 cut(r["model"] or label(r["family"],FAMILY,lang),78),
                 kind="report-case")

def case_page3(r,i,total,lang,page):
    roles=[
       (tr("Заказчик / ИНН","Buyer / tax ID",lang),
        (r["buyer"] or missing(lang))+(f' · {r["buyer_inn"]}' if r["buyer_inn"] else "")),
       (tr("Организатор","Organizer",lang),r["organizer"]),
       (tr("Протокольный участник","Named commission bidder",lang),
        (r["bidder"] or missing(lang))+(f' · {r["bidder_inn"]}' if r["bidder_inn"] else "")),
       (tr("Подписавший поставщик","Signed-contract supplier",lang),r["signed_supplier"]),
       (tr("EPC / проектировщик","EPC / designer",lang),
        " / ".join(z for z in (r["epc"],r["designer"]) if z) or None),
       (tr("Изготовитель OEM","Equipment OEM",lang),r["oem"]),
    ]
    body=case_head(r,i,total,lang,"case3")
    body+=title(tr("Участники, исходы и документы","Participants, outcome and source evidence",lang),
          tr("Роли не смешиваются: протокольный победитель не становится автоматически подписантом и OEM.",
             "Roles are distinct: a commission winner is not automatically the signed supplier or OEM.",lang))
    body+=tab([tr("Роль / статус","Role",lang),tr("Подтверждённое в записи значение","Value found in source row",lang)],
              [[k,cut(v,126) if v else missing(lang)] for k,v in roles])
    links=[]
    for k,source in enumerate(r["sources"][:4],1):
        tier=source["tier"] or tr("Уровень не указан","Source tier unspecified",lang)
        name=cut(source["excerpt"],67) or cut(source["url"].split("/")[2],35)
        links.append(f'<div class="source"><b>[{k}] {esc(cut(tier,51))}</b>'
            f'<a href="{esc(source["url"])}">{tr("Открыть первоисточник / карточку","Open source or listing",lang)} · {esc(name)}</a>'
            f'<span class="sha">{esc(source["sha256"][:24]+"…" if source["sha256"] else tr("SHA ещё не получен","SHA unavailable",lang))}</span></div>')
    body+='<div class="sourcegrid">'+''.join(links or [
       '<div class="source">'+tr("Ссылка на исходный документ отсутствует.","No source URL attached.",lang)+'</div>'
    ])+'</div>'
    gaps=case_missing(r)
    gaptext=", ".join(gaps[:9])
    if len(gaps)>9:gaptext+=f" … +{len(gaps)-9}"
    content=(tr("Уровень источника: ","Evidence tier: ",lang)+r["evidence_grade"]+
             "; "+tr("всего URL: ","source URLs: ",lang)+str(len(r["sources"]))+
             ". "+tr("Не установлены поля: ","Fields not established: ",lang)+gaptext+".")
    body+='<div class="note warning">'+esc(cut(content,510))+'</div>'
    extra=list((r["extra_verified"] or {}).items())[:2]
    if extra:
        detail="; ".join(str(k)+"="+str(v) for k,v in extra)
        body+='<div class="footnote">'+tr("Дополнительные архивные сигналы: ","Additional archive signals: ",lang)+esc(cut(detail,250))+'</div>'
    return frame(body,lang,page,tr("ПРОТОКОЛ И ИСТОЧНИКИ","PARTIES & SOURCES",lang),
                 tr("A = сохранённый первичный цифровой след; B = первичная ссылка; C = вторичный индекс.",
                    "A = original hash/evidence; B = first-party URL; C = third-party index.",lang),
                 kind="report-case source-page")
def render(data,lang):
    rows=data["items"];n=len(rows)
    assert n==len({r["id"] for r in rows})>=123
    slides=[cover(data,lang)]
    for rail,htmlpart in summary_pages(data,lang):
        slides.append(frame(htmlpart,lang,len(slides)+1,rail,kind="summary"))
    slides.extend(index_pages(rows,lang,len(slides)+1))
    for i,record in enumerate(rows,1):
        slides.append(case_page1(record,i,n,lang,len(slides)+1))
        slides.append(case_page2(record,i,n,lang,len(slides)+1))
        slides.append(case_page3(record,i,n,lang,len(slides)+1))
    protocol_cases=[r for r in rows if r["protocol_bidders"]]
    for record in protocol_cases:
        bid_rows=[]
        reasons=[]
        for participant in record["protocol_bidders"]:
            b=participant["fields"]
            entity=b.get("company") or b.get("legal_entity") or b.get("name") or missing(lang)
            tax=b.get("inn") or "—"
            offers=[k+": "+str(v) for k,v in b.items() if ("offer" in k or "price" in k or "bid" in k) and v]
            decision=(b.get("original_decision") or b.get("commission_outcome")
                      or b.get("role") or b.get("status") or missing(lang))
            bid_rows.append([cut(entity,65),tax,cut("; ".join(offers),130) or missing(lang),cut(decision,85)])
            if b.get("reason"):reasons.append(cut(b["reason"],280))
        if record["id"]=="223fz:32616181358:lot1":
            reasons.append(tr("Заявка КВАР отклонена: нет справки ФНС КНД 1120101; ток 37,5 А вместо 50 А для КЭПФ-12-600.",
                              "KVAR rejected: missing FNS KND 1120101 certificate, 37.5 A instead of required 50 A for KEPF-12-600.",lang))
        bdy=('<div class="eyebrow">'+esc(record["id"])+'</div>'+
              title(tr("Протокол: участники, предложения и решение",
                       "Original protocol: bidders, offers and decision",lang),
                    tr("Конкурсные цены и отклонённые заявки не являются подтверждёнными договорами.",
                       "Bid prices and rejected offers are not completed contract sales.",lang)))
        bdy+=tab([tr("Участник","Bidder",lang),tr("ИНН","TIN",lang),
                  tr("Цена предложения / поле источника","Offer / source field",lang),
                  tr("Роль или решение","Role or decision",lang)],bid_rows)
        bdy+='<div class="note warning"><b>'+tr("Особенности протокола: ","Protocol specifics: ",lang)+'</b>'+esc(
            " / ".join(reasons[:2]) if reasons else tr("Роль участника и решение приведены строго по архивному первоисточнику.",
              "Original archive statements only; no inference of signed supplier.",lang))+'</div>'
        orig=[x for x in record["sources"] if any(k in (x["tier"] or "").lower()
              for k in ("original","primary","protocol"))]
        if orig:
            bdy+='<div class="sourcegrid">'+''.join(
              f'<div class="source"><b>{esc(cut(x["tier"],50))}</b>'
              f'<a href="{esc(x["url"])}">{tr("Перейти к источнику","Open source",lang)}</a>'
              f'<span class="sha">{esc((x["sha256"] or "SHA not present")[:32])}</span></div>'
              for x in orig[:4])+'</div>'
        slides.append(frame(bdy,lang,len(slides)+1,tr("ПРОТОКОЛ ТОРГОВ","BID PROTOCOL",lang),
                            tr("Протокольный победитель не равен подписанному поставщику.",
                               "Commission winner ≠ signed supplier.",lang),
                            kind="report-case source-page"))
    conclusion=title(tr("Итог и следующая доказательная итерация","Conclusion and next evidence iteration",lang),
              tr("Весь корпус представлен без исключений; статус «не установлено» — отдельная задача.",
                 "Every lot is included; an unknown fact is a specific outstanding research task.",lang))
    conclusion+=grid_metrics([
      (n,tr("Лотов раскрыто","Lots documented",lang),""),
      (len(summary_pages(data,lang)),tr("Сводных разделов","Analytical pages",lang),""),
      (3*n+len(protocol_cases),tr("Страниц досье и протоколов","Dossier and protocol pages",lang),""),
      (sum(bool(r["contract_price"]) for r in rows),tr("Цен договоров","Contract-price fields",lang),"")])
    conclusion+='<div class="call">'+tr(
       "<b>Принцип:</b> продолжать P0–P5 по каждому лоту: оригиналы, техника, комиссия, договор, OEM, акт, оплата. Новую редакцию отчёта выпускать только по новому фиксированному срезу данных.",
       "<b>Principle:</b> continue per-lot P0–P5: originals, equipment, award, signed contract, OEM, acceptance and payment. Publish a new deck only against a new frozen corpus snapshot.",lang)+'</div>'
    slides.append(frame(conclusion,lang,len(slides)+1,tr("ДАЛЬНЕЙШИЕ ШАГИ","NEXT STEPS",lang),kind="summary"))
    for idx,s in enumerate(slides,1):
        if s.count("<section ")!=1:raise ValueError(f"Bad section {idx}")
    markup=('<!doctype html><html lang="'+lang+'"><head><meta charset="utf-8">'
            '<style>'+CSS+'</style></head><body>'+''.join(slides)+'</body></html>')
    return markup,len(slides),len(summary_pages(data,lang)),len(index_pages(rows,lang,1))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--snapshot",type=Path,default=SNAP)
    parser.add_argument("--outdir",type=Path,default=OUTPUT)
    parser.add_argument("--html-only",action="store_true")
    parser.add_argument("--lang",choices=("ru","en"),default=None)
    args=parser.parse_args()
    data=json.loads(args.snapshot.read_text(encoding="utf8"))
    args.outdir.mkdir(parents=True,exist_ok=True)
    for lang in ((args.lang,) if args.lang else ("ru","en")):
        html_source,page_count,nsummary,nindex=render(data,lang)
        stem=f"ARVECTUM_FGI_PQ_EXHAUSTIVE_{lang.upper()}_20261104"
        html_file=args.outdir/(stem+".html")
        html_file.write_text(html_source,encoding="utf8")
        print(f"{lang}: {page_count} slides, {nsummary} analytical, {nindex} index, {data['unique_lots']}x3 dossiers, {len(html_source)} chars",flush=True)
        if args.html_only:continue
        pdf=(args.outdir/(stem+".pdf")).resolve()
        profile="/tmp/fgi-asof-20261104-"+lang+"-"+str(__import__("os").getpid())
        command=["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
             "--headless=new","--no-first-run","--disable-gpu",
             "--no-default-browser-check",f"--user-data-dir={profile}",
             "--print-to-pdf-no-header",f"--print-to-pdf={pdf}",
             html_file.resolve().as_uri()]
        p=subprocess.run(command,capture_output=True,text=True,timeout=160,check=False)
        if p.returncode or not pdf.is_file():
            raise RuntimeError(f"PDF error {lang}: {p.stderr[-450:]}")
        print(f"{lang}: PDF {pdf.stat().st_size} bytes",flush=True)
if __name__=="__main__":
    main()
