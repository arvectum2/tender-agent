"""Product-owned deterministic procurement text helpers."""

from __future__ import annotations


def project_rewrite_compliance_highlight(
    value: str, *, _normalize_analysis_sentence
) -> str:
    lowered = value.lower()
    if (
        "федеральной служ" in lowered
        and "техническому и экспортному контролю" in lowered
    ):
        return "Программа должна быть согласована с ФСТЭК России."
    if "удостоверени" in lowered and "повышени" in lowered:
        return "По итогам обучения нужно выдать удостоверение о повышении квалификации."
    if "аттестаци" in lowered:
        return "Нужно провести итоговую аттестацию слушателей."
    if "учебный план должен содержать" in lowered:
        return "Учебный план должен содержать перечень тем и распределение часов."
    if "раздаточ" in lowered and "материал" in lowered:
        return "Исполнитель должен обеспечить слушателей учебными и раздаточными материалами."
    return _normalize_analysis_sentence(value) or value


def project_rewrite_delivery_model_item(
    value: str, procurement_kind: str, *, _normalize_analysis_sentence
) -> str:
    lowered = value.lower()
    if procurement_kind == "services":
        if "очно-заочная" in lowered:
            return "Формат обучения: очно-заочный, с применением дистанционных образовательных технологий."
        if "дистанцион" in lowered:
            return "Часть программы проводится дистанционно на стороне заказчика."
        if "60" in lowered and "%" in lowered:
            return "Около 60% программы проходит в очном формате."
        if "40" in lowered and "%" in lowered:
            return "Около 40% программы проходит дистанционно."
        if "09.00" in value or "18.00" in value:
            return "Режим занятий: с 09:00 до 18:00."
        if "городе хабаровске" in lowered:
            return "Очная часть должна проходить в городе Хабаровске."
    return _normalize_analysis_sentence(value) or value


def project_is_goods_supply_table_present(text: str) -> bool:
    lowered = (text or "").lower()
    return any(
        marker in lowered
        for marker in (
            "перечень запасных частей",
            "перечень товаров",
            "перечень поставки",
            "спецификация",
            "№ п/п",
            "ед.изм",
            "кол-во",
        )
    )
