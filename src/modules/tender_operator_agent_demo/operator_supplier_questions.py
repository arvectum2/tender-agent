"""Product-specific supplier RFQ question normalization, independent of upload I/O."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def normalize_supplier_questions(
    questions: list[dict[str, Any]],
    procurement_kind: str,
    *,
    translate_user_text: Callable[[str], str],
) -> list[str]:
    if procurement_kind != "services":
        return [translate_user_text(item["question"]) for item in questions[:8]]
    service_questions = {
        "spec_match": "Подтверждаете ли вы оказание услуг в полном объеме по техническому заданию?",
        "price": "Какова стоимость услуг с НДС и без НДС?",
        "delivery": "Какие организационные расходы входят в стоимость услуг?",
        "delivery_time": "Подтверждаете ли вы сроки оказания услуг по графику заказчика?",
        "availability": "Есть ли у вас преподаватели, аудитории и ресурсы на требуемые даты?",
        "certificates": "Есть ли документы и согласования, подтверждающие право на оказание этих услуг?",
        "warranty": "Какие итоговые документы и результаты обучения вы обеспечиваете по завершении программы?",
        "analog": "Есть ли отклонения от программы, формата или состава услуг, указанных в ТЗ?",
        "payment": "Какие условия оплаты вы готовы подтвердить со своей стороны?",
        "validity": "Какой срок действия вашего коммерческого предложения?",
        "installation": "Что входит в организацию очной части обучения на вашей площадке?",
        "logistics": "Входят ли в стоимость раздаточные материалы, дистанционная платформа и организационное сопровождение?",
    }
    normalized: list[str] = []
    seen: set[str] = set()
    for item in questions:
        category = str(item.get("category") or "").strip()
        question = service_questions.get(category) or translate_user_text(
            item["question"]
        )
        if question in seen:
            continue
        seen.add(question)
        normalized.append(question)
        if len(normalized) >= 8:
            break
    return normalized
