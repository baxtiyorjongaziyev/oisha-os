// Oisha Connect — maʼlumot DOM ga faqat textContent orqali yoziladi.
/* global QRCode */
// Faqat oʻz API mizga soʻrov: yoʻl → oldindan tuzilgan toʻliq URL.
const API_URLS = new Map(["/status", "/qr/start", "/qr/status", "/qr/password", "/qr/cancel", "/chats",
  "/chats/refresh", "/revoke", "/audit", "/mcp-token", "/settings"].map((p) => [p, "/api/connect" + p]));
const $ = (id) => document.getElementById(id);
const SECTIONS = ["loading", "login", "intro", "qr-step", "pw-step", "connected"];
const ERRORS = new Map(Object.entries({
  not_an_employee: "Telegram hisobingiz xodimlar roʻyxatiga bogʻlanmagan. Rahbaringizga murojaat qiling.",
  connect_not_configured: "Tizim hali sozlanmagan. Administratorga xabar bering.",
  already_connected: "Akkaunt allaqachon ulangan.",
  wrong_account: "Boshqa Telegram akkaunti skanerlandi. Sahifaga qaysi akkaunt bilan kirgan boʻlsangiz, oʻshani skanerlang.",
  expired: "Vaqt tugadi. Qaytadan urinib koʻring.",
  failed: "Ulanishda xato. Qaytadan urinib koʻring.",
  bad_password: "Parol notoʻgʻri.",
  rate_limited: "Juda koʻp urinish. Birozdan keyin qayta urinib koʻring.",
}));
const ACTIONS = new Map(Object.entries({
  connected: "Ulandi", revoked: "Uzildi", chats_updated: "Chatlar tanlovi oʻzgardi",
  mcp_token_issued: "ChatGPT/Claude havolasi yaratildi",
  mcp_list_chats: "AI chatlar roʻyxatini oldi", mcp_read_chat: "AI chatni oʻqidi",
  mcp_search_chat: "AI chatda qidirdi",
  write_pending: "AI yozish uchun tasdiq soʻradi", write_done: "AI nomingizdan yozdi",
  write_failed: "AI yozishi bajarilmadi", write_rejected: "Siz AI yozishini rad etdingiz",
  all_chats_on: "Barcha chatlar ochildi", all_chats_off: "Barcha chatlar yopildi",
}));
let qrObj = null, poll = null, chats = [];

function show(id) { SECTIONS.forEach((s) => $(s).classList.toggle("hidden", s !== id)); }
function err(code) {
  const box = $("error");
  box.textContent = code ? (ERRORS.get(code) || "Xato: " + String(code)) : "";
  box.classList.toggle("hidden", !code);
}

async function api(path, opts = {}) {
  const url = API_URLS.get(path);
  if (!url) throw new Error("unknown_api_path");
  const res = await fetch(url, {
    credentials: "same-origin", headers: { "Content-Type": "application/json" }, ...opts,
  });
  if (res.status === 401) { show("login"); throw new Error("unauthorized"); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) { err(data.detail || String(res.status)); throw new Error(data.detail); }
  return data;
}

function drawQr(url) {
  $("qr").textContent = "";
  qrObj = new QRCode($("qr"), { text: url, width: 220, height: 220, correctLevel: QRCode.CorrectLevel.M });
  const link = $("qr-link");
  link.href = url;
  link.classList.toggle("hidden", !/Android|iPhone|iPad/i.test(navigator.userAgent));
}

function stopPoll() { if (poll) clearInterval(poll); poll = null; }

function onAttempt(a) {
  if (a.state === "waiting" && a.qr_url) {
    show("qr-step");
    if (!qrObj || $("qr").dataset.url !== a.qr_url) { drawQr(a.qr_url); $("qr").dataset.url = a.qr_url; }
  } else if (a.state === "password_required") {
    stopPoll(); show("pw-step");
  } else if (a.state === "done") {
    stopPoll(); load();
  } else if (["wrong_account", "expired", "failed"].includes(a.state)) {
    stopPoll(); err(a.state); show("intro");
  }
}

function startPoll() {
  stopPoll();
  poll = setInterval(async () => onAttempt(await api("/qr/status").catch(() => ({}))), 2000);
}

function renderChats(filter = "") {
  const list = $("chat-list");
  list.textContent = "";
  const icons = { private: "👤", group: "👥", channel: "📢" };
  chats.filter((c) => c.title.toLowerCase().includes(filter.toLowerCase())).forEach((c) => {
    const row = document.createElement("label");
    row.className = "flex items-center gap-3 px-2 py-2 rounded-lg hover:bg-white/5 cursor-pointer text-sm";
    const box = document.createElement("input");
    box.type = "checkbox"; box.checked = c.allowed; box.className = "w-4 h-4 accent-sky-500";
    box.onchange = () => { c.allowed = box.checked; };
    const icon = document.createElement("span"); icon.textContent = icons[c.kind] || "💬";
    const title = document.createElement("span"); title.className = "truncate"; title.textContent = c.title;
    const auto = document.createElement("button");
    auto.type = "button"; auto.title = "AI tasdiqsiz yozsin";
    const paint = () => { auto.textContent = c.autonomous ? "⚡" : "·"; auto.className =
      "ml-auto w-7 h-7 rounded-lg " + (c.autonomous ? "bg-amber-500/20 text-amber-300" : "text-slate-500"); };
    auto.onclick = (ev) => {
      ev.preventDefault();
      if (!c.autonomous && !confirm("“" + c.title + "” chatida AI sizdan soʻramasdan yoza oladi. Rozimisiz?")) return;
      c.autonomous = !c.autonomous; paint();
    };
    paint();
    row.append(box, icon, title, auto);
    list.append(row);
  });
  if (!chats.length) { list.textContent = "Chatlar topilmadi. “Yangilash”ni bosing."; }
}

function fmt(ts) { return new Date(ts * 1000).toLocaleString("uz-UZ", { timeZone: "Asia/Tashkent" }); }

async function loadConnected(st) {
  show("connected");
  $("conn-meta").textContent = (st.username ? "@" + st.username + " · " : "") + fmt(st.connected_at)
    + " · " + (st.all_chats ? "barcha chatlar ochiq" : st.allowed_chats + " ta chat ochiq");
  $("all-chats").checked = !!st.all_chats;
  chats = (await api("/chats")).chats; renderChats();
  if (!chats.length) {
    api("/chats/refresh", { method: "POST" }).then((r) => {
      chats = r.chats; renderChats($("chat-filter").value);
    }).catch(() => {});
  }
  const audit = (await api("/audit")).events;
  const ul = $("audit"); ul.textContent = "";
  audit.forEach((e) => {
    const li = document.createElement("li");
    li.textContent = fmt(e.at) + " — " + (ACTIONS.get(e.action) || e.action)
      + (e.detail && e.detail.chat ? ": " + e.detail.chat : "");
    ul.append(li);
  });
}

async function load() {
  err(null);
  const st = await api("/status");
  if (st.connected) return loadConnected(st);
  if (st.attempt && ["waiting", "password_required"].includes(st.attempt.state)) {
    onAttempt(st.attempt); if (st.attempt.state === "waiting") startPoll(); return;
  }
  show("intro");
}

$("consent").onchange = (e) => { $("btn-start").disabled = !e.target.checked; };
$("btn-start").onclick = async () => { err(null); onAttempt(await api("/qr/start", { method: "POST" })); startPoll(); };
$("btn-cancel").onclick = async () => {
  stopPoll(); await api("/qr/cancel", { method: "POST" }).catch(() => null); show("intro");
};
$("btn-pw").onclick = async () => {
  const pw = $("pw").value; $("pw").value = "";
  const r = await api("/qr/password", { method: "POST", body: JSON.stringify({ password: pw }) }).catch(() => null);
  if (r) onAttempt(r);
};
$("chat-filter").oninput = (e) => renderChats(e.target.value);
$("btn-refresh").onclick = async () => { chats = (await api("/chats/refresh", { method: "POST" })).chats; renderChats(); };
$("all-chats").onchange = async (e) => {
  const on = e.target.checked;
  if (on && !confirm("AI barcha chatlaringizni oʻqiy oladi (yozish baribir tasdiq bilan). Davom etasizmi?")) {
    e.target.checked = false; return;
  }
  await api("/settings", { method: "PUT", body: JSON.stringify({ all_chats: on }) });
  load();
};
$("btn-save").onclick = async () => {
  const ids = chats.filter((c) => c.allowed).map((c) => c.id);
  const auto = chats.filter((c) => c.autonomous).map((c) => c.id);
  await api("/chats", { method: "PUT", body: JSON.stringify({ chat_ids: ids, autonomous_ids: auto }) });
  load();
};
$("btn-token").onclick = async () => {
  if (!confirm("Yangi havola yaratilsa, eski havola ishlamay qoladi. Davom etasizmi?")) return;
  const r = await api("/mcp-token", { method: "POST" });
  $("mcp-url").textContent = location.origin + "/api/connect/mcp/" + r.token;
  $("token-box").classList.remove("hidden");
};
$("btn-revoke").onclick = async () => {
  if (!confirm("Oisha Connect uziladi va sessiya Telegramda ham yopiladi. Davom etasizmi?")) return;
  const r = await api("/revoke", { method: "POST" });
  if (!r.telegram_logout) {
    alert("Sessiya Oisha serveridan oʻchirildi, lekin Telegram uni yopa olmadi. "
      + "Telegram → Settings → Devices boʻlimida “Oisha Connect”ni qoʻlda Terminate qiling.");
  }
  load();
};

load().catch(() => {});
