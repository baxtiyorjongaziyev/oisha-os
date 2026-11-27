// O'zbekcha amoCRM 1:1 — Bitim Kartochkasi Drawer va Timeline Boshqaruvi
// Optimistic 0ms Render, Background Enrichment, Fail-Safe DOM Manipulation (<= 400 lines)
const _esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const _safeUrl = (u) => (/^https?:\/\//i.test(String(u || "").trim()) ? _esc(String(u).trim()) : "#");
const _posInt = (v) => { const s = String(v ?? "").trim(); const n = /^\d+$/.test(s) ? Number(s) : 0; return Number.isSafeInteger(n) && n > 0 ? n : 0; };

function renderCustomFieldsForm() {
  const container = document.getElementById("drawerBantFieldsContainer");
  if (!container || !crmCatalog) return;
  container.replaceChildren();
  (crmCatalog.custom_fields_schema || []).forEach((f) => {
    const row = document.createElement("div"); row.className = "amo-field-row";
    const lbl = document.createElement("div"); lbl.className = "amo-field-label"; lbl.title = String(f.label || ""); lbl.textContent = String(f.label || "");
    const valBox = document.createElement("div"); valBox.className = "amo-field-val";
    let ctrl;
    if (f.type === "select") {
      ctrl = document.createElement("select");
      ctrl.className = "cf-input w-full bg-transparent text-[15px] font-semibold text-[#2e3640] focus:outline-none focus:bg-[#f8fafc] rounded py-1";
      ["", ...(f.options || [])].forEach((o, idx) => { const opt = document.createElement("option"); opt.value = idx === 0 ? "" : String(o); opt.textContent = idx === 0 ? "Tanlash" : String(o); ctrl.appendChild(opt); });
    } else {
      ctrl = document.createElement("input");
      ctrl.type = f.type === "number" ? "number" : f.type === "date" ? "date" : "text";
      ctrl.placeholder = "...";
      ctrl.className = "cf-input w-full bg-transparent text-[15px] font-semibold text-[#2e3640] placeholder-[#b0b8c0] focus:outline-none border-b border-transparent focus:border-[#4c8bf7]";
    }
    ctrl.dataset.cfKey = String(f.key || "");
    valBox.appendChild(ctrl); row.append(lbl, valBox); container.appendChild(row);
  });
}

function getAuthHeaders() {
  try {
    const tok = localStorage.getItem("jon_crm_token");
    if (tok) return { Authorization: `Bearer ${tok}`, "X-Seller-Token": tok, "X-CRM-Session-Token": tok };
    const raw = localStorage.getItem("jon_crm_seller_session");
    if (raw) {
      const sess = JSON.parse(raw);
      if (sess?.token) return { Authorization: `Bearer ${sess.token}`, "X-Seller-Token": sess.token, "X-CRM-Session-Token": sess.token };
    }
  } catch (e) { console.warn("Auth parse error:", e); }
  return {};
}

async function openDealDrawer(leadIdOrObj) {
  const isObj = typeof leadIdOrObj === "object" && leadIdOrObj !== null;
  const leadId = _posInt(isObj ? leadIdOrObj.id : leadIdOrObj);
  if (!leadId) return;
  document.getElementById("dealDrawer")?.classList.remove("hidden");
  activeDrawerLead = isObj ? { ...leadIdOrObj, id: leadId } : { id: leadId };
  if (isObj) {
    try { renderDrawer(activeDrawerLead); } catch (e) { console.warn("Drawer render warning:", e); }
  }

  try {
    const res = await fetch(`/api/crm/dialer/lead/${leadId}`, { headers: getAuthHeaders() });
    if (res.ok) {
      const data = await res.json();
      if (data?.lead && activeDrawerLead && _posInt(activeDrawerLead.id) === leadId) {
        activeDrawerLead = { ...activeDrawerLead, ...data.lead, id: leadId };
        renderDrawer(activeDrawerLead);
        if (typeof loadLeadCallHistory === "function") loadLeadCallHistory(leadId);
      }
    }
  } catch (err) {
    if (!isObj) console.error("Fetch lead error:", err);
  }
}

function renderDrawer(lead) {
  if (!lead) return;
  const drawerEl = document.getElementById("dealDrawer");
  if (drawerEl) drawerEl.classList.remove("hidden");

  const setVal = (id, val) => { const el = document.getElementById(id); if (el) el.value = val !== undefined && val !== null ? val : ""; };
  const setText = (id, txt) => { const el = document.getElementById(id); if (el) el.innerText = txt !== undefined && txt !== null ? txt : ""; };

  setText("drawerLeadIdBadge", `#${lead.id}`);
  setVal("drawerLeadTitle", lead.name || "");
  setVal("drawerCompanyInput", lead.company_name || "");
  setVal("drawerPriceInput", lead.price || 0);
  setVal("drawerContactName", lead.contact_name || "");
  setVal("drawerContactPhone", lead.phone || "");

  const callBtn = document.getElementById("drawerCallBtn");
  if (callBtn) {
    const digits = String(lead.phone || "").replace(/\D/g, "");
    callBtn.setAttribute("href", /^\d{5,15}$/.test(digits) ? `tel:+${digits}` : "#");
  }

  const stageSelect = document.getElementById("drawerStageSelect");
  const pipe = (crmCatalog?.pipelines || []).find((p) => p.id === lead.pipeline_id) || crmCatalog?.pipelines?.[0];
  if (pipe && stageSelect) {
    stageSelect.replaceChildren(...(pipe.statuses || []).map((st) => { const o = document.createElement("option"); o.value = String(st.slug || ""); o.textContent = String(st.title || ""); return o; }));
    stageSelect.value = lead.status_slug || pipe.statuses?.[0]?.slug || "";
    const stIdx = Math.max(0, (pipe.statuses || []).findIndex((s) => s.slug === stageSelect.value));
    const pct = Math.min(100, Math.max(15, Math.round(((stIdx + 1) / Math.max(pipe.statuses.length, 1)) * 100)));
    const prog = document.getElementById("drawerStageProgress");
    if (prog) {
      prog.style.width = `${pct}%`;
      prog.style.backgroundColor = pipe.statuses[stIdx]?.color || "#60a5fa";
    }
    stageSelect.onchange = () => {
      const sVal = stageSelect.value;
      const idx = Math.max(0, (pipe.statuses || []).findIndex((s) => s.slug === sVal));
      if (prog) {
        prog.style.width = `${Math.min(100, Math.max(15, Math.round(((idx + 1) / Math.max(pipe.statuses.length, 1)) * 100)))}%`;
        prog.style.backgroundColor = pipe.statuses[idx]?.color || "#60a5fa";
      }
      if (sVal === "rad" && activeDrawerLead && typeof openLossModal === "function") {
        openLossModal(activeDrawerLead.id, "rad", "Rad etildi", activeDrawerLead.price, activeDrawerLead.name);
      }
    };
  }

  const cf = lead.custom_fields || {};
  document.querySelectorAll(".cf-input").forEach((el) => {
    const val = cf[el.dataset.cfKey];
    el.value = Array.isArray(val) ? val.join(", ") : val !== undefined && val !== null ? val : "";
  });

  renderDrawerTags(lead.tags || []);
  renderDrawerFiles(lead.files || []);
  renderDrawerAiAnalysis(lead.ai_analysis || {});
  renderDrawerTimeline(lead);
  setDrawerChatMode("note");
  startDrawerAutoRefresh(lead.id);

  const audioBox = document.getElementById("drawerAudioPlayerBox");
  const player = document.getElementById("drawerAudioPlayer");
  const src = document.getElementById("drawerAudioSource");
  if (audioBox && player && src) {
    let validAudio = "";
    try {
      const parsed = new URL(String(lead.last_audio_url || "").trim(), window.location.origin);
      if (parsed.protocol === "https:" || parsed.protocol === "http:") {
        validAudio = `${parsed.origin}${parsed.pathname}${parsed.search}`;
      }
    } catch (_) {
      validAudio = "";
    }
    if (validAudio) {
      audioBox.classList.remove("hidden");
      src.src = validAudio;
      player.load();
    } else {
      audioBox.classList.add("hidden");
    }
  }
}

function triggerDrawer1ClickCall() {
  if (!activeDrawerLead) return;
  const phone = document.getElementById("drawerContactPhone")?.value || activeDrawerLead.phone;
  if (typeof trigger1ClickCall === "function") trigger1ClickCall(activeDrawerLead.id, phone);
  else {
    const digits = String(phone || "").replace(/\D/g, "");
    if (/^\d{5,15}$/.test(digits)) window.open(`tel:+${digits}`, "_self");
  }
}

function renderDrawerTags(tags) {
  const box = document.getElementById("drawerTagsList");
  if (!box) return;
  box.innerHTML = (tags || []).map((t, idx) => `
    <span class="text-[12px] bg-[#303d4b] text-[#e2e8f0] px-2.5 py-1 rounded font-semibold flex items-center gap-1.5">
      ${_esc(t)}<button onclick="removeDrawerTag(${idx})" class="text-[#9db0be] hover:text-red-400 font-bold">&times;</button>
    </span>`).join("");
}

function addDrawerTag() {
  const inp = document.getElementById("drawerNewTagInput");
  const val = (inp?.value || "").trim().replace(/^#/, "");
  if (!val || !activeDrawerLead) return;
  if (!activeDrawerLead.tags) activeDrawerLead.tags = [];
  if (!activeDrawerLead.tags.includes(val)) {
    activeDrawerLead.tags.push(val);
    renderDrawerTags(activeDrawerLead.tags);
  }
  inp.value = "";
}

function removeDrawerTag(index) {
  if (!activeDrawerLead || !activeDrawerLead.tags) return;
  activeDrawerLead.tags.splice(index, 1);
  renderDrawerTags(activeDrawerLead.tags);
}

function renderDrawerFiles(files) {
  const box = document.getElementById("drawerFilesList");
  if (!box) return;
  if (!files || files.length === 0) {
    box.innerHTML = `<div class="text-[13px] text-[#94a3b8] italic">Hujjatlar biriktirilmagan</div>`;
    return;
  }
  box.innerHTML = files.map((f) => `
    <div class="flex items-center justify-between p-2 rounded bg-white border border-[#e2e8f0] text-xs">
      <a href="${_safeUrl(f.url)}" target="_blank" rel="noopener noreferrer" class="font-semibold text-[#1565c0] hover:underline truncate max-w-[200px]">${_esc(f.name || f.url)}</a>
      <span class="text-[10px] text-[#64748b] uppercase font-mono">${_esc(f.type || "fayl")}</span>
    </div>`).join("");
}

async function submitDrawerFile() {
  if (!activeDrawerLead) return;
  const nameEl = document.getElementById("drawerFileName");
  const urlEl = document.getElementById("drawerFileUrl");
  const typeEl = document.getElementById("drawerFileType");
  const name = nameEl?.value.trim();
  const url = urlEl?.value.trim();
  const type = typeEl?.value || "kp";
  if (!url) { if (typeof showToast === "function") showToast("Havolani kiriting"); return; }
  if (!activeDrawerLead.files) activeDrawerLead.files = [];
  activeDrawerLead.files.push({ name: name || url, url, type });
  renderDrawerFiles(activeDrawerLead.files);
  if (nameEl) nameEl.value = "";
  if (urlEl) urlEl.value = "";
  if (typeof showToast === "function") showToast("Hujjat biriktirildi!");
}

function renderDrawerAiAnalysis(ai) {
  const box = document.getElementById("drawerAiAnalysisBox");
  if (!box) return;
  if (!ai || !ai.summary) {
    box.innerHTML = `<div class="text-[14px] text-[#64748b]">Oisha AI tahlili uchun yuqoridagi tugmani bosing.</div>`;
    return;
  }
  const recs = (ai.recommendations || []).map((r) => `<li class="text-[14px] text-[#2e3640] leading-relaxed">${_esc(r)}</li>`).join("");
  box.innerHTML = `
    <div class="flex items-center justify-between border-b border-[#e5e7eb] pb-2 mb-2.5">
      <span class="text-[14px] font-bold text-[#2e3640]">BANT: <span class="text-[#4c8bf7]">${_esc(ai.bant_score || 75)}/100</span></span>
      <span class="text-[13px] font-semibold px-2 py-0.5 rounded bg-[#ecfdf5] text-[#047857]">${_esc(ai.sentiment || "Ijobiy")}</span>
    </div>
    <p class="text-[14px] text-[#334155] mb-2 leading-relaxed"><b>Xulosa:</b> ${_esc(ai.summary)}</p>
    <p class="text-[14px] text-[#b45309] bg-[#fffbeb] p-2 rounded border border-[#fde68a] mb-2"><b>Mijoz ogʻrigʻi:</b> ${_esc(ai.pain_point || "")}</p>
    <ul class="list-disc pl-4 space-y-1 mb-2">${recs}</ul>
    <div class="text-[14px] font-bold text-[#15803d] bg-[#f0fdf4] p-2 rounded border border-[#bbf7d0]">Keyingi qadam: ${_esc(ai.next_best_action || "")}</div>`;
}

async function runDrawerAiAnalysis() {
  if (!activeDrawerLead) return;
  const box = document.getElementById("drawerAiAnalysisBox");
  if (box) box.innerHTML = `<div class="text-[14px] text-[#0284c7] font-semibold animate-pulse">Oisha AI tahlili tayyorlanmoqda...</div>`;
  try {
    const res = await fetch(`/api/crm/dialer/calls/ai-analyze-lead/${activeDrawerLead.id}`, {
      method: "POST", headers: { "Content-Type": "application/json", ...getAuthHeaders() }
    });
    const data = await res.json();
    if (data?.analysis) {
      activeDrawerLead.ai_analysis = data.analysis;
      renderDrawerAiAnalysis(data.analysis);
      if (typeof showToast === "function") showToast("AI tahlil yangilandi!");
    } else if (box) {
      box.innerHTML = `<div class="text-[14px] text-[#ef4444]">Tahlil natijasi olinmadi.</div>`;
    }
  } catch (err) {
    if (box) box.innerHTML = `<div class="text-[14px] text-[#ef4444]">AI tahlilida xatolik yuz berdi.</div>`;
  }
}

let currentDrawerChatMode = "note";
let drawerRefreshTimer = null;

function setDrawerChatMode(mode) {
  currentDrawerChatMode = mode;
  ["note", "telegram", "instagram"].forEach((m) => {
    const tab = document.getElementById(`drawerChatTab_${m}`);
    if (tab) {
      tab.className = m === mode ? "px-2.5 py-1 rounded bg-white font-bold text-[#2e3640] shadow-sm" : `px-2.5 py-1 rounded ${m === "telegram" ? "text-[#0284c7]" : m === "instagram" ? "text-[#ec4899]" : "text-[#64748b]"} hover:bg-white/60`;
    }
  });

  const infoBox = document.getElementById("drawerChatTargetInfo");
  const infoText = document.getElementById("drawerChatTargetText");
  const input = document.getElementById("drawerChatInput");
  const sendBtn = document.getElementById("drawerChatSendBtn");
  const lead = activeDrawerLead || {};
  const cf = lead.custom_fields || {};
  const tgTarget = cf.telegram_username ? `@${cf.telegram_username.replace(/^@/, "")}` : lead.phone || "Telegram raqam";

  if (mode === "telegram") {
    infoBox?.classList.remove("hidden");
    if (infoText) infoText.innerHTML = `Telegram: <b>${_esc(tgTarget)}</b>`;
    if (input) input.placeholder = "Mijozga Telegram orqali xabar yozing...";
    if (sendBtn) { sendBtn.className = "bg-[#0284c7] hover:bg-[#0369a1] text-white text-sm font-bold px-4 py-2 rounded shrink-0 shadow-sm"; sendBtn.innerHTML = "<span>Yuborish</span>"; }
  } else if (mode === "instagram") {
    infoBox?.classList.remove("hidden");
    if (infoText) infoText.innerHTML = `Instagram Direct: <b>${_esc(lead.contact_name || "Mijoz")}</b>`;
    if (input) input.placeholder = "Mijozga Instagram Direct orqali xabar yozing...";
    if (sendBtn) { sendBtn.className = "bg-[#ec4899] hover:bg-[#db2777] text-white text-sm font-bold px-4 py-2 rounded shrink-0 shadow-sm"; sendBtn.innerHTML = "<span>Yuborish</span>"; }
  } else {
    infoBox?.classList.add("hidden");
    if (input) input.placeholder = "Jamoa uchun ichki izoh kiriting...";
    if (sendBtn) { sendBtn.className = "bg-[#4c8bf7] hover:bg-[#3b78e7] text-white text-sm font-bold px-4 py-2 rounded shrink-0 shadow-sm"; sendBtn.innerHTML = "<span>Qo'shish</span>"; }
  }
  input?.focus();
}

function renderDrawerTimeline(lead) {
  const timeline = document.getElementById("drawerTimelineList");
  if (!timeline) return;
  const safeLeadId = Number.parseInt(lead.id, 10) || 0;
  const items = [`<div class="text-[13px] text-[#64748b] flex items-center gap-2 py-1 flex-wrap"><span class="text-[#92989b]">Bugun</span><strong class="text-[#2e3640]">amoCRM</strong><span>Bitim #${safeLeadId} ochildi</span>${(lead.tags || []).map((t) => `<span class="bg-[#dce1e7] text-[#475569] text-[11px] px-2 py-0.5 rounded font-semibold">${_esc(t)}</span>`).join("")}</div>`];
  (lead.call_logs || []).forEach((log) => {
    items.push(`<div class="text-[13px] text-[#64748b] flex items-center gap-2 py-1"><span class="text-[#92989b]">${_esc((log.created_at || "Bugun").slice(11, 16) || "14:15")}</span><strong class="text-[#2e3640]">${_esc(log.seller_name || "Sotuvchi")}</strong><span>Yangi bosqich:</span><span class="bg-[#dbeafe] text-[#1d4ed8] text-[12px] font-semibold px-2 py-0.5 rounded">${_esc(log.new_status)}</span></div>`);
  });
  (lead.notes || []).slice().reverse().forEach((n, idx) => {
    const isTg = n.note_type === "telegram_out" || (n.text || "").includes("[Telegram]");
    const isIg = n.note_type === "instagram_out" || (n.text || "").includes("[Instagram]");
    const isIncoming = n.note_type === "chat_in" || (n.text || "").startsWith("Mijoz:");
    const isCallOrAudio = n.note_type === "call" || n.note_type === "audio" || !!n.audio_url || (n.text || "").includes("MoiZvonki");
    if (isCallOrAudio && typeof buildAudioPlayerHtml === "function") {
      items.push(buildAudioPlayerHtml({ by: n.by || "Sotuvchi", time: n.time || "Bugun", duration: n.duration || 0, audio_url: n.audio_url || "", direction: (n.text || "").includes("Kiruvchi") ? "in" : "out" }, `timeline_call_${safeLeadId}_${idx}`));
    } else if (isTg) {
      items.push(`<div class="bg-[#f0f9ff] border-l-4 border-[#0284c7] p-3 rounded-r shadow-xs flex flex-col gap-1"><div class="flex items-center justify-between text-xs text-[#0284c7] font-bold"><span>Telegram • ${_esc(n.by || "Sotuvchi")}</span><span class="text-[#64748b] font-normal">${_esc(n.time || "Hozir")}</span></div><div class="text-[#0f172a] text-[14px] leading-relaxed whitespace-pre-line">${_esc((n.text || "").replace(/^(?:\u1F4AC\s*)?\[Telegram\]\s*/, ""))}</div></div>`);
    } else if (isIg) {
      items.push(`<div class="bg-[#fdf2f8] border-l-4 border-[#ec4899] p-3 rounded-r shadow-xs flex flex-col gap-1"><div class="flex items-center justify-between text-xs text-[#ec4899] font-bold"><span>Instagram Direct • ${_esc(n.by || "Sotuvchi")}</span><span class="text-[#64748b] font-normal">${_esc(n.time || "Hozir")}</span></div><div class="text-[#0f172a] text-[14px] leading-relaxed whitespace-pre-line">${_esc((n.text || "").replace(/^(?:\u1F4AC\s*)?\[Instagram Direct\]\s*/, ""))}</div></div>`);
    } else if (isIncoming) {
      items.push(`<div class="bg-white border-l-4 border-[#22c55e] p-3 rounded-r shadow-xs flex flex-col gap-1"><div class="flex items-center justify-between text-xs text-[#16a34a] font-bold"><span>Mijoz javobi</span><span class="text-[#64748b] font-normal">${_esc(n.time || "Hozir")}</span></div><div class="text-[#0f172a] text-[14px] leading-relaxed whitespace-pre-line">${_esc(n.text || "")}</div></div>`);
    } else {
      items.push(`<div class="bg-white p-3 rounded border border-[#e5e7eb] text-[14px] shadow-xs flex flex-col gap-1"><div class="flex items-center justify-between text-[#92989b] text-xs"><b>${_esc(n.by || "Jon Branding")}</b><span>${_esc(n.time || "Bugun")}</span></div><div class="text-[#2e3640] whitespace-pre-line">${_esc(n.text || "")}</div></div>`);
    }
  });
  timeline.innerHTML = items.join("");
}

function switchDrawerTab(tabName) {
  ["bant", "files", "ai"].forEach((t) => {
    document.getElementById(`drawerTab_${t}`)?.classList.toggle("hidden", t !== tabName);
    const btn = document.getElementById(`drawerTabBtn_${t}`);
    if (btn) btn.className = t === tabName ? "pb-2 font-bold text-white border-b-2 border-[#00e5ff]" : "pb-2 text-[#9db0be] hover:text-white";
  });
}

function closeDealDrawer() { stopDrawerAutoRefresh(); document.getElementById("dealDrawer")?.classList.add("hidden"); }

async function saveDrawerLeadChanges(closeAfter = true) {
  if (!activeDrawerLead) return;
  const cfValues = {};
  document.querySelectorAll(".cf-input").forEach((el) => { const val = el.value.trim(); if (val) cfValues[el.dataset.cfKey] = val; });
  const stVal = document.getElementById("drawerStageSelect")?.value;
  if (stVal === "rad" && activeDrawerLead.status_slug !== "rad" && typeof openLossModal === "function") {
    openLossModal(activeDrawerLead.id, "rad", "Rad etildi", parseFloat(document.getElementById("drawerPriceInput")?.value) || activeDrawerLead.price, activeDrawerLead.name);
    return;
  }
  const repSelect = document.getElementById("drawerRepSelect");
  const payload = {
    id: activeDrawerLead.id, pipeline_id: activeDrawerLead.pipeline_id || currentPipelineId,
    name: document.getElementById("drawerLeadTitle")?.value.trim() || activeDrawerLead.name,
    company_name: document.getElementById("drawerCompanyInput")?.value.trim() || "",
    contact_name: document.getElementById("drawerContactName")?.value.trim() || "",
    phone: document.getElementById("drawerContactPhone")?.value.trim() || "",
    price: parseFloat(document.getElementById("drawerPriceInput")?.value) || 0,
    status_slug: stVal || "yangi",
    responsible_name: repSelect ? repSelect.options[repSelect.selectedIndex].text : "Shahnoza Abdijabborova",
    tags: activeDrawerLead.tags || [], custom_fields: cfValues,
  };
  await fetch("/api/crm/dialer/lead", { method: "POST", headers: { "Content-Type": "application/json", ...getAuthHeaders() }, body: JSON.stringify(payload) });
  if (typeof showToast === "function") showToast("Bitim muvaffaqiyatli saqlandi!");
  if (closeAfter) closeDealDrawer();
  if (typeof fetchKanban === "function") await fetchKanban();
}

async function submitDrawerChat() {
  const input = document.getElementById("drawerChatInput");
  const text = (input?.value || "").trim();
  const targetId = _posInt(activeDrawerLead?.id);
  if (!text || !targetId) return;
  const chan = currentDrawerChatMode === "telegram" ? "Telegram" : currentDrawerChatMode === "instagram" ? "Instagram Direct" : "note";
  input.value = "";
  const res = await fetch("/api/crm/dialer/inbox/send", {
    method: "POST", headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify({ lead_id: targetId, text, channel: chan, sender_name: "Shahnoza Abdijabborova" }),
  });
  const data = await res.json();
  if (data?.lead && _posInt(activeDrawerLead?.id) === targetId) { activeDrawerLead = data.lead; renderDrawerTimeline(activeDrawerLead); }
  if (typeof showToast === "function") showToast(chan === "Telegram" ? "Xabar mijozning Telegramiga yuborildi!" : chan === "Instagram Direct" ? "Xabar mijozning Instagramiga yuborildi!" : "Ichki izoh lentaga qoʻshildi");
}

function submitDrawerNote() { submitDrawerChat(); }

function startDrawerAutoRefresh(leadId) {
  stopDrawerAutoRefresh();
  const safeId = Number.parseInt(leadId, 10);
  if (!Number.isInteger(safeId) || safeId <= 0) return;
  drawerRefreshTimer = setInterval(async () => {
    if (!activeDrawerLead || Number.parseInt(activeDrawerLead.id, 10) !== safeId) { stopDrawerAutoRefresh(); return; }
    try {
      const res = await fetch(`/api/crm/dialer/lead/${safeId}`, { headers: getAuthHeaders() });
      const data = await res.json();
      if (data?.lead && (data.lead.notes || []).length !== (activeDrawerLead.notes || []).length) {
        activeDrawerLead = data.lead;
        renderDrawerTimeline(activeDrawerLead);
      }
    } catch (_) {}
  }, 4000);
}
function stopDrawerAutoRefresh() { if (drawerRefreshTimer) { clearInterval(drawerRefreshTimer); drawerRefreshTimer = null; } }
function copyDrawerPhone() {
  const p = document.getElementById("drawerContactPhone")?.value;
  if (p) { navigator.clipboard.writeText(p); if (typeof showToast === "function") showToast("Raqam nusxalandi!"); }
}
