from datetime import date

import pytest

from scripts.research.build_sibur_sales_map import build


def row(ident,title,category="Электрооборудование",status="Прием предложений",organizer='ПАО "СИБУР Холдинг"'):
    return {"external_id":ident,"title":title,"publication_date":"2026-11-14","observations":[
        {"title":title,"subject":title,"category":category,"status_raw":status,"organizer":organizer,
         "deadline_raw":"20.11.2026","source_url":"https://example.test/","source_sha256":"a"*64,"source_row":"1"}]}


def test_multitag_count_and_central_site_not_verified_buyer():
    r=build([row("1/1","НКНХ_КРУ и трансформатор"),row("1/2","НКНХ_вакуумный выключатель")],date(2026,11,15))
    assert r["core_unique_records"]==2 and r["core_prefix_groups_for_review"]==1
    assert r["centralized_with_site_mentions"]==2
    assert r["core_counts"]["КРУ, КТП, НКУ"]==1
    assert r["core_subsegments"]["Вакуумные выключатели"]==1
    assert all(x["verified_end_buyer"] is None and x["signed_contract"] is None for x in r["candidates"])


def test_budget_cancelled_and_fire_department_exclusion():
    r=build([row("1/1","ПАСФ ПЧ г. Салават","Услуги ОТ ПБ и ОС"),
             row("2/1","ПЧ для КОС"),row("3/1","УКРМ бюджетная оценка"),
             row("4/1","РЗА",status="Процедура отменена")],date(2026,11,15))
    assert r["core_unique_records"]==3
    assert r["core_open_snapshot_future_nonbudget"]==1
    assert r["core_budget_signals"]==1 and r["core_cancelled"]==1


def test_duplicate_rejected():
    a=row("1/1","КРУ")
    with pytest.raises(ValueError):
        build([a,a],date(2026,11,15))


def test_ups_priority_includes_it_and_specific_batteries_not_car_batteries():
    from scripts.research.build_sibur_sales_map import UPS_FAMILY
    r=build([row("10/1","ИБП для серверной","ИТ"),
             row("11/1","ЗИП и АКБ для UPS"),
             row("12/1","Техническое обслуживание системы бесперебойного электропитания"),
             row("13/1","Стационарная аккумуляторная батарея"),
             row("14/1","АКБ автомобильная"),
             row("15/1","Оплата через СБП","ИТ")],date(2026,11,15))
    got={i["external_id"]:i["ups_tags"] for i in r["candidates"] if UPS_FAMILY in i["core_tags"]}
    assert set(got)=={"10/1","11/1","12/1","13/1"}
    assert "components" in got["11/1"] and "service" in got["12/1"]
    assert got["13/1"]==["stationary_battery_or_cabinet_review"]


def test_battery_module_without_ups_is_review_not_confirmed_ups():
    from scripts.research.build_sibur_sales_map import ups_tags
    assert ups_tags("Модуль батарейный Eaton EXB", "Электрооборудование")==["battery_application_review"]
    assert ups_tags("АКБ для погрузчика", "Электрооборудование")==[]
    assert ups_tags("ТЗ на байпасы трубопроводов", "Строительные работы")==[]
