from scripts.research.review_sibur_project_documents import evidence


def test_exact_spans_and_scope_signals():
    text="Проект: SKP23062-2000-EM.DS-0001; КТП 10 кВ. Заказчик: предприятие."
    out=evidence(text)
    assert {"technical_positions","electrical_scope","project_role","voltage_power"}<=out.keys()
    assert all(text[h["start"]:h["end"]]==h["excerpt"] for hits in out.values() for h in hits)


def test_unrelated_generic_text_not_equipment():
    assert "electrical_scope" not in evidence("Условия оплаты и порядок приемки работ")


def test_budget_control_kru_is_not_switchgear():
    assert "electrical_scope" not in evidence("Требования органов бюджетного контроля (Федеральное Казначейство, Счетная Палата, КРУ)")
    assert "electrical_scope" in evidence("Поставка КРУ 10 кВ")
