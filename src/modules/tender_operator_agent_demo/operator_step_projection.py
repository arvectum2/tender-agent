"""Pure legacy Operator step-view projection from report output payloads.

Agent runtime and persistence remain owned by Tender Agent; this module is
read-only presentation and does not call external services or infer evidence.
"""
from __future__ import annotations

from typing import Any

from src.modules.tender_operator_agent_demo.schemas import (
    DemoDetailSection,
    DemoStep,
    DemoStepStatus,
)


def build_operator_steps(metadata: dict[str, Any], outputs: dict[str, dict[str, Any]]) -> list[DemoStep]:
    requirements = outputs["requirements"]
    questions = outputs["supplier_questions"]
    rfq = outputs["rfq_draft"]
    quotes = outputs["quotes_comparison"]
    economics = outputs["economics"]
    risks = outputs["contract_risks"]
    final_recommendation = outputs["final_recommendation"]
    trace = outputs["trace"]["per_step"]

    quote_blocked = quotes["status"] == "blocked"
    quote_partial = quotes["status"] in {"partial", "needs_review"}
    economics_blocked = economics["status"] == "blocked"
    economics_partial = economics["status"] in {"partial", "needs_review"}
    core_limitations = outputs["trace"].get("limitations", [])
    partial_requirements = any("fallback" in item.lower() for item in core_limitations)
    file_count = len(metadata.get("files", []))
    docs_status = DemoStepStatus.DONE if file_count else DemoStepStatus.BLOCKED
    preliminary_analysis = requirements.get("preliminary_analysis", {})

    steps: list[DemoStep] = []
    if metadata.get("procurement_source"):
        procurement_title = metadata.get("tender_title", "Закупка")
        procurement_findings = [
            f"Источник: {metadata.get('procurement_source')}.",
            f"Идентификатор закупки: {metadata.get('procurement_id') or 'не указан'}.",
            f"Статус документации: {metadata.get('attachments_status') or 'не определён'}.",
        ]
        if metadata.get("procurement_url"):
            procurement_findings.append(f"Карточка закупки: {metadata.get('procurement_url')}.")
        steps.append(
            DemoStep(
                key="procurement_search",
                order=0,
                title="Поиск закупки",
                short_title="Поиск закупки",
                status=DemoStepStatus.DONE,
                description="Read-only поиск закупки и выбор карточки оператором.",
                agent_action=f"Найдена и выбрана закупка '{procurement_title}' из безопасного procurement discovery слоя.",
                result_summary=f"Выбрана закупка {metadata.get('procurement_id') or metadata.get('run_id')}.",
                findings=procurement_findings,
                human_review=[
                    "Проверить релевантность найденной закупки перед продолжением.",
                    "Подтвердить, что источник не требует авторизации, если будет подключаться реальный коннектор.",
                ],
                trace="Поиск выполнялся в безопасном режиме только чтения без авторизации, обхода captcha и внешних действий.",
                result_sections=[
                    DemoDetailSection(
                        title="Контекст поиска",
                        kind="bullets",
                        items=[
                            f"Запрос: {metadata.get('procurement_query') or 'не указан'}",
                            f"Источник: {metadata.get('procurement_source')}",
                            f"Статус документации: {metadata.get('attachments_status') or 'не определён'}",
                        ],
                    )
                ],
            )
        )

    steps.extend([
        DemoStep(
            key="documents",
            order=1,
            title="Документы",
            short_title="Документы",
            status=docs_status,
            description="Локальная загрузка и безопасная подготовка файлов к анализу.",
            agent_action="Файлы сохранены в локальную demo-run директорию, имена нормализованы, опасные пути удалены.",
            result_summary=(
                f"Загружено {file_count} файлов."
                if file_count
                else "Документы ещё не загружены. Для продолжения нужен ручной upload."
            ),
            findings=[item["display_name"] for item in metadata.get("files", [])]
            or ["Автоматически доступных документов нет, требуется ручная загрузка."],
            human_review=[
                "Проверить, что каждому файлу назначена корректная роль."
            ]
            if file_count
            else ["Загрузить документацию вручную и только потом запускать анализ."],
            trace=trace["documents"],
            result_sections=[
                DemoDetailSection(
                    title="Загруженные файлы",
                    kind="table",
                    columns=["Файл", "Расширение", "Размер"],
                    rows=[
                        {
                            "Файл": item["display_name"],
                            "Расширение": item["extension"],
                            "Размер": f"{item['size_bytes']} bytes",
                        }
                        for item in metadata.get("files", [])
                    ],
                )
            ],
        ),
        DemoStep(
            key="requirements",
            order=2,
            title="Требования",
            short_title="Требования",
            status=DemoStepStatus.PARTIAL if partial_requirements else DemoStepStatus.DONE,
            description="Извлечение ключевых требований и обязательных документов из доступного локального пакета.",
            agent_action="Собран снимок требований с помощью контролируемого парсера и fallback-адаптера.",
            result_summary=(
                preliminary_analysis.get("overview", [f"Выделено требований: {len(requirements['requirements'])}."])[0]
                if preliminary_analysis.get("overview")
                else f"Выделено требований: {len(requirements['requirements'])}."
            ),
            findings=(preliminary_analysis.get("overview", []) + [item["title"] for item in requirements["requirements"]])[:10],
            human_review=requirements["manual_review_points"],
            trace=trace["requirements"],
            result_sections=[
                DemoDetailSection(
                    title="Предварительный анализ закупки",
                    kind="bullets",
                    items=(
                        preliminary_analysis.get("overview", [])
                        + preliminary_analysis.get("compliance_highlights", [])[:3]
                        + preliminary_analysis.get("contract_highlights", [])[:2]
                    )[:10],
                ),
                DemoDetailSection(
                    title="Требования",
                    kind="table",
                    columns=["Требование", "Тип", "Приоритет", "Деталь", "Источник"],
                    rows=[
                        {
                            "Требование": item["title"],
                            "Тип": item.get("type", "общее"),
                            "Приоритет": item.get("priority", "medium"),
                            "Деталь": item["detail"],
                            "Источник": item["source"],
                        }
                        for item in requirements["requirements"]
                    ],
                )
            ],
        ),
        DemoStep(
            key="supplier_search",
            order=3,
            title="Поиск поставщиков",
            short_title="Поставщики",
            status=DemoStepStatus.DONE if metadata.get("supplier_search", {}).get("suppliers") else DemoStepStatus.PARTIAL,
            description="Интернет-поиск потенциальных поставщиков через Yandex Search API.",
            agent_action="Выполнен поиск поставщиков на основе требований закупки.",
            result_summary=f"Найдено поставщиков: {metadata.get('supplier_search', {}).get('total_found', 0)}." if metadata.get("supplier_search", {}).get("suppliers") else "Поиск поставщиков не выполнялся или не настроен.",
            findings=[f"{s['name']} — {s['site']}" for s in metadata.get("supplier_search", {}).get("suppliers", [])[:5]],
            human_review=["Проверить найденных поставщиков вручную перед отправкой RFQ."],
            trace=trace.get("supplier_search", "Поиск поставщиков выполнен через Yandex Search API без внешних изменений."),
            result_sections=[
                DemoDetailSection(
                    title="Найденные поставщики",
                    kind="table",
                    columns=["Поставщик", "Сайт", "Сигналы"],
                    rows=[
                        {"Поставщик": s["name"], "Сайт": s["site"], "Сигналы": ", ".join(s.get("signals", []) or ["—"])}
                        for s in metadata.get("supplier_search", {}).get("suppliers", [])[:10]
                    ],
                )
                if metadata.get("supplier_search", {}).get("suppliers")
                else DemoDetailSection(title="Статус поиска", kind="bullets", items=[
                    metadata.get("supplier_search", {}).get("query", "Поиск не выполнялся"),
                    "Поставщиков не найдено или API не настроено.",
                ]),
            ],
        ),
        DemoStep(
            key="questions",
            order=4,
            title="Вопросы",
            short_title="Вопросы",
            status=DemoStepStatus.NEEDS_REVIEW,
            description="Формирование вопросника по неоднозначностям и отсутствующим данным.",
            agent_action="Подготовлен набор вопросов для RFQ под контролем оператора.",
            result_summary=f"Подготовлено вопросов: {len(questions['questions'])}.",
            findings=questions["ambiguities"],
            human_review=questions["manual_checks"],
            trace=trace["questions"],
            result_sections=[
                DemoDetailSection(title="Вопросы поставщикам", kind="bullets", items=questions["questions"])
            ],
        ),
        DemoStep(
            key="rfq",
            order=5,
            title="RFQ",
            short_title="RFQ",
            status=DemoStepStatus.DONE if requirements["requirements"] else DemoStepStatus.PARTIAL,
            description="Подготовка draft RFQ для ручной отправки.",
            agent_action="Сформирован черновик RFQ на основе извлечённых требований и вопросов поставщикам.",
            result_summary="RFQ готов как внутренний черновик.",
            findings=rfq["sections"],
            human_review=rfq["manual_checks"],
            trace=trace["rfq"],
            result_sections=[
                DemoDetailSection(title="Секции RFQ", kind="bullets", items=rfq["sections"]),
                DemoDetailSection(
                    title="Позиции RFQ",
                    kind="table",
                    columns=["№", "Позиция", "Кол-во", "Ед.", "Обязательные характеристики", "ГОСТ / норматив", "Цена за ед.", "Сумма"],
                    rows=rfq.get("items", [])[:20],
                ),
            ] if rfq.get("items") else [DemoDetailSection(title="Секции RFQ", kind="bullets", items=rfq["sections"])],
        ),
        DemoStep(
            key="quotes",
            order=6,
            title="ТКП",
            short_title="ТКП",
            status=DemoStepStatus.BLOCKED if quote_blocked else (DemoStepStatus.PARTIAL if quote_partial else DemoStepStatus.DONE),
            description="Сопоставление коммерческих предложений, если они были загружены.",
            agent_action="Проверено наличие ТКП и собран локальный снимок сравнения с нормализацией таблиц.",
            result_summary=(
                "ТКП не загружены."
                if quote_blocked
                else (
                    "ТКП загружены, но требуют ручной нормализации."
                    if quotes.get("supplier_quotes_found", 0) == 0
                    else f"Найдено ТКП: {quotes.get('supplier_quotes_found', 0)}, позиций: {quotes.get('items_extracted', 0)}."
                )
            ),
            findings=quotes["highlights"],
            human_review=quotes["manual_checks"],
            trace=trace["quotes"],
            result_sections=[
                DemoDetailSection(
                    title="Извлечённые ТКП",
                    kind="table",
                    columns=["Поставщик", "Файл", "Сумма", "Валюта", "Позиций", "Уверенность"],
                    rows=[
                        {
                            "Поставщик": item.get("supplier_name", "Поставщик"),
                            "Файл": item.get("source_file", "unknown"),
                            "Сумма": item.get("total_amount", "unknown"),
                            "Валюта": item.get("currency", "unknown"),
                            "Позиций": item.get("items_count", "unknown"),
                            "Уверенность": item.get("price_confidence", "unknown"),
                        }
                        for item in quotes["suppliers"]
                    ],
                )
                if quotes["suppliers"]
                else DemoDetailSection(title="Статус ТКП", kind="bullets", items=quotes["highlights"]),
                DemoDetailSection(
                    title="Сравнение предложений",
                    kind="table",
                    columns=["Позиция", "Лучшая цена", "Разброс %", "Нужна проверка"],
                    rows=[
                        {
                            "Позиция": item.get("normalized_name", "unknown"),
                            "Лучшая цена": item.get("best_price_supplier", "unknown"),
                            "Разброс %": item.get("price_spread_percent", "unknown"),
                            "Нужна проверка": "да" if item.get("needs_review") else "нет",
                        }
                        for item in quotes.get("items", [])[:20]
                    ],
                )
                if quotes["suppliers"]
                else DemoDetailSection(title="Статус ТКП", kind="bullets", items=quotes["highlights"])
            ],
        ),
        DemoStep(
            key="economics",
            order=7,
            title="Экономика",
            short_title="Экономика",
            status=DemoStepStatus.BLOCKED if economics_blocked else (DemoStepStatus.PARTIAL if economics_partial else DemoStepStatus.NEEDS_REVIEW),
            description="Расчёт экономики только по доступным локальным данным.",
            agent_action="Собран снимок экономики без притворства полной автоматизации при нехватке данных.",
            result_summary=economics["result"],
            findings=economics["drivers"],
            human_review=economics["manual_checks"],
            trace=trace["economics"],
            result_sections=[
                DemoDetailSection(
                    title="Снимок экономики",
                    kind="table",
                    columns=["Показатель", "Значение"],
                    rows=[
                        {"Показатель": item["label"], "Значение": item["value"]}
                        for item in economics["metrics"]
                    ],
                )
            ],
        ),
        DemoStep(
            key="risks",
            order=9,
            title="Риски",
            short_title="Риски",
            status=DemoStepStatus.WARNING,
            description="Сводка рисков и ограничений demo-mode.",
            agent_action="Риски агрегированы в единый блок для удобной ручной проверки.",
            result_summary=risks["summary"],
            findings=[item["risk"] for item in risks["risks"]],
            human_review=risks["manual_checks"],
            trace=trace["risks"],
            result_sections=[
                DemoDetailSection(
                    title="Риски",
                    kind="table",
                    columns=["Риск", "Серьёзность", "Влияние", "Смягчение"],
                    rows=[
                        {
                            "Риск": item["risk"],
                            "Серьёзность": item["severity"],
                            "Влияние": item["impact"],
                            "Смягчение": item["mitigation"],
                        }
                        for item in risks["risks"]
                    ],
                )
            ],
        ),
        DemoStep(
            key="decision",
            order=9,
            title="Решение",
            short_title="Решение",
            status=DemoStepStatus.NEEDS_REVIEW,
            description="Предварительная рекомендация без внешних действий и без снятия human control.",
            agent_action="Собран итоговый блок рекомендации с открытыми вопросами и ручными проверками.",
            result_summary=f"Рекомендация: {final_recommendation['label']}.",
            findings=final_recommendation["rationale"],
            human_review=final_recommendation["manual_checks"],
            trace=trace["decision"],
            result_sections=[
                DemoDetailSection(title="Открытые вопросы", kind="bullets", items=final_recommendation["open_questions"])
            ],
        ),
    ])
    return steps
