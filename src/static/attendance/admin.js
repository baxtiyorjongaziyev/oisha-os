// HR panel: bugungi holat, hisobot/eksport, grafik va tuzatishlar, ofis sozlamasi.
const $ = (id) => document.getElementById(id);
const DAYS = ['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya'];
const CARDS = [
  ['scheduled_today', 'Bugun kutilgan'], ['present', 'Kelgan'], ['on_time', 'O‘z vaqtida'], ['late', 'Kechikkan'],
  ['absent', 'Kelmagan'], ['pending_verification', 'Tekshiruvda'], ['attendance_rate', 'Davomat, %'],
  ['average_lateness_min', 'O‘rtacha kechikish, daq'],
];
const SUMMARY_COLS = [
  ['name', 'Xodim'], ['scheduled_days', 'Ish kuni'], ['present_days', 'Kelgan'], ['late_days', 'Kechikkan'],
  ['late_minutes', 'Kechikish, daq'], ['early_leave_days', 'Erta ketgan'], ['absent_days', 'Kelmagan'],
  ['approved_leave_days', 'Ruxsatli'], ['pending_review', 'Tekshiruvda'], ['worked_hours', 'Soat'],
  ['overtime_hours', 'Overtime'],
];
const EVENT_COLS = [['employee_name', 'Xodim'], ['work_date', 'Sana'], ['kind', 'Turi'], ['local_time', 'Vaqt'], ['status', 'Holat']];
let employees = [];

const localDate = (d = new Date()) => d.toLocaleDateString('en-CA', { timeZone: TZ });
const td = (text, cls = 'px-5 py-2.5') => el('td', cls, text ?? '—');

function showTab(name) {
  document.querySelectorAll('[data-panel]').forEach((p) => p.classList.toggle('hidden', p.dataset.panel !== name));
  document.querySelectorAll('.tab').forEach((t) => t.className = `tab px-4 py-2 rounded-lg ${t.dataset.tab === name ? 'bg-slate-900 text-white' : 'text-slate-600'}`);
  if (name === 'reports') loadReport();
  if (name === 'team') loadTeam();
}

async function correct(e) {
  const choices = Object.entries(STATUS).map(([k, [l]], i) => `${i + 1}. ${l}`).join('\n');
  const pick = prompt(`${e.employee_name}, ${e.work_date} — yangi holat:\n${choices}`);
  const code = Object.keys(STATUS)[Number(pick) - 1];
  if (!code) return;
  const reason = prompt('Sabab (kamida 5 belgi):');
  if (!reason || reason.trim().length < 5) return alert('Sabab yozilishi shart.');
  try {
    await api('/admin/corrections', { method: 'POST', body: {
      employee_id: e.employee_id, work_date: e.work_date, new_status: code, reason: reason.trim(), event_id: e.id } });
    loadToday();
  } catch (err) { alert(err.message); }
}

async function loadToday() {
  try {
    $('loading').textContent = 'Yuklanmoqda…';
    const d = await api(`/admin/dashboard?day=${$('day').value}`);
    $('loading').classList.add('hidden');
    $('login').classList.add('hidden'); $('app').classList.remove('hidden');
    $('cards').replaceChildren(...CARDS.map(([k, label]) => {
      const c = el('div', 'bg-white rounded-2xl p-4 shadow-sm');
      c.append(el('p', 'text-xs text-slate-500', label), el('p', 'text-2xl font-semibold mt-1', d[k] ?? '—'));
      return c;
    }));
    $('rows').replaceChildren(...d.events.map((e) => {
      const tr = el('tr');
      const st = el('td', 'px-5 py-2.5'); st.append(statusBadge(e.status));
      const act = el('td', 'px-5 py-2.5 text-right');
      const b = el('button', 'text-sky-600 hover:underline', 'Tuzatish'); b.onclick = () => correct(e); act.append(b);
      tr.append(td(e.employee_name), td(e.kind === 'check_in' ? 'Keldi' : 'Ketdi'), td(e.local_time, 'px-5 py-2.5 tabular-nums'), st, act);
      return tr;
    }));
    if (!d.events.length) {
      const tr = el('tr'); tr.append(el('td', 'px-5 py-4 text-slate-400', 'Yozuv yo‘q')); $('rows').append(tr);
    }
    return true;
  } catch (err) {
    $('loading').classList.add('hidden');
    if (err.status === 401) { $('login').classList.remove('hidden'); return false; }
    $('app').classList.remove('hidden');
    $('cards').replaceChildren(el('p', 'text-rose-600 col-span-4', err.status === 403 ? 'Bu bo‘lim uchun HR/admin huquqi kerak.' : err.message));
    return false;
  }
}

function reportQuery(format) {
  const q = new URLSearchParams({ start: $('r-start').value, end: $('r-end').value, view: $('r-view').value, format });
  if ($('r-emp').value) q.set('employee_id', $('r-emp').value);
  if ($('r-view').value === 'events' && $('r-status').value) q.set('status', $('r-status').value);
  return `/api/attendance/admin/reports?${q}`;
}

async function loadReport() {
  $('r-status-wrap').classList.toggle('hidden', $('r-view').value !== 'events');
  const cols = $('r-view').value === 'summary' ? SUMMARY_COLS : EVENT_COLS;
  const head = el('tr'); cols.forEach(([, l]) => head.append(el('th', 'px-4 py-2 whitespace-nowrap', l)));
  $('r-head').replaceChildren(head);
  try {
    const data = await api(reportQuery('json').replace('/api/attendance', ''));
    $('r-body').replaceChildren(...data.rows.map((r) => {
      const tr = el('tr');
      for (const [k] of cols) {
        if (k === 'status') { const c = el('td', 'px-4 py-2'); c.append(statusBadge(r[k])); tr.append(c); }
        else if (k === 'kind') tr.append(td(r[k] === 'check_in' ? 'Keldi' : 'Ketdi', 'px-4 py-2'));
        else tr.append(td(r[k], 'px-4 py-2 tabular-nums'));
      }
      return tr;
    }));
    if (!data.rows.length) { const tr = el('tr'); tr.append(el('td', 'px-4 py-4 text-slate-400', 'Ma’lumot yo‘q')); $('r-body').append(tr); }
  } catch (err) {
    const tr = el('tr'); tr.append(el('td', 'px-4 py-4 text-rose-600', err.message)); $('r-body').replaceChildren(tr);
  }
}

function fmtDays(list) { return list.length ? list.map((d) => DAYS[d - 1]).join(', ') : '—'; }

async function loadEmployees() {
  employees = (await api('/admin/employees')).employees;
  for (const sel of [$('r-emp'), $('l-emp')]) {
    const keep = sel.id === 'r-emp' ? [sel.firstElementChild] : [];
    sel.replaceChildren(...keep, ...employees.map((e) => { const o = el('option', '', e.name); o.value = e.id; return o; }));
  }
}

async function loadTeam() {
  await loadEmployees();
  $('team-rows').replaceChildren(...employees.map((e) => {
    const tr = el('tr');
    const act = el('td', 'px-5 py-2.5 text-right');
    const b = el('button', 'text-sky-600 hover:underline', 'O‘zgartirish'); b.onclick = () => editSchedule(e); act.append(b);
    tr.append(td(e.name), td(fmtDays(e.weekdays)), td(fmtDays(e.optional_weekdays)), td(`${e.start}–${e.end}`), act);
    return tr;
  }));
}

function editSchedule(e) {
  const form = $('sched');
  form.classList.remove('hidden');
  form.dataset.emp = e.id;
  $('sched-title').textContent = `${e.name} — ish grafigi`;
  $('sched-start').value = e.start; $('sched-end').value = e.end;
  $('sched-msg').textContent = '';
  $('sched-days').replaceChildren(...DAYS.map((label, i) => {
    const d = i + 1;
    const b = el('button', '', label);
    b.type = 'button';
    b.dataset.state = e.weekdays.includes(d) ? 'work' : e.optional_weekdays.includes(d) ? 'optional' : 'off';
    const paint = () => b.className = 'w-12 py-2 rounded-lg font-medium ' +
      ({ work: 'bg-slate-900 text-white', optional: 'bg-amber-100 text-amber-800', off: 'bg-slate-100 text-slate-400' })[b.dataset.state];
    b.onclick = () => { b.dataset.state = { work: 'optional', optional: 'off', off: 'work' }[b.dataset.state]; paint(); };
    paint();
    return b;
  }));
  form.scrollIntoView({ behavior: 'smooth' });
}

$('sched').addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const btns = [...$('sched-days').children];
  const pick = (s) => btns.map((b, i) => (b.dataset.state === s ? i + 1 : 0)).filter(Boolean);
  try {
    await api(`/admin/schedules/${$('sched').dataset.emp}`, { method: 'PUT', body: {
      weekdays: [...pick('work'), ...pick('optional')], optional_weekdays: pick('optional'),
      start: $('sched-start').value, end: $('sched-end').value } });
    $('sched-msg').className = 'ml-2 text-emerald-600'; $('sched-msg').textContent = 'Saqlandi — bugundan amal qiladi.';
    loadTeam();
  } catch (err) { $('sched-msg').className = 'ml-2 text-rose-600'; $('sched-msg').textContent = err.message; }
});

$('leave').addEventListener('submit', async (ev) => {
  ev.preventDefault();
  try {
    await api('/admin/corrections', { method: 'POST', body: {
      employee_id: Number($('l-emp').value), work_date: $('l-date').value, new_status: $('l-status').value, reason: $('l-reason').value.trim() } });
    $('l-msg').className = 'w-full text-emerald-600'; $('l-msg').textContent = 'Saqlandi.';
    $('l-reason').value = '';
  } catch (err) { $('l-msg').className = 'w-full text-rose-600'; $('l-msg').textContent = err.message; }
});

$('set-office').addEventListener('click', async () => {
  const msg = $('office-msg');
  msg.className = 'text-sm mt-3 text-slate-600'; msg.textContent = 'Lokatsiya aniqlanmoqda…';
  try {
    const fix = await getLocationOnce();
    if (fix.accuracy_m > 50) throw new Error(`GPS aniqligi past (±${Math.round(fix.accuracy_m)} m). Deraza yoniga borib qayta bosing.`);
    if (!confirm(`Ofis markazi: ${fix.latitude.toFixed(6)}, ${fix.longitude.toFixed(6)} (±${Math.round(fix.accuracy_m)} m). Saqlansinmi?`)) { msg.textContent = ''; return; }
    await api('/admin/office', { method: 'PUT', body: {
      name: 'U-Enter Innovatsion Center', latitude: fix.latitude, longitude: fix.longitude, radius_m: Number($('radius').value), max_accuracy_m: 75 } });
    msg.className = 'text-sm mt-3 text-emerald-600'; msg.textContent = 'Ofis joylashuvi saqlandi.';
  } catch (err) { msg.className = 'text-sm mt-3 text-rose-600'; msg.textContent = err.message; }
});

for (const [k, [l]] of Object.entries(STATUS)) { const o = el('option', '', l); o.value = k; $('r-status').append(o); }
document.querySelectorAll('.tab').forEach((t) => t.addEventListener('click', () => showTab(t.dataset.tab)));
$('r-show').onclick = loadReport;
$('r-view').onchange = loadReport;
$('r-xlsx').onclick = () => { window.location = reportQuery('xlsx'); };
$('r-pdf').onclick = () => { window.location = reportQuery('pdf'); };
const now = new Date();
$('day').value = localDate(now);
$('r-start').value = localDate(new Date(now.getFullYear(), now.getMonth(), 1));
$('r-end').value = localDate(now);
$('l-date').value = localDate(now);
$('day').addEventListener('change', loadToday);
loadToday().then((ok) => { if (ok) { showTab('today'); loadEmployees().catch(() => {}); } });

// ---- ulanish so'rovlari ----
async function loadLinks() {
  let data;
  try { data = await api('/admin/link-requests'); } catch (_) { return; }
  $('links').classList.toggle('hidden', !data.requests.length);
  $('link-rows').replaceChildren(...data.requests.map((r) => {
    const row = el('div', 'flex flex-wrap items-center gap-2 bg-white rounded-lg p-3');
    row.append(el('span', 'font-medium mr-2', r.full_name), el('span', 'text-slate-400 mr-auto', `Telegram ${r.telegram_id}`));
    const sel = el('select', 'border rounded-lg px-2 py-1');
    const fresh = el('option', '', '➕ Yangi xodim sifatida'); fresh.value = '';
    sel.append(fresh, ...data.unlinked_employees.map((e) => { const o = el('option', '', e.name); o.value = e.id; return o; }));
    const ok = el('button', 'bg-emerald-600 text-white rounded-lg px-3 py-1', 'Tasdiqlash');
    const no = el('button', 'text-rose-600 px-2', 'Rad etish');
    ok.onclick = async () => {
      try {
        await api(`/admin/link-requests/${r.id}/approve`, { method: 'POST', body: { employee_id: sel.value ? Number(sel.value) : null } });
        loadTeam();
      } catch (err) { alert(err.message); }
    };
    no.onclick = async () => { await api(`/admin/link-requests/${r.id}/reject`, { method: 'POST' }).catch((e) => alert(e.message)); loadLinks(); };
    row.append(sel, ok, no);
    return row;
  }));
}
const _loadTeam = loadTeam;
loadTeam = async () => { await Promise.all([_loadTeam(), loadLinks()]); };

// ---- ofis Wi-Fi ----
async function loadWifi() {
  let d;
  try { d = await api('/admin/office-wifi'); } catch (err) { $('wifi-status').textContent = err.message; return; }
  const st = $('wifi-status');
  if (!d.networks.length) { st.className = 'text-sm mt-3 text-amber-700'; st.textContent = 'Hali belgilanmagan — hozircha faqat GPS tekshiriladi.'; }
  else if (d.you_are_on_office_wifi) { st.className = 'text-sm mt-3 text-emerald-700'; st.textContent = 'Siz hozir ofis Wi-Fi’sidasiz ✅'; }
  else { st.className = 'text-sm mt-3 text-slate-600'; st.textContent = 'Siz hozir ofis Wi-Fi’sida emassiz.'; }
  $('wifi-list').replaceChildren(...d.networks.map((n) => {
    const row = el('div', 'flex items-center gap-3 py-2');
    row.append(el('span', 'font-medium mr-auto', `${n.label} · ${n.ip}`));
    const b = el('button', 'text-rose-600', 'O‘chirish');
    b.onclick = async () => { if (confirm('Bu tarmoq o‘chirilsinmi?')) { await api(`/admin/office-wifi/${n.id}`, { method: 'DELETE' }); loadWifi(); } };
    row.append(b);
    return row;
  }));
}

$('wifi-set').addEventListener('click', async () => {
  if (!confirm('Hozir ofis Wi-Fi’siga ulanganmisiz? (mobil internet o‘chiq bo‘lsin)')) return;
  try { await api('/admin/office-wifi', { method: 'POST' }); loadWifi(); } catch (err) { alert(err.message); }
});

const _showTab = showTab;
showTab = (name) => { _showTab(name); if (name === 'settings') loadWifi(); };
