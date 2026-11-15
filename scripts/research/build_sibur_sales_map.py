"""Source-observation map, never confirmed buyer, award or contract."""
import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

SITES = {
    "Нижнекамскнефтехим": r"\bНКНХ\b|Нижнекамскнефтехим",
    "ЗапСибНефтехим": r"\bЗСНХ\b|ЗапСибНефтехим",
    "Казаньоргсинтез": r"\bКОС\b|Казаньоргсинтез",
    "Амурский ГХК": r"\bАГХК\b|Амурск\w+\s+ГХК",
    "СИБУР-Кстово": r"Сибур[- ]Кстово|\bКстово\b",
    "СИБУР-Нефтехим": r"Сибур[- ]Нефтехим|\bСНХ\b",
    "Томскнефтехим": r"Томскнефтехим|\bТНХ\b",
    "ПОЛИЭФ": r"\bПОЛИЭФ\b",
    "ПОЛИОМ": r"\bПОЛИОМ\b",
    "РусВинил": r"РусВинил",
    "Воронежсинтезкаучук": r"Воронежсинтезкаучук|\bВСК\b",
    "БИАКСПЛЕН": r"БИАКСПЛЕН",
    "СибурТюменьГаз": r"СибурТюменьГаз|\bСТГ\b",
    "СИБУР-Химпром": r"Сибур[- ]Химпром",
    "Южно-Приобский ГПЗ": r"Южно[- ]Приобск\w+\s+ГПЗ|\bЮПГПЗ\b",
    "СИБУР-Портэнерго": r"Сибур[- ]Портэнерго",
}
CORE = {
    "Выключатели и коммутация": r"\bвыключател\w*|разъединител\w*|контактор\w*|пускател\w*\s+магнитн",
    "КРУ, КТП, НКУ": r"\b(?:КРУ|КРУЭ|КСО|КТП|БКТП|НКУ|ГРЩ|РУВН|РУНН)\b|распределительн\w+\s+(?:устройств|щит)|комплектн\w+\s+трансформаторн\w+\s+подстанц",
    "Трансформаторы": r"\bтрансформатор\w*|\bтрансформат\b",
    "РЗА и автоматика электроснабжения": r"\b(?:РЗА|МПРЗА|АВР|АПВ|АСДУЭ|АСУЭ|АСУ\s*Э|АСКУЭ|АИИС\s*КУЭ)\b|релейн\w+\s+защит|терминал\w*\s+защит",
    "Электродвигатели": r"электродвигател\w*|(?:асинхронн|синхронн)\w+\s+двигател",
    "Частотные преобразователи и приводы": r"частотн\w+\s+преобразовател|преобразовател\w*\s+частот|\b(?:ЧРП|УПП)\b|электропривод\w*|устройств\w*\s+плавн\w+\s+пуск|сервопривод",
    "АСУ ТП, ПЛК, SCADA и сети": r"\b(?:АСУ\s*ТП|РСУ|ПАЗ|ПЛК|PLC|SCADA|DCS|HMI|SIS|PROFIBUS|PROFINET|MODBUS|OPC\s*UA)\b|контроллер\w*|модул\w*\s+ввод\w*\s*[/и-]?\s*вывод|промышленн\w+\s+коммутатор|телемеханик\w*",
    "КИП и измерительные приборы": r"\b(?:КИПиА|КИП|КИПА)\b|датчик\w*|расходомер\w*|уровнемер\w*|манометр\w*|термопар\w*|термометр\w*|газоанализатор\w*|преобразовател\w*\s+(?:давлен|расход|температур|уровн|измерительн)|позиционер\w*",
    "Источники и качество питания": r"\b(?:ИБП|UPS|УКРМ|STATCOM|СТАТКОМ|СОПТ|ЩПТ)\b|источник\w*\s+бесперебойн\w+\s+питан|компенсаци\w*\s+реакт\w+\s+мощност|конденсаторн\w+\s+установ|фильтр\w*\s+(?:высш\w+\s+)?гармоник|тиристорн\w+\s+компенсатор|выпрямител",
    "Подстанции и электроснабжение": r"подстанци\w*|электроснабжен\w*|\b(?:ГПП|ЗРУ|ОРУ|ЛЭП|ВВЛ)\b|высоковольтн\w+\s+(?:оборудован|ячейк|лини)",
    "Электротехнические компоненты": r"силов\w+\s+(?:модул|тиристор|полупроводник)|тиристор\w*|предохранител\w*|клемм\w*|кабельн\w+\s+(?:муфт|ввод|наконечник)|шинопровод\w*|изолятор\w*|дугогасительн\w+\s+камер",
}
UPS_FAMILY = "ИБП и комплектующие"
UPS_EXPLICIT = r"\b(?:ИБП|UPS|СБП)\b|(?:источник|систем)\w*\s+бесперебойн\w+\s+(?:электро)?питан|бесперебойн\w+\s+(?:электро)?питан"
UPS_COMPONENTS = r"аккумулятор\w*|\bАКБ\b|байпас\w*|батарейн\w+\s+(?:шкаф|модул|блок)|зарядн\w+\s+устройств|выпрямител\w*|инвертор\w*|\bЗИП\b|запасн\w+\s+част"
STATIONARY_BATTERY = r"стационарн\w+\s+аккумулятор|аккумуляторн\w+\s+батаре\w*\s+(?:для\s+)?(?:ИБП|UPS|СОПТ)|батарейн\w+\s+шкаф"
UPS_SERVICE = r"ремонт\w*|обслуживан\w*|диагностик\w*|замен\w*|модернизац\w*|пусконалад\w*"

def ups_tags(text, category):
    explicit = bool(re.search(UPS_EXPLICIT,text,re.IGNORECASE))
    stationary = bool(re.search(STATIONARY_BATTERY,text,re.IGNORECASE))
    # СБП without an expanded power reference can be the faster payments system.
    explicit = explicit and bool(re.search(r"\b(?:ИБП|UPS)\b|бесперебойн\w+\s+(?:электро)?питан",text,re.IGNORECASE) or (
        category in {"Электрооборудование","Системы и средства автоматизации, метрологии и КИП"}
        and re.search(r"\bСБП\b",text,re.IGNORECASE)))
    battery_review = (
        category in {"Электрооборудование", "Техническое обслуживание и ремонт", "Системы и средства автоматизации, метрологии и КИП"}
        and bool(re.search(r"батарейн\w+\s+(?:шкаф|модул|блок)|(?:блок|комплект|модул)\w*\s+батарейн|\bАКБ\b|аккумуляторн\w+\s+батаре|батаре\w*\s+аккумуляторн|\bаккумулятор\w*\b",text,re.IGNORECASE))
        and not re.search(r"автомобил|погрузчик|поломоеч|фонар|гидроаккумулятор|пружинно[- ]гидравлическ|калибратор|радиостанци|перфоратор|шуруповерт|шуруповёрт|тестер|пылесос|ноутбук|аккумуляторн\w+\s+инструмент",text,re.IGNORECASE)
    )
    if not explicit and not stationary and not battery_review:
        return []
    tags = ["explicit_ups" if explicit else "stationary_battery_or_cabinet_review" if stationary else "battery_application_review"]
    if explicit and re.search(UPS_COMPONENTS,text,re.IGNORECASE):
        tags.append("components")
    if re.search(UPS_SERVICE,text,re.IGNORECASE):
        tags.append("service")
    return tags


ADJ = {
    "Кабельная инфраструктура": r"кабел\w*",
    "Регулирующая арматура": r"регулирующ\w+\s+клапан|клапан\w*\s+регулирующ|позиционер|регулятор\w*\s+давлен|запорно[- ]регулирующ",
    "Насосы и компрессоры": r"насос\w*|компрессор\w*",
}
SERVICE = r"проектирован\w*|проектн\w+\s+документац|рабоч\w+\s+документац|модернизац\w*|ретрофит|техническ\w+\s+перевооруж|пусконалад\w*|\b(?:ПНР|СМР|ШМР)\b|монтаж\w*|ремонт\w*|обслуживан\w*"
BUDGET = r"бюджетн\w+\s+оценк|\bБО\b|оценочн\w+\s+стоимост"
CENTRAL = {'ПАО "СИБУР Холдинг"', 'ООО "Сибур"'}


def hit(text, patterns):
    return [k for k, p in patterns.items() if re.search(p, text, re.IGNORECASE)]


def build(rows, today):
    org, cat, year, status = Counter(), Counter(), Counter(), Counter()
    core, adj, sites, site_core = Counter(), Counter(), Counter(), Counter()
    central_sites, central_core_sites, core_special = Counter(), Counter(), Counter()
    matrix, paths = defaultdict(Counter), defaultdict(Counter)
    candidates = []
    central_count = central_named = central_ambiguous = 0
    all_ids = set()
    for r in rows:
        ident = r["external_id"]
        if ident in all_ids:
            raise ValueError("duplicate source identity")
        all_ids.add(ident)
        obs = r["observations"]
        os = {o["organizer"] for o in obs}
        cs = {o["category"] for o in obs}
        ss = {o["status_raw"] for o in obs}
        if len(os) != 1 or len(cs) != 1:
            raise ValueError("ambiguous published organizer or category")
        organizer, category = next(iter(os)), next(iter(cs))
        org[organizer] += 1
        cat[category] += 1
        status.update(ss)
        year[r["publication_date"][:4]] += 1
        matrix[organizer][category] += 1
        txt = "\n".join(sorted({o["title"]+" "+o["subject"] for o in obs})).replace("_", " ")
        mentions = hit(txt, SITES)
        sites.update(mentions)
        if organizer in CENTRAL:
            central_count += 1
            central_named += bool(mentions)
            central_sites.update(mentions)
            central_ambiguous += len(mentions) > 1
        ct, at = hit(txt, CORE), hit(txt, ADJ)
        power_tags = ups_tags(txt, category)
        if power_tags:
            ct.append(UPS_FAMILY)
        if category in {"Электрооборудование", "Системы и средства автоматизации, метрологии и КИП"} and re.search(r"\bПЧ\b", txt, re.IGNORECASE) and "Частотные преобразователи и приводы" not in ct:
            ct.append("Частотные преобразователи и приводы")
        # Fire service records are unrelated to the electrical abbreviation ПЧ.
        if category == "Услуги ОТ ПБ и ОС" and re.search(r"пожарн\w+|\bПАСФ\b",txt,re.IGNORECASE):
            ct = []
            power_tags = []

        if not ct and not at:
            continue
        core.update(ct)
        adj.update(at)
        if ct:
            site_core.update(mentions)
            if organizer in CENTRAL:
                central_core_sites.update(mentions)
            core_special.update(hit(txt,{
                "Генераторные выключатели":r"генераторн\w+\s+выключател|выключател\w*\s+генераторн",
                "Вакуумные выключатели":r"вакуумн\w+\s+выключател|выключател\w*\s+вакуумн",
                "Элегазовые выключатели":r"элегазов\w+\s+выключател|выключател\w*\s+элегазов",
                "Расходомеры":r"расходомер\w*",
                "Датчики давления, манометры":r"манометр\w*|(?:датчик|преобразовател)\w*\s+давлен",
                "Датчики температуры":r"термопар\w*|термометр\w*|датчик\w*\s+температур",
                "Газоанализаторы":r"газоанализатор\w*",
                "Уровнемеры":r"уровнемер\w*|датчик\w*\s+уровн",
            }))
            paths[organizer].update(ct)
        deadlines = sorted({o["deadline_raw"] for o in obs if o.get("deadline_raw")})
        future = False
        for d in deadlines:
            try:
                future |= date.fromisoformat("-".join(reversed(d[:10].split(".")))) >= today
            except ValueError:
                pass
        candidates.append({"external_id":ident, "publication_date":r["publication_date"],
            "organizer":organizer, "category":category, "title":r["title"],
            "subject":sorted({o["subject"] for o in obs}), "site_mentions":mentions,
            "core_tags":ct, "adjacent_tags":at, "ups_tags":power_tags, "service_signal":bool(re.search(SERVICE,txt,re.IGNORECASE)),
            "budget_signal":bool(re.search(BUDGET,txt,re.IGNORECASE)), "status_raw":sorted(ss),
            "deadline_raw":deadlines, "future_date_open_snapshot":ss=={"Прием предложений"} and future,
            "source_receipts":[{k:o[k] for k in ("source_url","source_sha256","source_row")} for o in obs],
            "signed_contract":None,"verified_end_buyer":None,"supplier":None})
    c = [r for r in candidates if r["core_tags"]]
    active = [r for r in c if r["future_date_open_snapshot"] and not r["budget_signal"]]
    return {"schema":"sibur_sionika_sales_map_v3","record_count":len(rows),
            "organizers":dict(org),"categories":dict(cat),"publication_year":dict(year),"statuses":dict(status),
            "organizer_category_matrix":dict(matrix),"site_mentions":dict(sites),
            "centralized_records":central_count,"centralized_with_site_mentions":central_named,
            "centralized_multiple_site_mentions":central_ambiguous,"central_site_mentions":dict(central_sites),"central_core_site_mentions":dict(central_core_sites),"core_subsegments":dict(core_special),"core_counts":dict(core),
            "adjacent_counts":dict(adj),"core_site_mentions":dict(site_core),"core_organizer_matrix":dict(paths),
            "core_unique_records":len(c),"core_prefix_groups_for_review":len({r["external_id"].split("/")[0] for r in c}),
            "adjacent_only_records":len(candidates)-len(c),"core_service_records":sum(r["service_signal"] for r in c),
            "core_budget_signals":sum(r["budget_signal"] for r in c),
            "core_cancelled":sum("Процедура отменена" in r["status_raw"] for r in c),
            "core_open_snapshot_future_nonbudget":len(active),
            "core_active_snapshot":active,"candidates":candidates,
            "verification":"TITLE_SUBJECT_LEXICAL_CANDIDATES_NOT_VERIFIED_SCOPE_OR_CONTRACT"}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("snapshot", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--date", type=date.fromisoformat, required=True)
    a = p.parse_args()
    raw = a.snapshot.read_bytes()
    report = build(json.loads(raw), a.date)
    report["snapshot_sha256"] = hashlib.sha256(raw).hexdigest()
    with a.output.open("x") as f:
        json.dump(report,f,ensure_ascii=False,indent=2)
    print(json.dumps({k:v for k,v in report.items() if k not in {"candidates","core_active_snapshot","organizer_category_matrix","core_organizer_matrix"}},ensure_ascii=False))


if __name__=="__main__":
    main()
