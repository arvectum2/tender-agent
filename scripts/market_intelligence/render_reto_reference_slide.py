"""Exemplar of one procurement: one executive slide + full two-page evidence annex.

The same normalized JSON feeds Russian and English; never invent field values.
"""
from __future__ import annotations

import argparse
import html
import json
import subprocess
from pathlib import Path

from scripts.market_intelligence.render_fgi_full_deck import official_logo

ROOT=Path("docs/market_intelligence")
SNAP=Path("data/market_intelligence/power_quality/exemplars/reto_32616181358_20261031.v1.json")
def e(x):return html.escape(str(x if x is not None else "—"),quote=True)
def m(v,en=False):
    return ("RUB "+f"{v:,.0f}") if en else f"{v:,}".replace(","," ")+" ₽"
def tr(ru,en,lang):return ru if lang=="ru" else en
def link(item,label):
    return f'<a href="{e(item["url"])}">{e(label)}</a>'
CSS="""
@page{size:13.333333in 7.5in;margin:0}
*{box-sizing:border-box}
body{margin:0;font-family:"PT Sans",Arial,sans-serif;background:white;color:#283246;-webkit-print-color-adjust:exact!important;print-color-adjust:exact!important}
.slide{position:relative;width:1280px;height:720px;overflow:hidden;background:#f7f9fa;break-after:page;page-break-after:always}
.slide:last-child{break-after:auto;page-break-after:auto}
.logo{position:absolute;top:25px;left:36px;width:202px;height:38px}
.logo svg{width:202px;height:38px}
.logosub{position:absolute;top:70px;left:39px;color:#64788b;font-size:12px}
.topline{position:absolute;right:43px;top:36px;color:#5b7283;font-size:12px;font-weight:800;letter-spacing:1.7px}
.rail{position:absolute;top:130px;left:39px;width:194px;font-size:19px;line-height:1.15;text-transform:uppercase;font-weight:800;color:#001432}
.rail-note{position:absolute;left:39px;top:240px;width:190px;color:#4d6b77;font-size:13px;line-height:1.35}
.rail-badge{display:inline-block;background:#def5ee;color:#00816e;padding:8px 11px;border-radius:7px;font-size:12px;font-weight:800;margin-bottom:12px}
.main{position:absolute;top:113px;left:265px;right:42px;bottom:57px;overflow:hidden}
footer{position:absolute;left:38px;right:40px;bottom:17px;border-top:1px solid #cedbe2;padding-top:9px;display:flex;justify-content:space-between;color:#637b89;font-size:11px}
footer b{color:#001432}footer strong{color:#00a58e}
.title{font-weight:800;color:#001432;letter-spacing:-.5px;font-size:34px;line-height:1.09}
.subtitle{font-size:15px;color:#526c79;line-height:1.26;margin-top:8px}
.eyebrow{font-weight:800;color:#008e7c;letter-spacing:1.25px;font-size:11px;text-transform:uppercase}
.metricgrid{display:grid;grid-template-columns:1.04fr 1fr .8fr 1.23fr;gap:11px;margin-top:22px}
.metric{background:white;border:1px solid #dbe5e9;border-radius:10px;padding:14px 16px;min-height:89px}
.metric .mname{font-size:11px;letter-spacing:.4px;font-weight:800;color:#5c7783;text-transform:uppercase}
.metric .big{font-size:26px;line-height:1.13;color:#001432;font-weight:800;margin-top:8px}.metric .big:not(.sm){font-family:"JetBrains Mono",monospace;font-size:23px;letter-spacing:-.4px}
.metric .big.sm{font-size:19px}
.metric small{font-size:10px;color:#6a8792;display:block;margin-top:3px}
.panels{display:grid;grid-template-columns:1.16fr 1fr;gap:12px;margin-top:14px}
.panel{background:white;border:1px solid #dbe5e9;border-radius:10px;padding:15px 18px}
.panel h3{margin:0 0 10px;color:#00695d;font-size:16px}
.price-row{display:grid;grid-template-columns:1.32fr .55fr .75fr;gap:8px;padding:7px 0;border-bottom:1px solid #e1e9ed;font-size:14px}
.price-row:last-child{border:0}
.price-row .m{font-family:"JetBrains Mono",Menlo,monospace;font-size:12.5px;text-align:right}
.timeline{display:grid;grid-template-columns:1fr 1fr;gap:9px}
.timeline .t{padding:9px 11px;background:#f2f6f8;border-radius:8px}
.timeline b{display:block;font-size:14px;color:#001432}
.timeline span{font-size:12px;color:#536d7b}
.insight{margin-top:14px;padding:14px 18px;border-radius:10px;background:#001432;color:#fff;font-size:15px;line-height:1.3}
.insight b{color:#78FAE6}
.footnote{margin-top:8px;font-size:10.5px;color:#647c88}
table{border-collapse:collapse;width:100%;font-size:13px}
th{background:#001432;color:white;padding:9px 10px;text-align:left;font-size:12px}
td{background:white;border-bottom:1px solid #e0e8ec;padding:9px 10px;vertical-align:top}
tr:nth-child(even) td{background:#f8fbfc}
.twocol{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:16px}
.kv{display:flex;justify-content:space-between;gap:15px;align-items:start;padding:7px 0;border-bottom:1px solid #e4e9ec;font-size:13px;line-height:1.2}
.kv span:first-child{color:#5b7480}.kv b{text-align:right;max-width:67%}
.note{margin-top:12px;background:#e7f7f2;border:1px solid #d7ece4;border-radius:9px;padding:12px 15px;font-size:13px;line-height:1.28}
.warning{background:#fff3e5;border-color:#f0dec8}
.sourcegrid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:14px}
.source{border-radius:9px;background:white;border:1px solid #dce6ec;padding:10px 13px;font-size:12px;line-height:1.3;min-height:59px}
.source b{color:#006f67}.source a{color:#006f67;text-decoration:underline;display:block;margin-top:4px}
.badges{display:flex;gap:8px;flex-wrap:wrap;margin-top:11px}
.badge{font-size:11px;font-weight:800;border-radius:30px;background:#def2ec;color:#007d6d;padding:6px 12px}
.badge.warn{background:#fff1db;color:#8c5e1e}
.small{font-size:12px}
.mono{font-family:"JetBrains Mono",Menlo,monospace}
"""
def frame(body,lang,page,rail,railnote=""):
    r=f'''<section class="slide"><div class="logo">{official_logo()}</div>
    <div class="logosub">arvectum.com · Market Intelligence</div>
    <div class="topline">FGI · REFERENCE CASE / 32616181358</div>
    <div class="rail">{e(rail)}</div><div class="rail-note"><div class="rail-badge">223-ФЗ · 12 кВ</div>{e(railnote)}</div>
    <main class="main">{body}</main>
    <footer><span><b>ARVECTUM</b> / POWER QUALITY 6–35 кВ</span>
    <span>31.10.2026 · {tr("эталонное досье","reference dossier",lang)} &nbsp; <strong>{page:02d}</strong></span></footer></section>'''
    return r
def lab(a,b,lang):return tr(a,b,lang)
def page1(d,lang):
    en=lang=="en";hardware=d["hardware"];items=hardware["items"]
    title=lab("КЭПФ 12 кВ · 10 конденсаторов для БСК",
              "12 kV KEPF · 10 capacitor-bank units",lang)
    subtitle=lab("АО «Завод РЭТО» · ИНН 7724646338 · Москва · запрос котировок",
                 "JSC RETO Plant · TIN 7724646338 · Moscow · RFQ",lang)
    mets=[
      (lab("НМЦ (с НДС 22%)","NMC (incl. 22% VAT)",lang),m(d["nmck_rub"],en),""),
      (lab("Договор · архив ЕИС","Contract · archival EIS",lang),m(d["contract_total_archived_rub"],en),
       lab("Подписант не установлен","Signatory unverified",lang)),
      (lab("Количество / мощность","Units / total power",lang),"10 / 5.25",lab("шт. / Мвар","units / Mvar",lang)),
      (lab("Победитель комиссии","Commission winner",lang),
       lab("ЭКСПЕРТ ГРУПП","EXPERT GROUP",lang),"ИНН 7720494275"),
    ]
    cards=''.join(f'<div class="metric"><div class="mname">{e(k)}</div><div class="big{" sm" if i==3 else ""}">{e(v)}</div><small>{e(n)}</small></div>' for i,(k,v,n) in enumerate(mets))
    spec='<div class="panel"><h3>'+lab("Предмет и состав поставки","Technical scope",lang)+'</h3>'
    for it in items:
        spec+=f'<div class="price-row"><b>{e(it["model"])}</b><span>{it["qty"]} {lab("шт.","pcs",lang)}</span><span>{it["power_each_kvar"]} kvar</span></div>'
    spec+=f'<p class="small" style="margin:10px 0 0;color:#647884">{lab("Компоненты БСК; не завершённый STATCOM/SVG. 12 кВ, 50 Гц, требование аттестации «Россетей».","Capacitor-bank components, NOT a ready-made STATCOM/SVG. 12 kV, 50 Hz, Rosseti approval required.",lang)}</p></div>'
    dates=[
      ("06.07.2026",lab("Размещение","Published",lang)),
      ("20.07.2026",lab("Приём заявок окончен","Bid deadline",lang)),
      ("03.08.2026",lab("Протокол №186-2","Commission protocol",lang)),
      ("19.08.2026",lab("Договор в архиве ЕИС","Archival EIS contract",lang)),
    ]
    proc='<div class="panel"><h3>'+lab("Путь процедуры","Procurement timeline",lang)+'</h3><div class="timeline">'
    proc+=''.join(f'<div class="t"><b>{e(dt)}</b><span>{e(v)}</span></div>' for dt,v in dates)
    proc+=f'</div><div class="badges"><span class="badge">{lab("3 заявки / 2 допущены","3 bids / 2 admitted",lang)}</span><span class="badge warn">{lab("1 отклонена","1 rejected",lang)}</span></div></div>'
    ins=lab(
       "<b>Вывод:</b> есть первичный протокол с победителем и историческая запись о договоре на 3,05 млн ₽. "
       "Но подписант, изготовитель, факт поставки и оплата не установлены. Цена завода «КВАР» 1,96 млн ₽ отклонена и не отражает реализованную продажу.",
       "<b>Takeaway:</b> an original protocol names the commission winner and an archival record reports a RUB 3.05m contract. "
       "Actual signatory, OEM, delivery and payment are unverified. KVAR's RUB 1.96m rejected bid is not a completed sale.",lang)
    body=f'<div class="eyebrow">{lab("ЭТАЛОН / ПОСТАВКА КОМПОНЕНТОВ","REFERENCE / COMPONENT SUPPLY",lang)}</div><div class="title">{e(title)}</div><div class="subtitle">{e(subtitle)}</div>'
    body+=f'<div class="metricgrid">{cards}</div><div class="panels">{spec}{proc}</div><div class="insight">{ins}</div>'
    body+=f'<div class="footnote">{lab("Источники: оригинальные ТЗ [TZ], протокол [PROTOCOL], карточка РАД [ETP]; сведения о договоре [EIS] — исторический снимок, сейчас HTTP 404.","Sources: original spec [TZ], commission minutes [PROTOCOL], RAD [ETP]; EIS contract data are archival and currently HTTP 404.",lang)}</div>'
    return frame(body,lang,1,lab("ЭТАЛОННАЯ ЗАКУПКА","REFERENCE CASE",lang),
                 lab("Комплектующие БСК, прямой физический спрос на 12 кВ","12 kV capacitor-bank component demand",lang))
def page2(d,lang):
    en=lang=="en"; hw=d["hardware"]
    title=lab("Техническая спецификация и экономика","Technical bill of materials and economics",lang)
    sub=lab("Первичное ТЗ на 7 страницах · все параметры относятся именно к конденсаторам, а не классу напряжения подстанции",
            "7-page original specification · parameters refer to the capacitor devices, not to substation voltage",lang)
    header=[lab("Изделие","Model",lang),lab("Кол-во","Qty",lang),lab("Uн / Iн","Rated U / I",lang),
            lab("Qн","Rated kvar",lang),lab("C, мкФ","Capacitance",lang),
            lab("НМЦ/шт.","NMC/unit",lang),lab("Архив договора/шт.","Archival contract/unit",lang)]
    r=[]
    for it in hw["items"]:
        r.append([it["model"],str(it["qty"]),f'12 kV / {it["current_a"]:g} A',
                  str(it["power_each_kvar"]),str(it["capacitance_uf"]),
                  m(it["nmc_unit_inc_vat_rub"],en),m(it["archived_contract_unit_rub"],en)])
    tbl='<table><thead><tr>'+''.join(f'<th>{e(z)}</th>' for z in header)+'</tr></thead><tbody>'
    tbl+=''.join('<tr>'+''.join(f'<td>{e(cell)}</td>' for cell in row)+'</tr>' for row in r)
    tbl+='</tbody></table>'
    technical=[
      (lab("Номинальная частота","Frequency",lang),"50 Hz"),
      (lab("Гарантия","Warranty",lang),lab("не менее 12 месяцев","at least 12 months",lang)),
      (lab("Условия доставки","Delivery deadline",lang),lab("не позднее 80 календарных дней после договора","within 80 calendar days after signing",lang)),
      (lab("Адрес поставки","Delivery address",lang),lab("Москва, Старокаширское шоссе, 4А","Moscow, Starokashirskoye Shosse 4A",lang)),
      (lab("Технические требования","Technical conditions",lang),lab("МЭК 60871-4, предохранители, разрядные резисторы","IEC 60871-4, fuses, discharge resistors",lang)),
      (lab("Допуск «Россетей»","Rosseti approval",lang),lab("Требуется положительная аттестация","Positive product accreditation required",lang)),
    ]
    finance=[
      (lab("НМЦ всего · с НДС 22%","NMC total · incl. 22% VAT",lang),m(d["nmck_rub"],en)),
      (lab("Цена победителя · с НДС 22%","Winning bid · incl. 22% VAT",lang),m(d["winning_bid_rub"],en)),
      (lab("Историческая договорная сумма","Archival registered amount",lang),m(d["contract_total_archived_rub"],en)),
      (lab("Разница к НМЦ","Difference vs NMC",lang),m(d["discount_rub"],en)),
      (lab("Снижение к НМЦ","NMC discount",lang),f'{d["discount_percent"]:.2f}%'),
      (lab("Фактически оплачено","Cash paid verified",lang),lab("НЕ ПОДТВЕРЖДЕНО","NOT VERIFIED",lang)),
    ]
    kv=lambda rows:''.join(f'<div class="kv"><span>{e(k)}</span><b>{e(v)}</b></div>' for k,v in rows)
    body=f'<div class="eyebrow">{lab("ЭТАЛОН / ПЕРВИЧНОЕ ТЗ","REFERENCE / ORIGINAL SPECIFICATION",lang)}</div><div class="title">{e(title)}</div><div class="subtitle">{e(sub)}</div>'
    body+=tbl
    body+=f'<div class="twocol"><div class="panel"><h3>{lab("Оборудование и условия поставки","Engineering and logistics",lang)}</h3>{kv(technical)}</div><div class="panel"><h3>{lab("Раздельные показатели цены","Distinct financial indicators",lang)}</h3>{kv(finance)}</div></div>'
    note=lab("КЭПФ-12-450 поставляется взамен CHDB-992 ABB. Две модели: 5×450 + 5×600 = 5 250 квар. Цены по позициям договора взяты из исторического архива ЕИС (сегодня URL недоступен); НМЦ/шт. — из оригинального ТЗ.",
                             "KEPF-12-450 replaces ABB CHDB-992. Five 450 + five 600 kvar units yield 5,250 kvar nameplate total. Contract item prices rely on archival EIS data (URL currently unavailable); NMC/unit values are from the original specification.",lang)
    body+=f'<div class="note">{e(note)}</div>'
    return frame(body,lang,2,lab("ТЕХНИКА И ЦЕНЫ","SPECS & PRICING",lang),
                 lab("ТЗ №186 · оригинал РАД · 7 страниц","Technical specification No. 186 · original RAD source",lang))

def page3(d,lang):
    en=lang=="en"
    # Source-grade and actual protocol decisions; never equate bidder with supplier.
    title=lab("Торги, результат и доказательность","Bidding, outcome and evidence",lang)
    sub=lab("Итоговый протокол №186-2 от 03.08.2026: 3 заявки, 2 допущены, 1 отклонена",
            "Original final protocol No. 186-2 dated 3 Aug 2026: 3 bids, 2 admitted, 1 rejected",lang)
    heads=[lab("Участник","Bidder",lang),lab("ИНН","Tax ID",lang),
           lab("Предложение","Offer",lang),lab("Решение комиссии","Decision",lang)]
    entries=[
      (lab("ООО «ЭКСПЕРТ ГРУПП»","LLC EXPERT GROUP",lang),"7720494275",3050000,lab("Победитель · 1-е место","Winner · rank 1",lang)),
      (lab("ООО «ТО-СТРОЙМОНТАЖ»","LLC TO-STROYMONTAZH",lang),"7721814062",3078500,lab("Допущен · 2-е место","Admitted · rank 2",lang)),
      (lab("Завод «КВАР»","KVAR capacitor plant",lang),"5043061102",1960906,lab("Отклонён · не договор","Rejected · not a contract",lang)),
    ]
    tbl='<table style="margin-top:19px"><thead><tr>'+''.join(f'<th>{e(v)}</th>' for v in heads)+'</tr></thead><tbody>'
    tbl+=''.join('<tr>'+''.join(f'<td>{e(v)}</td>' for v in (name,inn,m(price,en),outcome))+'</tr>' for name,inn,price,outcome in entries)
    tbl+='</tbody></table>'
    unknowns=lab(
       "Поставщик — подписант договора: не установлен. OEM: не установлен. Страна регистрации производителя в историческом ЕИС — Казахстан, но страна изготовления не доказана. Физическая поставка, приёмка и оплата: не подтверждены.",
       "Signed-contract supplier: unknown. OEM: unknown. Archival EIS lists Kazakhstan as manufacturer-registration country, but actual origin is unverified. Physical delivery, acceptance and payment: unverified.",lang)
    disq=lab(
       "«КВАР» отклонён по двум основаниям: отсутствовала справка ФНС КНД 1120101; у КЭПФ-12-600 заявлен ток 37,5 А при требуемых 50 А. Низкое предложение не следует учитывать как состоявшуюся продажу.",
       "KVAR was rejected for two reasons: missing tax-arrears certificate KND 1120101, and 37.5 A instead of the required 50 A for KEPF-12-600. Its low bid was not an awarded sale.",lang)
    sources=d["source_provenance"]
    cards='<div class="sourcegrid">'
    for code in ("TZ","PROTOCOL","ETP","EIS"):
        item=sources[code]
        cards+=f'<div class="source"><b>[{e(code)}] {e(item["label"])}</b>{link(item,lab("Открыть исходный источник","Open source",lang))}<div style="font-size:10px;color:#6b8491">SHA-256: {e(item["sha"][:20])}…</div></div>'
    cards+='</div>'
    body=f'<div class="eyebrow">{lab("ЭТАЛОН / КОНКУРЕНЦИЯ И ПОДТВЕРЖДЕНИЯ","REFERENCE / COMPETITION & PROVENANCE",lang)}</div><div class="title">{e(title)}</div><div class="subtitle">{e(sub)}</div>{tbl}'
    body+=f'<div class="note warning"><b>{lab("Причина отклонения дешёвой заявки:","Why the cheapest bid failed:",lang)}</b> {e(disq)}</div>'
    body+=cards
    body+=f'<div class="note"><b>{lab("Не установлено:","Not established:",lang)}</b> {e(unknowns)}</div>'
    return frame(body,lang,3,lab("ПРОТОКОЛ И ИСТОЧНИКИ","AWARD & SOURCES",lang),
                 lab("Договор в архиве ЕИС №57724646338260000460000; страница 31.10.2026 возвращает 404",
                     "EIS archived contract 57724646338260000460000; page currently returns HTTP 404",lang))
def render(d,lang):
    pages=[page1(d,lang),page2(d,lang),page3(d,lang)]
    assert len(pages)==3 and all('class="official-logo"' in p for p in pages)
    return '<!doctype html><html lang="'+lang+'"><head><meta charset="utf-8"><style>'+CSS+'</style></head><body>'+''.join(pages)+'</body></html>'
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,default=SNAP)
    p.add_argument("--output-dir",type=Path,default=ROOT)
    p.add_argument("--html-only",action="store_true")
    opt=p.parse_args()
    case=json.loads(opt.source.read_text(encoding="utf8"))
    assert case["case_id"]=="223fz:32616181358:lot1"
    opt.output_dir.mkdir(parents=True,exist_ok=True)
    for lang in ("ru","en"):
        source=opt.output_dir/f'ARVECTUM_RETO_REFERENCE_{lang.upper()}_20261031.html'
        source.write_text(render(case,lang),encoding="utf8")
        if opt.html_only: continue
        pdf=opt.output_dir/f'ARVECTUM_RETO_REFERENCE_{lang.upper()}_20261031.pdf'
        args=["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              "--headless=new","--disable-gpu","--no-first-run","--no-default-browser-check",
              f'--user-data-dir=/tmp/arvectum-reto-reference-{lang}-{__import__("os").getpid()}',
              "--print-to-pdf-no-header",f'--print-to-pdf={pdf.resolve()}',source.resolve().as_uri()]
        proc=subprocess.run(args,capture_output=True,text=True,timeout=85,check=False)
        if proc.returncode or not pdf.is_file():
            raise RuntimeError("Chrome PDF conversion failed "+proc.stderr[-450:])
        import pymupdf
        doc=pymupdf.open(pdf)
        if len(doc)!=3:raise ValueError(f"Expected 3 pages, got {len(doc)}")
        single=opt.output_dir/f'ARVECTUM_RETO_REFERENCE_SLIDE_{lang.upper()}_20261031.pdf'
        one=pymupdf.open();one.insert_pdf(doc,from_page=0,to_page=0);one.save(single);one.close()
        preview=opt.output_dir/f'ARVECTUM_RETO_REFERENCE_SLIDE_{lang.upper()}_20261031.png'
        pix=doc[0].get_pixmap(matrix=pymupdf.Matrix(1.5,1.5),alpha=False);pix.save(preview)
        print(lang,'3page',pdf.stat().st_size,'1page',single.stat().st_size,'preview',preview.stat().st_size)
if __name__=="__main__": main()
