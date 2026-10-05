def render_procurement_portfolio_html() -> str:
    return r"""
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Арвектум — портфель закупок</title>
  <style>
    :root {
      --bg:#06142b; --panel:#0d203a; --panel2:#102945; --text:#f4f7fb;
      --muted:#9fb0c4; --line:#243a55; --mint:#3ee7c1; --orange:#ffb35c;
      --red:#ff7c84; --green:#62e89b;
    }
    * { box-sizing:border-box }
    body { margin:0; font:14px/1.45 Inter,system-ui,-apple-system,sans-serif; color:var(--text);
      background:radial-gradient(circle at 15% 0,#10385d 0,transparent 32%),var(--bg); }
    .wrap { max-width:1500px; margin:auto; padding:28px 22px 60px }
    h1 { margin:0; font-size:34px } .sub { color:var(--muted); margin-top:6px }
    .toolbar { display:flex; gap:10px; flex-wrap:wrap; margin:24px 0 18px }
    input,select,button { border:1px solid var(--line); background:var(--panel); color:var(--text);
      border-radius:12px; padding:10px 12px; font:inherit }
    input { min-width:280px; flex:1 } button { cursor:pointer }
    .cards { display:grid; grid-template-columns:repeat(6,minmax(120px,1fr)); gap:12px; margin-bottom:18px }
    .card { background:linear-gradient(180deg,var(--panel2),var(--panel)); border:1px solid var(--line);
      border-radius:16px; padding:15px }
    .label { color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.06em }
    .value { font-size:26px; font-weight:750; margin-top:6px }
    .panel { background:rgba(13,32,58,.92); border:1px solid var(--line); border-radius:18px; overflow:hidden }
    .table-wrap { overflow:auto } table { width:100%; border-collapse:collapse; min-width:1180px }
    th,td { padding:13px 12px; border-bottom:1px solid var(--line); vertical-align:top; text-align:left }
    th { color:var(--muted); font-weight:600; position:sticky; top:0; background:#0c1d35; z-index:1 }
    tr:hover td { background:rgba(255,255,255,.025) }
    .num { font-family:ui-monospace,SFMono-Regular,Menlo,monospace; white-space:nowrap }
    .title { font-weight:650; max-width:390px } .muted { color:var(--muted) }
    .badge { display:inline-flex; padding:4px 9px; border:1px solid var(--line); border-radius:999px;
      font-size:12px; font-weight:700; white-space:nowrap }
    .go { color:var(--green); border-color:#28694a } .no-go { color:var(--red); border-color:#6b343d }
    .review { color:var(--orange); border-color:#70552e } .won { color:var(--mint); border-color:#26705f }
    .lost { color:#ff98a0; border-color:#6b343d }
    .reason { max-width:340px; color:#c8d4e2 }
    .actions { display:flex; gap:6px; flex-wrap:wrap }
    .actions button { padding:6px 9px; font-size:12px }
    .empty { padding:36px; color:var(--muted); text-align:center }
    .footer-grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-top:14px }
    .reason-list { display:flex; gap:8px; flex-wrap:wrap; margin-top:10px }
    @media (max-width:1000px) { .cards { grid-template-columns:repeat(3,1fr) } .footer-grid { grid-template-columns:1fr } }
    @media (max-width:600px) { .cards { grid-template-columns:repeat(2,1fr) } .wrap { padding:18px 12px } }
  </style>
</head>
<body>
<div class="wrap">
  <h1>Портфель закупок</h1>
  <div class="sub">Отбор → GO / NO GO → подача → результат → причины. Данные берутся из канонического контура Tender Agent.</div>

  <div class="card" style="margin:22px 0 12px">
    <div class="label">Добавить закупку вручную</div>
    <div class="toolbar" style="margin:10px 0 0">
      <input id="new-number" placeholder="Номер закупки">
      <input id="new-title" placeholder="Предмет закупки">
      <input id="new-customer" placeholder="Заказчик">
      <input id="new-url" placeholder="Ссылка ЕИС (необязательно)">
      <select id="new-direction">
        <option value="OTHER">Прочее</option>
        <option value="SERVICE">Услуги</option>
        <option value="WORK">Работы</option>
        <option value="SUPPLY">Поставка</option>
        <option value="MIXED">Смешанная</option>
      </select>
      <button onclick="addProcurement()">Добавить</button>
    </div>
  </div>

  <div class="toolbar">
    <input id="q" placeholder="Поиск по номеру, заказчику, названию или причине">
    <select id="decision">
      <option value="">Все решения</option>
      <option>GO</option><option>NO_GO</option><option>NEEDS_REVIEW</option><option>UNDECIDED</option>
    </select>
    <select id="outcome">
      <option value="">Все результаты</option>
      <option>WON</option><option>LOST</option><option>REJECTED</option><option>CANCELLED</option>
    </select>
    <select id="submitted">
      <option value="">Подача: все</option>
      <option value="true">Подались</option><option value="false">Не подались</option>
    </select>
    <button onclick="load()">Обновить</button>
  </div>

  <div class="cards" id="cards"></div>
  <div class="panel"><div class="table-wrap" id="table"></div></div>
  <div class="footer-grid">
    <div class="card"><div class="label">Причины NO GO</div><div id="reasons" class="reason-list"></div></div>
    <div class="card"><div class="label">Как считаются метрики</div>
      <div class="muted" style="margin-top:8px">Submission rate = подались / GO. Win rate = WON / (WON + LOST + REJECTED). Решение берётся из последнего явного решения, затем из факта workflow, затем из screening агента.</div>
    </div>
  </div>
</div>
<script>
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pct = v => (Number(v||0)*100).toFixed(1) + '%';
function badge(v) {
  const cls = v === 'GO' ? 'go' : v === 'NO_GO' ? 'no-go' : v === 'NEEDS_REVIEW' ? 'review' :
              v === 'WON' ? 'won' : v === 'LOST' || v === 'REJECTED' ? 'lost' : '';
  return '<span class="badge '+cls+'">'+esc(v || '—')+'</span>';
}
async function addProcurement() {
  const procurement_number = document.getElementById('new-number').value.trim();
  const title = document.getElementById('new-title').value.trim();
  const customer_name = document.getElementById('new-customer').value.trim();
  const source_url = document.getElementById('new-url').value.trim() || null;
  const direction_type = document.getElementById('new-direction').value;
  if (!procurement_number || !title || !customer_name) {
    alert('Нужны номер закупки, предмет и заказчик.');
    return;
  }
  const res = await fetch('/procurement-portfolio', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body:JSON.stringify({procurement_number,title,customer_name,source_url,direction_type,domain_type:'GENERAL'})
  });
  if (!res.ok) { alert('Не удалось добавить закупку: '+await res.text()); return; }
  ['new-number','new-title','new-customer','new-url'].forEach(id => document.getElementById(id).value='');
  await load();
}

async function decide(dealId, decision) {
  const rationale = prompt('Причина решения '+decision+':');
  if (!rationale) return;
  const rawCodes = prompt('Коды причин через запятую (необязательно):', '');
  const reason_codes = (rawCodes || '').split(',').map(x=>x.trim()).filter(Boolean);
  const res = await fetch('/procurement-portfolio/'+encodeURIComponent(dealId)+'/decision', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body:JSON.stringify({decision, rationale, reason_codes})
  });
  if (!res.ok) { alert('Не удалось записать решение: '+await res.text()); return; }
  await load();
}
async function load() {
  const p = new URLSearchParams();
  const q = document.getElementById('q').value.trim();
  const d = document.getElementById('decision').value;
  const o = document.getElementById('outcome').value;
  const s = document.getElementById('submitted').value;
  if (q) p.set('q',q); if (d) p.set('decision',d); if (o) p.set('outcome',o); if (s) p.set('submitted',s);
  const res = await fetch('/procurement-portfolio?'+p.toString());
  const data = await res.json(), m = data.summary;
  const cards = [
    ['Отобрано',m.total_considered],['GO',m.go],['NO GO',m.no_go],['Подались',m.submitted],
    ['Победы',m.won],['Win rate',pct(m.win_rate)]
  ];
  document.getElementById('cards').innerHTML = cards.map(x=>'<div class="card"><div class="label">'+x[0]+'</div><div class="value">'+x[1]+'</div></div>').join('');
  document.getElementById('reasons').innerHTML = Object.entries(m.no_go_reason_counts || {}).map(([k,v])=>badge(k)+' <span class="muted">'+v+'</span>').join(' ') || '<span class="muted">Пока нет данных</span>';
  if (!data.items.length) { document.getElementById('table').innerHTML='<div class="empty">Нет закупок по выбранным фильтрам</div>'; return; }
  document.getElementById('table').innerHTML = '<table><thead><tr>'+
    '<th>Закупка</th><th>Заказчик / предмет</th><th>Решение</th><th>Почему</th><th>Подача</th><th>Результат</th><th>Статус</th><th>Действия</th>'+
    '</tr></thead><tbody>'+data.items.map(x => {
      const why = x.decision_rationale || x.screening_rationale || '—';
      const resultWhy = x.outcome_rationale ? '<div class="muted" style="margin-top:5px">'+esc(x.outcome_rationale)+'</div>' : '';
      return '<tr>'+
        '<td class="num">'+esc(x.procurement_number || x.deal_id)+'</td>'+
        '<td><div class="muted">'+esc(x.customer_name || '—')+'</div><div class="title">'+esc(x.title)+'</div></td>'+
        '<td>'+badge(x.decision)+'<div class="muted">'+esc(x.decision_source || '')+'</div></td>'+
        '<td class="reason">'+esc(why)+'</td>'+
        '<td>'+badge(x.submitted ? 'SUBMITTED' : '—')+'</td>'+
        '<td>'+badge(x.outcome)+resultWhy+'</td>'+
        '<td>'+esc(x.current_status)+'</td>'+
        '<td><div class="actions"><button onclick="decide(\''+esc(x.deal_id)+'\',\'GO\')">GO</button><button onclick="decide(\''+esc(x.deal_id)+'\',\'NO_GO\')">NO GO</button><button onclick="decide(\''+esc(x.deal_id)+'\',\'NEEDS_REVIEW\')">Проверить</button></div></td>'+
      '</tr>';
    }).join('')+'</tbody></table>';
}
['q','decision','outcome','submitted'].forEach(id => document.getElementById(id).addEventListener('change',load));
document.getElementById('q').addEventListener('keydown',e=>{ if(e.key==='Enter') load(); });
load();
</script>
</body>
</html>
"""
