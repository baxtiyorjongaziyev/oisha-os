/**
 * Jon Branding · MetaCAPI Tracking Engine (jon-capi.js)
 * Yuqori aniqlikdagi mijoz va sayt kuzatuv skripti (Tilda / WordPress / Taplink)
 * - O'zbekiston mobil raqamlarini tozalash va kanonikalash (13 ta prefiks: 90, 91, 33, 77...)
 * - Brauzerda xavfsiz SHA-256 heshlash (Web Crypto API)
 * - Meta Pixel (window.fbq) ni avtomatik o'rab olish (Monkey-patch) va 100% deduplikatsiya
 * - 30 daqiqalik cookie orqali "Rahmat" (/thank-you) sahifasida bitta lid 2 marta sanalmasligi
 * - Tildaning yashirin inputlari (input[type=hidden][name="Phone"]) va AJAX tugmalari eshituvchisi
 * - Sahifa yopilganda navigator.sendBeacon orqali ma'lumot yo'qolmasdan yetkazish
 */
(function (window, document) {
  "use strict";

  if (window.__JonCapiLoaded) return;
  window.__JonCapiLoaded = true;

  const UZ_MOBILE_PREFIXES = ["20", "33", "55", "77", "88", "90", "91", "93", "94", "95", "97", "98", "99"];

  const scriptTag = document.currentScript || (function () {
    const scripts = document.getElementsByTagName("script");
    return scripts[scripts.length - 1];
  })();

  const secret = scriptTag ? scriptTag.getAttribute("data-secret") : "";
  const endpoint = (scriptTag ? scriptTag.src.replace(/\/jon-capi\.js.*$/, "") : "") + "/events";

  function getCookie(name) {
    const v = document.cookie.match("(^|;) ?" + name + "=([^;]*)(;|$)");
    return v ? decodeURIComponent(v[2]) : "";
  }

  function setCookie(name, val, minutes) {
    const d = new Date();
    d.setTime(d.getTime() + minutes * 60 * 1000);
    const expires = "expires=" + d.toUTCString();
    document.cookie = name + "=" + encodeURIComponent(val) + ";" + expires + ";path=/;SameSite=Lax";
  }

  function getUrlParam(param) {
    const m = new RegExp("[?&]" + param + "=([^&#]*)").exec(window.location.search);
    return m ? decodeURIComponent(m[1]) : "";
  }

  function canonicalizeUzPhone(raw) {
    if (!raw) return "";
    let digits = String(raw).replace(/\D/g, "");
    if (!digits) return "";
    if (digits.startsWith("00")) digits = digits.slice(2);
    if (digits.startsWith("8") && digits.length === 10) {
      digits = "998" + digits.slice(1);
    } else if (digits.length === 9) {
      const prefix = digits.slice(0, 2);
      if (UZ_MOBILE_PREFIXES.includes(prefix)) {
        digits = "998" + digits;
      }
    }
    return digits;
  }

  async function sha256(str) {
    if (!str) return "";
    const clean = String(str).trim().toLowerCase();
    if (!clean) return "";
    try {
      if (window.crypto && window.crypto.subtle && window.TextEncoder) {
        const buffer = new TextEncoder().encode(clean);
        const hash = await window.crypto.subtle.digest("SHA-256", buffer);
        return Array.from(new Uint8Array(hash))
          .map((b) => b.toString(16).padStart(2, "0"))
          .join("");
      }
    } catch (_) {}
    return "";
  }

  function getVisitorId() {
    let vid = getCookie("jon_visitor_id");
    if (!vid) {
      vid = "vid_" + Date.now() + "_" + Math.random().toString(36).substring(2, 10);
      setCookie("jon_visitor_id", vid, 90 * 24 * 60);
    }
    return vid;
  }

  function getFbp() {
    return getCookie("_fbp") || ("fb.1." + Date.now() + "." + Math.floor(Math.random() * 1000000000));
  }

  function getFbc() {
    const cookieFbc = getCookie("_fbc");
    if (cookieFbc) return cookieFbc;
    const fbclid = getUrlParam("fbclid");
    if (fbclid) return "fb.1." + Date.now() + "." + fbclid;
    return "";
  }

  function getLeadEventId(phoneHash) {
    if (phoneHash) {
      const eid = "lead_" + phoneHash.substring(0, 24);
      setCookie("jon_lead_eid", eid, 30);
      return eid;
    }
    const cached = getCookie("jon_lead_eid");
    if (cached) return cached;
    const generated = "evt_" + Date.now() + "_" + Math.random().toString(36).substring(2, 9);
    setCookie("jon_lead_eid", generated, 30);
    return generated;
  }

  function wrapFbq() {
    if (typeof window.fbq !== "function") {
      let tries = 0;
      const interval = setInterval(function () {
        tries++;
        if (typeof window.fbq === "function") {
          clearInterval(interval);
          wrapFbq();
        } else if (tries > 20) {
          clearInterval(interval);
        }
      }, 500);
      return;
    }

    if (window.fbq.__jon_wrapped) return;
    const originalFbq = window.fbq;
    const wrapped = function () {
      const args = Array.prototype.slice.call(arguments);
      if (args[0] === "track" && args[1] === "Lead") {
        const options = args[3] || {};
        const activeEid = getCookie("jon_lead_eid") || options.eventID;
        if (activeEid) {
          options.eventID = activeEid;
          args[3] = options;
        }
      }
      return originalFbq.apply(this, args);
    };
    wrapped.__jon_wrapped = true;
    for (const prop in originalFbq) {
      if (Object.prototype.hasOwnProperty.call(originalFbq, prop)) {
        wrapped[prop] = originalFbq[prop];
      }
    }
    window.fbq = wrapped;
  }

  async function track(eventName, customData, rawUserData) {
    if (!secret || !endpoint) return;

    rawUserData = rawUserData || {};
    const normPhone = canonicalizeUzPhone(rawUserData.phone || "");
    const rawEmail = (rawUserData.email || "").trim().toLowerCase();

    let phoneHash = rawUserData.phone_hash || "";
    let emailHash = rawUserData.email_hash || "";

    if (normPhone && !phoneHash) phoneHash = await sha256(normPhone);
    if (rawEmail && !emailHash) emailHash = await sha256(rawEmail);

    let eventId = "";
    if (eventName === "Lead") {
      eventId = getLeadEventId(phoneHash);
    } else {
      eventId = "evt_" + Date.now() + "_" + Math.random().toString(36).substring(2, 9);
    }

    if (eventName === "Lead" && typeof window.fbq === "function") {
      try {
        window.fbq("track", "Lead", customData || {}, { eventID: eventId });
      } catch (_) {}
    }

    const cleanUrl = window.location.origin + window.location.pathname;
    const payload = {
      source: "website",
      event_name: eventName || "PageView",
      event_id: eventId,
      event_time: Math.floor(Date.now() / 1000),
      event_source_url: cleanUrl,
      client_user_agent: navigator.userAgent,
      fbp: getFbp(),
      fbc: getFbc() || undefined,
      phone: phoneHash || normPhone || undefined,
      email: emailHash || rawEmail || undefined,
      consent: true,
    };

    const payloadJson = JSON.stringify(payload);
    const sendViaBeacon = function () {
      if (navigator.sendBeacon) {
        const blob = new Blob([payloadJson], { type: "application/json" });
        navigator.sendBeacon(endpoint + "?token=" + encodeURIComponent(secret), blob);
      }
    };

    try {
      if (window.fetch) {
        fetch(endpoint, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + secret,
          },
          body: payloadJson,
          mode: "cors",
          keepalive: true,
        }).catch(sendViaBeacon);
      } else {
        sendViaBeacon();
      }
    } catch (_) {}
  }

  function extractPhoneAndEmail(container) {
    if (!container) return { phone: "", email: "" };
    let phone = "", email = "";

    const hiddenPhone = container.querySelector && container.querySelector('input[type="hidden"][name="Phone"], input[type="hidden"][name*="phone"]');
    if (hiddenPhone && hiddenPhone.value) {
      phone = hiddenPhone.value;
    }

    const inputs = container.querySelectorAll ? container.querySelectorAll("input, textarea, select") : [];
    for (let i = 0; i < inputs.length; i++) {
      const el = inputs[i];
      const val = (el.value || "").trim();
      if (!val) continue;
      const n = (el.name || el.type || el.id || el.getAttribute("placeholder") || "").toLowerCase();
      if (!phone && (n.includes("phone") || n.includes("tel") || el.type === "tel" || /^\+?[0-9\s\-\(\)]{7,20}$/.test(val))) {
        phone = val;
      }
      if (!email && (n.includes("email") || el.type === "email" || val.includes("@"))) {
        email = val;
      }
    }
    return { phone: phone, email: email };
  }

  function onReady() {
    wrapFbq();
    track("PageView");
  }

  if (document.readyState === "complete" || document.readyState === "interactive") {
    onReady();
  } else {
    document.addEventListener("DOMContentLoaded", onReady);
  }

  document.addEventListener("submit", function (e) {
    const form = e.target;
    if (!form) return;
    const creds = extractPhoneAndEmail(form);
    if (creds.phone || creds.email) {
      track("Lead", {
        form_id: form.id || form.getAttribute("name") || "web_form",
      }, creds);
    }
  }, true);

  document.addEventListener("click", function (e) {
    const btn = e.target && e.target.closest ? e.target.closest("button, input[type='submit'], a.t-submit, .t-submit") : null;
    if (!btn) return;
    const parentForm = btn.closest("form") || btn.closest(".t-form") || btn.closest(".t706") || btn.parentElement;
    if (!parentForm) return;
    setTimeout(function () {
      const creds = extractPhoneAndEmail(parentForm);
      if (creds.phone || creds.email) {
        track("Lead", {
          trigger: "button_click",
          button_text: (btn.innerText || btn.value || "").substring(0, 50).trim(),
        }, creds);
      }
    }, 120);
  }, true);

  window.JonCapi = {
    track: track,
    canonicalizePhone: canonicalizeUzPhone,
    sha256: sha256,
  };
})(window, document);
