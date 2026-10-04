// Baholar mini app (teacher view). Plain JavaScript, no build step.
const tg = window.Telegram && window.Telegram.WebApp;
const inTelegram = !!(tg && tg.initData);
if (tg) { tg.ready(); tg.expand(); }

const $view = document.getElementById('view');
const S = { tab: 'classes', classes: [], topics: [], cls: null, mode: 'rank', topicId: null, studentId: null, editId: null };
const SYM = { green: '✓', yellow: '~', red: '✕' };
const ORDER = ['', 'green', 'yellow', 'red'];   // one tap moves to the next colour

const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const say = msg => (inTelegram ? tg.showAlert(msg) : alert(msg));
const ask = msg => new Promise(done => (inTelegram && tg.showConfirm ? tg.showConfirm(msg, done) : done(confirm(msg))));

async function api(method, path, body) {
  const res = await fetch('/api' + path, {
    method,
    headers: { 'Content-Type': 'application/json', 'X-Init-Data': tg ? tg.initData : '' },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Xatolik: ' + res.status);
  }
  return res.json();
}

// ---------- scoring ----------
const partsOf = t => (t.has_parts ? ['toq', 'juft'] : ['single']);
const PART_LABEL = { toq: 'Sinf', juft: 'Uy', single: '' };

function score(st) {
  let total = 0, cw = 0, hw = 0;
  for (const t of S.cls.topics) for (const p of partsOf(t)) {
    const pts = S.cls.points[st.marks[t.id + ':' + p]] || 0;
    total += pts;
    if (p === 'toq') cw += pts;
    if (p === 'juft') hw += pts;
  }
  return { total, cw, hw };
}

function ranked() {
  const rows = S.cls.students.map(st => ({ st, ...score(st) }));
  rows.sort((a, b) => b.total - a.total || a.st.name.localeCompare(b.st.name));
  rows.forEach(r => { r.place = 1 + rows.filter(o => o.total > r.total).length; });
  return rows;
}

function cellHtml(st, t, p, withLabel) {
  const c = st.marks[t.id + ':' + p] || '';
  const label = withLabel && PART_LABEL[p] ? `<span>${PART_LABEL[p]}</span>` : '';
  return `<span class="cellwrap"><button class="cell ${c}" data-s="${st.id}" data-t="${t.id}" data-p="${p}">${SYM[c] || ''}</button>${label}</span>`;
}

// ---------- screens ----------
function render() {
  document.querySelectorAll('.tabs button').forEach(b => b.classList.toggle('on', b.dataset.tab === S.tab));
  if (tg && tg.BackButton) (S.tab === 'classes' && S.cls ? tg.BackButton.show() : tg.BackButton.hide());
  if (S.tab === 'topics') return renderTopics();
  if (!S.cls) return renderClasses();
  if (S.studentId) return renderStudent();
  renderClass();
}

function renderClasses() {
  const rows = S.classes.map(c => `
    <button class="row" data-open-class="${c.id}">
      <span class="grow"><div class="name">${esc(c.name)}</div>
      <div class="hint">${c.students} o'quvchi · ${c.topics} mavzu · o'rtacha ${c.avg} / ${c.max}</div></span>
      <span class="chev">›</span>
    </button>`).join('');
  $view.innerHTML = `<h1>Sinflar</h1>` + (rows ? `<div class="list">${rows}</div>`
    : `<div class="empty">Hali sinf yo'q.<br>Botda /add_class yoki /import buyrug'idan foydalaning.</div>`);
}

function renderClass() {
  const c = S.cls;
  const seg = [['rank', 'Reyting'], ['topic', "Mavzu bo'yicha"], ['grid', 'Jadval']]
    .map(([m, label]) => `<button data-mode="${m}" class="${S.mode === m ? 'on' : ''}">${label}</button>`).join('');
  let body = '';
  if (!c.students.length) {
    body = `<div class="empty">Bu sinfda o'quvchi yo'q.<br>Botda /add_class_members buyrug'i bilan qo'shing.</div>`;
  } else if (!c.topics.length) {
    body = `<div class="empty">Bu sinfda mavzu yo'q.<br>«Mavzular» bo'limida mavzu qo'shing.</div>`;
  } else if (S.mode === 'rank') {
    body = `<div class="list">` + ranked().map(r => `
      <button class="row" data-open-student="${r.st.id}">
        <span class="place">${r.place}</span>
        <span class="grow"><div class="name">${esc(r.st.name)}</div>
        <div class="hint">Sinf ishi ${r.cw} · Uy ishi ${r.hw}</div></span>
        <span class="total">${r.total} <small>/ ${c.max}</small></span>
      </button>`).join('') + `</div>`;
  } else if (S.mode === 'topic') {
    if (!c.topics.some(t => t.id === S.topicId)) S.topicId = c.topics[c.topics.length - 1].id;
    const t = c.topics.find(x => x.id === S.topicId);
    body = `<div class="bar">
        <select id="topicSel">${c.topics.map(x => `<option value="${x.id}" ${x.id === t.id ? 'selected' : ''}>${esc(x.title)}</option>`).join('')}</select>
        <button class="btn ghost" id="fillGreen">Bo'shlari ✓</button>
      </div>
      <div class="list">` + c.students.map(st => `
        <div class="row"><span class="grow name">${esc(st.name)}</span>
        ${partsOf(t).map(p => cellHtml(st, t, p, true)).join('')}</div>`).join('') + `</div>
      <p class="hint">Katakni bosing: bo'sh → yashil → sariq → qizil.</p>`;
  } else {
    const head1 = c.topics.map(t => `<th class="topic ${t.has_parts ? '' : 'single'}" colspan="${partsOf(t).length}">${esc(t.title)}</th>`).join('');
    const head2 = c.topics.map(t => partsOf(t).map(p => `<th>${PART_LABEL[p] ? PART_LABEL[p][0] : '•'}</th>`).join('')).join('');
    const rows = c.students.map(st => `<tr>
        <td class="who"><b data-total="${st.id}">${score(st).total}</b>${esc(st.name)}</td>
        ${c.topics.map(t => partsOf(t).map((p, i) => `<td class="${i ? '' : 'first'}">${cellHtml(st, t, p, false)}</td>`).join('')).join('')}
      </tr>`).join('');
    body = `<div class="gridwrap"><table class="grid">
        <thead><tr><th class="who" rowspan="2">O'quvchi</th>${head1}</tr><tr>${head2}</tr></thead>
        <tbody>${rows}</tbody></table></div>
      <p class="hint">S — sinf ishi, U — uy ishi.</p>`;
  }
  $view.innerHTML = `<div class="head"><button class="back" data-back>‹ Sinflar</button><h1>${esc(c.name)}</h1></div>
    <div class="seg">${seg}</div>${body}`;
}

function studentStats(st) {
  const r = ranked().find(x => x.st.id === st.id);
  return `<div class="stat"><b>${r.total}</b><span>/ ${S.cls.max} ball</span></div>
    <div class="stat"><b>${r.place}</b><span>o'rin</span></div>
    <div class="stat"><b>${r.cw}</b><span>sinf ishi</span></div>
    <div class="stat"><b>${r.hw}</b><span>uy ishi</span></div>`;
}

function renderStudent() {
  const st = S.cls.students.find(x => x.id === S.studentId);
  $view.innerHTML = `<div class="head"><button class="back" data-back>‹ ${esc(S.cls.name)}</button><h1>${esc(st.name)}</h1></div>
    <div class="stats" id="stats">${studentStats(st)}</div>
    <div class="list">` + S.cls.topics.map(t => `
      <div class="row"><span class="grow name">${esc(t.title)}</span>
      ${partsOf(t).map(p => cellHtml(st, t, p, true)).join('')}</div>`).join('') + `</div>`;
}

function renderTopics() {
  const editing = S.topics.find(t => t.id === S.editId);
  const checked = id => (editing ? editing.class_ids.includes(id) : true);
  const classes = S.classes.map(c => `<label><input type="checkbox" name="cls" value="${c.id}" ${checked(c.id) ? 'checked' : ''}> ${esc(c.name)}</label>`).join('');
  const rows = S.topics.map((t, i) => `
    <div class="row">
      <span class="place">${i + 1}</span>
      <span class="grow"><div class="name">${esc(t.title)}</div>
      <div class="hint">${t.class_ids.length} ta sinf</div></span>
      <span class="badge">${t.has_parts ? 'sinf + uy' : 'bitta baho'}</span>
      <button class="btn small" data-edit-topic="${t.id}">✎</button>
      <button class="btn danger" data-del-topic="${t.id}">✕</button>
    </div>`).join('');
  $view.innerHTML = `<h1>Mavzular</h1>
    <form class="card" id="topicForm">
      <input type="text" id="topicTitle" placeholder="Mavzu nomi" maxlength="120" value="${editing ? esc(editing.title) : ''}">
      <label><input type="checkbox" id="topicParts" ${!editing || editing.has_parts ? 'checked' : ''} ${editing ? 'disabled' : ''}>
        Sinf ishi va uy ishi alohida baholanadi</label>
      ${classes ? `<div class="hint">Qaysi sinflar uchun:</div><div class="chips">${classes}</div>` : ''}
      <div class="bar" style="margin:10px 0 0">
        <button class="btn" type="submit">${editing ? 'Saqlash' : "Mavzu qo'shish"}</button>
        ${editing ? `<button class="btn ghost" type="button" data-cancel-edit>Bekor qilish</button>` : ''}
      </div>
    </form>` + (rows ? `<div class="list">${rows}</div>` : `<div class="empty">Hali mavzu yo'q.</div>`);
}

// ---------- actions ----------
async function loadLists() {
  [S.classes, S.topics] = await Promise.all([api('GET', '/classes'), api('GET', '/topics')]);
}

async function openClass(id) {
  S.cls = await api('GET', '/classes/' + id);
  S.studentId = null;
  render();
  window.scrollTo(0, 0);
}

async function goBack() {
  if (S.studentId) { S.studentId = null; render(); return; }
  S.cls = null;
  await loadLists();
  render();
}

async function setMark(btn, color) {
  const st = S.cls.students.find(x => x.id === +btn.dataset.s);
  const key = btn.dataset.t + ':' + btn.dataset.p;
  const before = st.marks[key] || '';
  const paint = c => {
    if (c) st.marks[key] = c; else delete st.marks[key];
    btn.className = 'cell ' + c;
    btn.textContent = SYM[c] || '';
    document.querySelectorAll(`[data-total="${st.id}"]`).forEach(el => { el.textContent = score(st).total; });
    const stats = document.getElementById('stats');
    if (stats) stats.innerHTML = studentStats(st);
  };
  paint(color);   // show at once, undo if the server refuses
  try {
    await api('PUT', '/marks', { student_id: st.id, topic_id: +btn.dataset.t, part: btn.dataset.p, color: color || null });
  } catch (e) { paint(before); say(e.message); }
}

$view.addEventListener('click', async e => {
  const el = e.target.closest('button');
  if (!el) return;
  try {
    if (el.classList.contains('cell')) {
      const now = ORDER.find(c => c && el.classList.contains(c)) || '';
      if (tg && tg.HapticFeedback) tg.HapticFeedback.selectionChanged();
      return setMark(el, ORDER[(ORDER.indexOf(now) + 1) % ORDER.length]);
    }
    if (el.dataset.openClass) return openClass(+el.dataset.openClass);
    if (el.dataset.openStudent) { S.studentId = +el.dataset.openStudent; render(); return window.scrollTo(0, 0); }
    if ('back' in el.dataset) return goBack();
    if (el.dataset.mode) { S.mode = el.dataset.mode; return render(); }
    if (el.id === 'fillGreen') {
      const empty = [...$view.querySelectorAll('.cell')].filter(b => !ORDER.some(c => c && b.classList.contains(c)));
      if (empty.length && await ask(`${empty.length} ta bo'sh katak yashil qilinsinmi?`)) await Promise.all(empty.map(b => setMark(b, 'green')));
      return;
    }
    if (el.dataset.editTopic) { S.editId = +el.dataset.editTopic; render(); return window.scrollTo(0, 0); }
    if ('cancelEdit' in el.dataset) { S.editId = null; return render(); }
    if (el.dataset.delTopic) {
      const t = S.topics.find(x => x.id === +el.dataset.delTopic);
      if (await ask(`«${t.title}» mavzusi va uning barcha baholari o'chirilsinmi?`)) {
        await api('DELETE', '/topics/' + t.id);
        S.editId = null;
        await loadLists();
        render();
      }
    }
  } catch (err) { say(err.message); }
});

$view.addEventListener('change', e => {
  if (e.target.id === 'topicSel') { S.topicId = +e.target.value; render(); }
});

$view.addEventListener('submit', async e => {
  e.preventDefault();
  const title = document.getElementById('topicTitle').value.trim();
  if (!title) return say('Mavzu nomini yozing.');
  const class_ids = [...document.querySelectorAll('input[name=cls]:checked')].map(i => +i.value);
  try {
    if (S.editId) await api('PATCH', '/topics/' + S.editId, { title, class_ids });
    else await api('POST', '/topics', { title, has_parts: document.getElementById('topicParts').checked, class_ids });
    S.editId = null;
    await loadLists();
    render();
  } catch (err) { say(err.message); }
});

document.querySelector('.tabs').addEventListener('click', async e => {
  const b = e.target.closest('button');
  if (!b) return;
  S.tab = b.dataset.tab;
  S.editId = null;
  try {
    await loadLists();
    if (S.tab === 'classes' && S.cls) S.cls = await api('GET', '/classes/' + S.cls.id);
  } catch (err) { say(err.message); }
  render();
});

if (tg && tg.BackButton) tg.BackButton.onClick(goBack);

loadLists().then(render).catch(err => {
  $view.innerHTML = `<div class="empty">${esc(err.message)}<br>Jurnalni Telegram bot orqali oching.</div>`;
});
