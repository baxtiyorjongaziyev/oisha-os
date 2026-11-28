/* Oisha-OS Sales Quality Controller & Agentic Sales Chat (DOM-safe, <=400 lines) */
(function () {
  "use strict";

  var state = { days: 30, sortBy: "natija", selectedManager: "", chatHistory: [] };
  var mediaRecorder = null;
  var audioChunks = [];

  function $(sel) { return document.querySelector(sel); }
  function R() { return window.OishaSalesRender; }

  function switchMainView(viewId) {
    document.querySelectorAll(".view-pane").forEach(function (p) {
      p.classList.toggle("active", p.id === viewId);
    });
    document.querySelectorAll("[data-view-btn]").forEach(function (b) {
      b.classList.toggle("active", b.getAttribute("data-view-btn") === viewId);
    });
  }

  function updateCsvHref() {
    var link = $("#csvExportBtn");
    if (!link) return;
    link.setAttribute(
      "href",
      "/api/sales-quality/leaderboard.csv?days=" + encodeURIComponent(state.days) +
      "&sort_by=" + encodeURIComponent(state.sortBy)
    );
  }

  async function loadOverviewAndCards() {
    var baseUrl = document.body.getAttribute("data-conversion-endpoint") || "/api/sales-quality/conversion-overview";
    try {
      var res = await fetch(baseUrl + "?days=" + encodeURIComponent(state.days), { credentials: "same-origin" });
      if (res.ok) R().renderOverviewKpis($("#overviewApp"), await res.json());
    } catch (_e) {
      R().renderOverviewKpis($("#overviewApp"), null);
    }
    try {
      var cRes = await fetch("/api/sales-quality/manager-cards", { credentials: "same-origin" });
      if (cRes.ok) R().renderManagerCards($("#mgrCardsApp"), await cRes.json());
    } catch (_e2) {
      R().renderManagerCards($("#mgrCardsApp"), null);
    }
  }

  async function loadLeaderboard() {
    updateCsvHref();
    try {
      var url = "/api/sales-quality/leaderboard?days=" + encodeURIComponent(state.days) +
        "&sort_by=" + encodeURIComponent(state.sortBy);
      var res = await fetch(url, { credentials: "same-origin" });
      var payload = res.ok ? await res.json() : null;
      R().renderLeaderboard($("#leaderboardApp"), $("#leaderboardMeta"), payload, function (mgrName) {
        state.selectedManager = mgrName;
        loadChecklist(mgrName);
      });
    } catch (_e) {
      R().renderLeaderboard($("#leaderboardApp"), $("#leaderboardMeta"), null, function () {});
    }
  }

  async function loadChecklist(mgrName) {
    try {
      var q = "/api/sales-quality/checklist?days=" + encodeURIComponent(state.days);
      if (mgrName) q += "&manager_name=" + encodeURIComponent(mgrName);
      var res = await fetch(q, { credentials: "same-origin" });
      R().renderChecklist($("#checklistApp"), $("#checklistTitle"), res.ok ? await res.json() : null);
    } catch (_e) {
      R().renderChecklist($("#checklistApp"), $("#checklistTitle"), null);
    }
  }

  function appendChatReply(questionText, reply) {
    var stream = $("#chatStream");
    if (!stream) return;
    var el = R().el;
    stream.appendChild(el("div", "chat-user", questionText));

    var card = el("div", "chat-assistant");
    if (reply && Array.isArray(reply.actions) && reply.actions.length) {
      var details = el("details", "chat-actions");
      details.appendChild(el("summary", "", reply.actions.length + " ta amal bajarildi"));
      var ul = el("ul", "chat-actions-list");
      reply.actions.forEach(function (act) {
        ul.appendChild(el("li", "", act.label + " (" + act.records + ")"));
      });
      details.appendChild(ul);
      card.appendChild(details);
    }

    String((reply && reply.answer) || "Javob olinmadi.").split("\n").forEach(function (line) {
      var trimmed = line.trim();
      if (trimmed) card.appendChild(el("p", "chat-line", trimmed.replace(/\*\*/g, "")));
    });
    stream.appendChild(card);
    stream.scrollTop = stream.scrollHeight;
  }

  async function sendChatQuestion(prefilled) {
    var input = $("#chatQuestionInput");
    var q = (prefilled || (input ? input.value : "")).trim();
    if (!q) return;
    if (input && !prefilled) input.value = "";
    var statusEl = $("#chatStatus");
    if (statusEl) statusEl.textContent = "Oisha AI bazadan tekshirmoqda...";

    try {
      var res = await fetch("/api/sales-quality/chat", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q, days: state.days, history: state.chatHistory })
      });
      var data = await res.json();
      if (!res.ok) {
        appendChatReply(q, { answer: "Xatolik: " + (data.reason || data.error || res.status), actions: [] });
      } else {
        appendChatReply(q, data);
        state.chatHistory.push({ role: "user", content: q });
        state.chatHistory.push({ role: "assistant", content: data.answer || "", focus_manager: data.focus_manager || "" });
        if (state.chatHistory.length > 8) state.chatHistory = state.chatHistory.slice(-8);
      }
    } catch (err) {
      appendChatReply(q, { answer: "Ulanish xatosi: " + err.message, actions: [] });
    } finally {
      if (statusEl) statusEl.textContent = "";
    }
  }

  async function submitRecordedBlob(blob, statusEl) {
    var reader = new FileReader();
    reader.onloadend = async function () {
      var raw = String(reader.result || "");
      var b64 = raw.indexOf(",") >= 0 ? raw.split(",")[1] : raw;
      if (statusEl) statusEl.textContent = "Ovoz tahlil qilinmoqda...";
      try {
        var res = await fetch("/api/sales-quality/chat/voice", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            audio_base64: b64,
            mime_type: blob.type || "audio/webm",
            days: state.days,
            history: state.chatHistory
          })
        });
        var data = await res.json();
        if (res.ok) {
          appendChatReply("🎙️ " + (data.transcript || "Ovozli savol"), data);
          if (statusEl) statusEl.textContent = "";
        } else if (statusEl) {
          statusEl.textContent = data.reason || data.error || "Ovoz aniqlanmadi";
        }
      } catch (_err) {
        if (statusEl) statusEl.textContent = "Ovoz yuborishda xatolik.";
      }
    };
    reader.readAsDataURL(blob);
  }

  async function toggleVoiceRecording() {
    var btn = $("#chatMicBtn");
    var statusEl = $("#chatStatus");
    if (mediaRecorder && mediaRecorder.state === "recording") {
      mediaRecorder.stop();
      return;
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      if (statusEl) statusEl.textContent = "Brauzerda mikrofon ruxsati mavjud emas.";
      return;
    }
    try {
      var stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunks = [];
      mediaRecorder = new MediaRecorder(stream);
      if (btn) btn.classList.add("recording");
      if (statusEl) statusEl.textContent = "Yozilmoqda... Tugatish uchun mikrofonni qayta bosing.";
      mediaRecorder.ondataavailable = function (ev) { if (ev.data.size > 0) audioChunks.push(ev.data); };
      mediaRecorder.onstop = function () {
        if (btn) btn.classList.remove("recording");
        stream.getTracks().forEach(function (t) { t.stop(); });
        submitRecordedBlob(new Blob(audioChunks, { type: mediaRecorder.mimeType || "audio/webm" }), statusEl);
      };
      mediaRecorder.start();
    } catch (_e) {
      if (statusEl) statusEl.textContent = "Mikrofonga ruxsat berilmadi.";
    }
  }

  function refreshAll() {
    loadOverviewAndCards();
    loadLeaderboard();
    loadChecklist(state.selectedManager);
  }

  window.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-view-btn]").forEach(function (btn) {
      btn.addEventListener("click", function () { switchMainView(btn.getAttribute("data-view-btn")); });
    });
    document.querySelectorAll("[data-sort-btn]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        state.sortBy = btn.getAttribute("data-sort-btn") || "natija";
        document.querySelectorAll("[data-sort-btn]").forEach(function (b) { b.classList.toggle("active", b === btn); });
        loadLeaderboard();
      });
    });
    var daysSel = $("#daysSelect");
    if (daysSel) daysSel.addEventListener("change", function () { state.days = Number(daysSel.value) || 30; refreshAll(); });
    var teamChkBtn = $("#resetTeamChecklistBtn");
    if (teamChkBtn) teamChkBtn.addEventListener("click", function () { state.selectedManager = ""; loadChecklist(""); });
    var sendBtn = $("#chatSendBtn");
    if (sendBtn) sendBtn.addEventListener("click", function () { sendChatQuestion(); });
    var input = $("#chatQuestionInput");
    if (input) input.addEventListener("keydown", function (ev) { if (ev.key === "Enter" && !ev.shiftKey) { ev.preventDefault(); sendChatQuestion(); } });
    var newChatBtn = $("#newChatBtn");
    if (newChatBtn) newChatBtn.addEventListener("click", function () { state.chatHistory = []; R().clearNode($("#chatStream")); });
    var micBtn = $("#chatMicBtn");
    if (micBtn) micBtn.addEventListener("click", toggleVoiceRecording);
    document.querySelectorAll("[data-prompt-chip]").forEach(function (chip) {
      chip.addEventListener("click", function () { switchMainView("view-chat"); sendChatQuestion(chip.getAttribute("data-prompt-chip")); });
    });
    if (window.location.pathname.indexOf("sales-chat") !== -1 || window.location.hash === "#chat") switchMainView("view-chat");
    refreshAll();
    setInterval(refreshAll, 60 * 60 * 1000);
  });
})();
