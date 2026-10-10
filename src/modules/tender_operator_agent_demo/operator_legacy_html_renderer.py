"""Historical Operator report HTML rendering isolated from upload orchestration.

The legacy callable signature remains unchanged at its original module boundary.
No authority is inferred from formatting; all values are HTML escaped as before.
"""
from __future__ import annotations

import html
from collections.abc import Callable
from typing import Any


def render_legacy_report_html(
    metadata: dict[str, Any],
    outputs: dict[str, dict[str, Any]],
    *,
    inventory_builder: Callable[..., Any],
    supply_section_title: Callable[..., Any],
    input_dir_resolver: Callable[..., Any],
) -> str:
    def list_html(items: list[str]) -> str:
        return "".join(f"<li>{html.escape(item)}</li>" for item in items)

    def is_missing(value: Any) -> bool:
        if value is None:
            return True
        text = str(value).strip()
        return not text or text.lower() in {"не указан", "none", "null", "n/a", "—"}

    def format_value(value: Any, *, fallback: str = "не указано") -> str:
        return fallback if is_missing(value) else str(value).strip()

    def format_date_ru(value: Any) -> str:
        text = str(value).strip() if value else ""
        import re
        iso_match = re.match(r"(\d{4})-(\d{2})-(\d{2})", text)
        if iso_match:
            return f"{iso_match.group(3)}.{iso_match.group(2)}.{iso_match.group(1)}"
        rus_match = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", text)
        if rus_match:
            return text
        return text

    def format_price(amount: Any, currency: Any) -> str:
        if amount in (None, ""):
            return "не указана"
        if isinstance(amount, float):
            amount_text = f"{amount:,.2f}".replace(",", " ").replace(".", ",")
        else:
            amount_text = str(amount)
        currency_text = str(currency).strip() if currency else ""
        if not currency_text:
            currency_text = "₽"
        return f"{amount_text} {currency_text}".strip()

    def build_archive_button_html(run_id: str, archive_available: bool) -> str:
        if not archive_available:
            return ""
        return (
            f'<a class="action-button primary" href="/api/demo/tender-agent/runs/{html.escape(run_id)}/archive/download">Скачать архив</a>'
        )

    def build_export_buttons_html(run_id: str) -> str:
        return (
            f'<a class="action-button" href="/api/demo/tender-agent/runs/{html.escape(run_id)}/export/docx">Скачать DOCX</a>'
            f'<a class="action-button" href="/api/demo/tender-agent/runs/{html.escape(run_id)}/export/pdf">Скачать PDF</a>'
        )

    def build_document_list_html(run_id: str, files_payload: list[dict[str, Any]]) -> str:
        items: list[str] = []
        for item in files_payload:
            file_id = str(item.get("file_id") or "").strip()
            display_name = format_value(item.get("display_name"), fallback="Документ")
            if not file_id:
                continue
            items.append(
                f'<li><a class="doc-link" href="/api/demo/tender-agent/runs/{html.escape(run_id)}/files/{html.escape(file_id)}/download">{html.escape(display_name)}</a></li>'
            )
        if not items:
            return '<div class="muted">Документы для скачивания пока не доступны.</div>'
        return "".join(items)

    def build_document_toggle_html(run_id: str, files_payload: list[dict[str, Any]]) -> str:
        content = build_document_list_html(run_id, files_payload)
        if content.startswith("<div"):
            return content
        return (
            '<details class="document-toggle">'
            '<summary class="action-button">Показать документы</summary>'
            f'<ul class="document-list">{content}</ul>'
            '</details>'
        )

    def format_publication_update(publication_date: Any, updated_date: Any) -> str:
        publication = format_value(publication_date)
        updated = format_value(updated_date, fallback="")
        if updated and updated != publication:
            return f"{publication} / {updated}"
        return publication

    def render_table(columns: list[str], rows: list[dict[str, Any]]) -> str:
        if not rows:
            return "<p>Нет данных для отображения.</p>"
        header_html = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
        body_html = "".join(
            "<tr>"
            + "".join(f"<td>{html.escape(str(row.get(column, '')))}</td>" for column in columns)
            + "</tr>"
            for row in rows
        )
        return f"<table><thead><tr>{header_html}</tr></thead><tbody>{body_html}</tbody></table>"

    requirements = outputs["requirements"]
    questions = outputs["supplier_questions"]
    quotes = outputs["quotes_comparison"]
    economics = outputs["economics"]
    risks = outputs["contract_risks"]
    final_recommendation = outputs["final_recommendation"]
    trace = outputs["trace"]
    preliminary_analysis = requirements.get("preliminary_analysis", {})
    downloaded_docs = inventory_builder(metadata)
    files = metadata.get("files", [])
    procurement = metadata.get("procurement", {})
    procurement_manual_required = bool(metadata.get("manual_upload_required") or metadata.get("attachments_status") == "manual_upload_required" or not files)
    procurement_url = str(metadata.get("procurement_url") or procurement.get("source_url") or "").strip()
    notice_number = format_value(metadata.get("notice_number") or metadata.get("procurement_id") or procurement.get("procurement_number"))
    notice_number_html = (
        f'<a class="inline-link" href="{html.escape(procurement_url)}" target="_blank" rel="noopener noreferrer">{html.escape(notice_number)}</a>'
        if procurement_url and notice_number != "не указано"
        else html.escape(notice_number)
    )
    publication_update = format_publication_update(
        format_date_ru(metadata.get("publication_date") or procurement.get("publication_date")),
        format_date_ru(metadata.get("updated_date") or procurement.get("updated_date")),
    )
    deadline_ru = format_date_ru(metadata.get("deadline") or procurement.get("deadline"))
    delivery_term_ru = format_date_ru(procurement.get("delivery_term"))
    downloaded_files_count = int(metadata.get("downloaded_files_count", len(files)))
    archive_available = (input_dir_resolver(str(metadata.get("run_id"))) / "documentation-archive.zip").is_file()
    archive_button_html = build_archive_button_html(str(metadata.get("run_id")), archive_available)
    document_toggle_html = build_document_toggle_html(str(metadata.get("run_id")), files)
    export_buttons_html = build_export_buttons_html(str(metadata.get("run_id")))

    return f"""
    <html lang="ru">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Отчёт по загруженному прогону тендерного агента</title>
        <style>
          body {{
            margin: 0;
            font-family: Arial, sans-serif;
            background: #001432;
            color: #ffffff;
          }}
          .page {{
            max-width: 1080px;
            margin: 0 auto;
            padding: 24px;
          }}
          .card {{
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(200,210,220,0.16);
            border-radius: 18px;
            padding: 20px;
            margin-bottom: 16px;
          }}
          h1, h2, h3 {{ margin-top: 0; }}
          .badge {{
            display: inline-block;
            padding: 8px 12px;
            border-radius: 999px;
            background: rgba(0,200,160,0.15);
            border: 1px solid rgba(120,250,230,0.25);
            margin-right: 8px;
            margin-bottom: 8px;
          }}
          table {{ width: 100%; border-collapse: collapse; }}
          th, td {{ text-align: left; padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.1); }}
          th {{ color: #78FAE6; font-size: 12px; text-transform: uppercase; }}
          ul {{ margin: 0; padding-left: 18px; }}
          .muted {{ color: rgba(255,255,255,0.75); }}
          .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 12px 18px;
            margin-top: 18px;
          }}
          .metric {{
            padding: 12px 14px;
            border-radius: 14px;
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.08);
          }}
          .metric-label {{
            display: block;
            font-size: 12px;
            text-transform: uppercase;
            color: #78FAE6;
            margin-bottom: 6px;
          }}
          .metric-value {{
            display: block;
            font-size: 15px;
            line-height: 1.4;
          }}
          .downloads {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 16px;
            align-items: flex-start;
          }}
          .action-button {{
            display: inline-flex;
            align-items: center;
            padding: 10px 14px;
            border-radius: 999px;
            color: #ffffff;
            text-decoration: none;
            border: 1px solid rgba(120,250,230,0.3);
            background: rgba(255,255,255,0.05);
          }}
          .action-button.primary {{
            background: rgba(0,200,160,0.18);
          }}
          .inline-link {{
            color: #9cfbee;
            text-decoration: none;
            border-bottom: 1px dashed rgba(156,251,238,0.5);
          }}
          .document-toggle {{
            min-width: 240px;
          }}
          .document-toggle summary {{
            list-style: none;
          }}
          .document-toggle summary::-webkit-details-marker {{
            display: none;
          }}
          .document-list {{
            margin-top: 12px;
            padding-left: 18px;
          }}
          .document-list li + li {{
            margin-top: 8px;
          }}
          .doc-link {{
            color: #ffffff;
            text-decoration: none;
            border-bottom: 1px dashed rgba(255,255,255,0.35);
          }}
          .table-scroll {{
            overflow-x: auto;
            margin-top: 12px;
          }}
        </style>
      </head>
      <body>
        <div class="page">
          <div class="card">
            <div class="badge">Демо / пилотный режим</div>
            <div class="badge">Без внешних действий</div>
            <div class="badge">Требуется подтверждение человека</div>
            <h1>{html.escape(metadata['tender_title'])}</h1>
            <div class="summary-grid">
              <div class="metric"><span class="metric-label">Номер извещения</span><span class="metric-value">{notice_number_html}</span></div>
              <div class="metric"><span class="metric-label">Категория закупки</span><span class="metric-value">{html.escape(format_value(metadata.get('law') or metadata.get('tender_category') or procurement.get('category')))}</span></div>
              <div class="metric"><span class="metric-label">Заказчик</span><span class="metric-value">{html.escape(format_value(metadata.get('customer_name') or procurement.get('customer_name')))}</span></div>
              <div class="metric"><span class="metric-label">НМЦК</span><span class="metric-value">{html.escape(format_price(procurement.get('initial_price'), procurement.get('currency')))}</span></div>
              <div class="metric"><span class="metric-label">Дата публикации / обновления</span><span class="metric-value">{html.escape(publication_update)}</span></div>
              <div class="metric"><span class="metric-label">Срок подачи</span><span class="metric-value">{html.escape(deadline_ru or 'не указан')}</span></div>
              <div class="metric"><span class="metric-label">Срок поставки</span><span class="metric-value">{html.escape(delivery_term_ru or 'не указан')}</span></div>
              <div class="metric"><span class="metric-label">Источник сведений</span><span class="metric-value">{html.escape(procurement.get('structured_source_label') or metadata.get('notice_source_label') or 'карточка ЕИС')}</span></div>
              <div class="metric"><span class="metric-label">Статус подключения</span><span class="metric-value">{html.escape("Документы получены через ЕИС" if metadata.get("procurement_source") else "Документы загружены вручную")}</span></div>
              <div class="metric"><span class="metric-label">Скачано документов</span><span class="metric-value">{downloaded_files_count}</span></div>
            </div>
            <div class="downloads">{export_buttons_html}{archive_button_html}{document_toggle_html}</div>
            {('<p class="muted">Документация не получена. Анализ невозможен до ручной загрузки файлов.</p>' if procurement_manual_required and not files else '')}
          </div>

          <div class="card">
            <h2>Загруженные документы</h2>
            {render_table(
                ["Тип", "Файл", "Статус скачивания", "Статус текста", "Источник"],
                [
                    {
                        "Тип": item["type"],
                        "Файл": item["name"],
                        "Статус скачивания": item["download_status"],
                        "Статус текста": item["text_status"],
                        "Источник": item["source"],
                    }
                    for item in downloaded_docs
                ],
            )}
            {('<p class="muted">По закупке не найдены публичные вложения кроме электронного извещения. Анализ технической части ограничен.</p>' if len(downloaded_docs) <= 1 else '')}
          </div>

          <div class="card">
            <h2>Предварительный анализ закупки</h2>
            <ul>{list_html(preliminary_analysis.get('overview', [])) or "<li>Пока не удалось извлечь структурированные выводы из ТЗ.</li>"}</ul>
            {(
                f"<h3>{html.escape(supply_section_title(preliminary_analysis))}</h3>"
                + f"<p>{html.escape(preliminary_analysis.get('supply_section_note', 'Состав поставки собран по техническим документам.'))}</p>"
                + '<div class="table-scroll">'
                + render_table(
                    preliminary_analysis.get('spec_table', {}).get('columns', []),
                    preliminary_analysis.get('spec_table', {}).get('rows', []),
                )
                + '</div>'
            ) if preliminary_analysis.get('spec_table', {}).get('rows') else ''}
            <h3>Ключевые требования и ограничения</h3>
            <ul>{list_html(preliminary_analysis.get('compliance_highlights', [])) or "<li>Требуется ручная валидация ключевых требований по исходным документам.</li>"}</ul>
            <h3>Модель исполнения</h3>
            <ul>{list_html(preliminary_analysis.get('delivery_model', [])) or "<li>Формат исполнения нужно уточнить вручную.</li>"}</ul>
            <h3>Ключевые условия договора</h3>
            <ul>{list_html(preliminary_analysis.get('contract_highlights', [])) or "<li>Ключевые условия договора нужно проверить вручную.</li>"}</ul>
            <h3>Что делать дальше</h3>
            <ul>{list_html(preliminary_analysis.get('next_actions', []))}</ul>
          </div>

          <div class="card">
            <h2>Извлечённые требования</h2>
            {render_table(
                ["Требование", "Тип", "Приоритет", "Источник"],
                [
                    {
                        "Требование": item.get("title", ""),
                        "Тип": item.get("type", "общее"),
                        "Приоритет": item.get("priority", "medium"),
                        "Источник": item.get("source", "не указан"),
                    }
                    for item in requirements['requirements']
                ],
            )}
          </div>

          <div class="card">
            <h2>Вопросы поставщикам</h2>
            <ul>{list_html(questions['questions'])}</ul>
          </div>

          <div class="card">
            <h2>RFQ draft</h2>
            <ul>{list_html(outputs['rfq_draft']['sections'])}</ul>
          </div>

          <div class="card">
            <h2>Извлечённые ТКП</h2>
            {render_table(
                ["Поставщик", "Файл", "Сумма", "Валюта", "Позиций", "Уверенность"],
                [
                    {
                        "Поставщик": item.get("supplier_name", "Поставщик"),
                        "Файл": item.get("source_file", "unknown"),
                        "Сумма": item.get("total_amount", "unknown"),
                        "Валюта": item.get("currency", "unknown"),
                        "Позиций": item.get("items_count", "unknown"),
                        "Уверенность": item.get("price_confidence", "unknown"),
                    }
                    for item in quotes.get("suppliers", [])
                ],
            )}
            <p class="muted">{html.escape(" ".join(quotes.get("limitations", [])))}</p>
          </div>

          <div class="card">
            <h2>Сравнение ТКП</h2>
            <ul>{list_html(quotes['highlights'])}</ul>
            {render_table(
                ["Позиция", "Лучшая цена", "Разброс %", "Нужна проверка"],
                [
                    {
                        "Позиция": item.get("normalized_name", "unknown"),
                        "Лучшая цена": item.get("best_price_supplier", "unknown"),
                        "Разброс %": item.get("price_spread_percent", "unknown"),
                        "Нужна проверка": "да" if item.get("needs_review") else "нет",
                    }
                    for item in quotes.get("items", [])[:24]
                ],
            )}
          </div>

          <div class="card">
            <h2>Экономика</h2>
            <ul>{list_html([f"{item['label']}: {item['value']}" for item in economics['metrics']])}</ul>
            <ul>{list_html(economics.get('manual_checks', []))}</ul>
            <p class="muted">{html.escape(" ".join(economics.get("limitations", [])))}</p>
          </div>

          <div class="card">
            <h2>Контрактные риски</h2>
            <ul>{list_html([item['risk'] for item in risks['risks']])}</ul>
          </div>

          <div class="card">
            <h2>Финальная рекомендация</h2>
            <p><strong>{html.escape(final_recommendation['label'])}</strong></p>
            <ul>{list_html(final_recommendation['rationale'])}</ul>
            <ul>{list_html(final_recommendation['manual_checks'])}</ul>
          </div>

          <div class="card">
            <h2>Трассировка и обоснование</h2>
            <p>{html.escape(trace['overall_explanation'])}</p>
            <ul>{list_html(trace.get('limitations', []))}</ul>
          </div>
        </div>
      </body>
    </html>
    """
