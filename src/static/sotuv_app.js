// O'zbekcha amoCRM 1:1 — Kanban, Drag-and-Drop, Tezkor Qo'shish va Fokus Dialer Dvigateli
let currentPipelineId = 11162698;
let currentRepId = "";
let currentTagFilter = "";
let currentSearchQuery = "";
let crmCatalog = null;
let kanbanData = null;
let dashboardCache = null;
let leadsQueue = [];
let queueIndex = 0;
let currentLead = null;
let activeDrawerLead = null;
let draggedLeadId = null;
let searchDebounceTimer = null;

window.addEventListener("DOMContentLoaded", async () => {
  await fetchBootstrap();
  setupKeyboardShortcuts();
  if (typeof startCallerIdPolling === "function") startCallerIdPolling();
  const urlParams = new URLSearchParams(window.location.search);
  const viewParam = urlParams.get("view");
  if (viewParam) setViewMode(viewParam);
  const leadParam = urlParams.get("lead_id");
  if (leadParam) setTimeout(() => openDealDrawer(leadParam), 150);
});

async function fetchBootstrap() {
  try {
    const res = await fetch(`/api/crm/dialer/bootstrap?pipeline_id=${currentPipelineId}`);
    if (res.status === 401) return; // seller not logged in yet; reloaded after login
    if (!res.ok) throw new Error(`bootstrap ${res.status}`);
    const data = await res.json();
    crmCatalog = data.catalog;
    kanbanData = data.kanban;
    dashboardCache = data.dashboard || null;
    leadsQueue = data.queue || [];
    if (dashboardCache?.kpis?.overdue_tasks_count !== undefined) {
      const tb = document.getElementById("navBadgeTasks");
      if (tb) tb.innerText = dashboardCache.kpis.overdue_tasks_count || 112;
    }
    renderPipelineMenu();
    if (kanbanData) renderAmoKanban(kanbanData);
    if (leadsQueue.length > 0) {
      queueIndex = 0;
      renderCurrentLead(leadsQueue[0]);
    }
    if (typeof renderCustomFieldsForm === "function") setTimeout(renderCustomFieldsForm, 20);
  } catch (err) {
    await Promise.all([fetchCatalog(), fetchKanban(), fetchQueue()]);
  }
}

async function fetchCatalog() {
  try {
    const res = await fetch("/api/crm/dialer/catalog");
    crmCatalog = await res.json();
    renderPipelineMenu();
    if (typeof renderCustomFieldsForm === "function") renderCustomFieldsForm();
  } catch (err) {
    console.error("Catalog fetch error:", err);
  }
}

function renderPipelineMenu() {
  const menu = document.getElementById("pipelineMenu");
  if (!menu || !crmCatalog) return;
  menu.innerHTML = "";
  (crmCatalog.pipelines || []).forEach((p) => {
    const btn = document.createElement("button");
    btn.className = "w-full text-left px-4 py-2.5 text-[14px] font-semibold text-[#2e3640] hover:bg-[#eff6ff] hover:text-[#4c8bf7] flex items-center justify-between gap-2 border-b border-[#f0f3f6] last:border-0";
    btn.onclick = () => switchPipeline(p.id, p.name);
    const badgeColor = p.is_archive ? "text-[#94a3b8]" : "text-[#4c8bf7] font-bold";
    btn.innerHTML = `<span class="truncate">${p.name}</span>
      <span class="flex items-center gap-2 shrink-0">
        <span class="text-[12px] px-2 py-0.5 rounded bg-[#f5f5f5] text-[#64748b]">${p.leads_count || 0}</span>
        <span class="text-[12px] ${badgeColor}">${p.badge || ""}</span>
      </span>`;
    menu.appendChild(btn);
  });
}

async function fetchKanban() {
  try {
    const params = new URLSearchParams({ pipeline_id: currentPipelineId });
    if (currentRepId) params.set("rep_id", currentRepId);
    if (currentSearchQuery) params.set("q", currentSearchQuery);
    if (currentTagFilter) params.set("tag", currentTagFilter);
    const res = await fetch(`/api/crm/dialer/kanban?${params.toString()}`);
    kanbanData = await res.json();
    renderAmoKanban(kanbanData);
  } catch (err) {
    console.error("Kanban fetch error:", err);
  }
}

function renderAmoKanban(data) {
  const container = document.getElementById("amoKanbanView");
  if (!container) return;
  container.innerHTML = "";
  document.getElementById("headerTotalCount").innerText = data.total_leads || 0;
  document.getElementById("headerTotalSum").innerText = Number(data.total_sum || 0).toLocaleString("uz-UZ");
  if (data.pipeline_name) document.getElementById("currentPipelineName").innerText = data.pipeline_name.toUpperCase();

  const frag = document.createDocumentFragment();
  (data.stages || []).forEach((st, colIdx) => {
    const stageSumFormatted = Number(st.sum || 0).toLocaleString("uz-UZ");
    const col = document.createElement("div");
    col.className = "w-[320px] min-w-[320px] flex flex-col h-full shrink-0 select-none";
    col.dataset.stageSlug = st.slug;
    col.ondragover = (e) => { e.preventDefault(); col.classList.add("bg-[#eff6ff]", "rounded"); };
    col.ondragleave = () => col.classList.remove("bg-[#eff6ff]", "rounded");
    col.ondrop = async (e) => {
      e.preventDefault();
      col.classList.remove("bg-[#eff6ff]", "rounded");
      const droppedId = parseInt(e.dataTransfer.getData("text/plain") || draggedLeadId, 10);
      if (droppedId && st.slug) await handleKanbanDrop(droppedId, st.slug, st.title);
    };

    const header = document.createElement("div");
    header.className = "amo-column-header";
    header.style.borderBottomColor = st.color || "#60a5fa";
    header.innerHTML = `
      <div class="amo-column-title" title="${st.title}">${st.title}</div>
      <div class="amo-column-stats">${st.count || 0} ta bitim: <strong class="text-[#19222b] font-semibold tabular-nums">${stageSumFormatted} so'm</strong></div>
    `;
    col.appendChild(header);

    const cardsList = document.createElement("div");
    cardsList.className = "flex-1 flex flex-col gap-2.5 overflow-y-auto custom-scrollbar pr-1";

    if (colIdx === 0) {
      const quickAdd = document.createElement("div");
      quickAdd.innerHTML = `
        <button onclick="toggleQuickAddBox(this)" class="w-full py-2.5 px-3.5 bg-white hover:bg-[#f8fafc] border border-[#d8dde3] rounded text-[14px] font-medium text-[#92989b] text-center transition shadow-[0_1px_2px_rgba(0,0,0,0.03)]">Tezkor qo'shish</button>
        <div class="hidden mt-2 bg-white p-3 rounded border border-[#4c8bf7] shadow-sm flex flex-col gap-2">
          <input id="quickInlineName" type="text" placeholder="Bitim yoki mijoz nomi" class="text-[14px] border border-[#d8dde3] rounded px-2.5 py-1.5 focus:outline-none">
          <input id="quickInlinePhone" type="text" placeholder="+998 90 123 45 67" class="text-[14px] border border-[#d8dde3] rounded px-2.5 py-1.5 font-mono focus:outline-none">
          <input id="quickInlinePrice" type="number" placeholder="0 so'm" class="text-[14px] border border-[#d8dde3] rounded px-2.5 py-1.5 focus:outline-none">
          <div class="flex items-center justify-end pt-1">
            <button onclick="submitQuickInlineDeal('${st.slug}')" class="bg-[#4c8bf7] text-white text-[13px] font-bold px-3.5 py-1.5 rounded">Qo'shish</button>
          </div>
        </div>`;
      cardsList.appendChild(quickAdd);
    }

    (st.leads || []).slice(0, 65).forEach((l, idx) => {
      const card = document.createElement("div");
      card.className = "amo-deal-card group";
      card.draggable = true;
      card.ondragstart = (e) => {
        draggedLeadId = l.id;
        e.dataTransfer.setData("text/plain", String(l.id));
        card.classList.add("opacity-50");
      };
      card.ondragend = () => card.classList.remove("opacity-50");
      card.onclick = () => openDealDrawer(l.id);

      const contactLine = l.company_name
        ? `${l.contact_name || "Mijoz"}, ${l.company_name}`
        : `${l.contact_name || "Mijoz"} · ${l.responsible_name ? l.responsible_name.split(" ")[0] : "JB"}`;
      const formattedDate = formatAmoCardDate(l.updated_at);
      const titleClean = l.name || (l.phone ? `Bitim (${l.phone})` : `Bitim #${l.id}`);
      const priceVal = Number(l.price || 0);
      const tags = (l.tags || []).slice(0, 3);
      const extraTags = (l.tags || []).length > 3 ? `<span class="amo-badge">+${l.tags.length - 3}</span>` : "";
      const tagsHtml = tags.map((t) => `<span class="amo-badge truncate max-w-[130px]">${t}</span>`).join("") + extraTags;
      const taskMeta = calculateLeadTaskDot(l);

      card.innerHTML = `
        <div class="flex items-center justify-between amo-type-meta leading-tight">
          <span class="truncate max-w-[190px] text-[#4a5568] font-medium">${contactLine}</span>
          <span class="shrink-0 text-[#9da8b6] font-mono">${formattedDate}</span>
        </div>
        <div class="amo-card-title line-clamp-2">${titleClean}</div>
        ${priceVal > 0 ? `<div class="amo-card-price tabular-nums text-[#1e293b]">${priceVal.toLocaleString("uz-UZ")} soʻm</div>` : ""}
        <div class="flex items-center justify-between gap-1.5 pt-1 mt-0.5">
          <div class="flex items-center gap-1 flex-wrap">${tagsHtml}</div>
          <span class="amo-dot ${taskMeta.dotClass}" title="${taskMeta.title}"></span>
        </div>`;
      cardsList.appendChild(card);
    });

    col.appendChild(cardsList);
    frag.appendChild(col);
  });
  container.appendChild(frag);
}

function toggleQuickAddBox(btn) {
  btn.nextElementSibling?.classList.toggle("hidden");
}

async function submitQuickInlineDeal(stageSlug) {
  const name = document.getElementById("quickInlineName")?.value.trim();
  const phone = document.getElementById("quickInlinePhone")?.value.trim();
  const price = parseFloat(document.getElementById("quickInlinePrice")?.value) || 0;
  if (!name) { showToast("Bitim nomini kiriting"); return; }
  await fetch("/api/crm/dialer/lead", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      pipeline_id: currentPipelineId, name, contact_name: name,
      phone: phone || "", price, status_slug: stageSlug || "yangi",
      responsible_name: "Shahnoza Abdijabborova",
    }),
  });
  showToast("Yangi bitim tezkor qo'shildi!");
  await fetchKanban();
}

async function handleKanbanDrop(leadId, targetSlug, stageTitle) {
  if (targetSlug === "rad" || (stageTitle && stageTitle.toLowerCase().includes("rad"))) {
    let leadPrice = 0, leadName = `Bitim #${leadId}`;
    if (kanbanData?.stages) {
      for (const st of kanbanData.stages) {
        const found = (st.leads || []).find((l) => l.id === leadId);
        if (found) { leadPrice = found.price || 0; leadName = found.name || leadName; break; }
      }
    }
    if (typeof openLossModal === "function") {
      openLossModal(leadId, targetSlug, stageTitle, leadPrice, leadName);
      return;
    }
  }
  showToast(`Bosqich o'zgartirilmoqda: ${stageTitle}...`);
  try {
    await fetch("/api/crm/dialer/action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        lead_id: leadId, action_slug: targetSlug, pipeline_id: currentPipelineId,
        seller_name: "Kanban Drag&Drop", note: `Kanban orqali '${stageTitle}' bosqichiga o'tkazildi`,
      }),
    });
    showToast(`'${stageTitle}' bosqichiga o'tkazildi!`);
    await fetchKanban();
  } catch (err) {
    showToast("Xatolik yuz berdi");
  }
}

async function fetchQueue() {
  try {
    const params = new URLSearchParams({ limit: "120", pipeline_id: currentPipelineId });
    if (currentRepId) params.set("rep_id", currentRepId);
    const res = await fetch(`/api/crm/dialer/queue?${params.toString()}`);
    const data = await res.json();
    leadsQueue = data.leads || [];
    if (leadsQueue.length > 0) { queueIndex = 0; renderCurrentLead(leadsQueue[0]); }
  } catch (err) {}
}

function renderCurrentLead(lead) {
  if (!lead) return;
  currentLead = lead;
  document.getElementById("leadIdBadge").innerText = `#${lead.id}`;
  document.getElementById("leadStageBadge").innerText = lead.status_slug || "yangi";
  let cleanName = lead.name || "Nomsiz Bitim";
  if (cleanName.includes("|")) cleanName = cleanName.split("|")[0].trim();
  document.getElementById("leadNameDisplay").innerText = cleanName;
  document.getElementById("leadContactName").innerText = lead.contact_name || "Mijoz";
  document.getElementById("leadRepName").innerText = lead.responsible_name || "Shahnoza";
  const rawPhone = lead.phone || "+998 90 000 00 00";
  document.getElementById("leadPhoneDisplay").innerText = formatPhone(rawPhone);
  document.getElementById("callPhoneBtn").href = `tel:${rawPhone.replace(/\s+/g, "")}`;
  const priceCont = document.getElementById("leadPriceContainer");
  if (lead.price && lead.price > 0) {
    priceCont.classList.remove("hidden");
    document.getElementById("leadPriceDisplay").innerText = Number(lead.price).toLocaleString("uz-UZ");
  } else priceCont.classList.add("hidden");

  const audioContainer = document.getElementById("audioPlayerContainer");
  const audioPlayer = document.getElementById("leadAudioPlayer");
  const audioSource = document.getElementById("leadAudioSource");
  if (lead.last_audio_url) {
    audioContainer.classList.remove("hidden");
    audioSource.src = lead.last_audio_url;
    audioPlayer.load();
  } else {
    audioContainer.classList.add("hidden");
    audioPlayer.pause();
  }
  document.getElementById("quickNoteInput").value = "";
}

function setViewMode(mode) {
  closeDealDrawer();
  const views = {
    dashboard: "dashboardView", kanban: "amoKanbanView", list: "dealsListView",
    focus: "focusView", inbox: "inboxView", tasks: "tasksView", aibots: "aibotsView",
    directory: "directoryView", mail: "mailView", analytics: "analyticsView", settings: "settingsView",
  };
  Object.values(views).forEach((id) => document.getElementById(id)?.classList.add("hidden"));
  document.getElementById(views[mode] || "amoKanbanView")?.classList.remove("hidden");
  document.getElementById("amoTopHeader")?.classList.toggle("hidden", !["kanban", "list", "focus"].includes(mode));

  document.querySelectorAll(".amo-nav-btn").forEach((b) => b.classList.remove("amo-nav-active"));
  const navKey = ["list", "focus"].includes(mode) ? "kanban" : mode;
  document.getElementById(`navBtn_${navKey}`)?.classList.add("amo-nav-active");

  if (mode === "kanban") fetchKanban();
  else if (mode === "list" && typeof renderDealsTableView === "function") renderDealsTableView();
  else if (mode === "dashboard" && typeof renderDashboardView === "function") renderDashboardView();
  else if (mode === "inbox" && typeof renderInboxView === "function") renderInboxView();
  else if (mode === "tasks" && typeof renderTasksView === "function") renderTasksView();
  else if (mode === "aibots" && typeof renderAiBotsView === "function") renderAiBotsView();
  else if (mode === "directory" && typeof renderDirectoryView === "function") renderDirectoryView();
  else if (mode === "mail" && typeof renderMailView === "function") renderMailView();
  else if (mode === "analytics" && typeof renderAnalyticsView === "function") renderAnalyticsView();
  else if (mode === "settings" && typeof renderSettingsView === "function") renderSettingsView();
}

async function submitOutcome(outcomeSlug, customLeadId) {
  const targetLeadId = customLeadId || (currentLead ? currentLead.id : null);
  if (!targetLeadId) return;
  const note = document.getElementById("quickNoteInput")?.value.trim();
  if (!customLeadId) {
    leadsQueue.splice(queueIndex, 1);
    if (queueIndex >= leadsQueue.length) queueIndex = 0;
    renderCurrentLead(leadsQueue[queueIndex]);
  }
  await fetch("/api/crm/dialer/action", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      lead_id: targetLeadId, action_slug: outcomeSlug,
      pipeline_id: currentPipelineId, seller_name: "Sotuvchi", note: note || undefined,
    }),
  });
  showToast("Natija saqlandi!");
}

function skipLead(delta) {
  if (!leadsQueue.length) return;
  queueIndex = (queueIndex + delta + leadsQueue.length) % leadsQueue.length;
  renderCurrentLead(leadsQueue[queueIndex]);
}

function copyCurrentPhone() {
  if (currentLead?.phone) { navigator.clipboard.writeText(currentLead.phone); showToast("Raqam nusxalandi!"); }
}

function copyPhone(phone) {
  if (phone) { navigator.clipboard.writeText(phone); showToast("Raqam nusxalandi!"); }
}

function togglePipelineMenu() { document.getElementById("pipelineMenu")?.classList.toggle("hidden"); }

function switchPipeline(id, name) {
  currentPipelineId = id;
  document.getElementById("currentPipelineName").innerText = name.toUpperCase();
  document.getElementById("pipelineMenu")?.classList.add("hidden");
  fetchKanban(); fetchQueue(); showToast(`${name} voronkasiga o'tildi`);
}

function onRepChange(val) { currentRepId = val; fetchKanban(); fetchQueue(); }

function handleSearch(val) {
  currentSearchQuery = val.trim();
  clearTimeout(searchDebounceTimer);
  searchDebounceTimer = setTimeout(() => fetchKanban(), 120);
}

async function syncWithTwentyBackend() {
  showToast("Baza yangilanmoqda...");
  try {
    const res = await fetch("/api/crm/dialer/sync?mode=both_pull", { method: "POST" });
    const data = await res.json();
    await fetchKanban();
    showToast("Barcha bitimlar muvaffaqiyatli sinxronlandi!");
  } catch (err) {
    showToast("CRM sinxronizatsiya xatosi");
  }
}

function formatPhone(phone) {
  if (!phone) return "Raqam yo'q";
  const clean = phone.replace(/[^0-9+]/g, "");
  if (clean.length === 13 && clean.startsWith("+998")) {
    return `${clean.slice(0, 4)} ${clean.slice(4, 6)} ${clean.slice(6, 9)} ${clean.slice(9, 11)} ${clean.slice(11, 13)}`;
  }
  return clean;
}

function showToast(msg) {
  const t = document.getElementById("toast");
  document.getElementById("toastMsg").innerText = msg;
  t.classList.remove("translate-y-20", "opacity-0");
  setTimeout(() => t.classList.add("translate-y-20", "opacity-0"), 1800);
}

function setupKeyboardShortcuts() {
  window.addEventListener("keydown", (e) => {
    if (["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName)) return;
    if (e.key === "Escape") { closeDealDrawer(); closeNewDealModal(); }
  });
}
