from __future__ import annotations

import json


def render_tender_operator_console_html(selected_run_id: str | None = None) -> str:
    initial_run_id = json.dumps(selected_run_id)
    return f"""
    <html lang="ru">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Тендерный агент: демонстрация работы</title>
        <style>
          :root {{
            --mint-primary: #00c8a0;
            --mint-light: #78fae6;
            --deep-navy: #001432;
            --graphite: #283246;
            --soft-gray: #c8d2dc;
            --white: #ffffff;
            --line: rgba(200, 210, 220, 0.16);
            --panel: rgba(255, 255, 255, 0.05);
            --panel-strong: rgba(255, 255, 255, 0.08);
            --warning: #ffb454;
            --danger: #ff7f87;
            --review: #8bd8ff;
          }}
          * {{ box-sizing: border-box; }}
          body {{
            margin: 0;
            font-family: "PT Sans", Arial, sans-serif;
            background:
              radial-gradient(circle at top left, rgba(0, 200, 160, 0.14), transparent 28%),
              linear-gradient(180deg, #03142f 0%, #001432 52%, #071d38 100%);
            color: var(--white);
          }}
          .page {{
            width: min(1440px, calc(100vw - 32px));
            margin: 0 auto;
            padding: 20px 0 48px;
          }}
          .shell {{
            border-radius: 28px;
            border: 1px solid var(--line);
            background: linear-gradient(180deg, rgba(255,255,255,0.08), rgba(255,255,255,0.03));
            overflow: hidden;
            box-shadow: 0 30px 80px rgba(0, 20, 50, 0.28);
          }}
          .header {{
            padding: 28px 28px 20px;
            border-bottom: 1px solid var(--line);
            display: flex;
            justify-content: space-between;
            gap: 24px;
            align-items: flex-start;
          }}
          .brand-lockup {{
            display: flex;
            align-items: center;
            gap: 14px;
            margin-bottom: 12px;
          }}
          .brand-lockup img {{
            width: 168px;
            height: auto;
            display: block;
            filter: drop-shadow(0 10px 24px rgba(0, 200, 160, 0.18));
          }}
          .eyebrow {{
            color: var(--mint-light);
            font-size: 12px;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            margin-bottom: 10px;
          }}
          h1 {{
            margin: 0 0 10px;
            font-size: clamp(32px, 4vw, 52px);
            line-height: 0.95;
          }}
          .subtitle {{
            margin: 0;
            max-width: 720px;
            color: rgba(255,255,255,0.78);
            font-size: 18px;
            line-height: 1.45;
          }}
          .header-actions {{
            margin-top: 16px;
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
          }}
          .badge-row {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            justify-content: flex-end;
          }}
          .badge {{
            padding: 10px 14px;
            border-radius: 999px;
            background: rgba(0, 200, 160, 0.13);
            border: 1px solid rgba(120, 250, 230, 0.25);
            color: var(--mint-light);
            font-size: 12px;
            white-space: nowrap;
          }}
          .content {{
            padding: 18px;
            display: grid;
            gap: 18px;
          }}
          .tabs {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
          }}
          .tab-button, .button, .link-button {{
            appearance: none;
            border: 1px solid rgba(255,255,255,0.14);
            border-radius: 999px;
            min-height: 44px;
            padding: 0 18px;
            background: rgba(255,255,255,0.05);
            color: var(--white);
            cursor: pointer;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
          }}
          .tab-button.active, .button.primary {{
            background: rgba(0, 200, 160, 0.16);
            border-color: rgba(120, 250, 230, 0.32);
          }}
          .layout {{
            display: grid;
            grid-template-columns: minmax(320px, 0.9fr) minmax(0, 1.35fr);
            gap: 18px;
          }}
          .stack {{
            display: grid;
            gap: 18px;
            align-content: start;
          }}
          .card {{
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 22px;
            padding: 20px;
          }}
          .card h2, .card h3 {{
            margin: 0 0 14px;
          }}
          .card p {{
            margin: 0;
            color: rgba(255,255,255,0.78);
            line-height: 1.5;
          }}
          .grid-2 {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 12px;
          }}
          .grid-3 {{
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 8px;
          }}
          .metric {{
            padding: 14px;
            border-radius: 16px;
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.06);
          }}
          .metric-label {{
            display: block;
            color: rgba(255,255,255,0.58);
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 6px;
          }}
          .metric-value {{
            display: block;
            font-size: 16px;
            line-height: 1.4;
          }}
          .list, .steps-list {{
            list-style: none;
            margin: 0;
            padding: 0;
            display: grid;
            gap: 10px;
          }}
          .list-item {{
            padding: 12px 14px;
            border-radius: 16px;
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.06);
          }}
          .run-item {{
            padding: 14px;
            border-radius: 18px;
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.06);
            cursor: pointer;
          }}
          .run-item.active {{
            border-color: rgba(120, 250, 230, 0.3);
            background: rgba(0, 200, 160, 0.11);
          }}
          .run-meta {{
            color: rgba(255,255,255,0.62);
            font-size: 13px;
            margin-top: 4px;
          }}
          .event-list {{
            list-style: none;
            margin: 0;
            padding: 0;
            display: grid;
            gap: 10px;
          }}
          .event-item {{
            padding: 12px 14px;
            border-radius: 14px;
            background: rgba(255,255,255,0.035);
            border: 1px solid rgba(255,255,255,0.06);
          }}
          .event-head {{
            display: flex;
            justify-content: space-between;
            gap: 12px;
            color: rgba(255,255,255,0.58);
            font-size: 12px;
            margin-bottom: 6px;
          }}
          .event-severity {{
            color: var(--mint-light);
            text-transform: uppercase;
            letter-spacing: 0.08em;
          }}
          .event-severity.warning {{ color: var(--warning); }}
          .event-severity.error {{ color: var(--danger); }}
          .step-card {{
            padding: 16px;
            border-radius: 18px;
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.06);
          }}
          .step-top {{
            display: flex;
            justify-content: space-between;
            gap: 12px;
            align-items: center;
            margin-bottom: 10px;
          }}
          .status-chip {{
            padding: 7px 10px;
            border-radius: 999px;
            background: rgba(255,255,255,0.06);
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.06em;
          }}
          .status-done {{ color: var(--mint-light); }}
          .status-partial {{ color: var(--review); }}
          .status-needs_review {{ color: var(--review); }}
          .status-warning {{ color: var(--warning); }}
          .status-blocked {{ color: var(--danger); }}
          .status-pending {{ color: var(--soft-gray); }}
          .status-running {{ color: var(--mint-primary); }}
          .section-title {{
            color: var(--mint-light);
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 10px;
          }}
          .split {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 14px;
          }}
          .trace {{
            padding: 16px;
            border-radius: 16px;
            background: rgba(0, 200, 160, 0.08);
            border: 1px solid rgba(120, 250, 230, 0.18);
            color: rgba(255,255,255,0.88);
            font-size: 14px;
            line-height: 1.6;
          }}
          .safety {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
          }}
          .safety span {{
            padding: 10px 12px;
            border-radius: 999px;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.08);
            color: rgba(255,255,255,0.78);
            font-size: 13px;
          }}
          form {{
            display: grid;
            gap: 12px;
          }}
          label {{
            display: grid;
            gap: 8px;
            font-size: 14px;
            color: rgba(255,255,255,0.86);
          }}
          .checkbox {{
            display: flex;
            align-items: center;
            gap: 10px;
          }}
          .checkbox input {{
            width: 18px;
            min-height: 18px;
            height: 18px;
            margin: 0;
            padding: 0;
          }}
          .checkbox span {{
            color: rgba(255,255,255,0.86);
          }}
          input, select, textarea {{
            width: 100%;
            min-height: 46px;
            border-radius: 14px;
            border: 1px solid rgba(255,255,255,0.12);
            background: rgba(255,255,255,0.05);
            color: var(--white);
            padding: 0 14px;
            font: inherit;
          }}
          textarea {{
            min-height: 96px;
            padding-top: 12px;
            resize: vertical;
          }}
          input[type="file"] {{
            padding: 10px 14px;
          }}
          .form-actions {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
          }}
          .note {{
            font-size: 13px;
            color: rgba(255,255,255,0.62);
            line-height: 1.5;
          }}
          table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
          }}
          th, td {{
            text-align: left;
            padding: 9px 8px;
            border-bottom: 1px solid rgba(255,255,255,0.08);
            vertical-align: top;
          }}
          th {{
            color: var(--mint-light);
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.06em;
          }}
          .flash {{
            padding: 12px 14px;
            border-radius: 14px;
            border: 1px solid rgba(120,250,230,0.22);
            background: rgba(0,200,160,0.12);
            color: rgba(255,255,255,0.9);
          }}
          .flash.error {{
            background: rgba(255, 127, 135, 0.12);
            border-color: rgba(255, 127, 135, 0.28);
          }}
          .hidden {{
            display: none !important;
          }}
          .empty {{
            padding: 28px 16px;
            border-radius: 18px;
            border: 1px dashed rgba(255,255,255,0.16);
            color: rgba(255,255,255,0.66);
            text-align: center;
          }}
          a.inline-link {{
            color: var(--mint-light);
          }}
          @media (max-width: 1080px) {{
            .layout, .split {{
              grid-template-columns: 1fr;
            }}
          }}
          @media (max-width: 700px) {{
            .page {{
              width: min(100vw - 20px, 1440px);
              padding-top: 10px;
            }}
            .header {{
              flex-direction: column;
              padding: 22px 18px 18px;
            }}
            .content {{
              padding: 14px;
            }}
            .grid-2 {{
              grid-template-columns: 1fr;
            }}
          }}
        </style>
      </head>
      <body>
        <div class="page">
          <div class="shell">
            <header class="header">
              <div>
                <div class="brand-lockup">
                  <img src="/demo/tender-agent/assets/arvectum-logo-block.svg" alt="Arvectum" />
                  <div class="eyebrow">Демонстрация тендерного агента</div>
                </div>
                <h1>Тендерный агент</h1>
                <p class="subtitle">Как ИИ-агент разбирает закупку, готовит RFQ, показывает риски и оставляет критичные действия под контролем человека.</p>
                <div class="header-actions">
                  <a class="link-button" href="/pilot/tender-agent">Пошаговый мастер</a>
                </div>
              </div>
              <div class="badge-row">
                <span class="badge">Демо-режим / подтверждение человеком</span>
                <span class="badge">Пилотный контур</span>
                <span class="badge">Без внешних действий</span>
              </div>
            </header>

            <div class="content">
              <div class="tabs">
                <button class="tab-button active" data-tab="search" type="button">Найти закупку</button>
                <button class="tab-button" data-tab="docs" type="button">Получить документацию по номеру</button>
                <button class="tab-button" data-tab="upload" type="button">Загрузить документы</button>
                <button class="tab-button" data-tab="dataset" type="button">Демо-набор</button>
                <button class="tab-button" data-tab="profile" type="button">Профиль поставщика</button>
                <button class="tab-button" data-tab="analysis" type="button">Анализ закупки</button>
              </div>

              <section id="tab-search">
                <div class="layout">
                  <aside class="stack">
                    <div class="card">
                      <h2>Найти закупку</h2>
                      <p>Первый шаг controlled demo-сценария: найти закупку, выбрать карточку, безопасно получить публичную документацию или честно перейти к ручной загрузке.</p>
                      <div id="procurement-flash" class="hidden"></div>
                      <form id="procurement-search-form">
                        <label>
                          Поисковый запрос
                          <input name="query" value="электротехническое оборудование" />
                        </label>
                        <div class="split">
                          <label>
                            Источник
                            <select name="source" id="procurement-source-select">
                              <option value="demo_local">demo_local</option>
                              <option value="public_eis_html_44fz">Публичный поиск ЕИС 44-ФЗ</option>
                              <option value="public_eis_html_223fz">Публичный поиск ЕИС 223-ФЗ (fallback)</option>
                            </select>
                          </label>
                          <label>
                            Макс. результатов
                            <input name="max_results" type="number" min="1" max="50" value="10" />
                          </label>
                        </div>
                        <div class="split">
                          <label>
                            Закон
                            <select name="law">
                              <option value="">Все</option>
                              <option value="44-ФЗ">44-ФЗ</option>
                              <option value="223-ФЗ">223-ФЗ</option>
                            </select>
                          </label>
                          <label>
                            Статус
                            <select name="status_filter">
                              <option value="Подача заявок" selected>Действующие — подача заявок</option>
                              <option value="">Все статусы</option>
                              <option value="Работа комиссии">Работа комиссии</option>
                              <option value="Закупка завершена">Завершённые</option>
                              <option value="Закупка отменена">Отменённые</option>
                            </select>
                          </label>
                        </div>
                        <div class="split">
                          <label>
                            ИНН заказчика
                            <input name="customer_inn" placeholder="Необязательно" />
                          </label>
                          <div class="note" style="align-self:end">Для публичного поиска по умолчанию показываются закупки на стадии подачи заявок.</div>
                        </div>
                        <div class="split">
                          <label>
                            Заказчик
                            <input name="customer_name" placeholder="Необязательно" />
                          </label>
                          <label>
                            Регион
                            <input name="region" placeholder="Необязательно" />
                          </label>
                        </div>
                        <div class="split">
                          <label>
                            Дата публикации с
                            <input name="date_from" type="date" />
                          </label>
                          <label>
                            Дата публикации по
                            <input name="date_to" type="date" />
                          </label>
                        </div>
                        <div class="split">
                          <label>
                            Цена от
                            <input name="price_from" type="number" min="0" step="1000" placeholder="Необязательно" />
                          </label>
                          <label>
                            Цена до
                            <input name="price_to" type="number" min="0" step="1000" placeholder="Необязательно" />
                          </label>
                        </div>
                        <div class="form-actions">
                          <button class="button primary" type="submit">Найти закупки</button>
                        </div>
                      </form>
                    </div>
                    <div class="card">
                      <h2>Диагностика ЕИС</h2>
                      <div id="procurement-source-diagnostics" class="list">
                        <div class="empty">Диагностика источника загрузится автоматически.</div>
                      </div>
                    </div>
                    <div class="card">
                      <h2>Безопасный режим</h2>
                      <div class="safety">
                        <span>Только чтение (поиск)</span>
                        <span>Без логина и паролей</span>
                        <span>Без обхода captcha</span>
                        <span>Без подачи на площадку</span>
                        <span>Без писем поставщикам</span>
                        <span>Требуется подтверждение человека</span>
                      </div>
                      <p style="margin-top:14px">Поиск работает в безопасном read-only режиме. Система не входит в личный кабинет, не обходит captcha, не подаёт заявку. Система только получает публичную документацию и готовит анализ для человека.</p>
                    </div>
                  </aside>

                  <main class="stack">
                    <div class="card" id="procurement-results-card">
                      <h2>Результаты поиска</h2>
                      <div id="procurement-results" class="list">
                        <div class="empty">Введите запрос и нажмите «Найти закупки», чтобы открыть первый шаг тендерного pipeline.</div>
                      </div>
                    </div>
                    <div class="card">
                      <h2>Как это работает</h2>
                      <p>Поиск закупки и получение документации объединены в один сценарий: найдите закупку по ключевому слову через публичный поиск ЕИС 44-ФЗ, выберите карточку, и система сама получит документацию через getDocsIP, распакует архив, создаст run и запустит анализ.</p>
                      <p style="margin-top:8px">Если HTML поиска не парсится (captcha, JS-heavy или изменилась структура), интерфейс честно показывает кнопку «Откройте поиск в ЕИС» и позволяет вставить номер закупки вручную.</p>
                      <div class="trace" style="margin-top:14px">Если автоматическое получение документации недоступно, интерфейс не притворяется автономным: создаётся run со статусом «нужна загрузка документов», а оператор вручную добавляет пакет и только потом запускает анализ.</div>
                    </div>
                  </main>
                </div>
              </section>

              <section id="tab-docs" class="hidden">
                <div class="layout">
                  <aside class="stack">
                    <div class="card">
                      <h2>Получить документацию по номеру</h2>
                      <p>Токен выпущен как физическое лицо. Используется сервис getDocsIP для read-only получения публичной документации по номеру закупки.</p>
                      <div id="eis-docs-flash" class="hidden"></div>
                      <form id="eis-docs-form">
                        <label>
                          Реестровый номер / номер извещения
                          <input name="reestr_number" required placeholder="Например: 0888200000224000038" />
                        </label>
                        <div class="split">
                          <label>
                            Закон
                            <select name="law">
                              <option value="44fz">44-ФЗ</option>
                            </select>
                          </label>
                          <label>
                            Подсистема
                            <input name="subsystem_type" value="PRIZ" />
                          </label>
                        </div>
                        <label>
                          SOAP-метод
                          <input name="method" value="getDocsByReestrNumber" readonly />
                        </label>
                        <label class="checkbox">
                          <input name="download_archive" type="checkbox" checked />
                          <span>Скачать архив</span>
                        </label>
                        <label class="checkbox">
                          <input name="analyze_after_download" type="checkbox" />
                          <span>Запустить анализ после скачивания</span>
                        </label>
                        <div class="form-actions">
                          <button class="button primary" type="submit">Получить документацию из ЕИС</button>
                        </div>
                      </form>
                    </div>
                    <div class="card">
                      <h2>Диагностика getDocsIP</h2>
                      <div id="eis-docs-diagnostics" class="list">
                        <div class="empty">Диагностика getDocsIP загрузится автоматически.</div>
                      </div>
                    </div>
                    <div class="card">
                      <h2>Ограничения</h2>
                      <div class="safety">
                        <span>Токен физлица</span>
                        <span>Только чтение getDocsIP</span>
                        <span>Без личного кабинета</span>
                        <span>Без ЭЦП</span>
                        <span>Без подачи заявки</span>
                        <span>Без писем поставщикам</span>
                      </div>
                      <p style="margin-top:14px">Токен выпущен как физическое лицо. Используется сервис getDocsIP для read-only получения публичной документации по номеру закупки. Система не входит в личный кабинет, не подаёт заявки, не использует ЭЦП и не отправляет письма.</p>
                    </div>
                  </aside>
                  <main class="stack">
                    <div class="card">
                      <h2>Сценарий работы</h2>
                      <div class="trace">1. Найдите закупку через `demo_local` или публичный HTML fallback. 2. Скопируйте реестровый номер. 3. Запросите архив документации через getDocsIP. 4. Если archiveUrl получен, архив скачивается и safely обрабатывается локально. 5. Если archiveUrl не получен, интерфейс честно переводит вас в ручной upload fallback.</div>
                    </div>
                    <div class="card" id="eis-docs-result-card">
                      <h2>Результат получения документации</h2>
                      <div id="eis-docs-result" class="empty">После запроса сюда попадут статус SOAP, статус архива, количество распакованных файлов и ссылки на run/report.</div>
                    </div>
                  </main>
                </div>
              </section>

              <section id="tab-upload" class="hidden">
                <div class="layout">
                  <aside class="stack">
                    <div class="card">
                      <h2>Загрузка и анализ</h2>
                      <p>Локальная загрузка документов закупки, безопасное сохранение в рабочую директорию и контролируемый pipeline анализа без внешних интеграций.</p>
                      <div id="upload-flash" class="hidden"></div>
                      <form id="upload-form">
                        <label>
                          Название закупки
                          <input name="tender_title" required value="Поставка электротехнического оборудования" />
                        </label>
                        <label>
                          Категория
                          <select name="tender_category">
                            <option>Электротехническое оборудование</option>
                            <option>Кабельная продукция</option>
                            <option>Шкафы управления</option>
                            <option>Промышленная автоматизация</option>
                          </select>
                        </label>
                        <label>
                          Заказчик
                          <input name="customer_name" value="Промышленный заказчик" />
                        </label>
                        <label>
                          Комментарий оператора
                          <textarea name="notes" placeholder="Например: демонстрационный прогон для встречи с заказчиком, без ТКП"></textarea>
                        </label>
                        <div class="split">
                          <label>
                            Целевая маржа, %
                            <input name="target_margin_percent" type="number" step="0.1" min="0" max="95" value="15" />
                          </label>
                          <label>
                            Резерв логистики, %
                            <input name="logistics_reserve_percent" type="number" step="0.1" min="0" max="95" value="3" />
                          </label>
                        </div>
                        <div class="split">
                          <label>
                            Резерв риска, %
                            <input name="risk_reserve_percent" type="number" step="0.1" min="0" max="95" value="5" />
                          </label>
                          <label>
                            Отсрочка оплаты, дней
                            <input name="payment_delay_days" type="number" step="1" min="0" max="365" value="45" />
                          </label>
                        </div>
                        <label>
                          Файлы закупки
                          <input name="files" type="file" multiple required />
                        </label>
                        <div class="note">Поддержаны: PDF, DOCX, XLSX, XLS, TXT, CSV, ZIP. В демо-режиме действуют безопасные лимиты на размер и количество файлов.</div>
                        <div class="form-actions">
                          <button class="button primary" type="submit">Создать демонстрационный прогон</button>
                        </div>
                      </form>
                    </div>

                    <div class="card">
                      <h2>Последние прогоны</h2>
                      <div id="runs-list" class="list">
                        <div class="empty">Пока нет загруженных прогонов.</div>
                      </div>
                    </div>
                  </aside>

                  <main class="stack">
                    <div class="card" id="selected-run-card">
                      <div class="empty">Создайте демонстрационный прогон или выберите существующий справа, чтобы увидеть детали анализа.</div>
                    </div>
                    <div class="card" id="selected-run-steps">
                      <div class="empty">Pipeline загруженного прогона появится после запуска анализа.</div>
                    </div>
                    <div class="card" id="selected-run-summary">
                      <div class="empty">Финальная рекомендация для загруженного прогона появится здесь.</div>
                    </div>
                  </main>
                </div>
              </section>

              <section id="tab-dataset" class="hidden">
                <div class="layout">
                  <aside class="stack">
                    <div class="card" id="dataset-tender-card">
                      <div class="empty">Загрузка демонстрационного набора…</div>
                    </div>
                    <div class="card">
                      <h2>Ограничения демо</h2>
                      <div class="safety">
                        <span>Только синтетические demo-data</span>
                        <span>Без подачи на площадку</span>
                        <span>Без отправки писем</span>
                        <span>Без ЭЦП</span>
                        <span>Требуется подтверждение человека</span>
                      </div>
                    </div>
                  </aside>

                  <main class="stack">
                    <div class="card">
                      <div class="step-top">
                        <div>
                          <h2>Pipeline агента</h2>
                          <p>Документы → Требования → Вопросы → RFQ → ТКП → Экономика → Риски → Решение</p>
                        </div>
                        <button class="button primary" id="replay-dataset" type="button">Запустить демонстрационный прогон</button>
                      </div>
                      <div class="steps-list" id="dataset-steps"></div>
                    </div>
                    <div class="card" id="dataset-summary">
                      <div class="empty">Собираем финальную рекомендацию…</div>
                    </div>
                  </main>
                </div>
              </section>

              <section id="tab-profile" class="hidden">
                <div class="layout">
                  <aside class="stack">
                    <div class="card">
                      <h2>Профиль поставщика</h2>
                      <p>Настройки профиля используются для оценки релевантности закупок. Все настройки хранятся в памяти сессии и сбрасываются при перезагрузке страницы.</p>
                      <div id="supplier-profile-flash" class="hidden"></div>
                      <div class="form-actions">
                        <button class="button primary" id="reset-supplier-profile" type="button">Сбросить профиль на демо-настройки</button>
                      </div>
                      <div class="note" style="margin-top:12px">Профиль поставщика влияет на скоринг релевантности в результатах публичного поиска 44-ФЗ и на глубинный анализ документов.</div>
                    </div>
                  </aside>
                  <main class="stack">
                    <div class="card" id="supplier-profile-display">
                      <div class="empty">Загрузка профиля поставщика…</div>
                    </div>
                  </main>
                </div>
              </section>

              <section id="tab-analysis" class="hidden">
                <div class="layout">
                  <aside class="stack">
                    <div class="card">
                      <h2>Анализ закупки через RAG</h2>
                      <p>Полный RAG-анализ закупки: поиск по проиндексированным документам и генерация структурированного отчета по 10 разделам (извещение → предмет → требования → заявка → оценка → контракт → документы → ограничения → сроки → список документов).</p>
                      <div id="analysis-flash" class="hidden"></div>
                      <form id="analysis-form">
                        <label>
                          Реестровый номер
                          <input name="registry_number" required placeholder="Например: 0323100010326000013" />
                        </label>
                        <label>
                          Контур выполнения
                          <select name="runtime_preset" id="analysis-runtime-preset">
                            <option value="mac_mini_local" selected>Mac mini: локальная LLM + Qwen3 embeddings</option>
                            <option value="local_hash_smoke">Быстрый тест без LLM / local hash</option>
                          </select>
                        </label>
                        <label>
                          Режим анализа
                          <select name="analysis_mode">
                            <option value="fast" selected>Быстрый</option>
                            <option value="balanced">Сбалансированный</option>
                            <option value="detailed">Подробный</option>
                          </select>
                        </label>
                        <label class="checkbox">
                          <input name="use_llm" type="checkbox" checked />
                          <span>Использовать локальную LLM (может работать долго)</span>
                        </label>
                        <label class="checkbox">
                          <input name="save_report" type="checkbox" checked />
                          <span>Сохранить отчёт на диск</span>
                        </label>
                        <div class="form-actions" style="display:flex;flex-wrap:wrap;gap:8px;">
                          <button type="button" class="button" id="check-readiness-btn">Проверить готовность</button>
                          <button type="button" class="button" id="prepare-tender-btn" disabled>Подготовить закупку к анализу</button>
                          <button type="submit" class="button primary" id="run-analysis-btn">Проанализировать закупку</button>
                        </div>
                      </form>
                    </div>
                    <div class="card" id="analysis-runtime-card">
                      <h2>Параметры анализа</h2>
                      <div id="analysis-runtime-summary" class="list">
                        <div class="empty">Выберите контур, чтобы увидеть runtime-параметры.</div>
                      </div>
                    </div>
                    <div class="card" id="analysis-preparation-card">
                      <h2>Состояние готовности</h2>
                      <div id="analysis-readiness-status" class="empty">Нажмите «Проверить готовность».</div>
                      <div id="analysis-preparation-steps" class="hidden" style="margin-top:12px;"></div>
                    </div>
                    <div class="card" id="analysis-job-card">
                      <h2>Статус фоновой задачи</h2>
                      <div id="analysis-job-status" class="empty">Запустите подготовку или анализ, чтобы увидеть progress и статус.</div>
                    </div>
                  </aside>
                  <main class="stack">
                    <div class="card" id="analysis-result-card">
                      <h2>Результат анализа</h2>
                      <div id="analysis-result" class="empty">Введите реестровый номер и нажмите «Проанализировать закупку».</div>
                    </div>
                    <div class="card" id="analysis-report-card" class="hidden">
                      <h2>Отчёт</h2>
                      <div id="analysis-report-content"></div>
                    </div>
                    <div class="card">
                      <h2>История анализов</h2>
                      <div class="form-actions" style="margin-bottom:10px;display:flex;gap:8px;flex-wrap:wrap;">
                        <button type="button" class="button" id="history-refresh-btn">Обновить историю</button>
                      </div>
                      <div id="history-list" class="empty">Пока нет сохранённых анализов.</div>
                      <div id="history-report-container" class="hidden" style="margin-top:12px;">
                        <h3>Отчёт из истории</h3>
                        <div id="history-report-content"></div>
                      </div>
                    </div>
                  </main>
                </div>
              </section>
            </div>
          </div>
        </div>

        <script>
          const state = {{
            procurementSources: [],
            procurementResults: [],
            publicSearchCards: [],
            publicSearchCursor: null,
            publicSearchParams: null,
            publicSearchSeen: [],
            datasetRun: null,
            datasetReplayActive: false,
            datasetDisplayStatuses: new Map(),
            uploadedRuns: [],
            selectedRunId: {initial_run_id},
            eventsPollTimer: null,
            analysisJobPollTimer: null,
            activeAnalysisJobId: null,
            activeAnalysisJobStartedAt: null,
            activeAnalysisRuntime: null,
          }};

          const ANALYSIS_PRESETS = {{
            mac_mini_local: {{
              key: 'mac_mini_local',
              name: 'Mac mini: локальная LLM + Qwen3 embeddings',
              contour_label: 'Mac mini local',
              provider: 'llama_cpp',
              model: 'Qwen3-Embedding-4B',
              base_url: 'http://127.0.0.1:8090/v1',
              use_llm: true,
              llm_base_url: 'http://127.0.0.1:8088/v1',
              llm_model: '/Users/master/models/Qwen2.5-14B-Instruct-Q4_K_M.gguf',
              llm_model_label: 'Qwen2.5-14B local',
              analysis_mode: 'fast',
              limit: 8,
              save_report: true,
            }},
            local_hash_smoke: {{
              key: 'local_hash_smoke',
              name: 'Быстрый тест без LLM / local hash',
              contour_label: 'Smoke local hash',
              provider: 'local_hash',
              model: 'local-hash-v1',
              base_url: null,
              use_llm: false,
              llm_base_url: null,
              llm_model: null,
              llm_model_label: 'LLM отключена',
              analysis_mode: 'fast',
              limit: 3,
              save_report: true,
            }},
          }};

          const STEP_STATUS_LABELS = {{
            pending: 'ожидает',
            running: 'в работе',
            done: 'выполнено',
            partial: 'частично',
            needs_review: 'нужна проверка',
            warning: 'риск',
            blocked: 'заблокировано',
          }};

          const RUN_STATUS_LABELS = {{
            uploaded: 'загружено',
            docs_required: 'нужна загрузка документов',
            ready_to_analyze: 'готово к анализу',
            analyzing: 'анализируется',
            completed: 'завершено',
            completed_with_warnings: 'завершено с ограничениями',
            failed: 'ошибка',
            needs_review: 'нужна проверка',
          }};

          const ANALYSIS_MODE_LABELS = {{
            not_started: 'не запущен',
            analyzing: 'анализ выполняется',
            controlled_runner_adapter: 'контролируемый адаптер раннера',
            fallback_deterministic_adapter: 'детерминированный fallback-адаптер',
          }};

          const ATTACHMENTS_STATUS_LABELS = {{
            downloadable: 'можно скачать',
            downloaded: 'документация получена',
            manual_upload_required: 'нужна ручная загрузка',
            manual_upload_received: 'документы загружены вручную',
            unavailable_in_demo: 'недоступно в демо-режиме',
            source_requires_authorization: 'источник требует авторизации или интерактивного доступа',
          }};

          const statusClass = (status) => `status-${{status || 'pending'}}`;

          function statusLabel(status) {{
            return STEP_STATUS_LABELS[status] || RUN_STATUS_LABELS[status] || status || 'ожидает';
          }}

          function analysisModeLabel(mode) {{
            return ANALYSIS_MODE_LABELS[mode] || mode || 'не определено';
          }}

          function getAnalysisPreset(presetKey) {{
            return ANALYSIS_PRESETS[presetKey] || ANALYSIS_PRESETS.mac_mini_local;
          }}

          function attachmentsStatusLabel(status) {{
            return ATTACHMENTS_STATUS_LABELS[status] || status || 'не определено';
          }}

          function booleanLabel(value) {{
            return value ? 'да' : 'нет';
          }}

          function displayValue(value, fallback = 'не определено') {{
            if (value === null || value === undefined || value === '') {{
              return fallback;
            }}
            if (value === true) {{
              return 'да';
            }}
            if (value === false) {{
              return 'нет';
            }}
            if (value === 'unknown') {{
              return fallback;
            }}
            return String(value);
          }}

          function escapeHtml(value) {{
            return String(value ?? '')
              .replaceAll('&', '&amp;')
              .replaceAll('<', '&lt;')
              .replaceAll('>', '&gt;')
              .replaceAll('"', '&quot;')
              .replaceAll("'", '&#39;');
          }}

          function formatMoney(value, currency = '') {{
            if (value === null || value === undefined || value === '' || Number.isNaN(Number(value))) {{
              return 'не определено';
            }}
            const number = Number(value);
            const suffix = currency ? ` ${{currency}}` : '';
            return `${{number.toLocaleString('ru-RU', {{ maximumFractionDigits: 2 }})}}${{suffix}}`;
          }}

          function relevanceBadge(rel) {{
            const score = rel.score || 0;
            const status = rel.status || 'not_recommended';
            let cls = 'status-chip status-warning';
            let label = `${{Math.round(score)}}% · не рекомендовано`;
            if (status === 'high') {{ cls = 'status-chip status-done'; label = `${{Math.round(score)}}% · высокая релевантность`; }}
            else if (status === 'medium') {{ cls = 'status-chip status-review'; label = `${{Math.round(score)}}% · средняя релевантность`; }}
            else if (status === 'low') {{ cls = 'status-chip status-warning'; label = `${{Math.round(score)}}% · низкая релевантность`; }}
            return `<span class="${{cls}}">${{label}}</span>`;
          }}

          function relevanceBreakdownHtml(rel) {{
            const breakdown = rel.breakdown || {{}};
            const reasons = rel.reasons || [];
            const entries = Object.entries(breakdown);
            const items = [];
            for (let i = 0; i < entries.length; i++) {{
              const key = entries[i][0];
              const val = entries[i][1];
              let displayVal = String(val);
              if (typeof val === 'number' && val > 0) displayVal = '+' + val;
              items.push('<div class="metric"><span class="metric-label">' + escapeHtml(key) + '</span><span class="metric-value" style="font-size:13px">' + displayVal + '</span></div>');
            }}
            const itemsHtml = items.join('');
            let reasonsHtml = '';
            if (reasons.length) {{
              const reasonItems = reasons.map(function(r) {{ return '<div>\\u00B7 ' + escapeHtml(r) + '</div>'; }}).join('');
              reasonsHtml = '<div style="margin-top:6px;font-size:12px;color:var(--soft-gray)">' + reasonItems + '</div>';
            }}
            return '<div style="margin-top:10px;padding:12px;background:var(--panel);border-radius:12px">' +
              '<div class="section-title" style="margin-bottom:6px">Оценка релевантности</div>' +
              '<div class="grid-3" style="gap:4px">' + itemsHtml + '</div>' +
              reasonsHtml +
              '</div>';
          }}

          function queryMatchBadge(rel) {{
            const score = Number(rel?.score || 0);
            const status = rel?.status || 'unknown';
            let cls = 'status-chip status-warning';
            if (status === 'high') cls = 'status-chip status-done';
            else if (status === 'medium') cls = 'status-chip status-review';
            return `<span class="${{cls}}">${{Math.round(score)}}% · совпадение с запросом</span>`;
          }}

          function queryMatchHtml(rel) {{
            if (!rel) return '';
            const reasons = rel.reasons || [];
            return `
              <div style="margin-top:10px;padding:12px;background:var(--panel);border-radius:12px">
                <div class="section-title" style="margin-bottom:6px">Совпадение с запросом</div>
                <div class="run-meta">${{Math.round(Number(rel.score || 0))}}% · терминов совпало: ${{rel.matched_terms || 0}} из ${{rel.total_terms || 0}}</div>
                ${{reasons.length ? `<div style="margin-top:6px;font-size:12px;color:var(--soft-gray)">${{reasons.map((reason) => `<div>· ${{escapeHtml(reason)}}</div>`).join('')}}</div>` : ''}}
              </div>`;
          }}

          function renderQuoteSection(run) {{
            const comparison = run.quote_comparison;
            if (!comparison) {{
              return `<div class="empty">Нормализованные ТКП появятся после завершения анализа.</div>`;
            }}
            const suppliers = comparison.suppliers || [];
            const items = comparison.items || [];
            const manualChecks = [
              ...(comparison.manual_checks || []).map((item) => item.message),
              ...(comparison.limitations || []),
            ];
            return `
              <div class="card" style="padding:16px">
                <div class="section-title">Извлечённые ТКП</div>
                ${{
                  suppliers.length
                    ? `<div class="grid-2">${{suppliers.map((supplier) => `
                      <div class="metric">
                        <span class="metric-label">${{escapeHtml(supplier.supplier_name)}}</span>
                        <span class="metric-value">${{formatMoney(supplier.total_amount, supplier.currency || '')}}</span>
                        <div class="run-meta">${{escapeHtml(supplier.source_file)}} · позиций=${{supplier.items_count}} · уверенность=${{supplier.price_confidence}}</div>
                      </div>
                    `).join('')}}</div>`
                    : `<div class="empty">ТКП не распознаны как структурированные таблицы.</div>`
                }}
              </div>
              <div class="card" style="padding:16px">
                <div class="section-title">Сравнение предложений</div>
                ${{
                  items.length
                    ? `<div style="overflow:auto"><table>
                        <thead><tr><th>Позиция</th><th>Лучшая цена</th><th>Разброс %</th><th>Проверка</th></tr></thead>
                        <tbody>${{items.slice(0, 18).map((item) => `
                          <tr>
                            <td>${{escapeHtml(item.normalized_name)}}</td>
                            <td>${{escapeHtml(displayValue(item.best_price_supplier))}}</td>
                            <td>${{escapeHtml(displayValue(item.price_spread_percent))}}</td>
                            <td>${{item.needs_review ? 'нужна проверка' : 'без замечаний'}}</td>
                          </tr>
                        `).join('')}}</tbody>
                      </table></div>`
                    : `<div class="empty">Сравнение позиций пока недоступно.</div>`
                }}
              </div>
              <div class="card" style="padding:16px">
                <div class="section-title">Что проверить вручную</div>
                <ul>${{manualChecks.length ? manualChecks.map((item) => `<li>${{escapeHtml(item)}}</li>`).join('') : '<li>Дополнительных замечаний нет.</li>'}}</ul>
              </div>
            `;
          }}

          function renderEconomicsSection(run) {{
            const economics = run.economics_summary;
            if (!economics) {{
              return `<div class="empty">Экономика появится после завершения анализа.</div>`;
            }}
            const manualChecks = [
              ...(economics.manual_checks || []).map((item) => item.message),
              ...(economics.limitations || []),
            ];
            return `
              <div class="card" style="padding:16px">
                <div class="section-title">Экономика</div>
                <div class="grid-2">
                  <div class="metric"><span class="metric-label">Минимальная закупочная стоимость</span><span class="metric-value">${{formatMoney(economics.supplier_cost_min, economics.currency || '')}}</span></div>
                  <div class="metric"><span class="metric-label">Выбранная закупочная стоимость</span><span class="metric-value">${{formatMoney(economics.supplier_cost_selected, economics.currency || '')}}</span></div>
                  <div class="metric"><span class="metric-label">Резерв логистики</span><span class="metric-value">${{formatMoney(economics.logistics_reserve, economics.currency || '')}}</span></div>
                  <div class="metric"><span class="metric-label">Резерв риска</span><span class="metric-value">${{formatMoney(economics.risk_reserve, economics.currency || '')}}</span></div>
                  <div class="metric"><span class="metric-label">Целевая маржа</span><span class="metric-value">${{economics.gross_margin_percent === null || economics.gross_margin_percent === undefined ? 'не определено' : `${{escapeHtml(economics.gross_margin_percent)}}%`}}</span></div>
                  <div class="metric"><span class="metric-label">Предварительная цена подачи</span><span class="metric-value">${{formatMoney(economics.preliminary_bid_price, economics.currency || '')}}</span></div>
                </div>
                <div class="trace" style="margin-top:12px">Статус экономики: ${{escapeHtml(displayValue(economics.economics_status))}}. Выбранный поставщик: ${{escapeHtml(displayValue(economics.selected_supplier_name))}}.</div>
              </div>
              <div class="card" style="padding:16px">
                <div class="section-title">Что проверить вручную</div>
                <ul>${{manualChecks.length ? manualChecks.map((item) => `<li>${{escapeHtml(item)}}</li>`).join('') : '<li>Дополнительных замечаний нет.</li>'}}</ul>
              </div>
            `;
          }}

          async function fetchJson(url, options) {{
            const response = await fetch(url, options);
            if (!response.ok) {{
              let detail = `HTTP ${{response.status}}`;
              try {{
                const payload = await response.json();
                detail = payload.detail || detail;
              }} catch (_error) {{
              }}
              throw new Error(detail);
            }}
            return response.json();
          }}

          function renderRunEventList(events) {{
            return (events || []).map((item) => `
              <li class="event-item">
                <div class="event-head">
                  <span>${{escapeHtml(item.timestamp || item.created_at)}} · ${{escapeHtml(item.step || 'Система')}}</span>
                  <span class="event-severity ${{escapeHtml(item.severity || 'info')}}">${{escapeHtml(item.severity || 'info')}}</span>
                </div>
                <div><strong>${{escapeHtml(item.event_type)}}</strong> · ${{escapeHtml(item.message_ru || item.message)}}</div>
              </li>
            `).join('');
          }}

          async function refreshRunEvents(runId) {{
            if (!runId) {{
              return;
            }}
            try {{
              const events = await fetchJson(`/api/demo/tender-agent/runs/${{encodeURIComponent(runId)}}/events`);
              const node = document.getElementById('run-events-list');
              if (!node || state.selectedRunId !== runId) {{
                return;
              }}
              node.innerHTML = renderRunEventList(events) || '<li class="event-item">Событий пока нет.</li>';
            }} catch (_error) {{
            }}
          }}

          function startRunEventsPolling(runId) {{
            if (state.eventsPollTimer) {{
              window.clearInterval(state.eventsPollTimer);
              state.eventsPollTimer = null;
            }}
            if (!runId) {{
              return;
            }}
            refreshRunEvents(runId);
            state.eventsPollTimer = window.setInterval(() => {{
              refreshRunEvents(runId);
            }}, 2500);
          }}

          function setFlash(nodeId, message, isError = false) {{
            const node = document.getElementById(nodeId);
            node.className = `flash${{isError ? ' error' : ''}}`;
            node.textContent = message;
            node.classList.remove('hidden');
          }}

          function clearFlash(nodeId) {{
            const node = document.getElementById(nodeId);
            node.className = 'hidden';
            node.textContent = '';
          }}

          function stopAnalysisJobPolling() {{
            if (state.analysisJobPollTimer) {{
              window.clearInterval(state.analysisJobPollTimer);
              state.analysisJobPollTimer = null;
            }}
            state.activeAnalysisJobId = null;
            state.activeAnalysisJobStartedAt = null;
          }}

          function formatSeconds(value) {{
            if (typeof value !== 'number' || !Number.isFinite(value)) {{
              return '—';
            }}
            return value.toFixed(value >= 10 ? 1 : 2) + ' сек';
          }}

          function buildAnalysisRuntime() {{
            const form = document.getElementById('analysis-form');
            const presetKey = form?.querySelector('[name="runtime_preset"]')?.value || 'mac_mini_local';
            const preset = getAnalysisPreset(presetKey);
            const analysisMode = String(form?.querySelector('[name="analysis_mode"]')?.value || preset.analysis_mode || 'fast');
            const useLlm = form?.querySelector('[name="use_llm"]')?.checked ?? preset.use_llm;
            const saveReport = form?.querySelector('[name="save_report"]')?.checked ?? preset.save_report;
            return {{
              preset_key: preset.key,
              preset_name: preset.name,
              contour_label: preset.contour_label,
              provider: preset.provider,
              model: preset.model,
              base_url: preset.base_url,
              use_llm: useLlm,
              llm_base_url: useLlm ? preset.llm_base_url : null,
              llm_model: useLlm ? preset.llm_model : null,
              llm_model_label: useLlm ? preset.llm_model_label : 'LLM отключена',
              analysis_mode: analysisMode,
              limit: preset.limit,
              save_report: saveReport,
            }};
          }}

          function renderAnalysisRuntimeSummary() {{
            const runtime = buildAnalysisRuntime();
            const node = document.getElementById('analysis-runtime-summary');
            const embeddingEndpoint = runtime.base_url || 'не требуется';
            const llmEndpoint = runtime.use_llm ? (runtime.llm_base_url || 'не задан') : 'LLM отключена';
            const llmModelDebug = runtime.use_llm && runtime.llm_model
              ? `<div class="note" style="margin-top:12px">Debug: llm_model=${{escapeHtml(runtime.llm_model)}}</div>`
              : `<div class="note" style="margin-top:12px">Упрощённый smoke-контур без локальной LLM.</div>`;
            node.innerHTML = `
              <div class="metric"><span class="metric-label">Контур</span><span class="metric-value">${{escapeHtml(runtime.preset_name)}}</span></div>
              <div class="metric"><span class="metric-label">Embeddings</span><span class="metric-value">${{escapeHtml(runtime.model)}} через ${{escapeHtml(runtime.provider)}}</span></div>
              <div class="metric"><span class="metric-label">Embedding endpoint</span><span class="metric-value">${{escapeHtml(embeddingEndpoint)}}</span></div>
              <div class="metric"><span class="metric-label">LLM</span><span class="metric-value">${{runtime.use_llm ? escapeHtml(runtime.llm_model_label) : 'выключена'}}</span></div>
              <div class="metric"><span class="metric-label">LLM endpoint</span><span class="metric-value">${{escapeHtml(llmEndpoint)}}</span></div>
              <div class="metric"><span class="metric-label">Режим</span><span class="metric-value">${{escapeHtml(runtime.analysis_mode)}}</span></div>
              <div class="metric"><span class="metric-label">Источники</span><span class="metric-value">до ${{runtime.limit}} фрагментов на раздел</span></div>
              <div class="metric"><span class="metric-label">Отчёт</span><span class="metric-value">${{runtime.save_report ? 'сохраняется' : 'не сохраняется'}}</span></div>
              ${{llmModelDebug}}
            `;
            node.className = 'list';
            return runtime;
          }}

          function applyAnalysisPreset() {{
            const form = document.getElementById('analysis-form');
            const presetKey = form?.querySelector('[name="runtime_preset"]')?.value || 'mac_mini_local';
            const preset = getAnalysisPreset(presetKey);
            const analysisMode = form?.querySelector('[name="analysis_mode"]');
            const useLlm = form?.querySelector('[name="use_llm"]');
            const saveReport = form?.querySelector('[name="save_report"]');
            if (analysisMode) {{
              analysisMode.value = preset.analysis_mode;
            }}
            if (useLlm) {{
              useLlm.checked = preset.use_llm;
            }}
            if (saveReport) {{
              saveReport.checked = preset.save_report;
            }}
            renderAnalysisRuntimeSummary();
          }}

          function buildTimingSummary(payload) {{
            const timings = payload.timings || {{}};
            const slowest = (timings.slowest_sections || []).map(function(item) {{
              return '<li>' + escapeHtml(item.section_title || item.section_id || 'section') + ': ' + escapeHtml(formatSeconds(item.duration_seconds)) + '</li>';
            }}).join('');
            return `
              <div class="grid-2" style="margin-top:12px">
                <div class="metric"><span class="metric-label">Длительность</span><span class="metric-value">${{escapeHtml(formatSeconds(payload.duration_seconds))}}</span></div>
                <div class="metric"><span class="metric-label">Режим</span><span class="metric-value">${{escapeHtml(payload.analysis_mode || 'balanced')}}</span></div>
                <div class="metric"><span class="metric-label">Retrieval</span><span class="metric-value">${{escapeHtml(formatSeconds(timings.retrieval_seconds))}}</span></div>
                <div class="metric"><span class="metric-label">LLM вызовов</span><span class="metric-value">${{payload.llm_calls_count ?? 0}}</span></div>
                <div class="metric"><span class="metric-label">Контекст</span><span class="metric-value">${{payload.total_context_chars ?? 0}} симв.</span></div>
                <div class="metric"><span class="metric-label">Макс. секция</span><span class="metric-value">${{payload.max_section_context_chars ?? 0}} симв.</span></div>
              </div>
              ${{slowest ? '<div class="note" style="margin-top:12px"><strong>Самые медленные разделы:</strong><ul style="margin:8px 0 0 18px">' + slowest + '</ul></div>' : ''}}
            `;
          }}

          function renderAnalysisResultPayload(payload, registryNumber) {{
            const node = document.getElementById('analysis-result');
            const runtime = state.activeAnalysisRuntime || buildAnalysisRuntime();
            const warningsHtml = (payload.warnings || []).map(function(w) {{ return '<div class="note" style="color:var(--warning)">⚠ ' + escapeHtml(w) + '</div>'; }}).join('');
            const errorsHtml = (payload.errors || []).map(function(e) {{ return '<div class="note" style="color:var(--danger)">✗ ' + escapeHtml(e) + '</div>'; }}).join('');
            const analysisRunId = payload.analysis_run_id || payload.run_id || '';
            const demoRunId = payload.run_id || '';
            const isDemoAgentRun = !!(demoRunId && String(demoRunId).startsWith('toa-run-'));
            const reportLink = analysisRunId
              ? (isDemoAgentRun
                  ? '/demo/tender-agent/runs/' + encodeURIComponent(demoRunId) + '/report'
                  : '/api/tender-research/analyze/history/' + encodeURIComponent(analysisRunId) + '/report')
              : (payload.report_path ? '/api/tender-research/analyze/' + encodeURIComponent(registryNumber) + '/latest' : '');
            const docxExportLink = analysisRunId
              ? (isDemoAgentRun
                  ? '/api/demo/tender-agent/runs/' + encodeURIComponent(demoRunId) + '/export/docx'
                  : '/api/tender-research/analyze/history/' + encodeURIComponent(analysisRunId) + '/export/docx')
              : '';
            const pdfExportLink = analysisRunId
              ? (isDemoAgentRun
                  ? '/api/demo/tender-agent/runs/' + encodeURIComponent(demoRunId) + '/export/pdf'
                  : '/api/tender-research/analyze/history/' + encodeURIComponent(analysisRunId) + '/export/pdf')
              : '';
            const actions = [];
            if (reportLink) {{
              actions.push(`<a class="link-button" href="${{reportLink}}" target="_blank" rel="noreferrer">Открыть отчёт</a>`);
            }}
            if (docxExportLink) {{
              actions.push(`<a class="link-button" href="${{docxExportLink}}" target="_blank" rel="noreferrer">Скачать DOCX</a>`);
            }}
            if (pdfExportLink) {{
              actions.push(`<a class="link-button" href="${{pdfExportLink}}" target="_blank" rel="noreferrer">Скачать PDF</a>`);
            }}
            node.innerHTML = `
              <div class="grid-2" style="margin-bottom:12px">
                <div class="metric"><span class="metric-label">Контур</span><span class="metric-value">${{escapeHtml(runtime.preset_name || 'не определено')}}</span></div>
                <div class="metric"><span class="metric-label">Embeddings</span><span class="metric-value">${{escapeHtml((payload.retrieval_model || runtime.model || '?') + ' / ' + (payload.retrieval_provider || runtime.provider || '?'))}}</span></div>
                <div class="metric"><span class="metric-label">Embedding endpoint</span><span class="metric-value">${{escapeHtml(runtime.base_url || 'не требуется')}}</span></div>
                <div class="metric"><span class="metric-label">LLM endpoint</span><span class="metric-value">${{escapeHtml(payload.llm_endpoint || runtime.llm_base_url || 'LLM отключена')}}</span></div>
              </div>
              <div class="grid-2">
                <div class="metric"><span class="metric-label">Статус</span><span class="metric-value">${{escapeHtml(payload.status || 'unknown')}}</span></div>
                <div class="metric"><span class="metric-label">Разделов</span><span class="metric-value">${{payload.sections_count ?? 0}}</span></div>
                <div class="metric"><span class="metric-label">Источников</span><span class="metric-value">${{payload.sources_count ?? 0}}</span></div>
                <div class="metric"><span class="metric-label">LLM</span><span class="metric-value">${{payload.used_llm ? 'да' : 'нет'}}</span></div>
              </div>
              ${{buildTimingSummary(payload)}}
              ${{payload.preview ? '<div class="note" style="margin-top:12px;white-space:pre-wrap">' + escapeHtml(payload.preview) + '</div>' : ''}}
              ${{warningsHtml}}
              ${{errorsHtml}}
              ${{actions.length ? `<div class="form-actions" style="margin-top:14px">${{actions.join('')}}</div>` : ''}}
            `;
            node.className = '';
          }}

          function renderAnalysisJobStatus(job) {{
            const node = document.getElementById('analysis-job-status');
            if (!job) {{
              node.innerHTML = '<div class="empty">Нет активной фоновой задачи.</div>';
              node.className = 'empty';
              return;
            }}
            const runtime = state.activeAnalysisRuntime || buildAnalysisRuntime();
            const statusColor = job.status === 'completed' ? 'var(--success)' : job.status === 'completed_with_warnings' ? 'var(--warning)' : job.status === 'failed' ? 'var(--danger)' : 'var(--text)';
            const stepsHtml = (job.steps || []).map(function(step) {{
              const icon = step.status === 'completed' ? '✓' : step.status === 'skipped' ? '–' : step.status === 'warning' ? '⚠' : step.status === 'failed' ? '✗' : step.status === 'running' ? '…' : '·';
              const color = step.status === 'completed' || step.status === 'skipped' ? 'var(--success)' : step.status === 'warning' ? 'var(--warning)' : step.status === 'failed' ? 'var(--danger)' : 'inherit';
              return '<div style="padding:4px 0;color:' + color + '">' + icon + ' <strong>' + escapeHtml(step.title || step.name) + '</strong>' +
                (step.message ? ' — ' + escapeHtml(step.message) : '') + '</div>';
            }}).join('');
            const warningsHtml = (job.warnings || []).map(function(item) {{ return '<div class="note" style="color:var(--warning)">⚠ ' + escapeHtml(item) + '</div>'; }}).join('');
            const errorsHtml = (job.errors || []).map(function(item) {{ return '<div class="note" style="color:var(--danger)">✗ ' + escapeHtml(item) + '</div>'; }}).join('');
            node.innerHTML = `
              <div class="grid-2">
                <div class="metric"><span class="metric-label">Job ID</span><span class="metric-value" style="font-size:12px">${{escapeHtml(job.id)}}</span></div>
                <div class="metric"><span class="metric-label">Тип</span><span class="metric-value">${{escapeHtml(job.job_type)}}</span></div>
                <div class="metric"><span class="metric-label">Статус</span><span class="metric-value" style="color:${{statusColor}}">${{escapeHtml(job.status)}}</span></div>
                <div class="metric"><span class="metric-label">Прогресс</span><span class="metric-value">${{job.progress_percent ?? 0}}%</span></div>
                <div class="metric"><span class="metric-label">Шаг</span><span class="metric-value">${{escapeHtml(job.current_step || 'queued')}}</span></div>
                <div class="metric"><span class="metric-label">Текущая секция</span><span class="metric-value">${{escapeHtml(job.current_section_title || '—')}}</span></div>
                <div class="metric"><span class="metric-label">Источник</span><span class="metric-value">${{escapeHtml(job.source || 'api')}}</span></div>
                <div class="metric"><span class="metric-label">Режим</span><span class="metric-value">${{escapeHtml(job.analysis_mode || 'balanced')}}</span></div>
                <div class="metric"><span class="metric-label">Время</span><span class="metric-value">${{escapeHtml(formatSeconds(job.duration_seconds))}}</span></div>
                <div class="metric"><span class="metric-label">Контур</span><span class="metric-value">${{escapeHtml(runtime.preset_name || 'не определено')}}</span></div>
                <div class="metric"><span class="metric-label">Embeddings</span><span class="metric-value">${{escapeHtml(runtime.model + ' / ' + runtime.provider)}}</span></div>
                <div class="metric"><span class="metric-label">LLM endpoint</span><span class="metric-value">${{escapeHtml(runtime.use_llm ? (runtime.llm_base_url || 'не задан') : 'LLM отключена')}}</span></div>
                <div class="metric"><span class="metric-label">LLM model</span><span class="metric-value" style="font-size:12px">${{escapeHtml(runtime.use_llm ? (runtime.llm_model || runtime.llm_model_label || 'не задана') : 'LLM отключена')}}</span></div>
              </div>
              <div style="margin-top:12px;border:1px solid var(--border);border-radius:10px;overflow:hidden">
                <div style="height:10px;background:var(--panel)">
                  <div style="height:100%;width:${{Math.max(0, Math.min(100, job.progress_percent || 0))}}%;background:linear-gradient(90deg, var(--accent), var(--success))"></div>
                </div>
              </div>
              <div style="margin-top:10px">${{stepsHtml || '<div class="empty">Шаги ещё не доступны.</div>'}}</div>
              ${{warningsHtml}}
              ${{errorsHtml}}
            `;
            node.className = '';
          }}

          async function pollAnalysisJobOnce(jobId, registryNumber) {{
            const job = await fetchJson('/api/tender-research/jobs/' + encodeURIComponent(jobId));
            renderAnalysisJobStatus(job);
            if (job.status === 'completed' || job.status === 'completed_with_warnings') {{
              stopAnalysisJobPolling();
              if (job.job_type === 'prepare') {{
                setFlash('analysis-flash', `Подготовка завершена: статус «${{job.status}}».`);
                await handleCheckReadiness();
              }} else if (job.job_type === 'analyze') {{
                renderAnalysisResultPayload(job.result || {{}}, registryNumber);
                setFlash('analysis-flash', `Анализ завершён: статус «${{job.status}}», разделов: ${{job.result?.sections_count ?? 0}}, источников: ${{job.result?.sources_count ?? 0}}.`);
                await handleRefreshHistory(registryNumber);
              }}
              return;
            }}
            if (job.status === 'failed' || job.status === 'cancelled') {{
              stopAnalysisJobPolling();
              setFlash('analysis-flash', 'Фоновая задача завершилась ошибкой: ' + escapeHtml((job.errors || []).join('; ') || job.status), true);
              document.getElementById('prepare-tender-btn').disabled = false;
            }}
          }}

          function startAnalysisJobPolling(jobId, registryNumber) {{
            stopAnalysisJobPolling();
            state.activeAnalysisJobId = jobId;
            state.activeAnalysisJobStartedAt = Date.now();
            pollAnalysisJobOnce(jobId, registryNumber).catch(function(error) {{
              setFlash('analysis-flash', 'Ошибка получения статуса фоновой задачи: ' + escapeHtml(error.message), true);
            }});
            state.analysisJobPollTimer = window.setInterval(async function() {{
              if (!state.activeAnalysisJobStartedAt || (Date.now() - state.activeAnalysisJobStartedAt) > 10 * 60 * 1000) {{
                stopAnalysisJobPolling();
                setFlash('analysis-flash', 'Задача выполняется дольше обычного. Можно продолжить проверку статуса позже.', true);
                return;
              }}
              try {{
                await pollAnalysisJobOnce(jobId, registryNumber);
              }} catch (error) {{
                stopAnalysisJobPolling();
                setFlash('analysis-flash', 'Ошибка получения статуса фоновой задачи: ' + escapeHtml(error.message), true);
              }}
            }}, 1500);
          }}

          function wireTabs() {{
            for (const button of document.querySelectorAll('.tab-button')) {{
              button.addEventListener('click', () => {{
                for (const item of document.querySelectorAll('.tab-button')) {{
                  item.classList.toggle('active', item === button);
                }}
                const target = button.dataset.tab;
                document.getElementById('tab-search').classList.toggle('hidden', target !== 'search');
                document.getElementById('tab-docs').classList.toggle('hidden', target !== 'docs');
                document.getElementById('tab-dataset').classList.toggle('hidden', target !== 'dataset');
                document.getElementById('tab-upload').classList.toggle('hidden', target !== 'upload');
                document.getElementById('tab-profile').classList.toggle('hidden', target !== 'profile');
                document.getElementById('tab-analysis').classList.toggle('hidden', target !== 'analysis');
                if (target === 'profile') {{
                  loadSupplierProfile();
                }}
              }});
            }}
          }}

          function procurementActionLabel(result) {{
            if (result.can_download_attachments || result.attachments_status === 'downloadable') {{
              return 'Скачать документацию и анализировать';
            }}
            return 'Создать run и загрузить документы вручную';
          }}

          async function loadSupplierProfile() {{
            try {{
              const profile = await fetchJson('/api/demo/tender-agent/supplier-profile');
              renderSupplierProfile(profile);
            }} catch (error) {{
              document.getElementById('supplier-profile-display').innerHTML = '<div class="empty">Не удалось загрузить профиль: ' + escapeHtml(error.message) + '</div>';
            }}
          }}

          function renderSupplierProfile(profile) {{
            const criteria = profile.criteria || {{}};
            const risk = profile.risk_preferences || {{}};
            const html = `
              <div class="card">
                <h2>${{escapeHtml(profile.name)}}</h2>
                <div class="grid-2">
                  <div class="metric"><span class="metric-label">ID</span><span class="metric-value">${{escapeHtml(profile.supplier_id)}}</span></div>
                  <div class="metric"><span class="metric-label">ИНН</span><span class="metric-value">${{escapeHtml(profile.inn || 'не указан')}}</span></div>
                  <div class="metric"><span class="metric-label">Категории</span><span class="metric-value" style="font-size:13px">${{(criteria.categories || []).join(', ') || 'не указаны'}}</span></div>
                  <div class="metric"><span class="metric-label">Регионы</span><span class="metric-value" style="font-size:13px">${{(criteria.regions || []).join(', ') || 'не указаны'}}</span></div>
                  <div class="metric"><span class="metric-label">Цена от</span><span class="metric-value">${{criteria.price_min != null ? formatMoney(criteria.price_min, 'RUB') : 'не указано'}}</span></div>
                  <div class="metric"><span class="metric-label">Цена до</span><span class="metric-value">${{criteria.price_max != null ? formatMoney(criteria.price_max, 'RUB') : 'не указано'}}</span></div>
                </div>
                <div style="margin-top:14px">
                  <div class="section-title">Ключевые слова</div>
                  <div class="safety">${{(criteria.keywords || []).map(function(k) {{ return '<span>' + escapeHtml(k) + '</span>'; }}).join('') || '<span>не указаны</span>'}}</div>
                </div>
                <div style="margin-top:10px">
                  <div class="section-title">Стоп-слова</div>
                  <div class="safety">${{(criteria.stop_words || []).map(function(k) {{ return '<span>' + escapeHtml(k) + '</span>'; }}).join('') || '<span>не указаны</span>'}}</div>
                </div>
                <div style="margin-top:14px">
                  <div class="section-title">Риски и предпочтения</div>
                  <div class="grid-2">
                    <div class="metric"><span class="metric-label">Толерантность</span><span class="metric-value">${{escapeHtml(risk.tolerance || 'medium')}}</span></div>
                    <div class="metric"><span class="metric-label">Макс. штраф, %</span><span class="metric-value">${{risk.max_penalty_percent != null ? risk.max_penalty_percent + '%' : 'не указано'}}</span></div>
                    <div class="metric"><span class="metric-label">Макс. задержка, дней</span><span class="metric-value">${{risk.max_delay_days != null ? risk.max_delay_days : 'не указано'}}</span></div>
                    <div class="metric"><span class="metric-label">Сертификаты</span><span class="metric-value">${{risk.require_certificates ? 'требуются' : 'не требуются'}}</span></div>
                  </div>
                </div>
                ${{(profile.certificates || []).length ? '<div style="margin-top:14px"><div class="section-title">Сертификаты</div><div class="safety">' + profile.certificates.map(function(c) {{ return '<span>' + escapeHtml(c) + '</span>'; }}).join('') + '</div></div>' : ''}}
              </div>
            `;
            document.getElementById('supplier-profile-display').innerHTML = html;
          }}

          async function resetSupplierProfile() {{
            try {{
              const profile = await fetchJson('/api/demo/tender-agent/supplier-profile/reset', {{ method: 'POST' }});
              renderSupplierProfile(profile);
              setFlash('supplier-profile-flash', 'Профиль сброшен на демо-настройки.');
            }} catch (error) {{
              setFlash('supplier-profile-flash', 'Ошибка сброса профиля: ' + escapeHtml(error.message), true);
            }}
          }}

          async function loadProcurementSources() {{
            state.procurementSources = await fetchJson('/api/demo/tender-agent/procurement/sources');
            const select = document.getElementById('procurement-source-select');
            select.innerHTML = state.procurementSources.filter((source) => ['demo_local', 'public_eis_html_44fz', 'public_eis_html_223fz'].includes(source.source)).map((source) => `
              <option value="${{escapeHtml(source.source)}}"${{source.configured ? '' : ' disabled'}}>${{escapeHtml(source.label)}}${{source.configured ? '' : ` — ${{escapeHtml(source.reason || 'не настроен')}}`}}</option>
            `).join('');
            if (!state.procurementSources.some((source) => source.source === select.value && source.configured)) {{
              select.value = 'demo_local';
            }}
            renderProcurementSourceDiagnostics(select.value);
            renderEisDocsDiagnostics();
            select.addEventListener('change', () => renderProcurementSourceDiagnostics(select.value));
          }}

          function renderProcurementSourceDiagnostics(selectedSource) {{
            const node = document.getElementById('procurement-source-diagnostics');
            const source = state.procurementSources.find((item) => item.source === selectedSource) || state.procurementSources[0];
            if (!source) {{
              node.innerHTML = `<div class="empty">Источник ещё не загружен.</div>`;
              return;
            }}
            const diagnostics = source.safe_diagnostics || {{}};
            const lastStatus = diagnostics.last_status || (source.configured ? 'configured' : 'not_configured');
            const isPublicReadOnly = diagnostics.mode === 'public_html_read_only' || diagnostics.mode === 'public_html_fallback';
            const tokenState = diagnostics.token_present ? 'токен найден' : 'токен не найден';
            const statusLabel = isPublicReadOnly
              ? 'Публичный read-only поиск: готов'
              : (source.configured ? 'ЕИС настроена: токен найден' : (source.reason || 'ЕИС не настроена'));
            const structuredStatus = isPublicReadOnly
              ? 'без авторизации · токен не требуется'
              : (source.configured ? `настроен · ${{tokenState}}` : (source.reason || 'не настроен'));
            node.innerHTML = `
              <div class="list-item">
                <strong>${{escapeHtml(source.label)}}</strong>
                <div class="run-meta">${{escapeHtml(statusLabel)}}</div>
              </div>
              <div class="list-item">
                <strong>Статус подключения</strong>
                <div class="run-meta">${{escapeHtml(structuredStatus)}} · последний статус: ${{escapeHtml(String(lastStatus))}}</div>
              </div>
              <div class="list-item">
                <strong>Endpoint</strong>
                <div class="run-meta">${{escapeHtml(displayValue(diagnostics.endpoint_host, 'не определён'))}}${{escapeHtml(displayValue(diagnostics.endpoint_path, ''))}}</div>
              </div>
              <div class="list-item">
                <strong>Последняя диагностика</strong>
                <div class="run-meta">${{escapeHtml(displayValue(diagnostics.last_error || source.reason, 'ошибок не зафиксировано'))}}</div>
              </div>
            `;
          }}

          function renderEisDocsDiagnostics() {{
            const node = document.getElementById('eis-docs-diagnostics');
            const source = state.procurementSources.find((item) => item.source === 'zakupki_gov_ru_getdocs_ip');
            if (!source) {{
              node.innerHTML = `<div class="empty">Источник getDocsIP ещё не загружен.</div>`;
              return;
            }}
            const diagnostics = source.safe_diagnostics || {{}};
            const eisStatus = source.configured ? 'настроен' : 'не настроен';
            const eisTokenState = diagnostics.token_present ? 'токен найден' : 'токен не найден';
            node.innerHTML = `
              <div class="list-item">
                <strong>${{escapeHtml(source.label)}}</strong>
                <div class="run-meta">${{escapeHtml(source.reason || 'Источник загружен')}}</div>
              </div>
              <div class="list-item">
                <strong>Статус</strong>
                <div class="run-meta">${{escapeHtml(eisStatus)}} · ${{escapeHtml(eisTokenState)}} · владелец: ${{escapeHtml(displayValue(diagnostics.token_owner, 'неизвестно'))}}</div>
              </div>
              <div class="list-item">
                <strong>Адрес getDocsIP</strong>
                <div class="run-meta">${{escapeHtml(displayValue(diagnostics.endpoint_host, 'не определён'))}}${{escapeHtml(displayValue(diagnostics.endpoint_path, ''))}}</div>
              </div>
              <div class="list-item">
                <strong>Последняя диагностика</strong>
                <div class="run-meta">${{escapeHtml(displayValue(diagnostics.last_error || diagnostics.method_name || source.reason, 'ошибок не зафиксировано'))}}</div>
              </div>
            `;
          }}

          function renderProcurementResults() {{
            const node = document.getElementById('procurement-results');
            if (!state.procurementResults.length) {{
              node.innerHTML = `<div class="empty">По текущему фильтру закупки не найдены. Уточните запрос или используйте demo_local без дополнительных фильтров.</div>`;
              return;
            }}
            node.innerHTML = state.procurementResults.map((result) => `
              <div class="run-item">
                <div class="step-top" style="margin-bottom:8px">
                  <div>
                    <strong>${{escapeHtml(result.title)}}</strong>
                    <div class="run-meta">${{escapeHtml(result.notice_number || result.procurement_number || result.procurement_id)}} · ${{escapeHtml(result.customer_name)}} · ${{escapeHtml(result.law || result.source)}}</div>
                  </div>
                  <span class="status-chip ${{result.attachments_status === 'downloadable' ? 'status-done' : 'status-needs_review'}}">${{escapeHtml(attachmentsStatusLabel(result.attachments_status))}}</span>
                </div>
                <div class="grid-2">
                  <div class="metric"><span class="metric-label">Дата публикации</span><span class="metric-value">${{escapeHtml(displayValue(result.publication_date))}}</span></div>
                  <div class="metric"><span class="metric-label">Срок подачи</span><span class="metric-value">${{escapeHtml(displayValue(result.deadline))}}</span></div>
                  <div class="metric"><span class="metric-label">Начальная цена</span><span class="metric-value">${{formatMoney(result.initial_price, result.currency || '')}}</span></div>
                  <div class="metric"><span class="metric-label">Регион</span><span class="metric-value">${{escapeHtml(displayValue(result.region))}}</span></div>
                </div>
                <div style="height:12px"></div>
                <p>${{escapeHtml(result.summary || result.status || '')}}</p>
                <div class="note" style="margin-top:10px">${{escapeHtml((result.warnings || []).join(' '))}}</div>
                <div class="note" style="margin-top:8px">Вложений: ${{result.attachments_count}} · статус: ${{attachmentsStatusLabel(result.attachments_status)}}</div>
                <div class="form-actions" style="margin-top:12px">
                  <a class="link-button" href="${{result.source_url}}" target="_blank" rel="noreferrer">Открыть источник</a>
                  <button class="button primary procurement-run-button" type="button" data-procurement-id="${{escapeHtml(result.procurement_id)}}" data-source="${{escapeHtml(result.source)}}" data-auto-analyze="${{result.can_download_attachments || result.attachments_status === 'downloadable' ? 'true' : 'false'}}">${{procurementActionLabel(result)}}</button>
                </div>
              </div>
            `).join('');

            for (const button of node.querySelectorAll('.procurement-run-button')) {{
              button.addEventListener('click', () => {{
                createProcurementRun(button.dataset.procurementId, button.dataset.source, button.dataset.autoAnalyze === 'true');
              }});
            }}
          }}

          function renderPublicSearchCards(cards, pagination = {{}}) {{
            const node = document.getElementById('procurement-results');
            if (!cards || !cards.length) {{
              node.innerHTML = `<div class="empty">По вашему запросу закупки не найдены.</div>`;
              return;
            }}
            node.innerHTML = cards.map((card, index) => {{
              const queryRel = card.query_relevance || null;
              const relBadge = queryRel ? queryMatchBadge(queryRel) : '';
              const relBreakdown = queryRel ? queryMatchHtml(queryRel) : '';
              return `
              <div class="run-item">
                <div class="step-top" style="margin-bottom:8px">
                  <div>
                    <strong>${{escapeHtml(card.title || 'Закупка без названия')}}</strong>
                    <div class="run-meta">${{card.notice_number || card.reestr_number || ''}} · ${{escapeHtml(card.customer_name || 'Заказчик не указан')}} · 44-ФЗ</div>
                  </div>
                  <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">
                    ${{relBadge}}
                    <span class="status-chip status-done">Публичный поиск ЕИС</span>
                  </div>
                </div>
                <div class="grid-2">
                  <div class="metric"><span class="metric-label">Номер извещения</span><span class="metric-value">${{escapeHtml(card.notice_number || card.reestr_number || 'не указан')}}</span></div>
                  <div class="metric"><span class="metric-label">Начальная цена</span><span class="metric-value">${{card.initial_price ? formatMoney(card.initial_price, 'RUB') : 'не указана'}}</span></div>
                  <div class="metric"><span class="metric-label">Дата публикации</span><span class="metric-value">${{escapeHtml(card.publication_date || 'не указана')}}</span></div>
                  <div class="metric"><span class="metric-label">Срок подачи</span><span class="metric-value">${{escapeHtml(card.deadline || 'не указан')}}</span></div>
                  <div class="metric"><span class="metric-label">Статус</span><span class="metric-value">${{escapeHtml(card.status || 'стадия определена фильтром ЕИС')}}</span></div>
                  <div class="metric"><span class="metric-label">Заказчик</span><span class="metric-value">${{escapeHtml(card.customer_name || 'не указан')}}</span></div>
                </div>
                ${{relBreakdown}}
                ${{(card.warnings || []).length ? `<div class="note" style="margin-top:10px">${{escapeHtml(card.warnings.join('; '))}}</div>` : ''}}
                <div class="form-actions" style="margin-top:12px">
                  ${{card.reestr_number ? `<button class="button primary public-search-handoff-button" type="button" data-reestr="${{escapeHtml(card.reestr_number)}}" data-title="${{escapeHtml(card.title)}}" data-customer="${{escapeHtml(card.customer_name || '')}}" data-url="${{escapeHtml(card.source_url || '')}}">Получить документацию</button>` : ''}}
                  ${{card.source_url ? `<a class="link-button" href="${{escapeHtml(card.source_url)}}" target="_blank" rel="noreferrer">Открыть в ЕИС</a>` : ''}}
                </div>
                <div class="note" style="margin-top:8px">Поиск работает в read-only режиме. Система не входит в личный кабинет, не обходит captcha, не подаёт заявку.</div>
              </div>
            `;
            }}).join('') + `
              <div class="form-actions" style="margin-top:12px">
                ${{pagination.has_more && pagination.next_cursor ? '<button class="button" id="public-search-next-button" type="button">Загрузить ещё</button>' : ''}}
              </div>`;
            for (const button of node.querySelectorAll('.public-search-handoff-button')) {{
              button.addEventListener('click', () => {{
                handlePublicSearchHandoff(button.dataset.reestr, button.dataset.title, button.dataset.customer, button.dataset.url);
              }});
            }}
            document.getElementById('public-search-next-button')?.addEventListener('click', loadNextPublicSearchPage);
          }}

          async function loadNextPublicSearchPage() {{
            if (!state.publicSearchCursor || !state.publicSearchParams) return;
            const searchParams = new URLSearchParams(state.publicSearchParams);
            searchParams.set('cursor', state.publicSearchCursor);
            searchParams.set('seen_registry_numbers', JSON.stringify(state.publicSearchSeen));
            try {{
              const result = await fetchJson('/api/demo/tender-agent/procurement/public-44fz-search', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/x-www-form-urlencoded' }},
                body: searchParams,
              }});
              const known = new Set(state.publicSearchSeen);
              for (const card of result.cards || []) {{
                const number = card.notice_number || card.reestr_number || '';
                if (number && !known.has(number)) {{
                  state.publicSearchCards.push(card);
                  state.publicSearchSeen.push(number);
                  known.add(number);
                }}
              }}
              state.publicSearchCursor = result.next_cursor || null;
              renderPublicSearchCards(state.publicSearchCards, result);
              setFlash('procurement-flash', `Загружено уникальных карточек: ${{state.publicSearchCards.length}}.`);
            }} catch (error) {{
              setFlash('procurement-flash', `Не удалось загрузить следующую страницу: ${{error.message}}`, true);
            }}
          }}

          function renderPublicSearchFallback(eisSearchUrl) {{
            const node = document.getElementById('procurement-results');
            node.innerHTML = `
              <div class="run-item">
                <strong>Откройте поиск в ЕИС</strong>
                <p style="margin-top:10px">Публичный HTML поиска ЕИС не удалось обработать автоматически. Откройте поиск в ЕИС, найдите нужную закупку и вставьте номер извещения ниже.</p>
                ${{eisSearchUrl ? `<div class="form-actions" style="margin-top:12px"><a class="link-button" href="${{escapeHtml(eisSearchUrl)}}" target="_blank" rel="noreferrer">Открыть поиск в ЕИС</a></div>` : ''}}
                <div style="margin-top:14px">
                  <label>
                    Или вставьте номер закупки (реестровый номер)
                    <div class="form-actions" style="margin-top:8px">
                      <input id="manual-reestr-input" placeholder="Например: 0888200000224000038" style="flex:1" />
                      <button class="button primary" type="button" id="manual-reestr-handoff-button">Получить документацию</button>
                    </div>
                  </label>
                </div>
              </div>
            `;
            document.getElementById('manual-reestr-handoff-button')?.addEventListener('click', () => {{
              const reestr = document.getElementById('manual-reestr-input')?.value?.trim();
              if (reestr) {{
                handlePublicSearchHandoff(reestr, '', '', '');
              }}
            }});
          }}

          async function handlePublicSearchHandoff(reestrNumber, title, customerName, sourceUrl) {{
            if (!reestrNumber) {{
              setFlash('procurement-flash', 'Не указан номер закупки.', true);
              return;
            }}
            const startedAt = Date.now();
            const button = Array.from(document.querySelectorAll('.public-search-handoff-button'))
              .find((node) => node.dataset.reestr === reestrNumber);
            if (button) {{
              button.disabled = true;
              button.textContent = 'Получаем документацию…';
            }}
            const timer = window.setInterval(() => {{
              const seconds = Math.max(1, Math.round((Date.now() - startedAt) / 1000));
              setFlash(
                'procurement-flash',
                `Получаем документацию по ${{reestrNumber}} через getDocsIP · ${{seconds}} с. Анализ запускается отдельно после получения документов.`
              );
            }}, 1000);
            setFlash('procurement-flash', `Получаем документацию по ${{reestrNumber}} через getDocsIP. Анализ запускается отдельно.`);
            try {{
              const payload = await fetchJson('/api/demo/tender-agent/runs/from-search-result', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{
                  source: 'public_44fz',
                  reestr_number: reestrNumber,
                  title: title || null,
                  customer_name: customerName || null,
                  source_url: sourceUrl || null,
                  download_archive: true,
                  analyze_after_download: false,
                }}),
              }});
              setFlash('procurement-flash', `Создан run: ${{payload.run_id}}. Документов распаковано: ${{payload.documents_extracted_count}}. Анализ не запускался автоматически — проверьте документы и запустите его отдельно.`);
              await loadRuns();
              if (payload.run_id) {{
                await selectRun(payload.run_id, true);
              }}
            }} catch (error) {{
              setFlash('procurement-flash', `Не удалось получить документацию: ${{error.message}}`, true);
            }} finally {{
              window.clearInterval(timer);
              if (button) {{
                button.disabled = false;
                button.textContent = 'Получить документацию';
              }}
            }}
          }}

          function renderEisDocsResult(result) {{
            const node = document.getElementById('eis-docs-result');
            if (!result) {{
              node.innerHTML = 'После запроса сюда попадут статус SOAP, статус архива, количество распакованных файлов и ссылки на run/report.';
              node.className = 'empty';
              return;
            }}
            node.className = '';
            const analyzeButton = result.status !== 'docs_required'
              ? `<button class="button primary" type="button" id="eis-result-analyze-button">Запустить анализ</button>`
              : '';
            const reportLink = result.report_url
              ? `<a class="link-button" href="${{escapeHtml(result.report_url)}}" target="_blank" rel="noreferrer">Открыть report</a>`
              : '';
            const docxExportLink = result.run_id
              ? `<a class="link-button" href="/api/demo/tender-agent/runs/${{encodeURIComponent(result.run_id)}}/export/docx" target="_blank" rel="noreferrer">Скачать DOCX</a>`
              : '';
            const pdfExportLink = result.run_id
              ? `<a class="link-button" href="/api/demo/tender-agent/runs/${{encodeURIComponent(result.run_id)}}/export/pdf" target="_blank" rel="noreferrer">Скачать PDF</a>`
              : '';
            node.innerHTML = `
              <div class="grid-2">
                <div class="metric"><span class="metric-label">Run ID</span><span class="metric-value">${{escapeHtml(result.run_id)}}</span></div>
                <div class="metric"><span class="metric-label">Статус run</span><span class="metric-value">${{escapeHtml(statusLabel(result.status))}}</span></div>
                <div class="metric"><span class="metric-label">SOAP-метод</span><span class="metric-value">${{escapeHtml(displayValue(result.soap_method))}}</span></div>
                <div class="metric"><span class="metric-label">ID запроса (refId)</span><span class="metric-value">${{escapeHtml(displayValue(result.ref_id))}}</span></div>
                <div class="metric"><span class="metric-label">URL архива (archiveUrl)</span><span class="metric-value">${{booleanLabel(result.archive_url_present)}}</span></div>
                <div class="metric"><span class="metric-label">Статус скачивания</span><span class="metric-value">${{escapeHtml(displayValue(result.archive_download_status))}}</span></div>
                <div class="metric"><span class="metric-label">Архив скачан</span><span class="metric-value">${{booleanLabel(result.archive_downloaded)}}</span></div>
                <div class="metric"><span class="metric-label">Распаковано документов</span><span class="metric-value">${{escapeHtml(displayValue(result.documents_extracted_count, '0'))}}</span></div>
                <div class="metric"><span class="metric-label">Источник архива</span><span class="metric-value">${{escapeHtml(displayValue(result.archive_source_host && result.archive_source_path ? `${{result.archive_source_host}}${{result.archive_source_path}}` : null))}}</span></div>
                <div class="metric"><span class="metric-label">Статус анализа</span><span class="metric-value">${{escapeHtml(displayValue(result.analysis_status, 'not_started'))}}</span></div>
              </div>
              <div class="form-actions" style="margin-top:14px">
                <a class="link-button" href="${{escapeHtml(result.run_url)}}" target="_blank" rel="noreferrer">Открыть run</a>
                ${{reportLink}}
                ${{docxExportLink}}
                ${{pdfExportLink}}
                ${{analyzeButton}}
              </div>
              <div class="note" style="margin-top:12px">Полный archive URL и ticket в интерфейсе не показываются. Отображаются только host/path summary.</div>
            `;
            const analyzeButtonNode = document.getElementById('eis-result-analyze-button');
            if (analyzeButtonNode) {{
              analyzeButtonNode.addEventListener('click', async () => {{
                await analyzeRun(result.run_id);
                await selectRun(result.run_id, true);
              }});
            }}
          }}

          async function handleProcurementSearch(event) {{
            event.preventDefault();
            clearFlash('procurement-flash');
            const form = event.currentTarget;
            const payload = {{}};
            for (const [key, value] of new FormData(form).entries()) {{
              if (String(value).trim() !== '') {{
                payload[key] = ['max_results', 'price_from', 'price_to'].includes(key) ? Number(value) : String(value);
              }}
            }}
            try {{
              if (String(payload.source || '').startsWith('public_eis_html_')) {{
                const law = payload.source === 'public_eis_html_223fz' ? '223fz' : '44fz';
                if (law === '223fz') {{
                  const searchUrlPayload = await fetchJson(`/api/demo/tender-agent/procurement/public-search-url?${{new URLSearchParams({{
                    query: String(payload.query || ''),
                    law,
                    region: String(payload.region || ''),
                    date_from: String(payload.date_from || ''),
                    date_to: String(payload.date_to || ''),
                  }})}}`);
                  state.procurementResults = [];
                  document.getElementById('procurement-results').innerHTML = `
                    <div class="run-item">
                      <strong>Публичный HTML fallback</strong>
                      <p style="margin-top:10px">${{escapeHtml(searchUrlPayload.note)}}</p>
                      <div class="form-actions" style="margin-top:12px">
                        <a class="link-button" href="${{searchUrlPayload.eis_search_url}}" target="_blank" rel="noreferrer">Открыть поиск ЕИС</a>
                      </div>
                    </div>
                  `;
                  renderProcurementSourceDiagnostics(payload.source);
                  setFlash('procurement-flash', 'Сформирована публичная ссылка поиска ЕИС. Выберите закупку вручную и затем используйте getDocsIP по номеру.');
                  return;
                }}
                const searchParams = new URLSearchParams();
                searchParams.set('query', String(payload.query || ''));
                if (payload.region) searchParams.set('region', String(payload.region));
                if (payload.date_from) searchParams.set('date_from', String(payload.date_from));
                if (payload.date_to) searchParams.set('date_to', String(payload.date_to));
                if (payload.price_from) searchParams.set('price_from', String(payload.price_from));
                if (payload.price_to) searchParams.set('price_to', String(payload.price_to));
                if (payload.status_filter) searchParams.set('status_filter', String(payload.status_filter));
                if (payload.max_results) searchParams.set('max_results', String(payload.max_results));
                const searchResult = await fetchJson('/api/demo/tender-agent/procurement/public-44fz-search', {{
                  method: 'POST',
                  headers: {{ 'Content-Type': 'application/x-www-form-urlencoded' }},
                  body: searchParams,
                }});
                if (searchResult.status === 'parsed' && searchResult.cards && searchResult.cards.length) {{
                  state.publicSearchCards = searchResult.cards;
                  state.publicSearchParams = searchParams.toString();
                  state.publicSearchSeen = searchResult.cards.map((card) => card.notice_number || card.reestr_number || '').filter(Boolean);
                  state.publicSearchCursor = searchResult.next_cursor || null;
                  renderPublicSearchCards(searchResult.cards, searchResult);
                  renderProcurementSourceDiagnostics(payload.source);
                  setFlash('procurement-flash', `Найдено закупок: ${{searchResult.cards.length}}. Выберите карточку для получения документации.`);
                }} else {{
                  const fallbackUrl = searchResult.eis_search_url || '';
                  renderPublicSearchFallback(fallbackUrl);
                  renderProcurementSourceDiagnostics(payload.source);
                  const note = searchResult.status === 'empty_results' ? 'По вашему запросу ничего не найдено.' : 'Публичный HTML-поиск не удалось обработать автоматически.';
                  setFlash('procurement-flash', note, searchResult.status !== 'empty_results');
                }}
                return;
              }}
              const response = await fetchJson('/api/demo/tender-agent/procurement/search', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify(payload),
              }});
              state.procurementResults = response || [];
              renderProcurementResults();
              const selectedSource = payload.source || document.getElementById('procurement-source-select').value;
              renderProcurementSourceDiagnostics(selectedSource);
              setFlash('procurement-flash', `Поиск выполнен, найдено закупок: ${{state.procurementResults.length}}.`);
            }} catch (error) {{
              state.procurementResults = [];
              renderProcurementResults();
              await loadProcurementSources();
              setFlash('procurement-flash', `Не удалось выполнить поиск: ${{error.message}}`, true);
            }}
          }}

          async function createProcurementRun(procurementId, source, autoAnalyze = false) {{
            const activeQuery = new FormData(document.getElementById('procurement-search-form')).get('query') || '';
            setFlash('procurement-flash', `Создаём run для закупки ${{procurementId}}…`);
            try {{
              const payload = await fetchJson('/api/demo/tender-agent/runs/from-procurement', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ procurement_id: procurementId, source, query: String(activeQuery) }}),
              }});
              setFlash('procurement-flash', `Создан run: ${{payload.run_id}}. Статус документации: ${{attachmentsStatusLabel(payload.attachments_status)}}.`);
              await loadRuns();
              await selectRun(payload.run_id, true);
              if (autoAnalyze && payload.status !== 'docs_required') {{
                await analyzeRun(payload.run_id);
              }}
            }} catch (error) {{
              setFlash('procurement-flash', `Не удалось создать run: ${{error.message}}`, true);
            }}
          }}

          async function handleEisDocsArchive(event) {{
            event.preventDefault();
            clearFlash('eis-docs-flash');
            const form = event.currentTarget;
            const data = new FormData(form);
            const payload = {{
              reestr_number: String(data.get('reestr_number') || ''),
              law: String(data.get('law') || '44fz'),
              subsystem_type: String(data.get('subsystem_type') || 'PRIZ'),
              method: String(data.get('method') || 'getDocsByReestrNumber'),
              download_archive: data.get('download_archive') === 'on',
              analyze_after_download: data.get('analyze_after_download') === 'on',
            }};
            setFlash('eis-docs-flash', `Запрашиваем документацию по номеру ${{payload.reestr_number}} через getDocsIP…`);
            try {{
              const response = await fetchJson('/api/demo/tender-agent/runs/from-eis-docs-archive', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify(payload),
              }});
              renderEisDocsResult(response);
              await loadProcurementSources();
              await loadRuns();
              await selectRun(response.run_id, true);
              setFlash('eis-docs-flash', `Создан run ${{response.run_id}}. Статус документации: ${{attachmentsStatusLabel(response.attachments_status)}}. Статус архива: ${{displayValue(response.archive_download_status, 'не определён')}}.`);
            }} catch (error) {{
              await loadProcurementSources();
              renderEisDocsResult(null);
              setFlash('eis-docs-flash', `Не удалось получить документацию: ${{error.message}}`, true);
            }}
          }}

          function renderDatasetTenderCard(run) {{
            const tender = run.tender;
            document.getElementById('dataset-tender-card').innerHTML = `
              <h2>Карточка закупки</h2>
              <div class="grid-2">
                <div class="metric"><span class="metric-label">Название закупки</span><span class="metric-value">${{escapeHtml(tender.title)}}</span></div>
                <div class="metric"><span class="metric-label">Тип процедуры</span><span class="metric-value">${{escapeHtml(tender.procedure_type)}}</span></div>
                <div class="metric"><span class="metric-label">Заказчик</span><span class="metric-value">${{escapeHtml(tender.customer)}}</span></div>
                <div class="metric"><span class="metric-label">Категория</span><span class="metric-value">${{escapeHtml(tender.category)}}</span></div>
                <div class="metric"><span class="metric-label">Документы</span><span class="metric-value">${{tender.document_count}}</span></div>
                <div class="metric"><span class="metric-label">Требования</span><span class="metric-value">${{tender.requirement_count}}</span></div>
                <div class="metric"><span class="metric-label">Вопросы</span><span class="metric-value">${{tender.question_count}}</span></div>
                <div class="metric"><span class="metric-label">Рекомендация</span><span class="metric-value">${{escapeHtml(tender.final_recommendation_label)}}</span></div>
              </div>
            `;
          }}

          function renderSteps(nodeId, steps, displayStatuses = null) {{
            const node = document.getElementById(nodeId);
            if (!steps.length) {{
              node.innerHTML = `<div class="empty">Шаги ещё не готовы.</div>`;
              return;
            }}
            node.innerHTML = steps.map((step) => {{
              const status = displayStatuses?.get(step.key) || step.status;
              return `
                <div class="step-card">
                  <div class="step-top">
                    <div>
                      <strong>#${{step.order}} · ${{escapeHtml(step.title)}}</strong>
                      <div class="run-meta">${{escapeHtml(step.result_summary)}}</div>
                    </div>
                    <span class="status-chip ${{statusClass(status)}}">${{escapeHtml(statusLabel(status))}}</span>
                  </div>
                  <p>${{escapeHtml(step.agent_action)}}</p>
                  <div class="split" style="margin-top:12px">
                    <div>
                      <div class="section-title">Что найдено</div>
                      <ul>${{step.findings.map((item) => `<li>${{escapeHtml(item)}}</li>`).join('')}}</ul>
                    </div>
                    <div>
                      <div class="section-title">Что проверить человеку</div>
                      <ul>${{step.human_review.map((item) => `<li>${{escapeHtml(item)}}</li>`).join('')}}</ul>
                    </div>
                  </div>
                  <div class="trace" style="margin-top:12px">${{escapeHtml(step.trace)}}</div>
                </div>
              `;
            }}).join('');
          }}

          function renderDatasetSummary(run) {{
            const finalRecommendation = run.final_recommendation;
            document.getElementById('dataset-summary').innerHTML = `
              <div class="step-top">
                <div>
                  <h2>Финальная рекомендация</h2>
                  <p>Рекомендация: ${{escapeHtml(finalRecommendation.label)}}.</p>
                </div>
                <a class="link-button" href="/demo/tender-agent/report" target="_blank" rel="noreferrer">Открыть синтетический отчёт</a>
              </div>
              <div class="split">
                <div class="card" style="padding:16px">
                  <div class="section-title">Причины</div>
                  <ul>${{finalRecommendation.rationale.map((item) => `<li>${{escapeHtml(item)}}</li>`).join('')}}</ul>
                </div>
                <div class="card" style="padding:16px">
                  <div class="section-title">Ручные проверки</div>
                  <ul>${{finalRecommendation.manual_checks.map((item) => `<li>${{escapeHtml(item)}}</li>`).join('')}}</ul>
                </div>
              </div>
              <div class="trace" style="margin-top:14px">${{escapeHtml(finalRecommendation.trace)}}</div>
            `;
          }}

          async function loadDataset() {{
            state.datasetRun = await fetchJson('/api/demo/tender-agent/run');
            state.datasetDisplayStatuses = new Map(state.datasetRun.steps.map((step) => [step.key, step.status]));
            renderDatasetTenderCard(state.datasetRun);
            renderSteps('dataset-steps', state.datasetRun.steps, state.datasetDisplayStatuses);
            renderDatasetSummary(state.datasetRun);
          }}

          async function replayDataset() {{
            if (!state.datasetRun || state.datasetReplayActive) {{
              return;
            }}
            state.datasetReplayActive = true;
            state.datasetDisplayStatuses = new Map(state.datasetRun.steps.map((step) => [step.key, 'pending']));
            renderSteps('dataset-steps', state.datasetRun.steps, state.datasetDisplayStatuses);
            for (const step of state.datasetRun.steps) {{
              state.datasetDisplayStatuses.set(step.key, 'running');
              renderSteps('dataset-steps', state.datasetRun.steps, state.datasetDisplayStatuses);
              await new Promise((resolve) => window.setTimeout(resolve, 220));
              state.datasetDisplayStatuses.set(step.key, step.status);
              renderSteps('dataset-steps', state.datasetRun.steps, state.datasetDisplayStatuses);
              await new Promise((resolve) => window.setTimeout(resolve, 120));
            }}
            state.datasetReplayActive = false;
          }}

          function renderRunsList() {{
            const node = document.getElementById('runs-list');
            if (!state.uploadedRuns.length) {{
              node.innerHTML = `<div class="empty">Пока нет загруженных прогонов.</div>`;
              return;
            }}
            node.innerHTML = state.uploadedRuns.map((run) => `
              <div class="run-item${{run.run_id === state.selectedRunId ? ' active' : ''}}" data-run-id="${{escapeHtml(run.run_id)}}">
                <strong>${{escapeHtml(run.tender_title)}}</strong>
                <div class="run-meta">${{escapeHtml(run.run_id)}} · ${{escapeHtml(statusLabel(run.status))}} · файлов=${{run.file_count}}</div>
                <div class="run-meta">${{escapeHtml(run.procurement_source || run.mode)}}${{run.attachments_status ? ` · ${{escapeHtml(attachmentsStatusLabel(run.attachments_status))}}` : ''}}</div>
              </div>
            `).join('');
            for (const item of node.querySelectorAll('.run-item')) {{
              item.addEventListener('click', () => selectRun(item.dataset.runId, true));
            }}
          }}

          function renderSelectedRun(run) {{
            const reportLinks = run.report_html_url
              ? `<a class="link-button" href="${{run.report_html_url}}" target="_blank" rel="noreferrer">Открыть HTML-отчёт</a>
                 <a class="link-button" href="${{run.report_download_url}}">Скачать артефакт отчёта</a>
                 <a class="link-button" href="/api/demo/tender-agent/runs/${{encodeURIComponent(run.run_id)}}/export/docx" target="_blank" rel="noreferrer">Скачать DOCX</a>
                 <a class="link-button" href="/api/demo/tender-agent/runs/${{encodeURIComponent(run.run_id)}}/export/pdf" target="_blank" rel="noreferrer">Скачать PDF</a>`
              : `<span class="note">HTML-отчёт будет доступен после анализа.</span>`;
            const needsDocs = run.status === 'docs_required';
            const eisBlock = run.procurement_source === 'zakupki_gov_ru_getdocs_ip' ? `
              <div class="card" style="padding:16px">
                <div class="section-title">Источник: ЕИС getDocsIP</div>
                <div class="grid-2">
                  <div class="metric"><span class="metric-label">Реестровый номер</span><span class="metric-value">${{escapeHtml(displayValue(run.procurement_notice_number || run.procurement_id))}}</span></div>
                  <div class="metric"><span class="metric-label">SOAP-метод</span><span class="metric-value">${{escapeHtml(displayValue(run.soap_method))}}</span></div>
                  <div class="metric"><span class="metric-label">ID запроса (refId)</span><span class="metric-value">${{escapeHtml(displayValue(run.eis_ref_id))}}</span></div>
                  <div class="metric"><span class="metric-label">Владелец токена</span><span class="metric-value">${{escapeHtml(displayValue(run.token_owner))}}</span></div>
                  <div class="metric"><span class="metric-label">URL архива (archiveUrl)</span><span class="metric-value">${{booleanLabel(run.archive_url_present)}}</span></div>
                  <div class="metric"><span class="metric-label">Архив скачан</span><span class="metric-value">${{booleanLabel(run.archive_downloaded)}}</span></div>
                  <div class="metric"><span class="metric-label">Статус скачивания</span><span class="metric-value">${{escapeHtml(displayValue(run.archive_download_status))}}</span></div>
                  <div class="metric"><span class="metric-label">Распаковано документов</span><span class="metric-value">${{escapeHtml(displayValue(run.documents_extracted_count, '0'))}}</span></div>
                  <div class="metric"><span class="metric-label">Источник архива</span><span class="metric-value">${{escapeHtml(displayValue(run.archive_source_host && run.archive_source_path ? `${{run.archive_source_host}}${{run.archive_source_path}}` : null))}}</span></div>
                </div>
                <div class="note" style="margin-top:12px">Полный archive URL и ticket не отображаются в UI.</div>
              </div>
            ` : '';
            const procurementBlock = run.procurement_source ? `
              <div class="card" style="padding:16px">
                <div class="section-title">Источник закупки</div>
                <div class="grid-2">
                  <div class="metric"><span class="metric-label">Источник</span><span class="metric-value">${{escapeHtml(displayValue(run.procurement_source))}}</span></div>
                  <div class="metric"><span class="metric-label">Номер извещения</span><span class="metric-value">${{escapeHtml(displayValue(run.procurement_notice_number || run.procurement_id))}}</span></div>
                  <div class="metric"><span class="metric-label">Закон</span><span class="metric-value">${{escapeHtml(displayValue(run.procurement_law, 'не указан'))}}</span></div>
                  <div class="metric"><span class="metric-label">Статус документации</span><span class="metric-value">${{escapeHtml(attachmentsStatusLabel(run.attachments_status))}}</span></div>
                  <div class="metric"><span class="metric-label">Скачано/добавлено файлов</span><span class="metric-value">${{run.downloaded_files_count || run.files.length}}</span></div>
                  <div class="metric"><span class="metric-label">Ручная загрузка</span><span class="metric-value">${{booleanLabel(run.manual_upload_required)}}</span></div>
                  <div class="metric"><span class="metric-label">Ссылка на источник</span><span class="metric-value"><a class="inline-link" href="${{escapeHtml(displayValue(run.procurement_url, '#'))}}" target="_blank" rel="noreferrer">Открыть источник</a></span></div>
                </div>
              </div>
            ` : '';
            const manualUploadBlock = needsDocs ? `
              <div class="card" style="padding:16px">
                <div class="section-title">Ручная загрузка документов</div>
                <p>Автоматическое получение документации недоступно для этой закупки. Загрузите документы вручную, после чего run перейдёт в статус «готово к анализу».</p>
                <form id="manual-upload-form">
                  <label>
                    Файлы закупки
                    <input name="files" type="file" multiple required />
                  </label>
                  <div class="form-actions">
                    <button class="button primary" type="submit">Добавить документы в run</button>
                  </div>
                </form>
              </div>
            ` : '';
            const eventItems = renderRunEventList(run.events);
            document.getElementById('selected-run-card').innerHTML = `
              <div class="step-top">
                <div>
                  <h2>${{escapeHtml(run.tender_title)}}</h2>
                  <p>${{escapeHtml(run.run_id)}} · ${{escapeHtml(statusLabel(run.status))}} · ${{escapeHtml(analysisModeLabel(run.analysis_mode))}}</p>
                </div>
                <div class="form-actions">
                  <button class="button primary" id="analyze-run-button" type="button"${{run.status === 'analyzing' || needsDocs ? ' disabled' : ''}}>Анализировать</button>
                </div>
              </div>
              <div class="grid-2">
                <div class="metric"><span class="metric-label">Категория</span><span class="metric-value">${{escapeHtml(run.tender_category)}}</span></div>
                <div class="metric"><span class="metric-label">Заказчик</span><span class="metric-value">${{escapeHtml(run.customer_name)}}</span></div>
                <div class="metric"><span class="metric-label">Файлов</span><span class="metric-value">${{run.files.length}}</span></div>
                <div class="metric"><span class="metric-label">Контроль человека</span><span class="metric-value">${{booleanLabel(run.human_in_the_loop)}}</span></div>
              </div>
              <div style="height:14px"></div>
              <div class="safety">
                <span>${{run.procurement_source ? 'Локальные и безопасно полученные публичные данные' : 'Только локально загруженные данные'}}</span>
                <span>Без внешних действий</span>
                <span>Без подачи на площадку</span>
                <span>Без отправки писем</span>
                <span>Без ЭЦП</span>
                <span>Требуется подтверждение человека</span>
              </div>
              <div style="height:14px"></div>
              <div class="split">
                <div>
                  <div class="section-title">Загруженные файлы</div>
                  <ul>${{run.files.map((item) => `<li>${{escapeHtml(item.display_name)}} · ${{escapeHtml(item.extension)}} · текст извлечён: ${{booleanLabel(item.extracted_text_available)}}</li>`).join('')}}</ul>
                </div>
                  <div>
                    <div class="section-title">Предупреждения и ограничения</div>
                    <ul>${{[...run.warnings, ...run.limitations].map((item) => `<li>${{escapeHtml(item)}}</li>`).join('')}}</ul>
                  </div>
                </div>
              <div style="height:14px"></div>
              ${{eisBlock}}
              <div style="height:14px"></div>
              ${{procurementBlock}}
              <div style="height:14px"></div>
              ${{manualUploadBlock}}
              <div style="height:14px"></div>
              <div class="form-actions">${{reportLinks}}</div>
              <div class="note" style="margin-top:12px">${{escapeHtml(run.uploaded_files_note || '')}}</div>
              <div style="height:14px"></div>
              <div class="card" style="padding:16px">
                <div class="section-title">Журнал работы агента</div>
                <ul class="event-list" id="run-events-list">${{eventItems || '<li class="event-item">Событий пока нет.</li>'}}</ul>
              </div>
              <div style="height:14px"></div>
              ${{renderQuoteSection(run)}}
              <div style="height:14px"></div>
              ${{renderEconomicsSection(run)}}
            `;
            const analyzeButton = document.getElementById('analyze-run-button');
            if (analyzeButton) {{
              analyzeButton.addEventListener('click', () => analyzeRun(run.run_id));
            }}
            const manualUploadForm = document.getElementById('manual-upload-form');
            if (manualUploadForm) {{
              manualUploadForm.addEventListener('submit', (event) => handleManualRunUpload(event, run.run_id));
            }}
            startRunEventsPolling(run.run_id);
          }}

          function renderSelectedRunSteps(run) {{
            if (!run.steps.length) {{
              document.getElementById('selected-run-steps').innerHTML = `
                <h2>Pipeline загруженного прогона</h2>
                <div class="empty">Пошаговый pipeline появится после запуска анализа.</div>
              `;
              return;
            }}
            const pipelineLabel = run.procurement_source
              ? 'Поиск закупки → Документация → Требования → Вопросы → RFQ → ТКП → Экономика → Риски → Решение'
              : 'Документы → Требования → Вопросы → RFQ → ТКП → Экономика → Риски → Решение';
            document.getElementById('selected-run-steps').innerHTML = `
              <div class="step-top">
                <div>
                  <h2>Pipeline загруженного прогона</h2>
                  <p>${{pipelineLabel}}</p>
                </div>
              </div>
              <div class="steps-list" id="uploaded-steps-body"></div>
            `;
            renderSteps('uploaded-steps-body', run.steps);
          }}

          function renderSelectedRunSummary(run) {{
            if (!run.final_recommendation) {{
              document.getElementById('selected-run-summary').innerHTML = `<div class="empty">Финальная рекомендация появится после завершения анализа.</div>`;
              return;
            }}
            const summary = run.final_recommendation;
            document.getElementById('selected-run-summary').innerHTML = `
              <div class="step-top">
                <div>
                  <h2>Финальная рекомендация</h2>
                  <p>Рекомендация: ${{escapeHtml(summary.label)}}.</p>
                </div>
                <span class="status-chip ${{statusClass(run.status)}}">${{escapeHtml(statusLabel(run.status))}}</span>
              </div>
              <div class="split">
                <div class="card" style="padding:16px">
                  <div class="section-title">Причины</div>
                  <ul>${{summary.rationale.map((item) => `<li>${{escapeHtml(item)}}</li>`).join('')}}</ul>
                </div>
                <div class="card" style="padding:16px">
                  <div class="section-title">Ручные проверки</div>
                  <ul>${{summary.manual_checks.map((item) => `<li>${{escapeHtml(item)}}</li>`).join('')}}</ul>
                </div>
                <div class="card" style="padding:16px">
                  <div class="section-title">Открытые вопросы</div>
                  <ul>${{summary.open_questions.map((item) => `<li>${{escapeHtml(item)}}</li>`).join('')}}</ul>
                </div>
                <div class="card" style="padding:16px">
                  <div class="section-title">Риски</div>
                  <ul>${{summary.risks.map((item) => `<li>${{escapeHtml(item)}}</li>`).join('')}}</ul>
                </div>
              </div>
              <div class="trace" style="margin-top:14px">${{escapeHtml(summary.trace)}}</div>
            `;
          }}

          async function loadRuns() {{
            const payload = await fetchJson('/api/demo/tender-agent/runs');
            state.uploadedRuns = payload.runs || [];
            renderRunsList();
            if (state.selectedRunId) {{
              const exists = state.uploadedRuns.some((item) => item.run_id === state.selectedRunId);
              if (exists) {{
                await selectRun(state.selectedRunId, false);
              }}
            }}
          }}

          async function selectRun(runId, switchTab) {{
            state.selectedRunId = runId;
            renderRunsList();
            const run = await fetchJson(`/api/demo/tender-agent/runs/${{encodeURIComponent(runId)}}`);
            renderSelectedRun(run);
            renderSelectedRunSteps(run);
            renderSelectedRunSummary(run);
            if (switchTab) {{
              document.querySelector('[data-tab="upload"]').click();
            }}
            if (window.history?.replaceState) {{
              window.history.replaceState(null, '', `/demo/tender-agent/runs/${{encodeURIComponent(runId)}}`);
            }}
          }}

          async function analyzeRun(runId) {{
            setFlash('upload-flash', `Запускаем анализ для ${{runId}}…`);
            try {{
              const payload = await fetchJson(`/api/demo/tender-agent/runs/${{encodeURIComponent(runId)}}/analyze`, {{
                method: 'POST',
              }});
              setFlash('upload-flash', `Анализ завершён: статус «${{statusLabel(payload.status)}}», режим «${{analysisModeLabel(payload.analysis_mode)}}».`);
              await loadRuns();
              await selectRun(runId, false);
            }} catch (error) {{
              setFlash('upload-flash', `Анализ не запущен: ${{error.message}}`, true);
            }}
          }}

          async function handleManualRunUpload(event, runId) {{
            event.preventDefault();
            setFlash('upload-flash', `Добавляем документы в run ${{runId}}…`);
            const form = event.currentTarget;
            const data = new FormData(form);
            try {{
              const response = await fetch(`/api/demo/tender-agent/runs/${{encodeURIComponent(runId)}}/files`, {{
                method: 'POST',
                body: data,
              }});
              if (!response.ok) {{
                let detail = `HTTP ${{response.status}}`;
                try {{
                  const payload = await response.json();
                  detail = payload.detail || detail;
                }} catch (_error) {{
                }}
                throw new Error(detail);
              }}
              const payload = await response.json();
              setFlash('upload-flash', `Документы добавлены. Новый статус: ${{statusLabel(payload.status)}}.`);
              await loadRuns();
              await selectRun(runId, false);
            }} catch (error) {{
              setFlash('upload-flash', `Не удалось добавить документы: ${{error.message}}`, true);
            }}
          }}

          async function handleUpload(event) {{
            event.preventDefault();
            clearFlash('upload-flash');
            const form = event.currentTarget;
            const data = new FormData(form);
            try {{
              const response = await fetch('/api/demo/tender-agent/runs', {{
                method: 'POST',
                body: data,
              }});
              if (!response.ok) {{
                let detail = `HTTP ${{response.status}}`;
                try {{
                  const payload = await response.json();
                  detail = payload.detail || detail;
                }} catch (_error) {{
                }}
                throw new Error(detail);
              }}
              const payload = await response.json();
              setFlash('upload-flash', `Создан демонстрационный прогон: ${{payload.run_id}}. Теперь можно запускать анализ.`);
              form.reset();
              await loadRuns();
              await selectRun(payload.run_id, true);
            }} catch (error) {{
              setFlash('upload-flash', `Не удалось создать прогон: ${{error.message}}`, true);
            }}
          }}

          async function handleCheckReadiness() {{
            clearFlash('analysis-flash');
            const rn = document.querySelector('#analysis-form [name="registry_number"]').value.trim();
            if (!rn) {{ setFlash('analysis-flash', 'Введите реестровый номер.', true); return; }}
            const statusNode = document.getElementById('analysis-readiness-status');
            const stepsNode = document.getElementById('analysis-preparation-steps');
            stepsNode.classList.add('hidden');
            stepsNode.innerHTML = '';
            statusNode.innerHTML = '<div class="note">Проверяем готовность…</div>';
            try {{
              const data = await fetchJson('/api/tender-research/prepare/' + encodeURIComponent(rn) + '/status');
              if (!data.tender_found) {{
                statusNode.innerHTML = '<div class="note" style="color:var(--warning)">⚠ Закупка не найдена в БД. Нажмите «Подготовить закупку к анализу» для загрузки.</div>';
                document.getElementById('prepare-tender-btn').disabled = false;
                return;
              }}
              const ready = data.ready_for_analysis;
              let html = '<div class="grid-2" style="margin-bottom:8px">';
              html += '<div class="metric"><span class="metric-label">Документов</span><span class="metric-value">' + data.documents_total + '</span></div>';
              html += '<div class="metric"><span class="metric-label">Загружено</span><span class="metric-value">' + data.documents_downloaded + '</span></div>';
              html += '<div class="metric"><span class="metric-label">Текстов</span><span class="metric-value">' + data.extracted_texts_total + '</span></div>';
              html += '<div class="metric"><span class="metric-label">Чанков</span><span class="metric-value">' + data.chunks_total + '</span></div>';
              html += '<div class="metric"><span class="metric-label">Эмбеддингов</span><span class="metric-value">' + data.embeddings_total + '</span></div>';
              html += '</div>';
              if (ready) {{
                html += '<div class="note" style="color:var(--success)">✓ Закупка готова к анализу</div>';
              }} else {{
                const missing = (data.missing || []).join(', ');
                html += '<div class="note" style="color:var(--warning)">⚠ Закупка не полностью подготовлена. Отсутствует: ' + escapeHtml(missing || 'неизвестно') + '.</div>';
              }}
              statusNode.innerHTML = html;
              document.getElementById('prepare-tender-btn').disabled = ready || data.missing.length === 0;
              statusNode.className = '';
            }} catch (error) {{
              statusNode.innerHTML = '<div class="note" style="color:var(--danger)">✗ Ошибка проверки: ' + escapeHtml(error.message) + '</div>';
            }}
          }}

          async function handlePrepareTender() {{
            clearFlash('analysis-flash');
            const rn = document.querySelector('#analysis-form [name="registry_number"]').value.trim();
            if (!rn) {{ setFlash('analysis-flash', 'Введите реестровый номер.', true); return; }}
            const runtime = renderAnalysisRuntimeSummary();
            const stepsNode = document.getElementById('analysis-preparation-steps');
            const statusNode = document.getElementById('analysis-readiness-status');
            stepsNode.classList.remove('hidden');
            stepsNode.innerHTML = '<div class="note">Подготовка будет выполнена в фоне…</div>';
            statusNode.innerHTML = '<div class="note">Создаём background job…</div>';
            document.getElementById('prepare-tender-btn').disabled = true;
            try {{
              const job = await fetchJson('/api/tender-research/jobs/prepare', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{
                  registry_number: rn,
                  provider: runtime.provider,
                  model: runtime.model,
                  base_url: runtime.base_url,
                  rebuild_chunks: false,
                  rebuild_embeddings: false,
                }}),
              }});
              state.activeAnalysisRuntime = runtime;
              renderAnalysisJobStatus({{
                id: job.job_id,
                job_type: job.job_type,
                registry_number: job.registry_number,
                status: job.status,
                progress_percent: 0,
                current_step: 'queued',
                steps: [],
                warnings: [],
                errors: [],
                source: 'api',
              }});
              statusNode.innerHTML = '<div class="note">Фоновая задача создана. Обновляем статус…</div>';
              startAnalysisJobPolling(job.job_id, rn);
            }} catch (error) {{
              stepsNode.innerHTML = '<div class="note" style="color:var(--danger)">✗ Ошибка подготовки: ' + escapeHtml(error.message) + '</div>';
              document.getElementById('prepare-tender-btn').disabled = false;
            }}
          }}

          async function handleAnalysisForm(event) {{
            event.preventDefault();
            clearFlash('analysis-flash');
            const form = event.currentTarget;
            const data = new FormData(form);
            const registryNumber = String(data.get('registry_number') || '').trim();
            if (!registryNumber) {{
              setFlash('analysis-flash', 'Введите реестровый номер.', true);
              return;
            }}
            const runtime = renderAnalysisRuntimeSummary();
            setFlash('analysis-flash', `Создаём задачу анализа для ${{registryNumber}}…`);
            try {{
              const payload = {{
                registry_number: registryNumber,
                provider: runtime.provider,
                model: runtime.model,
                base_url: runtime.base_url,
                use_llm: runtime.use_llm,
                analysis_mode: runtime.analysis_mode,
                limit: runtime.limit,
                save_report: runtime.save_report,
              }};
              if (runtime.use_llm) {{
                payload.llm_base_url = runtime.llm_base_url;
                payload.llm_model = runtime.llm_model;
              }}
              const job = await fetchJson('/api/tender-research/jobs/analyze', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify(payload),
              }});
              state.activeAnalysisRuntime = runtime;
              renderAnalysisJobStatus({{
                id: job.job_id,
                job_type: job.job_type,
                registry_number: job.registry_number,
                status: job.status,
                progress_percent: 0,
                current_step: 'queued',
                steps: [],
                warnings: [],
                errors: [],
                source: 'api',
              }});
              document.getElementById('analysis-result').innerHTML = '<div class="empty">Фоновая задача анализа создана. Ожидаем результат…</div>';
              document.getElementById('analysis-result').className = '';
              startAnalysisJobPolling(job.job_id, registryNumber);
            }} catch (error) {{
              setFlash('analysis-flash', 'Ошибка анализа: ' + escapeHtml(error.message), true);
            }}
          }}

          async function handleRefreshHistory(registryNumber) {{
            const rn = registryNumber || String(document.querySelector('#analysis-form [name=registry_number]').value || '').trim();
            const listNode = document.getElementById('history-list');
            const containerNode = document.getElementById('history-report-container');
            containerNode.className = 'hidden';
            try {{
              const url = '/api/tender-research/analyze/history?limit=20' + (rn ? '&registry_number=' + encodeURIComponent(rn) : '');
              const data = await fetchJson(url);
              if (!data.items || data.items.length === 0) {{
                listNode.innerHTML = '<div class="empty">Пока нет сохранённых анализов.</div>';
                listNode.className = '';
                return;
              }}
              let html = '<table style="width:100%;border-collapse:collapse;font-size:0.9em">';
              html += '<thead><tr style="border-bottom:1px solid var(--border)"><th>Дата</th><th>Номер</th><th>Статус</th><th>Разделов</th><th>Источников</th><th>LLM</th><th></th></tr></thead><tbody>';
              for (const item of data.items) {{
                const date = item.created_at ? new Date(item.created_at).toLocaleString('ru-RU') : '—';
                const statusColor = item.status === 'completed' ? 'var(--success)' : 'var(--warning)';
                const reportUrl = '/api/tender-research/analyze/history/' + encodeURIComponent(item.id) + '/report';
                const docxUrl = '/api/tender-research/analyze/history/' + encodeURIComponent(item.id) + '/export/docx';
                const pdfUrl = '/api/tender-research/analyze/history/' + encodeURIComponent(item.id) + '/export/pdf';
                html += '<tr style="border-bottom:1px solid var(--border)">';
                html += '<td style="padding:6px 8px">' + escapeHtml(date) + '</td>';
                html += '<td style="padding:6px 8px">' + escapeHtml(item.registry_number) + '</td>';
                html += '<td style="padding:6px 8px;color:' + statusColor + '">' + escapeHtml(item.status) + '</td>';
                html += '<td style="padding:6px 8px;text-align:center">' + item.sections_count + '</td>';
                html += '<td style="padding:6px 8px;text-align:center">' + item.sources_count + '</td>';
                html += '<td style="padding:6px 8px;text-align:center">' + (item.used_llm ? 'да' : 'нет') + '</td>';
                html += '<td style="padding:6px 8px"><div style="display:flex;gap:6px;flex-wrap:wrap"><button class="button button-small history-open-report" data-run-id="' + escapeHtml(item.id) + '" data-report-url="' + escapeHtml(reportUrl) + '">Открыть отчёт</button><a class="link-button button-small" href="' + escapeHtml(docxUrl) + '" target="_blank" rel="noreferrer">Скачать DOCX</a><a class="link-button button-small" href="' + escapeHtml(pdfUrl) + '" target="_blank" rel="noreferrer">Скачать PDF</a></div></td>';
                html += '</tr>';
              }}
              html += '</tbody></table>';
              html += '<div style="margin-top:8px;font-size:0.85em;opacity:0.7">Всего записей: ' + data.total + '</div>';
              listNode.innerHTML = html;
              listNode.querySelectorAll('.history-open-report').forEach(function(button) {{
                button.addEventListener('click', function() {{
                  handleOpenHistoryReport(button.dataset.runId || '');
                }});
              }});
              listNode.className = '';
            }} catch (error) {{
              listNode.innerHTML = '<div class="note" style="color:var(--danger)">✗ Ошибка загрузки истории: ' + escapeHtml(error.message) + '</div>';
            }}
          }}

          async function handleOpenHistoryReport(runId) {{
            const containerNode = document.getElementById('history-report-container');
            const contentNode = document.getElementById('history-report-content');
            containerNode.className = '';
            contentNode.innerHTML = '<div class="empty">Загрузка отчёта…</div>';
            try {{
              const data = await fetchJson('/api/tender-research/analyze/history/' + encodeURIComponent(runId) + '/report');
              if (!data.report_markdown) {{
                contentNode.innerHTML = '<div class="note" style="color:var(--warning)">⚠ Метаданные запуска найдены, но файл отчёта недоступен.</div>';
                return;
              }}
              contentNode.innerHTML = '<pre style="white-space:pre-wrap;font-size:0.85em;max-height:600px;overflow-y:auto;border:1px solid var(--border);padding:12px;border-radius:6px;">' + escapeHtml(data.report_markdown) + '</pre>';
            }} catch (error) {{
              contentNode.innerHTML = '<div class="note" style="color:var(--danger)">✗ ' + escapeHtml(error.message) + '</div>';
            }}
          }}

          async function bootstrap() {{
            wireTabs();
            document.getElementById('check-readiness-btn').addEventListener('click', handleCheckReadiness);
            document.getElementById('prepare-tender-btn').addEventListener('click', handlePrepareTender);
            document.getElementById('analysis-form').addEventListener('submit', handleAnalysisForm);
            document.getElementById('history-refresh-btn').addEventListener('click', function() {{ handleRefreshHistory(); }});
            document.getElementById('analysis-runtime-preset').addEventListener('change', applyAnalysisPreset);
            document.querySelector('#analysis-form [name="analysis_mode"]').addEventListener('change', renderAnalysisRuntimeSummary);
            document.querySelector('#analysis-form [name="use_llm"]').addEventListener('change', renderAnalysisRuntimeSummary);
            document.querySelector('#analysis-form [name="save_report"]').addEventListener('change', renderAnalysisRuntimeSummary);
            document.querySelector('#analysis-form [name="registry_number"]').addEventListener('change', function(event) {{
              handleRefreshHistory(event.currentTarget.value.trim());
            }});
            document.getElementById('procurement-search-form').addEventListener('submit', handleProcurementSearch);
            document.getElementById('eis-docs-form').addEventListener('submit', handleEisDocsArchive);
            document.getElementById('replay-dataset').addEventListener('click', replayDataset);
            document.getElementById('upload-form').addEventListener('submit', handleUpload);
            const resetBtn = document.getElementById('reset-supplier-profile');
            if (resetBtn) resetBtn.addEventListener('click', resetSupplierProfile);
            applyAnalysisPreset();
            await loadProcurementSources();
            await loadDataset();
            await loadRuns();
            if (state.selectedRunId) {{
              document.querySelector('[data-tab="upload"]').click();
            }}
            await handleProcurementSearch({{
              preventDefault() {{}},
              currentTarget: document.getElementById('procurement-search-form'),
            }});
          }}

          bootstrap().catch((error) => {{
            document.getElementById('dataset-tender-card').innerHTML = `<div class="empty">Не удалось загрузить демонстрационный интерфейс: ${{escapeHtml(error.message)}}</div>`;
          }});
        </script>
      </body>
    </html>
    """
