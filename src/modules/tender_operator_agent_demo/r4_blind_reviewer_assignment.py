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



def human_label_input_template(evaluator_bundle: dict[str, Any]) -> dict[str, Any]:
    """An intentionally INVALID gold schema, with no inferred answers.

    The human fills labels from verified original sources and signs a detached
    attestation using a separately owner-enrolled reviewer key. This tool does
    not generate keys, expertise, ratings, or legal findings.
    """
    assert_blind_evaluator_bundle(evaluator_bundle)
    return {
        "draft_status": "TEMPLATE_ONLY_NOT_HUMAN_GOLD",
        "sut_inference_allowed": False,
        "case_id": evaluator_bundle["case_id"],
        "source_bundle_sha256": evaluator_bundle["source_bundle_sha256"],
        "blind_discovery_label": {
            "schema_version": "1.1.0",
            "case_id": evaluator_bundle["case_id"],
            "source_bundle_sha256": evaluator_bundle["source_bundle_sha256"],
            "label": None,
            "reason": None,
            "confidence": None,
            "evidence": [],
            "evaluator": None,
            "evaluated_at": None,
        },
        "blind_document_truth": {
            "schema_version": "1.1.0",
            "case_id": evaluator_bundle["case_id"],
            "source_bundle_sha256": evaluator_bundle["source_bundle_sha256"],
            "facts": [],
            "confidence": None,
            "evaluator": None,
            "evaluated_at": None,
        },
        "external_human_reviewer_attestation": {
            "reviewer_id": None,
            "attested_at": None,
            "no_prior_sut_access": None,
            "ed25519_signature_b64": None,
        },
        "required_next_step": (
            "Independent human enters factual source-anchored labels; "
            "owner separately verifies reviewer identity/qualification and "
            "enrolls reviewer public key; reviewer signs label digests; "
            "offline preflight verifies source quote and signature; "
            "only then benchmark_pipeline can freeze truth."
        ),
    }
