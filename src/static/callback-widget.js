/*!
 * Oisha "Sizga qo'ng'iroq qilamiz" vidjeti.
 *
 * Saytga qo'yish (</body> dan oldin):
 *   <script src="https://oisha.jonbranding.uz/api/callback-widget.js"
 *           data-color="#111111" data-lang="uz" defer></script>
 *
 * Atributlar (ixtiyoriy):
 *   data-api       — API manzili (default: skript yuklangan domen)
 *   data-color     — asosiy rang (default: #111111)
 *   data-lang      — uz | ru (default: uz)
 *   data-position  — right | left (default: right)
 *   data-button    — "0" bo'lsa suzuvchi tugma chiqmaydi (o'z tugmangizdan foydalanasiz)
 *
 * O'z tugmangizdan ochish: <button data-oisha-callback>Qo'ng'iroq qiling</button>
 *   yoki JS: window.OishaCallback.open()
 *
 * Call tracking (ixtiyoriy): data-call-tracking="1" bo'lsa, sahifadagi
 *   <a data-oisha-phone href="tel:+998712000000">+998 71 200 00 00</a>
 * elementlarida mijoz kelgan kanalning raqami ko'rsatiladi
 * (raqamlar serverdagi CALL_TRACKING_NUMBERS dan olinadi).
 *
 * UTM: birinchi tashrifdagi utm_* / fbclid / gclid 30 kun saqlanadi va
 * so'rov bilan birga AmoCRM lidiga yoziladi.
 */
(function () {
  "use strict";
  if (window.OishaCallback) return;

  var script = document.currentScript || document.querySelector('script[src*="callback-widget.js"]');
  var cfg = {
    api: (script && script.getAttribute("data-api")) || (script ? new URL(script.src).origin : ""),
    color: (script && script.getAttribute("data-color")) || "#111111",
    lang: (script && script.getAttribute("data-lang")) === "ru" ? "ru" : "uz",
    position: (script && script.getAttribute("data-position")) === "left" ? "left" : "right",
    button: !(script && script.getAttribute("data-button") === "0"),
    callTracking: !!(script && script.getAttribute("data-call-tracking") === "1"),
  };

  var T = {
    uz: {
      fab: "Qo'ng'iroq qiling",
      title: "Sizga qo'ng'iroq qilamiz",
      sub: "Raqamingizni qoldiring — menejerimiz tez orada bog'lanadi.",
      name: "Ismingiz",
      phone: "Telefon raqamingiz",
      send: "Qo'ng'iroq kutaman",
      sending: "Yuborilmoqda…",
      ok: "Rahmat! Menejerimiz tez orada qo'ng'iroq qiladi.",
      badPhone: "Raqamni to'liq kiriting: +998 XX XXX XX XX",
      fail: "Yuborilmadi. Iltimos, qayta urinib ko'ring.",
      close: "Yopish",
      privacy: "Raqamingiz faqat siz bilan bog'lanish uchun ishlatiladi.",
    },
    ru: {
      fab: "Перезвоните мне",
      title: "Мы вам перезвоним",
      sub: "Оставьте номер — менеджер скоро свяжется с вами.",
      name: "Ваше имя",
      phone: "Номер телефона",
      send: "Жду звонка",
      sending: "Отправляем…",
      ok: "Спасибо! Менеджер скоро вам перезвонит.",
      badPhone: "Введите номер полностью: +998 XX XXX XX XX",
      fail: "Не отправилось. Попробуйте ещё раз.",
      close: "Закрыть",
      privacy: "Номер используется только для связи с вами.",
    },
  }[cfg.lang];

  // ---- UTM: birinchi tashrif 30 kun saqlanadi ----
  var KEYS = ["utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "fbclid", "gclid", "yclid"];
  var STORE = "oisha_first_touch";
  var TTL = 30 * 24 * 3600 * 1000;

  function readStore() {
    try {
      var raw = JSON.parse(localStorage.getItem(STORE) || "null");
      if (raw && Date.now() - raw.ts < TTL) return raw;
    } catch (e) { /* storage yopiq bo'lishi mumkin */ }
    return null;
  }

  function captureTouch() {
    var params = new URLSearchParams(location.search);
    var current = {};
    KEYS.forEach(function (k) { if (params.get(k)) current[k] = params.get(k); });
    var stored = readStore();
    if (!stored && (Object.keys(current).length || document.referrer)) {
      stored = { ts: Date.now(), data: current, landing_url: location.href, referrer: document.referrer };
      try { localStorage.setItem(STORE, JSON.stringify(stored)); } catch (e) { /* e'tiborsiz */ }
    }
    return { current: current, stored: stored };
  }

  var touch = captureTouch();

  function tracking() {
    // Joriy URL'da UTM bo'lsa — u ustun, aks holda birinchi tashrif.
    var src = Object.keys(touch.current).length ? touch.current : (touch.stored && touch.stored.data) || {};
    var out = {};
    KEYS.forEach(function (k) { if (src[k]) out[k] = String(src[k]).slice(0, 200); });
    out.page_url = location.href.slice(0, 500);
    if (touch.stored) {
      out.landing_url = String(touch.stored.landing_url || "").slice(0, 500);
      out.referrer = String(touch.stored.referrer || "").slice(0, 500);
    } else if (document.referrer) {
      out.referrer = document.referrer.slice(0, 500);
    }
    return out;
  }

  // ---- Telefon ----
  function phoneDigits(v) {
    var d = String(v || "").replace(/\D/g, "");
    if (d.length === 9) d = "998" + d;
    return d;
  }

  function formatPhone(v) {
    var d = String(v || "").replace(/\D/g, "");
    if (d.indexOf("998") === 0) d = d.slice(3);
    d = d.slice(0, 9);
    var out = "+998";
    if (d.length) out += " " + d.slice(0, 2);
    if (d.length > 2) out += " " + d.slice(2, 5);
    if (d.length > 5) out += " " + d.slice(5, 7);
    if (d.length > 7) out += " " + d.slice(7, 9);
    return out;
  }

  // ---- UI (Shadow DOM — sayt stillari bilan to'qnashmaydi) ----
  var host = document.createElement("div");
  host.setAttribute("data-oisha-callback-host", "");
  var root = host.attachShadow ? host.attachShadow({ mode: "open" }) : host;
  var side = cfg.position;

  root.innerHTML =
    "<style>" +
    ":host{all:initial}" +
    "*{box-sizing:border-box;font-family:Inter,system-ui,-apple-system,'Segoe UI',Roboto,sans-serif}" +
    ".fab{position:fixed;bottom:24px;" + side + ":24px;z-index:2147483000;display:flex;align-items:center;gap:10px;" +
    "padding:14px 20px;border:0;border-radius:999px;background:var(--c);color:#fff;font-size:15px;font-weight:600;" +
    "cursor:pointer;box-shadow:0 10px 30px rgba(0,0,0,.18);transition:transform .15s ease}" +
    ".fab:hover{transform:translateY(-2px)}.fab svg{width:20px;height:20px}" +
    ".wrap{position:fixed;inset:0;z-index:2147483001;display:none;align-items:flex-end;justify-content:" + (side === "left" ? "flex-start" : "flex-end") + ";padding:24px;background:rgba(0,0,0,.25)}" +
    ".wrap.open{display:flex}" +
    ".card{width:100%;max-width:360px;background:#fff;color:#111;border-radius:20px;padding:24px;box-shadow:0 20px 60px rgba(0,0,0,.25);position:relative}" +
    "h2{margin:0 0 6px;font-size:20px;line-height:1.25}p{margin:0 0 16px;font-size:14px;color:#555;line-height:1.45}" +
    "label{display:block;font-size:12px;color:#666;margin:0 0 6px}" +
    "input{width:100%;padding:13px 14px;margin:0 0 12px;border:1px solid #ddd;border-radius:12px;font-size:16px;color:#111;background:#fff;outline:none}" +
    "input:focus{border-color:var(--c);box-shadow:0 0 0 3px rgba(0,0,0,.06)}" +
    ".hp{position:absolute;left:-9999px;width:1px;height:1px;opacity:0}" +
    ".send{width:100%;padding:14px;border:0;border-radius:12px;background:var(--c);color:#fff;font-size:16px;font-weight:600;cursor:pointer}" +
    ".send[disabled]{opacity:.6;cursor:default}" +
    ".x{position:absolute;top:12px;right:12px;width:32px;height:32px;border:0;border-radius:50%;background:#f2f2f2;cursor:pointer;font-size:18px;line-height:32px;color:#333}" +
    ".msg{font-size:13px;margin:0 0 12px;min-height:0}.msg.err{color:#c62828}" +
    ".ok{font-size:16px;line-height:1.5;padding:12px 0}" +
    ".small{font-size:11px;color:#999;margin:10px 0 0}" +
    "@media (max-width:480px){.wrap{padding:12px}.card{max-width:none}.fab{bottom:16px;" + side + ":16px}}" +
    "</style>" +
    (cfg.button
      ? '<button class="fab" type="button" part="button"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.13.96.36 1.9.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.91.34 1.85.57 2.81.7A2 2 0 0 1 22 16.92z"/></svg><span></span></button>'
      : "") +
    '<div class="wrap" role="dialog" aria-modal="true"><div class="card">' +
    '<button class="x" type="button">×</button>' +
    "<h2></h2><p class=\"sub\"></p>" +
    '<form novalidate>' +
    '<label for="oc-name"></label><input id="oc-name" name="name" autocomplete="name" maxlength="80">' +
    '<label for="oc-phone"></label><input id="oc-phone" name="phone" type="tel" inputmode="tel" autocomplete="tel" value="+998 ">' +
    '<input class="hp" name="website" tabindex="-1" autocomplete="off" aria-hidden="true">' +
    '<div class="msg" role="alert"></div>' +
    '<button class="send" type="submit"></button>' +
    '<p class="small"></p>' +
    "</form></div></div>";

  host.style.setProperty("--c", cfg.color);
  var $ = function (sel) { return root.querySelector(sel); };
  var wrap = $(".wrap"), form = $("form"), msg = $(".msg"), send = $(".send");
  var nameInput = $("#oc-name"), phoneInput = $("#oc-phone");

  if ($(".fab")) { $(".fab span").textContent = T.fab; $(".fab").setAttribute("aria-label", T.fab); }
  $("h2").textContent = T.title;
  $(".sub").textContent = T.sub;
  $('label[for="oc-name"]').textContent = T.name;
  $('label[for="oc-phone"]').textContent = T.phone;
  $(".x").setAttribute("aria-label", T.close);
  wrap.setAttribute("aria-label", T.title);
  send.textContent = T.send;
  $(".small").textContent = T.privacy;

  var lastFocus = null;
  function open() {
    lastFocus = document.activeElement;
    wrap.classList.add("open");
    setTimeout(function () { phoneInput.focus(); }, 30);
  }
  function close() {
    wrap.classList.remove("open");
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }

  if ($(".fab")) $(".fab").addEventListener("click", open);
  $(".x").addEventListener("click", close);
  wrap.addEventListener("click", function (e) { if (e.target === wrap) close(); });
  root.addEventListener("keydown", function (e) { if (e.key === "Escape") close(); });
  // Niqob har doim oxirdan yoziladi: kursor "+998" dan oldinga tushib qolmasin.
  function caretToEnd() {
    var n = phoneInput.value.length;
    try { phoneInput.setSelectionRange(n, n); } catch (e) { /* ba'zi brauzerlar */ }
  }
  phoneInput.addEventListener("focus", function () { setTimeout(caretToEnd, 0); });
  phoneInput.addEventListener("click", caretToEnd);
  phoneInput.addEventListener("input", function () {
    phoneInput.value = formatPhone(phoneInput.value);
    caretToEnd();
  });

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    msg.textContent = "";
    msg.className = "msg";
    var digits = phoneDigits(phoneInput.value);
    if (digits.length !== 12 || digits.indexOf("998") !== 0) {
      msg.textContent = T.badPhone;
      msg.className = "msg err";
      phoneInput.focus();
      return;
    }
    var payload = tracking();
    payload.phone = "+" + digits;
    payload.name = nameInput.value.trim().slice(0, 80);
    payload.website = form.website.value;
    send.disabled = true;
    send.textContent = T.sending;
    fetch(cfg.api + "/api/callback-request", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        form.innerHTML = '<div class="ok"></div>';
        form.querySelector(".ok").textContent = "✅ " + T.ok;
        try {
          if (window.dataLayer) window.dataLayer.push({ event: "oisha_callback_request" });
          if (window.fbq) window.fbq("track", "Lead");
        } catch (err) { /* analitika ixtiyoriy */ }
      })
      .catch(function () {
        msg.textContent = T.fail;
        msg.className = "msg err";
        send.disabled = false;
        send.textContent = T.send;
      });
  });

  document.addEventListener("click", function (e) {
    var el = e.target && e.target.closest ? e.target.closest("[data-oisha-callback]") : null;
    if (el) { e.preventDefault(); open(); }
  });

  // ---- Call tracking: kanalga mos raqamni ko'rsatish ----
  var REFERRER_SOURCES = { "t.me": "telegram", "telegram": "telegram", "instagram": "instagram",
    "facebook": "facebook", "google": "google", "yandex": "yandex", "youtube": "youtube" };

  function pickSource(numbers) {
    var src = Object.keys(touch.current).length ? touch.current : (touch.stored && touch.stored.data) || {};
    var utm = String(src.utm_source || "").toLowerCase();
    if (utm && numbers[utm]) return utm;
    if (src.gclid && numbers.google) return "google";
    if (src.fbclid) {
      var meta = ["meta", "instagram", "facebook"].filter(function (k) { return numbers[k]; })[0];
      if (meta) return meta;
    }
    if (src.yclid && numbers.yandex) return "yandex";
    var ref = (touch.stored && touch.stored.referrer) || document.referrer || "";
    var host = "";
    try { host = ref ? new URL(ref).hostname : ""; } catch (e) { host = ""; }
    if (host && host !== location.hostname) {
      for (var needle in REFERRER_SOURCES) {
        if (host.indexOf(needle) !== -1 && numbers[REFERRER_SOURCES[needle]]) return REFERRER_SOURCES[needle];
      }
    }
    return numbers["default"] ? "default" : null;
  }

  function displayPhone(number) {
    var d = String(number).replace(/\D/g, "");
    if (d.length === 12 && d.indexOf("998") === 0) {
      return "+998 " + d.slice(3, 5) + " " + d.slice(5, 8) + " " + d.slice(8, 10) + " " + d.slice(10, 12);
    }
    return "+" + d;
  }

  var trackedNumber = null;
  function applyPhones() {
    if (!trackedNumber) return;
    var els = document.querySelectorAll("[data-oisha-phone]");
    for (var i = 0; i < els.length; i++) {
      var el = els[i];
      if (el.getAttribute("data-oisha-phone-text") !== "0") el.textContent = displayPhone(trackedNumber);
      if (el.tagName === "A") el.setAttribute("href", "tel:" + trackedNumber);
    }
  }

  function loadCallTracking() {
    if (!cfg.callTracking || !window.fetch) return;
    fetch(cfg.api + "/api/call-tracking/config")
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        var numbers = (data && data.numbers) || {};
        var source = pickSource(numbers);
        if (!source) return;
        trackedNumber = numbers[source];
        applyPhones();
      })
      .catch(function () { /* raqamlar o'zgarmaydi — sayt odatdagidek ishlaydi */ });
  }

  function mount() { document.body.appendChild(host); loadCallTracking(); }
  if (document.body) mount(); else document.addEventListener("DOMContentLoaded", mount);

  window.OishaCallback = { open: open, close: close, tracking: tracking, applyPhones: applyPhones };
})();
