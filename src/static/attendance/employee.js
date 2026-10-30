// Xodim ekrani: Keldim/Ketdim → GPS → QR → tasdiq.
const $ = (id) => document.getElementById(id);
let busy = false;

function tick() {
  $('clock').textContent = new Date().toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit', timeZone: TZ });
}

function setStep(id, state) {
  const dot = $(id).firstElementChild;
  dot.className = 'w-6 h-6 rounded-full flex items-center justify-center text-xs ' +
    ({ wait: 'bg-slate-900 text-white animate-pulse', ok: 'bg-emerald-500 text-white', fail: 'bg-rose-500 text-white' }[state] || 'bg-slate-100');
  if (state === 'ok') dot.textContent = '✓';
  if (state === 'fail') dot.textContent = '!';
}

function message(text, tone = 'slate') {
  $('message').className = `mt-4 text-sm text-${tone}-600`;
  $('message').textContent = text;
}

function renderToday(events) {
  const box = $('today-events');
  box.replaceChildren();
  const byKind = Object.fromEntries(events.map((e) => [e.kind, e]));
  for (const [kind, label] of [['check_in', 'Keldi'], ['check_out', 'Ketdi']]) {
    const row = el('div', 'flex items-center justify-between');
    row.append(el('span', 'text-slate-600', label));
    const e = byKind[kind];
    if (e) {
      const right = el('div', 'flex items-center gap-2');
      right.append(el('span', 'font-semibold', hhmm(e.server_ts)), statusBadge(e.status));
      row.append(right);
    } else {
      row.append(el('span', 'text-slate-400', '—'));
    }
    box.append(row);
  }
  const btn = $('action');
  if (!byKind.check_in) { btn.textContent = 'Keldim'; btn.dataset.kind = 'check_in'; btn.disabled = false; }
  else if (!byKind.check_out) { btn.textContent = 'Ketdim'; btn.dataset.kind = 'check_out'; btn.disabled = false; }
  else { btn.textContent = 'Bugun uchun tayyor ✓'; btn.disabled = true; }
}

function renderHistory(events) {
  const box = $('history');
  box.replaceChildren();
  const days = {};
  for (const e of events) (days[e.work_date] ||= {})[e.kind] = e;
  const dates = Object.keys(days).sort().reverse();
  if (!dates.length) box.append(el('p', 'text-slate-400 py-2', 'Hali yozuv yo‘q'));
  for (const d of dates) {
    const row = el('div', 'flex items-center justify-between py-2.5');
    row.append(el('span', 'text-slate-600', d));
    const right = el('div', 'flex items-center gap-2');
    const ci = days[d].check_in, co = days[d].check_out;
    right.append(el('span', 'tabular-nums', `${ci ? hhmm(ci.server_ts) : '—'} – ${co ? hhmm(co.server_ts) : '—'}`));
    if (ci) right.append(statusBadge(ci.status));
    row.append(right);
    box.append(row);
  }
}

async function load() {
  try {
    const [today, hist] = await Promise.all([api('/today'), api('/history?days=14')]);
    $('loading').classList.add('hidden');
    $('login').classList.add('hidden');
    $('app').classList.remove('hidden');
    renderToday(today.events);
    renderHistory(hist.events);
  } catch (err) {
    $('loading').classList.add('hidden');
    if (err.status === 401) { $('login').classList.remove('hidden'); return; }
    if (err.code === 'not_an_employee') { showLink(); return; }
    $('app').classList.remove('hidden');
    $('action').disabled = true;
    $('action').textContent = err.message;
  }
}

async function run() {
  if (busy) return;
  busy = true;
  const kind = $('action').dataset.kind;
  $('action').disabled = true;
  $('flow').classList.remove('hidden');
  ['step-gps', 'step-qr', 'step-ok'].forEach((s) => setStep(s, ''));
  message('');
  let step = 'step-gps';
  try {
    setStep(step, 'wait'); message('Lokatsiya aniqlanmoqda…');
    const fix = await getLocationOnce();
    setStep(step, 'ok');
    step = 'step-qr'; setStep(step, 'wait'); message('Tekshirilmoqda…');
    const res = await api('/punch', { method: 'POST', body: { kind, ...fix }, headers: { 'Idempotency-Key': crypto.randomUUID() } });
    setStep(step, 'ok');
    step = 'step-ok'; setStep(step, 'ok');
    const [label] = STATUS[res.status] || [res.status];
    const extra = res.minutes_late ? ` · ${res.minutes_late} daqiqa kechikish` : res.minutes_early ? ` · ${res.minutes_early} daqiqa erta` : '';
    message(`${kind === 'check_in' ? 'Kelish' : 'Ketish'} qayd etildi${res.server_ts ? ': ' + hhmm(res.server_ts) : ''} — ${label}${extra}`, 'emerald');
    if (navigator.vibrate) navigator.vibrate(80);
  } catch (err) {
    if (err.code === 'outside_geofence') step = 'step-gps';
    setStep(step, 'fail');
    message(err.message || 'Xatolik. Internetni tekshirib, qayta urinib ko‘ring.', 'rose');
  } finally {
    busy = false;
    load();
  }
}

async function showLink() {
  $('link').classList.remove('hidden');
  $('app').classList.add('hidden');
  const st = (await api('/link-request').catch(() => ({}))).state;
  if (st === 'pending') {
    $('link-form').classList.add('hidden');
    $('link-text').textContent = 'So‘rovingiz yuborilgan. Rahbar tasdiqlagach shu sahifani yangilang.';
  } else if (st === 'rejected') {
    $('link-text').textContent = 'Oldingi so‘rov rad etilgan. Ma’lumotni tekshirib, qayta yuboring.';
  }
}

$('link-form').addEventListener('submit', async (ev) => {
  ev.preventDefault();
  try {
    await api('/link-request', { method: 'POST', body: { full_name: $('link-name').value.trim() } });
    showLink();
  } catch (err) { $('link-msg').className = 'text-sm mt-3 text-rose-600'; $('link-msg').textContent = err.message; }
});

$('action').addEventListener('click', run);
tick(); setInterval(tick, 10000);
load();
