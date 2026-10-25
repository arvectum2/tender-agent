"""Historical operator report HTML layout.

No new procurement inference. Original f-string AST is unchanged.
"""
from __future__ import annotations

from typing import Any


def render_operator_html_layout(
    archive_button_html: Any,
    deadline_ru: Any,
    delivery_term_ru: Any,
    document_toggle_html: Any,
    downloaded_docs: Any,
    downloaded_files_count: Any,
    economics: Any,
    export_buttons_html: Any,
    files: Any,
    final_recommendation: Any,
    format_price: Any,
    format_value: Any,
    list_html: Any,
    metadata: Any,
    notice_number_html: Any,
    outputs: Any,
    preliminary_analysis: Any,
    procurement: Any,
    procurement_manual_required: Any,
    publication_update: Any,
    questions: Any,
    quotes: Any,
    render_table: Any,
    requirements: Any,
    risks: Any,
    supply_section_title: Any,
    trace: Any,
) -> str:
    import html

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
