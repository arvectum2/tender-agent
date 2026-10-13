"""Domain-owned deterministic renderer or service analysis; upload-I/O independent."""

from __future__ import annotations

import html
from typing import Any


def project_render_product_report_html(
    model: dict[str, Any], *, customer: bool = True
) -> str:

    def esc(value: Any) -> str:
        return html.escape(
            str(
                value
                if value not in (None, "")
                else "Данных недостаточно — требуется проверка"
            )
        )

    decision = model["customer_decision"]
    documents = "".join(
        f"<li>{esc(item['name'])} ({esc(item['type'])})</li>"
        for item in model["customer_documents"]
    )
    bullets = lambda values: "".join(f"<li>{esc(value)}</li>" for value in values)
    rows = "".join(
        f"<tr><td>{row['sequence']}</td><td>{esc(row['original_name'])}</td><td>{esc(row['quantity_display'])}</td><td>{esc(row['unit_original'])}</td><td>{esc(row.get('okpd2') or 'Не извлечён')}</td><td>Извещение о закупке — раздел «Объект закупки», {esc(row['source_row'] or 'позиция не указана')}</td></tr>"
        for row in model["line_items"]
    )
    evidence = bullets(
        [
            f"{item['document']} — {item.get('document_type', 'документ')}, {item['row']}"
            for item in model["evidence_map"]
        ]
    )
    risks = bullets(
        [
            f"{risk.get('risk')}: {risk.get('impact')}. Что сделать: {risk.get('mitigation')}"
            for risk in model["risks"]
        ]
    )
    economics = ""
    if model.get("unit_economics"):
        item = model["unit_economics"]
        value = f"{item['value']:,.2f}".replace(",", " ").replace(".", ",")
        economics = f"<section><h2>Экономический ориентир</h2><p>НМЦК, делённая на подтверждённый объём, составляет ориентировочно <strong>{value} ₽ за {esc(item['unit'])}</strong>.</p><p>Это арифметический ориентир по НМЦК, а не подтверждённая закупочная себестоимость.</p></section>"
    if customer:
        return f"""<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>Анализ закупки № {esc(model.get("procurement_number"))}</title><style>body{{margin:0;background:#f5f8fa;color:#10243e;font:16px Arial,sans-serif}}main{{max-width:1180px;margin:auto;padding:24px}}section{{background:#fff;border:1px solid #dce5eb;border-radius:12px;padding:20px;margin:16px 0}}h1,h2{{color:#003b5c}}.decision{{border-left:6px solid #d08300}}.scroll{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;min-width:760px}}th,td{{border-bottom:1px solid #dce5eb;padding:9px;text-align:left;vertical-align:top}}th{{background:#e9f7f5}}</style></head><body><main>\n<section><h1>Анализ закупки № {esc(model.get("procurement_number"))}</h1><p>Отчёт для принятия решения об участии</p><details><summary>Документы комплекта ({len(model["customer_documents"])})</summary><ul>{documents}</ul></details></section>\n<section><h2>{esc(model.get("procurement_title"))}</h2><p>Заказчик: {esc(model.get("customer_name"))}</p><p>Дата публикации: {esc(model.get("publication_datetime_display"))}</p><p>Окончание подачи заявок: {esc(model.get("application_deadline_display"))}</p><p>НМЦК: {esc(model.get("nmck"))} ₽</p><p>Место поставки: {esc(model.get("delivery_place"))}</p>{(f"<p>Отчёт сформирован по состоянию на: {esc(model.get('analysis_as_of'))}</p>" if model.get("analysis_as_of") != "Данных недостаточно — требуется проверка" else "")}</section>\n<section class="decision"><h2>Решение: {esc(decision["recommendation"])}</h2><h3>Ключевые основания</h3><ul>{bullets(decision["reasons"])}</ul><h3>Подтверждено документами</h3><ul>{bullets(decision["confirmed"])}</ul>{("<h3>Не удалось оценить</h3><ul>" + bullets(decision["not_evaluated"]) + "</ul>" if decision["not_evaluated"] else "")}<p><strong>Следующее действие:</strong> {esc(decision["next_action"])}</p></section>\n{(f'<section><h2>Состав и объём закупки</h2><div class="scroll"><table><thead><tr><th>№</th><th>Наименование</th><th>Количество</th><th>Единица</th><th>ОКПД2</th><th>Подтверждённый источник</th></tr></thead><tbody>{rows}</tbody></table></div><p>Зимний класс, ГОСТ, экологический класс и другие детальные характеристики не извлечены из текущего комплекта документов.</p></section>' if rows else "")}\n{economics}<section><h2>Коммерческие предложения</h2><p>Коммерческие предложения не загружены; экономика участия не рассчитана.</p></section>{(f"<section><h2>Риски, подтверждённые документами</h2><ul>{risks}</ul></section>" if risks else "")}\n{(f"<section><h2>Вопросы для уточнения</h2><ul>{bullets(model['customer_questions'])}</ul></section>" if model["customer_questions"] else "<section><h2>Вопросы для уточнения</h2><p>Сначала необходимо запросить отсутствующие документы. Предметные вопросы по договорным и техническим условиям будут сформированы после их получения.</p></section>")}\n{(f"<section><h2>Источники</h2><ul>{evidence}</ul></section>" if evidence else "")}{(f"<section><h2>Ограничения комплекта документов</h2><ul>{bullets(model['corpus_limitations'])}</ul></section>" if model["corpus_limitations"] else "")}</main></body></html>"""

    def esc(value: Any) -> str:
        return html.escape(
            str(
                value
                if value not in (None, "")
                else "Данных недостаточно — требуется проверка"
            )
        )

    (summary, passport, meta) = (
        model["executive_summary"],
        model["procurement_passport"],
        model["metadata"],
    )
    compatibility = model.get("compatibility_sections", {})
    rows = (
        "".join(
            f"<tr><td>{row['sequence']}</td><td>{esc(row['original_name'])}</td><td>{esc(row['quantity_display'])}</td><td>{esc(row['unit_original'])}</td><td>{esc(row['quantity_status'])}</td><td>{esc(row['source_document_id'])}, {row['source_row']} [{esc(', '.join(row['evidence_ids']))}]</td></tr>"
            for row in model["line_items"]
        )
        or '<tr><td colspan="6">Позиции и количество не удалось извлечь из доступных документов; требуется проверка первоисточника.</td></tr>'
    )
    risks = "".join(
        f"<li><strong>{esc(risk.get('status', 'Требует проверки'))}</strong>: {esc(risk.get('risk'))}. {esc(risk.get('impact'))}</li>"
        for risk in model["risks"]
    )
    evidence = "".join(
        f"<li id='{esc(item['evidence_id'])}'><strong>[{esc(item['evidence_id'])}]</strong> {esc(item['document'])}, строка {esc(item['row'])}: {esc(item['short_excerpt'])}</li>"
        for item in model["evidence_map"]
    )
    bullets = lambda values: (
        "".join(f"<li>{esc(value)}</li>" for value in values)
        or "<li>Не применимо — подтверждённых данных нет.</li>"
    )
    compatibility_rows = "".join(
        "<tr>"
        + "".join(
            f"<td>{esc(row.get(column))}</td>"
            for column in compatibility.get("spec_columns", [])
        )
        + "</tr>"
        for row in compatibility.get("spec_rows", [])
    )
    compatibility_table = (
        f"<div class='scroll'><table><thead><tr>{''.join(f'<th>{esc(column)}</th>' for column in compatibility.get('spec_columns', []))}</tr></thead><tbody>{compatibility_rows}</tbody></table></div>"
        if compatibility.get("spec_rows") and (not model.get("service_catalog"))
        else ""
    )
    return f"""<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Анализ закупки {esc(meta.get("procurement_number"))}</title><style>\nbody{{margin:0;background:#f5f8fa;color:#10243e;font:16px Arial,sans-serif}}main{{max-width:1180px;margin:auto;padding:24px}}section{{background:#fff;border:1px solid #dce5eb;border-radius:12px;padding:20px;margin:16px 0}}h1,h2{{color:#003b5c}}.decision{{border-left:6px solid #d08300}}.scroll{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;min-width:760px}}th,td{{border-bottom:1px solid #dce5eb;padding:9px;text-align:left;vertical-align:top}}th{{background:#e9f7f5}}.label{{font-weight:bold;color:#006b66}}@media print{{body{{background:#fff}}section{{break-inside:avoid}}}}@media(max-width:700px){{main{{padding:12px}}section{{padding:14px}}}}</style></head><body><main>\n<section><h1>{esc(compatibility.get("report_title"))}</h1><p>Номер извещения: {esc(compatibility.get("notice_number"))}</p><p>{esc(compatibility.get("source_status"))}</p><p>Скачано документов: {esc(compatibility.get("downloaded_files_count"))}</p><details><summary>Показать документы</summary><p>Документы текущего run доступны через защищённые ссылки интерфейса.</p></details>{('<a href="#archive">Скачать архив</a>' if compatibility.get("archive_available") else "")}<p class="label">Версия: {esc(meta.get("report_version"))}; полнота источников: {esc(meta.get("completeness_status"))}</p></section>\n<section><h2>Резюме для принятия решения</h2><p><strong>Название закупки: {esc(model.get("procurement_title"))}</strong></p><p>Номер закупки: {esc(model.get("procurement_number"))}</p><p>Дата публикации: {esc(model.get("publication_datetime"))}</p><p>Окончание подачи заявок: {esc(model.get("application_deadline"))}</p><p>НМЦК: {esc(model.get("nmck"))} {esc(model.get("currency"))}</p><p>Заказчик: {esc(model.get("customer_name"))}</p><p>Место поставки: {esc(model.get("delivery_place"))}</p><p>Проект контракта: {esc("приложен" if model.get("contract_draft_status") == "present" else "приложен, но автоматически разобрать его не удалось" if model.get("contract_draft_status") == "parse_failed" else model.get("contract_draft_status"))}</p><p>Позиций: {esc(len(model["line_items"]))}</p><div class="decision"><strong>{esc(model.get("decision"))}</strong><ul>{bullets(summary["blockers"])}</ul><p>Следующее действие: {esc(summary["next_action"])}</p></div></section>\n<section><h2>Паспорт закупки</h2><ul><li>Категория: {esc(passport.get("category"))}</li><li>ОКПД2: {esc(passport.get("okpd2"))}</li><li>Статус объёма: {esc(model.get("procurement_volume_status"))}</li><li>Причина статуса объёма: {esc(model.get("volume_status_reason"))}</li><li>Заказчик: {esc(passport.get("customer"))}</li><li>Место поставки: {esc(passport.get("delivery_place"))}</li></ul></section>\n<section><h2>Предварительный анализ закупки</h2><ul>{bullets(compatibility.get("preliminary_overview", []))}</ul><h3>Состав поставки</h3>{compatibility_table}<h3>Ключевые условия договора</h3><ul>{bullets(compatibility.get("contract_highlights", []))}</ul></section>\n<section><h2>Состав и объём закупки</h2><div class="scroll"><table><thead><tr><th>№</th><th>Наименование / Услуга</th><th>Количество</th><th>Единица</th><th>Статус количества</th><th>Источник и evidence</th></tr></thead><tbody>{rows}</tbody></table></div></section>\n<section><h2>Извлечённые ТКП</h2><ul>{bullets(compatibility.get("quotes", []))}</ul><h3>Сравнение ТКП</h3><ul>{bullets(compatibility.get("quotes", []))}</ul></section><section><h2>Экономика</h2><ul>{bullets(compatibility.get("economics", []))}</ul></section>\n<section><h2>Недостающие данные и ограничения</h2><ul>{bullets([item["description"] + ": " + item["required_action"] for item in model["missing_data"]] + model["limitations"])}</ul></section>\n<section><h2>Риски</h2><ul>{risks}</ul></section><section><h2>Вопросы заказчику/внутренней команде</h2><ul>{bullets(model["customer_questions"])}</ul></section><section><h2>Evidence map</h2><ul>{evidence}</ul></section>\n</main></body></html>"""


def project_render_procurement_blocked_report_html(metadata: dict[str, Any]) -> str:
    procurement = metadata.get("procurement", {})
    procurement_url = str(
        metadata.get("procurement_url") or procurement.get("source_url") or ""
    ).strip()
    notice_number = str(
        metadata.get("notice_number")
        or metadata.get("procurement_id")
        or procurement.get("procurement_number")
        or "не указано"
    )
    notice_number_html = (
        f'<a class="inline-link" href="{html.escape(procurement_url)}" target="_blank" rel="noopener noreferrer">{html.escape(notice_number)}</a>'
        if procurement_url and notice_number.strip() and (notice_number != "не указано")
        else html.escape(notice_number)
    )
    import re as _re

    def _format_d(v: Any) -> str:
        t = str(v).strip() if v else ""
        m = _re.match("(\\d{4})-(\\d{2})-(\\d{2})", t)
        return f"{m.group(3)}.{m.group(2)}.{m.group(1)}" if m else t

    publication_date = _format_d(
        metadata.get("publication_date")
        or procurement.get("publication_date")
        or "не указано"
    )
    updated_date = _format_d(
        metadata.get("updated_date") or procurement.get("updated_date") or ""
    ).strip()
    publication_update = (
        f"{publication_date} / {updated_date}"
        if updated_date and updated_date != publication_date
        else publication_date
    )
    deadline_ru = _format_d(metadata.get("deadline") or procurement.get("deadline"))
    source_label = html.escape(
        procurement.get("structured_source_label")
        or metadata.get("notice_source_label")
        or "карточка ЕИС"
    )
    return f"""\n    <html lang="ru">\n      <head>\n        <meta charset="utf-8" />\n        <meta name="viewport" content="width=device-width, initial-scale=1" />\n        <title>Источник закупки: документация требуется</title>\n        <style>\n          body {{ margin:0; font-family: Arial, sans-serif; background:#001432; color:#fff; }}\n          .page {{ max-width:960px; margin:0 auto; padding:24px; }}\n          .card {{ background:rgba(255,255,255,.06); border:1px solid rgba(200,210,220,.16); border-radius:18px; padding:20px; margin-bottom:16px; }}\n          .badge {{ display:inline-block; padding:8px 12px; border-radius:999px; background:rgba(0,200,160,.15); border:1px solid rgba(120,250,230,.25); margin-right:8px; }}\n          .warning {{ color:#78FAE6; font-weight:700; }}\n          .summary-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:12px 18px; margin-top:18px; }}\n          .metric {{ padding:12px 14px; border-radius:14px; background:rgba(255,255,255,.04); border:1px solid rgba(255,255,255,.08); }}\n          .metric-label {{ display:block; font-size:12px; text-transform:uppercase; color:#78FAE6; margin-bottom:6px; }}\n          .metric-value {{ display:block; font-size:15px; line-height:1.4; }}\n          .inline-link {{ color:#9cfbee; text-decoration:none; border-bottom:1px dashed rgba(156,251,238,.5); }}\n        </style>\n      </head>\n      <body>\n        <div class="page">\n          <div class="card">\n            <span class="badge">Демо / пилотный режим</span>\n            <span class="badge">Без внешних действий</span>\n            <span class="badge">Требуется подтверждение человека</span>\n            <h1>{html.escape(str(metadata.get("tender_title") or "Закупка"))}</h1>\n            <div class="summary-grid">\n              <div class="metric"><span class="metric-label">Номер извещения</span><span class="metric-value">{notice_number_html}</span></div>\n              <div class="metric"><span class="metric-label">Категория закупки</span><span class="metric-value">{html.escape(str(metadata.get("law") or procurement.get("category") or "не указана"))}</span></div>\n              <div class="metric"><span class="metric-label">Заказчик</span><span class="metric-value">{html.escape(str(metadata.get("customer_name") or procurement.get("customer_name") or "не указан"))}</span></div>\n              <div class="metric"><span class="metric-label">НМЦК</span><span class="metric-value">{html.escape(str(procurement.get("initial_price") or "не указана"))} {html.escape(str(procurement.get("currency") or "₽"))}</span></div>\n              <div class="metric"><span class="metric-label">Дата публикации / обновления</span><span class="metric-value">{html.escape(publication_update)}</span></div>\n              <div class="metric"><span class="metric-label">Срок подачи</span><span class="metric-value">{html.escape(deadline_ru or "не указан")}</span></div>\n              <div class="metric"><span class="metric-label">Источник сведений</span><span class="metric-value">{source_label}</span></div>\n              <div class="metric"><span class="metric-label">Статус подключения</span><span class="metric-value">Документы получены через ЕИС</span></div>\n              <div class="metric"><span class="metric-label">Скачано документов</span><span class="metric-value">{html.escape(str(metadata.get("downloaded_files_count", len(metadata.get("files", [])))))}</span></div>\n            </div>\n            <p class="warning">Документация не получена. Анализ невозможен до ручной загрузки файлов.</p>\n          </div>\n        </div>\n      </body>\n    </html>\n    """
