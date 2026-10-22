// Smart Attendance — umumiy yordamchilar. Ma'lumot DOM ga faqat textContent orqali yoziladi.
const TZ = 'Asia/Tashkent';
const STATUS = {
  ON_TIME: ['O‘z vaqtida', 'bg-emerald-100 text-emerald-700'],
  LATE: ['Kechikdi', 'bg-amber-100 text-amber-700'],
  EARLY_LEAVE: ['Erta ketdi', 'bg-orange-100 text-orange-700'],
  ABSENT: ['Kelmadi', 'bg-rose-100 text-rose-700'],
  APPROVED_LEAVE: ['Ruxsatli', 'bg-sky-100 text-sky-700'],
  DAY_OFF: ['Dam olish', 'bg-slate-100 text-slate-600'],
  PENDING_REVIEW: ['Tekshiruvda', 'bg-violet-100 text-violet-700'],
};
const ERRORS = {
  outside_geofence: 'Siz ofis hududida emassiz.',
  qr_expired: 'QR kod eskirdi. Monitordagi yangi kodni skanerlang.',
  qr_replayed: 'Bu QR kod allaqachon ishlatilgan.',
  qr_bad_signature: 'QR kod Oisha monitoriga tegishli emas.',
  qr_wrong_branch: 'QR kod boshqa ofisniki.',
  already_recorded: 'Bugun bu belgi allaqachon qo‘yilgan.',
  check_in_required: 'Avval “Keldim” belgisini qo‘ying.',
  not_an_employee: 'Telegram hisobingiz xodimlar ro‘yxatiga bog‘lanmagan. HR ga murojaat qiling.',
  geofence_not_configured: 'Ofis joylashuvi hali sozlanmagan.',
  session_expired: 'Vaqt tugadi. Qaytadan boshlang.',
  rate_limited: 'Juda ko‘p urinish. Bir daqiqadan keyin qayta urinib ko‘ring.',
};

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
}

function statusBadge(code) {
  const [label, cls] = STATUS[code] || [code, 'bg-slate-100 text-slate-600'];
  return el('span', `px-2.5 py-1 rounded-full text-xs font-semibold ${cls}`, label);
}

function hhmm(iso) {
  return new Date(iso).toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit', timeZone: TZ });
}

class ApiError extends Error {
  constructor(status, code) { super(ERRORS[code] || code || `HTTP ${status}`); this.status = status; this.code = code; }
}

async function api(path, { method = 'GET', body, headers = {} } = {}) {
  const res = await fetch(`/api/attendance${path}`, {
    method, credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', ...headers },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  let data = null;
  try { data = await res.json(); } catch (_) { /* bo'sh javob */ }
  if (!res.ok) throw new ApiError(res.status, data && (typeof data.detail === 'string' ? data.detail : null));
  return data;
}

// GPS faqat shu chaqiruvda bir marta olinadi — doimiy kuzatuv yo'q.
function getLocationOnce() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) return reject(new Error('Brauzer GPS ni qo‘llamaydi.'));
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({
        latitude: p.coords.latitude, longitude: p.coords.longitude,
        accuracy_m: p.coords.accuracy, captured_at: new Date(p.timestamp).toISOString(),
      }),
      (e) => reject(new Error(e.code === 1 ? 'Lokatsiyaga ruxsat bering (brauzer sozlamalari).' : 'GPS aniqlanmadi. Ochiq joyga yaqinroq turing.')),
      { enableHighAccuracy: true, maximumAge: 0, timeout: 20000 },
    );
  });
}
