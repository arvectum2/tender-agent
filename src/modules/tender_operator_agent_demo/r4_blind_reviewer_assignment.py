"""Generate standard source-only reviewer instructions, never legal gold or SUT."""
from __future__ import annotations

from typing import Any

from src.modules.benchmark_pipeline.workflow import assert_blind_evaluator_bundle

REVIEW_CATEGORIES = (
    "Права на результаты, лицензии ПО и передачу исходных файлов",
    "Квалификация, лицензирование участника и исполнителя",
    "Обеспечение заявки, исполнения и независимые гарантии",
    "Стоимость, аванс, условия и сроки оплаты",
    "Сроки выполнения работ и ответственность за нарушение",
    "Приёмка, критерии испытаний и сдача результата",
    "Гарантия, исправление недостатков, поддержка",
    "Персональные данные, информационная безопасность, доступы",
)


def build_source_only_assignment(evaluator_bundle: dict[str, Any]) -> str:
    """Validates schema and blocklists all model-result keys before review."""
    assert_blind_evaluator_bundle(evaluator_bundle)
    if not evaluator_bundle["documents"]:
        raise ValueError("No independently attested documents for evaluator")
    name = evaluator_bundle["case_id"]
    lines = [
        "# Независимая экспертиза — " + name,
        "",
        "**Режим:** слепая разметка на подлинных исходниках до показа ответа Tender Agent.",
        "**Эталон НЕ подготовлен.** Не использовать отчёты модели или предложения разработчиков.",
        "",
        "## Первичные документы",
        "",
        "SHA пакета: " + evaluator_bundle["source_bundle_sha256"],
    ]
    for original in evaluator_bundle["documents"]:
        lines.extend([
            "",
            "Источник: " + original["path"],
            "SHA-256: " + original["sha256"],
            "Официальный адрес: " + original["source_url"],
        ])
    lines.extend([
        "",
        "## Обязательная независимая проверка по категориям",
        "",
    ])
    for i, topic in enumerate(REVIEW_CATEGORIES, 1):
        lines.append(str(i) + ". " + topic)
    lines.extend([
        "",
        "## Для КАЖДОГО существенного факта заполнить отдельно",
        "",
        "Категория: [заполняет эксперт]",
        "Условие и область применения: [заполняет эксперт]",
        "Субъект (участник, исполнитель, соисполнитель, заказчик, банк и т.д.): [заполняет эксперт]",
        "Модальность (требуется/запрещено/не требуется/право/неизвестно): [заполняет эксперт]",
        "Срок, сумма, единица измерения и обстоятельства: [заполняет эксперт]",
        "Оригинал и SHA: [заполняет эксперт]",
        "Дословная цитата и точный локатор: [заполняет эксперт]",
        "Сопоставление с другими частями договора и ТЗ: [заполняет эксперт]",
        "Уверенность и нерешённые противоречия: [заполняет эксперт]",
        "",
        "## Протокол",
        "",
        ("Если пункт не обнаружен, не доказывать автоматически, что его нет: "
         "отдельно отмечать полноту прочитанных исходников и статус UNKNOWN."),
        ("Если источник сканирован, таблица неполная или документы конфликтуют, "
         "не создавать ASSERTED без точной привязки."),
        ("До независимого подписания truth нельзя запускать Tender Agent на "
         "этой выборке. После проверки использовать штатный benchmark_pipeline "
         "freeze_blind_labels; не создавать собственный обход схемы."),
        "",
        "Подписанный экспертный gold: **ОТСУТСТВУЕТ**.",
        "precision/recall: **NOT_MEASURED**. bid_ready=false.",
        "",
    ])
    return "\n".join(lines)
