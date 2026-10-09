/* APR-03B. Every substantive value is fetched from the running Tender Agent; no mock fallbacks. */
(() => {
  'use strict';
  const api = '/api/demo/tender-agent';
  const state = { runId: null, poll: null, busy: false, registryOffset: 0, registryTotal: 0, registryQuery: '', runReady: false, searchParams: null, searchCursor: null, seenNumbers: [] };
  const $ = id => document.getElementById(id);
  const node = (tag, cls = '', content = null) => {
    const el = document.createElement(tag);
    if (cls) el.className = cls;
    if (content !== null && content !== undefined) el.textContent = String(content);
    return el;
  };
  const wipe = target => target.replaceChildren();
  const show = (id, yes = true) => { $(id).hidden = !yes; };
  const date = value => {
    if (!value) return 'Не указано';
    const d = new Date(value);
    return Number.isNaN(d.getTime()) ? String(value) : new Intl.DateTimeFormat('ru-RU', {dateStyle:'medium', timeStyle:'short'}).format(d);
  };
  const money = (value, currency = 'RUB') => value === undefined || value === null
    ? 'Не указано' : new Intl.NumberFormat('ru-RU',{ maximumFractionDigits: 2 }).format(Number(value)) + ' ' + (currency === 'RUB' ? '₽' : (currency || ''));
  function msg(text) {
    const toast = $('toast');
    toast.textContent = String(text);
    toast.hidden = false;
    clearTimeout(msg.timeout);
    msg.timeout = setTimeout(() => { toast.hidden = true; }, 8000);
  }
  async function json(path, options) {
    const res = await fetch(path, { credentials: 'same-origin', cache: 'no-store', ...options });
    if (!res.ok) {
      let detail = 'Ошибка HTTP ' + res.status;
      try {
        const payload = await res.json();
        detail = typeof payload.detail === 'string' ? payload.detail : detail;
      } catch (_) { /* non-JSON backend failure */ }
      throw new Error(detail);
    }
    return res.json();
  }
  function progress(active, title, description = '') {
    show('progress', active);
    if (title) $('progress-title').textContent = title;
    $('progress-description').textContent = description;
  }
  function setBusy(value) {
    state.busy = value;
    $('import-btn').disabled = value;
    $('analyze-btn').disabled = value || !state.runReady;
    $('refresh-run').disabled = value;
    $('search-submit').disabled = value;
    $('search-next').disabled = value;
    $('append-files-button').disabled = value;
  }
  function tab(name) {
    const labels = {new:'Новый анализ',history:'История анализов',registry:'База закупок'};
    if (!(name in labels)) return;
    for (const key of Object.keys(labels)) show('pane-' + key, key === name);
    for (const button of document.querySelectorAll('.nav-btn')) {
      button.classList.toggle('active', button.dataset.tab === name);
      button.setAttribute('aria-current', button.dataset.tab === name ? 'page' : 'false');
    }
    $('current-tab').textContent = labels[name];
    if (name === 'history') void loadHistory();
    if (name === 'registry') void loadRegistry();
    window.history.replaceState(null, '', name === 'new' ? '/pilot/tender-agent/workspace' : '/pilot/tender-agent/workspace#' + name);
  }
  const appendFact = (container, name, value) => {
    const wrapper = node('div','fact');
    wrapper.append(node('span','',name), node('strong','', value === null || value === undefined || value === '' ? 'Не указано' : value));
    container.append(wrapper);
  };
  function link(href, label, className = '') {
    const a = node('a', className, label);
    a.href = href;
    return a;
  }
  function trustedEis(url) {
    try {
      const u = new URL(url);
      return u.protocol === 'https:' && ['zakupki.gov.ru','www.zakupki.gov.ru'].includes(u.hostname) && !u.username && !u.password && !u.port;
    } catch (_) { return false; }
  }
  const isReadyForAnalysis = run => (run.files?.length || run.file_count || 0) > 0 && ['ready_to_analyze','uploaded','docs_required'].includes(run.status);
  const paragraph = (container, text, className = '') => container.append(node('p', className, text));
  function searchParams() {
    const params = new URLSearchParams({
      query: $('search-query').value.trim(),
      law: $('search-law').value,
      max_results: '10',
      page_size: '10',
      page: '1',
    });
    const fields = [
      ['search-region','region'], ['search-status','status_filter'],
      ['search-procedure','procedure_type'],
      ['search-price-from','price_from'],['search-price-to','price_to'],
      ['search-date-from','date_from'], ['search-date-to','date_to'],
      ['search-deadline-from','deadline_from'], ['search-deadline-to','deadline_to'],
    ];
    for (const [element,key] of fields) {
      const value = $(element).value.trim();
      if (value) params.set(key,value);
    }
    return params;
  }
  async function searchProcurements(event) {
    event.preventDefault();
    if (state.busy) return;
    const params=searchParams();
    if (!params.get('query')) return msg('Укажите ключевые слова поиска.');
    state.searchParams=params;
    state.seenNumbers=[];
    await loadSearchPage(null);
  }
  async function loadSearchPage(cursor) {
    if (state.busy || !state.searchParams) return;
    setBusy(true);
    const label=$('search-status-message');
    label.textContent = 'Ищем реальные закупки по заданным фильтрам…';
    wipe($('search-results'));
    show('search-pagination',false);
    try {
      const params=new URLSearchParams(state.searchParams);
      if(cursor) params.set('cursor',cursor);
      if(state.seenNumbers.length) params.set('seen_registry_numbers',JSON.stringify(state.seenNumbers));
      const data = await json(api+'/procurement/public-44fz-search?'+params.toString(),{method:'POST'});
      const root=$('search-results');
      const outcome=String(data.outcome||'');
      const cards=Array.isArray(data.cards)?data.cards:[];
      label.textContent=data.message || (outcome==='success_empty'?'Совпадений не найдено.':'Поиск завершён: '+outcome);
      if(data.warnings?.length) label.textContent+=' · '+data.warnings[0];
      if(data.eis_search_url && trustedEis(data.eis_search_url)){
        const a=link(data.eis_search_url,'Посмотреть поиск на сайте ЕИС ↗');
        a.target='_blank';a.rel='noopener noreferrer';label.append(' · ',a);
      }
      if(outcome!=='success_with_results'&&outcome!=='success_empty') msg('Источник поиска не подтвердил результаты: '+label.textContent);
      for(const card of cards){
        const number=String(card.reestr_number||card.notice_number||'');
        const supportedLaw=String(card.law||params.get('law'))!=='capital_repair';
        const plausible=supportedLaw && /^(\d{11}|\d{19})$/.test(number);
        const item=node('article','eis-search-item'),left=node('div');
        left.append(node('small','',number+' · '+(card.law||params.get('law'))));
        left.append(node('h3','',card.title||'Наименование не подтверждено'));
        left.append(node('p','',card.customer_name||'Заказчик не указан'));
        left.append(node('p','',[money(card.initial_price,card.currency),card.deadline?'Срок: '+card.deadline:'Срок не указан',card.status||''].join(' · ')));
        if(card.source_url&&trustedEis(card.source_url)){
          const a=link(card.source_url,'Оригинальное извещение ↗');a.target='_blank';a.rel='noopener noreferrer';left.append(a);
        }
        const button=node('button','button button-primary','Скачать и проанализировать →');
        button.type='button';button.disabled=!plausible;
        if(!supportedLaw) button.textContent='Капремонт: анализ пока недоступен';
        button.addEventListener('click',()=>{ $('reference').value=number;void runSelectedReference(number); });
        item.append(left,button);root.append(item);
        if(plausible&&!state.seenNumbers.includes(number)) state.seenNumbers.push(number);
      }
      if(!cards.length) paragraph(root,'Нет подтверждённых карточек. Попробуйте изменить запрос или фильтры.','empty-state');
      const cursorNext=data.next_cursor;
      state.searchCursor=(data.has_more&&cursorNext)?cursorNext:null;
      $('search-count').textContent = (data.total_count_exact_for_displayed_filters && Number.isInteger(data.total_count))
        ? 'Найдено в ЕИС: '+data.total_count : 'Показано карточек: '+cards.length;
      show('search-pagination',cards.length>0||Boolean(state.searchCursor));
      $('search-next').hidden=!state.searchCursor;
    }catch(error){label.textContent='Поиск недоступен: '+error.message;msg(label.textContent);}
    finally{setBusy(false);}
  }

  async function runSelectedReference(reference) {
    if (state.busy) return;
    setBusy(true);
    progress(true,'Скачиваем документацию ЕИС','Это могут быть XML, PDF, DOC, DOCX, XLS и другие оригинальные файлы. Не закрывайте вкладку.');
    try {
      const result=await json(api+'/workspace/import',{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({reference})
      });
      if(!result.run_id) throw new Error('Источник не вернул идентификатор запуска');
      state.runId=result.run_id;
      tab('new');
      const run=await loadRun();
      if(isReadyForAnalysis(run)){
        progress(true,'Анализируем реально скачанные документы','Формируем требования, риски и отчёт с указанием первоисточников.');
        state.poll=setInterval(()=>{void loadEvents();},3500);
        await json(api+'/runs/'+encodeURIComponent(state.runId)+'/analyze',{method:'POST'});
        const finished=await loadRun();
        if(!['completed','completed_with_warnings','needs_review'].includes(finished.status)){
          throw new Error('Запуск не достиг завершённого состояния: '+finished.status);
        }
        msg('Документы обработаны. Проверьте цитаты, неподтверждённые факты и результаты ниже.');
        $('run-section').scrollIntoView({behavior:'smooth',block:'start'});
      }else if(!run.files?.length){
        msg('Список вложений не является скачанными документами. ЕИС не отдала файлы; анализ не запускался. Загрузите оригиналы вручную.');
      }else{
        msg('Автоматический анализ невозможен в статусе '+run.status+'. Проверьте ограничения и доступность файлов.');
      }
    }catch(error){
      msg('Обработка не завершилась: '+error.message+'; сохранённый запуск доступен в истории.');
      if(state.runId) await loadRun().catch(()=>{});
    }finally{
      if(state.poll) clearInterval(state.poll);
      state.poll=null;
      progress(false);
      setBusy(false);
    }
  }
  async function importRequest(event) {
    event.preventDefault();
    const reference=$('reference').value.trim();
    if(!reference) return msg('Введите номер или официальную HTTPS-ссылку на извещение.');
    await runSelectedReference(reference);
  }
  async function appendMissingFiles(event) {
    event.preventDefault();
    const files=$('append-files').files;
    if(!state.runId||!files.length||state.busy) return msg('Выберите подлинные файлы документации.');
    const form=new FormData();
    for(const file of files) form.append('files',file,file.name);
    setBusy(true);progress(true,'Загружаем недостающие документы','Сохраняем файлы в текущем запуске.');
    try{
      await json(api+'/runs/'+encodeURIComponent(state.runId)+'/files',{method:'POST',body:form});
      const run=await loadRun();
      if(!isReadyForAnalysis(run)){
        msg('Файлы сохранены, но анализ ещё недоступен: '+run.status);
        return;
      }
      progress(true,'Анализируем добавленные документы');
      await json(api+'/runs/'+encodeURIComponent(state.runId)+'/analyze',{method:'POST'});
      await loadRun();
      msg('Файлы добавлены, анализ запущен и результат сохранён.');
    }catch(error){msg('Загрузка/анализ не завершились: '+error.message);await loadRun().catch(()=>{});}
    finally{progress(false);setBusy(false);}
  }
  async function loadRun() {
    if (!state.runId) return;
    const id = encodeURIComponent(state.runId);
    const run = await json(api + '/runs/' + id);
    show('run-empty', false);
    show('run-section', true);
    $('run-status').textContent = run.status || 'неизвестен';
    $('run-status').className = 'tag ' + (run.status === 'failed' ? 'danger' : (run.status === 'completed_with_warnings' || run.warnings?.length ? 'warning' : ''));
    $('run-id').textContent = 'Run · ' + state.runId + ' · ' + date(run.created_at);
    $('run-title').textContent = run.tender_title || run.procurement_notice_number || 'Закупка ЕИС';
    wipe($('run-facts'));
    appendFact($('run-facts'), 'Реестровый номер', run.procurement_notice_number || run.procurement_id || 'UNKNOWN');
    appendFact($('run-facts'), 'Правовой режим', run.procurement_law || 'UNKNOWN');
    appendFact($('run-facts'), 'Заказчик', run.customer_name || 'UNKNOWN');
    appendFact($('run-facts'), 'Файлов', run.files?.length ?? run.file_count ?? 0);
    appendFact($('run-facts'), 'Документы ЕИС', run.attachments_status || 'UNKNOWN');
    appendFact($('run-facts'), 'Проверка человека', run.human_in_the_loop ? 'Обязательна' : 'НЕ ПОДТВЕРЖДЕНО');
    state.runReady = isReadyForAnalysis(run);
    $('analyze-btn').disabled = state.busy || !state.runReady;
    $('analyze-btn').textContent = isReadyForAnalysis(run) ? 'Запустить анализ загруженных файлов' : 'Анализ недоступен / уже выполнен';
    show('append-files-form',['docs_required','ready_to_analyze','uploaded'].includes(run.status));
    const source = $('source-link');
    source.hidden = !trustedEis(run.procurement_url);
    if (!source.hidden) source.href = run.procurement_url;
    wipe($('run-warnings'));
    for (const warning of [...(run.warnings || []),...(run.limitations || [])].slice(0,8)) paragraph($('run-warnings'), '⚠ ' + warning);
    renderFiles(run);
    await loadEvents();
    await loadReport(run);
    return run;
  }
  function renderFiles(run) {
    const root = $('file-list');
    wipe(root);
    const files = run.files || [];
    $('document-count').textContent = String(files.length);
    if (!files.length) return paragraph(root, 'ЕИС не предоставила скачиваемых файлов. Наличие списка вложений не подтверждает загрузку. Добавьте оригинальные документы вручную ниже.', 'empty-state');
    for (const file of files) {
      const item = node('div','file-item');
      const head = node('div');
      head.append(node('strong','',file.display_name || file.original_name || 'Документ'));
      head.append(node('small','',(file.extracted_text_available ? 'Текст извлечён' : 'Текст не подтверждён') + ' · ' + (file.extension || 'файл') + ' · ' + Math.ceil((file.size_bytes||0)/1024) + ' КБ'));
      item.append(head);
      if (file.file_id) item.append(link(api + '/runs/' + encodeURIComponent(state.runId) + '/files/' + encodeURIComponent(file.file_id) + '/download', 'Скачать ↓'));
      root.append(item);
    }
  }
  async function loadEvents() {
    if (!state.runId) return;
    const root = $('event-list');
    try {
      const events = await json(api + '/runs/' + encodeURIComponent(state.runId) + '/events');
      wipe(root);
      $('event-count').textContent = String(events.length);
      for (const event of events.slice(-35).reverse()) {
        const li = node('li','event-item ' + (event.severity === 'warning' ? 'warning' : ''));
        li.append(node('strong','',event.step || event.event_type || 'Этап'));
        paragraph(li, event.message_ru || event.message || event.event_type);
        li.append(node('small','',date(event.timestamp)));
        root.append(li);
      }
      if (!events.length) paragraph(root, 'События пока отсутствуют.', 'empty-state');
    } catch (error) { msg('Не удалось загрузить этапы: ' + error.message); }
  }
  async function analyze() {
    if (!state.runId || state.busy) return;
    setBusy(true);
    progress(true,'Анализируем реальные документы','Результат может формироваться несколько минут; ниже обновляется журнал обработки.');
    state.poll = setInterval(() => { void loadEvents(); }, 3500);
    try {
      const result = await json(api + '/runs/' + encodeURIComponent(state.runId) + '/analyze', {method:'POST'});
      progress(false);
      await loadRun();
      msg(result.warnings?.length ? 'Анализ завершён с замечаниями. Проверьте UNKNOWN и источники.' : 'Анализ завершён. Откройте результаты и доказательства.');
    } catch (error) { progress(false); msg('Не удалось завершить анализ: ' + error.message); await loadRun(); }
    finally { clearInterval(state.poll); state.poll = null; setBusy(false); }
  }
  const summaryList = (container, values) => {
    if (!Array.isArray(values) || !values.length) return;
    const list = node('ul');
    for (const value of values) list.append(node('li','',typeof value === 'string' ? value : JSON.stringify(value)));
    container.append(list);
  };
  const validCitations = values => Array.isArray(values)
    ? values.filter(c => c && c.source_ref && c.document && c.locator)
    : [];
  function renderCitations(container, citations) {
    const trusted = validCitations(citations);
    if (!trusted.length) return paragraph(container, 'UNKNOWN · Нет подтверждённой цитаты', 'unknown');
    for (const c of trusted.slice(0,8)) {
      const text = [c.document,c.locator,c.excerpt].filter(Boolean).join(' · ');
      paragraph(container, 'Источник: ' + text, 'citation');
    }
  }
  function renderEvidence(report, verifiedEvidence) {
    const root = $('evidence-facts');
    wipe(root);
    const core = report.decision_core || {};
    const facts = verifiedEvidence?.facts || {};
    const fields = Object.keys(facts);
    if (!fields.length) paragraph(root, 'Факты из исходного XML недоступны; требуется проверка.', 'empty-state');
    const section = node('section','report-section');
    section.append(node('h3','','Факты из оригинального XML ЕИС'));
    for (const field of fields.slice(0,28)) {
      const f = facts[field];
      if (!f || typeof f !== 'object') continue;
      const block = node('div','evidence-item');
      const verified = f.status === 'KNOWN' && validCitations(f.evidence).length > 0;
      block.append(node('strong','',field + ' · ' + (verified ? String(f.value) : 'UNKNOWN')));
      renderCitations(block, verified ? f.evidence : []);
      section.append(block);
    }
    root.append(section);
    for (const warning of verifiedEvidence?.warnings || []) paragraph(root, '⚠ ' + warning, 'unknown');
    for (const key of ['blockers','unknowns','readiness']) {
      if (!Array.isArray(core[key]) || !core[key].length) continue;
      const sub = node('section','report-section');
      sub.append(node('h3','',({blockers:'Блокирующие риски',unknowns:'Неизвестные сведения',readiness:'Проверка готовности'})[key]));
      for (const item of core[key].slice(0,25)) {
        const block = node('div','evidence-item');
        const grounded = validCitations(item.evidence).length > 0;
        paragraph(block, (item.summary || item.label || item.code || 'Риск') + ' · ' + (grounded ? item.status : 'UNKNOWN · требуется подтверждение'));
        renderCitations(block, item.evidence);
        sub.append(block);
      }
      root.append(sub);
    }
  }
  function renderSections(report) {
    const root = $('report-sections');
    wipe(root);
    for (const section of report.sections || []) {
      const block = node('section','report-section');
      block.append(node('h3','',section.title || 'Раздел'));
      if (Array.isArray(section.items)) summaryList(block,section.items);
      if (Array.isArray(section.rows) && section.rows.length) {
        const table = node('table'), tbody = node('tbody');
        for (const row of section.rows.slice(0,100)) {
          const tr = node('tr');
          const columns = section.columns?.length ? section.columns : Object.keys(row);
          for (const key of columns) tr.append(node('td','',row[key] === null || row[key] === undefined ? 'UNKNOWN' : (typeof row[key] === 'object' ? JSON.stringify(row[key]) : String(row[key]))));
          tbody.append(tr);
        }
        table.append(tbody);
        block.append(table);
      }
      root.append(block);
    }
    if (report.commercial_core) {
      const block = node('section','report-section');
      block.append(node('h3','','Коммерческая оценка · без автоматического решения'));
      const pre = node('pre','',JSON.stringify(report.commercial_core,null,2));
      block.append(pre);
      root.append(block);
    }
  }
  async function loadReport(run) {
    show('report-panel',false);
    if (!['completed','completed_with_warnings','needs_review'].includes(run.status)) return;
    try {
      const [report, verifiedEvidence] = await Promise.all([
        json(api + '/runs/' + encodeURIComponent(state.runId) + '/report'),
        json(api + '/workspace/runs/' + encodeURIComponent(state.runId) + '/evidence')
      ]);
      show('report-panel');
      $('report-recommendation').textContent = report.recommendation_label || 'Требуется проверка человеком';
      wipe($('executive-summary'));
      summaryList($('executive-summary'), report.executive_summary);
      renderEvidence(report, verifiedEvidence);
      renderSections(report);
      $('report-text').textContent = report.report_markdown || 'Исходный отчёт не сформирован';
      $('download-pdf').href = api + '/runs/' + encodeURIComponent(state.runId) + '/export/pdf';
      $('download-docx').href = api + '/runs/' + encodeURIComponent(state.runId) + '/export/docx';
    } catch (error) { msg('Отчёт пока недоступен: ' + error.message); }
  }
  function historyEntry(title, caption, onClick) {
    const wrap = node('div','history-item');
    const meta = node('div');
    meta.append(node('strong','',title),node('small','',caption));
    const button = node('button','','Открыть →');
    button.type = 'button';
    button.addEventListener('click',onClick);
    wrap.append(meta,button);
    return wrap;
  }
  async function loadHistory() {
    const uploaded = $('operator-history'), rag = $('rag-history');
    wipe(uploaded);wipe(rag);
    paragraph(uploaded,'Загружаем сохранённые запуски…','empty-state');
    paragraph(rag,'Загружаем записи Tender Research…','empty-state');
    try {
      const result = await json(api + '/runs');
      wipe(uploaded);
      const list = result.runs || [];
      if (!list.length) paragraph(uploaded,'Нет сохранённых запусков оператора.','empty-state');
      for (const r of list.slice(0,70)) uploaded.append(historyEntry(r.tender_title || r.run_id, [r.status, r.procurement_id, date(r.created_at)].filter(Boolean).join(' · '),async () => {
        state.runId = r.run_id;tab('new');try { await loadRun(); } catch (e) { msg(e.message); }
      }));
    } catch(error) { wipe(uploaded);paragraph(uploaded,'Недоступно: '+error.message,'empty-state'); }
    try {
      const result = await json('/api/tender-research/analyze/history?limit=30');
      wipe(rag);
      if (!result.items?.length) paragraph(rag,'В канонической базе пока нет запусков анализа.','empty-state');
      for (const r of result.items || []) rag.append(historyEntry('№ '+r.registry_number, [r.status, r.sources_count+' источников',date(r.created_at)].join(' · '),async () => {
        try {
          const data = await json('/api/tender-research/analyze/history/' + encodeURIComponent(r.id) + '/report');
          $('rag-preview-title').textContent='Отчёт · '+r.registry_number;
          $('rag-preview-text').textContent=data.report_markdown || 'Отчёт пуст';
          $('rag-export-pdf').href='/api/tender-research/analyze/history/' + encodeURIComponent(r.id) + '/export/pdf';
          show('rag-preview');
          $('rag-preview').scrollIntoView({behavior:'smooth',block:'nearest'});
        } catch (error) {msg(error.message);}
      }));
    } catch(error) { wipe(rag);paragraph(rag,'История недоступна: '+error.message,'empty-state'); }
  }
  async function loadRegistry() {
    const root = $('registry-list');
    wipe(root);
    paragraph(root,'Запрашиваем каноническую базу…','empty-state');
    try {
      const params = new URLSearchParams({limit:'25',offset:String(state.registryOffset),query:state.registryQuery});
      const response = await json(api + '/workspace/registry?' + params);
      state.registryTotal = response.total;
      $('registry-counter').textContent = 'Найдено записей: ' + response.total;
      $('prev-registry').disabled = state.registryOffset === 0;
      $('next-registry').disabled = state.registryOffset + 25 >= response.total;
      wipe(root);
      if (!response.items?.length) paragraph(root,'В базе нет подходящих записей.','empty-state');
      for (const record of response.items || []) {
        root.append(historyEntry(record.title || 'Закупка', [record.registry_number||'№ неизвестен', record.customer_name||'Заказчик UNKNOWN',money(record.nmck_amount,record.currency), record.law||'Закон UNKNOWN'].join(' · '), () => {void loadRegistryDetail(record.id);}));
      }
    } catch(error) {wipe(root);paragraph(root,'База недоступна: '+error.message,'empty-state');}
  }
  async function loadRegistryDetail(id) {
    try {
      const data = await json(api + '/workspace/registry/' + encodeURIComponent(id));
      show('registry-detail-panel');
      const root = $('registry-detail');
      wipe(root);
      for (const [key,val] of [
        ['Предмет',data.title],['Реестровый номер',data.registry_number],
        ['Закон',data.law],['Заказчик',data.customer_name],
        ['Начальная цена',money(data.nmck_amount,data.currency)],['Статус',data.status]]) {
        const row=node('div','detail-row');
        row.append(node('span','',key),node('strong','',val || 'UNKNOWN'));
        root.append(row);
      }
      if(trustedEis(data.eis_url)) {
        const a=link(data.eis_url,'Открыть официальный источник ↗','button button-ghost');
        a.target='_blank';a.rel='noopener noreferrer';root.append(a);
      }
      root.append(node('h3','','Оригинальные документы · '+(data.documents?.length||0)));
      for (const d of data.documents || []) {
        const line=node('div','registry-doc');
        line.append(node('span','',d.name+' · '+d.download_status+' · OCR/text: '+d.text_extraction_status));
        if(d.local_download) line.append(link(api+'/workspace/registry/'+encodeURIComponent(id)+'/documents/'+encodeURIComponent(d.id)+'/download','Скачать ↓'));
        root.append(line);
      }
      if (!data.documents?.length) paragraph(root,'Документы не сохранены в канонической базе.','empty-state');
      $('registry-detail-panel').scrollIntoView({behavior:'smooth',block:'start'});
    } catch(error) {msg('Не удалось открыть запись: '+error.message);}
  }
  document.querySelectorAll('[data-tab]').forEach(b=>b.addEventListener('click',()=>tab(b.dataset.tab)));
  $('import-form').addEventListener('submit',importRequest);
  $('eis-search-form').addEventListener('submit',searchProcurements);
  $('search-reset').addEventListener('click',()=>{
    $('eis-search-form').reset();
    wipe($('search-results'));show('search-pagination',false);
    $('search-status-message').textContent='Фильтры сброшены. Введите запрос.';
    state.searchParams=null;state.seenNumbers=[];state.searchCursor=null;
  });
  $('search-next').addEventListener('click',()=>{if(state.searchCursor)void loadSearchPage(state.searchCursor);});
  $('append-files-form').addEventListener('submit',appendMissingFiles);
  $('analyze-btn').addEventListener('click',()=>void analyze());
  $('refresh-run').addEventListener('click',()=>void loadRun().catch(e=>msg(e.message)));
  $('refresh-history').addEventListener('click',()=>void loadHistory());
  $('registry-form').addEventListener('submit',event=>{ event.preventDefault();state.registryOffset=0;state.registryQuery=$('registry-search').value.trim();void loadRegistry(); });
  $('prev-registry').addEventListener('click',()=>{state.registryOffset=Math.max(0,state.registryOffset-25);void loadRegistry();});
  $('next-registry').addEventListener('click',()=>{ if (state.registryOffset+25<state.registryTotal) { state.registryOffset+=25;void loadRegistry();}});
  const hash=location.hash.replace('#','');
  if (hash==='history'||hash==='registry') tab(hash);
  const urlRun=new URLSearchParams(location.search).get('run');
  if(urlRun && /^[a-zA-Z0-9-]{1,64}$/.test(urlRun)){state.runId=urlRun;tab('new');void loadRun().catch(e=>msg(e.message));}
})();
