/**
 * Jon Branding · Standalone Client-side Meta CAPI & Pixel Tracker (jon-capi.js)
 * Avtomatik ravishda fbp, fbc, user-agent, referer va formalarni kuzatib
 * backend CAPI intake (/api/marketing/capi/events) ga jo'natadi.
 */
(function (window, document) {
  "use strict";

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

  function getUrlParam(param) {
    const m = new RegExp("[?&]" + param + "=([^&#]*)").exec(window.location.search);
    return m ? decodeURIComponent(m[1]) : "";
  }

  function generateEventId() {
    return "evt_" + Date.now() + "_" + Math.random().toString(36).substring(2, 9);
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

  async function track(eventName, customData, userData) {
    if (!secret || !endpoint) return;
    const eventId = generateEventId();
    const payload = {
      event_id: eventId,
      event_name: eventName || "PageView",
      source: "website",
      user_data: Object.assign({
        fbp: getFbp(),
        fbc: getFbc() || undefined,
        client_user_agent: navigator.userAgent,
      }, userData || {}),
      custom_data: Object.assign({
        event_source_url: window.location.href,
        referrer: document.referrer || undefined,
      }, customData || {}),
    };

    try {
      await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": "Bearer " + secret,
        },
        body: JSON.stringify(payload),
        mode: "cors",
      });
    } catch (_) {}
  }

  // Auto-track PageView on load
  if (document.readyState === "complete" || document.readyState === "interactive") {
    track("PageView");
  } else {
    document.addEventListener("DOMContentLoaded", () => track("PageView"));
  }

  // Auto-listen to forms for Lead capture (Tilda, WordPress, etc.)
  document.addEventListener("submit", function (e) {
    const form = e.target;
    if (!form || !form.elements) return;
    let phone = "", email = "";
    for (let i = 0; i < form.elements.length; i++) {
      const el = form.elements[i];
      const val = (el.value || "").trim();
      const n = (el.name || el.type || el.id || "").toLowerCase();
      if (!phone && (n.includes("phone") || n.includes("tel") || el.type === "tel")) phone = val;
      if (!email && (n.includes("email") || el.type === "email")) email = val;
    }
    track("Lead", { form_id: form.id || form.getAttribute("name") || "web_form" }, {
      phone: phone || undefined,
      email: email || undefined,
    });
  }, true);

  window.JonCapi = { track: track };
})(window, document);
