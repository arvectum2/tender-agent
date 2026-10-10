"""Pure markdown report presentation; zero direct filesystem or EIS/LLM I/O.

The old operator entrypoints inject their existing functions to keep the exact
legacy behavior and test monkeypatch compatibility while removing monolith logic.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any


def preliminary_supply_section_title(preliminary_analysis: dict[str, Any]) -> str:
    columns = preliminary_analysis.get("spec_table", {}).get("columns", []) or []
    if "Блок работ / результат" in columns:
        return "Состав работ / поставки / услуг"
    return "Состав поставки"


def preliminary_supply_section_markdown(preliminary_analysis: dict[str, Any]) -> str:
    rows = preliminary_analysis.get("spec_table", {}).get("rows", []) or []
    if not rows:
        return "Структурированный состав поставки не выделен автоматически. Требуется ручная проверка ТЗ и приложений."

    note = preliminary_analysis.get("supply_section_note", "").strip()
    columns = preliminary_analysis.get("spec_table", {}).get("columns", []) or []
    lines: list[str] = [note] if note else []
    if "Блок работ / результат" in columns:
        lines.extend(
            [
                (
                    f"- {row.get('№', '—')}. {row.get('Блок работ / результат', 'Блок работ')} | "
                    f"что сделать: {row.get('Что нужно сделать', 'не указано')} | "
                    f"системы: {row.get('Входные/внешние системы', 'не указано')} | "
                    f"результат: {row.get('Результат для заказчика', 'не указано')} | "
                    f"приемка: {row.get('Критерии приёмки', 'не указано')} | "
                    f"источник: {row.get('Источник', 'не указан')}"
                )
                for row in rows
            ]
        )
        return "\n".join(lines)

    lines.extend(
        [
            (
                f"- {row.get('№', '—')}. {row.get('Наименование', 'Позиция')} | "
                f"кол-во: {row.get('Кол-во', 'не указано')} | "
                f"ед.: {row.get('Ед. изм.', '—')} | "
                f"характеристики: {row.get('Ключевые характеристики', row.get('Характеристики', '—'))} | "
                f"ГОСТ: {row.get('ГОСТ / норматив', '—')} | "
                f"эквивалент: {row.get('Эквивалент', '—')} | "
                f"цена: {row.get('Цена за ед., руб.', '—')} | "
                f"источник: {row.get('Источник', 'не указан')}"
            )
            for row in rows
        ]
    )
    return "\n".join(lines)


def render_operator_report_markdown(
    metadata: dict[str, Any],
    outputs: dict[str, dict[str, Any]],
    *,
    inventory_builder: Callable[[dict[str, Any]], list[dict[str, str]]],
    supply_title: Callable[[dict[str, Any]], str],
    supply_markdown: Callable[[dict[str, Any]], str],
) -> str:
    final_recommendation = outputs["final_recommendation"]
    quotes = outputs["quotes_comparison"]
    economics = outputs["economics"]
    preliminary_analysis = outputs["requirements"].get("preliminary_analysis", {})
    downloaded_docs = inventory_builder(metadata)
    procurement_block = ""
    if metadata.get("procurement_source"):
        procurement = metadata.get("procurement", {})
        documentation = procurement.get("attachment_names") or [item.get("display_name", "") for item in metadata.get("files", [])]
        documentation_block = "\n".join(f"- {item}" for item in documentation) or "- Документация не получена."
        downloaded_documents_block = (
            "\n".join(
                f"- {item['type']}: {item['name']} | download={item['download_status']} | text={item['text_status']} | source={item['source']}"
                for item in downloaded_docs
            )
            or "- Документы не скачаны."
        )
        blocked_note = (
            "\nДокументация не получена. Анализ невозможен до ручной загрузки файлов.\n"
            if metadata.get("attachments_status") == "manual_upload_required" or not metadata.get("files")
            else ""
        )
        procurement_block = (
            "## Источник закупки\n"
            f"- Источник: {metadata.get('procurement_source')}\n"
            f"- Номер извещения: {metadata.get('notice_number') or metadata.get('procurement_id')}\n"
            f"- Заказчик: {metadata.get('customer_name')}\n"
            f"- Закон: {metadata.get('law') or procurement.get('category') or 'не указан'}\n"
            f"- НМЦК: {procurement.get('initial_price') or 'не указана'} {procurement.get('currency') or '₽'}\n"
            f"- Дата публикации: {metadata.get('publication_date') or procurement.get('publication_date') or 'не указана'}\n"
            f"- Срок подачи: {metadata.get('deadline') or 'не указан'}\n"
            f"- Источник сведений: {procurement.get('structured_source_label') or metadata.get('notice_source_label') or 'карточка ЕИС'}\n"
            f"- Ссылка на источник: {metadata.get('procurement_url')}\n"
            f"- Статус скачивания: {metadata.get('attachments_status')}\n"
            f"- Ручная загрузка требовалась: {'да' if metadata.get('manual_upload_required') else 'нет'}\n"
            f"- Скачано/добавлено файлов: {metadata.get('downloaded_files_count', len(metadata.get('files', [])))}\n\n"
            "### Документация\n"
            f"{documentation_block}\n"
            "### Загруженные документы\n"
            f"{downloaded_documents_block}\n"
            f"{blocked_note}\n"
        )
    return (
        "# Отчёт по загруженному прогону тендерного агента\n\n"
        f"- Run ID: {metadata['run_id']}\n"
        f"- Закупка: {metadata['tender_title']}\n"
        f"- Категория: {metadata['tender_category']}\n"
        f"- Заказчик: {metadata['customer_name']}\n"
        f"- Статус: {metadata['status']}\n"
        f"- Режим анализа: {metadata['analysis_mode']}\n"
        f"- Код рекомендации: {final_recommendation['recommendation']}\n\n"
        + procurement_block
        + "## Краткий вывод\n"
        + "\n".join(f"- {item}" for item in final_recommendation["rationale"])
        + "\n\n## Предварительный анализ закупки\n"
        + (
            "\n".join(f"- {item}" for item in preliminary_analysis.get("overview", []))
            if preliminary_analysis.get("overview")
            else "- Пока не удалось извлечь структурированные выводы из ТЗ."
        )
        + "\n\n### Ключевые требования и ограничения\n"
        + (
            "\n".join(f"- {item}" for item in preliminary_analysis.get("compliance_highlights", []))
            if preliminary_analysis.get("compliance_highlights")
            else "- Требуется ручная валидация ключевых требований по исходным документам."
        )
        + "\n\n### Ключевые условия договора\n"
        + (
            "\n".join(f"- {item}" for item in preliminary_analysis.get("contract_highlights", []))
            if preliminary_analysis.get("contract_highlights")
            else "- Ключевые условия договора нужно проверить вручную."
        )
        + f"\n\n## {supply_title(preliminary_analysis)}\n"
        + supply_markdown(preliminary_analysis)
        + "\n\n## Извлечённые ТКП\n"
        + (
            "\n".join(
                f"- {item.get('supplier_name', 'Поставщик')}: сумма={item.get('total_amount', 'unknown')} {item.get('currency', '')}, позиций={item.get('items_count', 'unknown')}"
                for item in quotes.get("suppliers", [])
            )
            if quotes.get("suppliers")
            else "- ТКП не загружены или не распознаны."
        )
        + "\n\n## Экономика\n"
        + "\n".join(f"- {item['label']}: {item['value']}" for item in economics["metrics"])
        + "\n\n## Ключевые требования\n"
        + (
            "\n".join(
                f"- {item['title']} | тип: {item.get('type', 'общее')} | приоритет: {item.get('priority', 'medium')} | источник: {item['source']}"
                for item in outputs["requirements"].get("requirements", [])
            )
            if outputs["requirements"].get("requirements")
            else "- Требования не выделены автоматически."
        )
        + "\n\n## Ручные проверки\n"
        + "\n".join(f"- {item}" for item in final_recommendation["manual_checks"])
        + "\n"
    )

