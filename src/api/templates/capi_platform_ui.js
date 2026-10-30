/**
 * Jon Branding · Meta CAPI va Sotuv Analitikasi UI Controller
 */
(function (global) {
  "use strict";

  const M = global.CapiPlatformModel;
  const state = { days: 0, searchQuery: "", logFilter: "all", activeSection: "sec-overview", model: null, activeProjectId: "default", projects: [], editingProjectId: null };
  global.CapiPlatformState = state;

  function el(id) { return document.getElementById(id); }
  function esc(str) { return String(str ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }

  async function loadProjects() {
    try {
      const res = await fetch("/api/marketing/capi/projects", { credentials: "same-origin" });
      if (!res.ok) return;
      const list = await res.json();
      state.projects = Array.isArray(list) ? list : [];
      const sel = el("projectSelect");
      if (sel && Array.isArray(list)) {
        sel.innerHTML = !list.length ? '<option value="">Hech qanday loyiha yo\'q</option>' : list.map((p) => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join("");
        if (list.length && !list.some((p) => p.id === state.activeProjectId)) state.activeProjectId = list[0].id;
        sel.value = state.activeProjectId;
      }
    } catch (_) {}
  }

  function initProjects() {
    loadProjects();
    const sel = el("projectSelect");
    if (sel) sel.addEventListener("change", () => { state.activeProjectId = sel.value; loadDashboardData(); });
    const modal = el("newProjectModal");
    const form = el("newProjectForm");
    if (el("openNewProjectBtn") && modal) el("openNewProjectBtn").onclick = () => {
      state.editingProjectId = null;
      if (el("projectModalTitle")) el("projectModalTitle").textContent = "Yangi loyiha ulash (Meta CAPI)";
      if (form) form.reset();
      modal.showModal();
    };
    if (el("editProjectBtn") && modal) el("editProjectBtn").onclick = () => {
      const p = (state.projects || []).find((x) => x.id === state.activeProjectId) || (state.model && state.model.configuration) || {};
      state.editingProjectId = state.activeProjectId || "default";
      if (el("projectModalTitle")) el("projectModalTitle").textContent = "Loyiha sozlamalarini tahrirlash";
      if (el("projNameInput")) el("projNameInput").value = p.name || p.project_name || "Jon Branding";
      if (el("projDatasetInput")) el("projDatasetInput").value = p.dataset_id || "";
      if (el("projTokenInput")) el("projTokenInput").value = "";
      if (el("projAdAccountInput")) el("projAdAccountInput").value = p.ad_account_id || "";
      if (el("projPipelineInput")) el("projPipelineInput").value = p.crm_pipeline_id || "";
      modal.showModal();
    };
    if (el("closeProjectModalBtn") && modal) el("closeProjectModalBtn").onclick = () => modal.close();
    if (el("cancelProjectModalBtn") && modal) el("cancelProjectModalBtn").onclick = () => modal.close();
    if (form && modal) {
      form.addEventListener("submit", async function (e) {
        e.preventDefault();
        const payload = {
          name: el("projNameInput").value, dataset_id: el("projDatasetInput").value,
          ad_account_id: el("projAdAccountInput") ? el("projAdAccountInput").value : "",
          crm_pipeline_id: el("projPipelineInput").value,
        };
        const tok = el("projTokenInput").value;
        if (tok || !state.editingProjectId) payload.access_token = tok;
        const url = state.editingProjectId ? "/api/marketing/capi/projects/" + encodeURIComponent(state.editingProjectId) : "/api/marketing/capi/projects";
        const res = await fetch(url, {
          method: state.editingProjectId ? "PATCH" : "POST",
          headers: { "Content-Type": "application/json" }, credentials: "same-origin", body: JSON.stringify(payload),
        });
        if (res.ok) {
          const saved = await res.json();
          modal.close(); form.reset();
          if (saved && saved.id) state.activeProjectId = saved.id;
          await loadProjects();
          loadDashboardData();
        }
      });
    }
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("oisha_capi_theme", theme);
    if (el("themeToggleLabel")) el("themeToggleLabel").textContent = theme === "dark" ? "Yorug' rejim" : "Qorong'u rejim";
  }

  function initTheme() {
    applyTheme(localStorage.getItem("oisha_capi_theme") || "light");
    if (el("themeToggleBtn")) el("themeToggleBtn").addEventListener("click", () => applyTheme(document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark"));
  }

  function switchTab(targetId) {
    state.activeSection = targetId;
    if (el("mainNavTabs")) el("mainNavTabs").querySelectorAll(".nav-item").forEach((b) => b.classList.toggle("is-active", b.getAttribute("data-section") === targetId));
    const titles = {
      "sec-overview": "Umumiy ko'rinish", "sec-creatives": "Reklama kreativlari samaradorligi",
      "sec-funnel": "Sotuv voronkasi va yo'qotishlar", "sec-bridge": "CRM va Meta CAPI integratsiyasi",
      "sec-logs": "Meta CAPI signallar jurnali", "sec-snippet": "Saytga ulash (Vidjet)",
    };
    if (el("activeViewTitle") && titles[targetId]) el("activeViewTitle").textContent = titles[targetId];
    ["sec-overview", "sec-creatives", "sec-funnel", "sec-bridge", "sec-logs", "sec-snippet"].forEach((sId) => {
      if (el(sId)) el(sId).style.display = sId === targetId ? "" : "none";
    });
  }

  function initTabs() {
    if (el("mainNavTabs")) el("mainNavTabs").addEventListener("click", (e) => {
      const btn = e.target.closest(".nav-item");
      if (btn) switchTab(btn.getAttribute("data-section") || "sec-overview");
    });
    if (el("ovGoToFunnelBtn")) el("ovGoToFunnelBtn").onclick = () => switchTab("sec-funnel");
    if (el("ovGoToCreativesBtn")) el("ovGoToCreativesBtn").onclick = () => switchTab("sec-creatives");
    if (el("ovQuickSnippetBtn")) el("ovQuickSnippetBtn").onclick = () => switchTab("sec-snippet");
  }

  function initFilters() {
    const periodGroup = el("periodFilterGroup");
    if (periodGroup) periodGroup.addEventListener("click", (e) => {
      const btn = e.target.closest(".seg-btn");
      if (!btn) return;
      periodGroup.querySelectorAll(".seg-btn").forEach((b) => b.classList.remove("is-active"));
      btn.classList.add("is-active");
      state.days = Number(btn.getAttribute("data-days") || 0);
      loadDashboardData();
    });
    const searchInput = el("creativeSearchInput");
    if (searchInput) searchInput.addEventListener("input", () => {
      state.searchQuery = String(searchInput.value || "").trim().toLowerCase();
      if (state.model) renderCreativesTable(state.model);
    });
    const logFilter = el("logStatusFilter");
    if (logFilter) logFilter.addEventListener("change", () => {
      state.logFilter = logFilter.value || "all";
      if (state.model) renderLogsTable(state.model);
    });
    if (el("refreshBtn")) el("refreshBtn").addEventListener("click", loadDashboardData);
    const copyBtn = el("copySnippetBtn");
    if (copyBtn) copyBtn.addEventListener("click", () => {
      const blk = el("snippetCodeBlock");
      if (blk && navigator.clipboard) {
        navigator.clipboard.writeText(blk.textContent);
        const orig = copyBtn.innerHTML;
        copyBtn.innerHTML = "<span>Nusxalandi!</span>";
        setTimeout(() => { copyBtn.innerHTML = orig; }, 2000);
      }
    });
  }

  function initAuthControls() {
    const form = el("tokenLoginForm");
    if (form) form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const tokenInput = el("tokenInput"), errEl = el("authErrorMsg");
      const token = tokenInput ? String(tokenInput.value || "").trim() : "";
      if (!token) return;
      if (errEl) errEl.hidden = true;
      const res = await fetch("/api/auth/token/login", {
        method: "POST", headers: { "Content-Type": "application/json" }, credentials: "same-origin", body: JSON.stringify({ token: token }),
      });
      if (res.ok) { if (tokenInput) tokenInput.value = ""; loadDashboardData(); }
      else if (errEl) { errEl.textContent = "Kirish kaliti noto'g'ri yoki ruxsat etilmagan."; errEl.hidden = false; }
    });
    const magicBtn = el("sendTelegramMagicBtn");
    if (magicBtn) magicBtn.addEventListener("click", async () => {
      const errEl = el("authErrorMsg");
      magicBtn.disabled = true;
      try {
        const res = await fetch("/api/auth/token/login", {
          method: "POST", headers: { "Content-Type": "application/json" }, credentials: "same-origin", body: JSON.stringify({ token: "__SEND_TELEGRAM_MAGIC__" }),
        });
        if (errEl) {
          errEl.style.color = res.ok ? "var(--dot-ok)" : "var(--dot-err)";
          errEl.textContent = res.ok ? "Telegram botingizga (@jonairobot) 1-bosishda kirish tugmasi yuborildi." : "Telegram xabar yuborishda xatolik yuz berdi.";
          errEl.hidden = false;
        }
      } finally { magicBtn.disabled = false; }
    });
    if (el("logoutBtn")) el("logoutBtn").onclick = async () => { await fetch("/api/auth/logout", { method: "POST", credentials: "same-origin" }); window.location.href = "/login?next=/api/marketing/capi/console"; };
  }

  function mountTelegramWidget() {
    const mount = el("telegramWidgetMount");
    if (!mount || mount.dataset.mounted === "1") return;
    mount.dataset.mounted = "1";
    const s = document.createElement("script");
    s.async = true; s.src = "https://telegram.org/js/telegram-widget.js?22";
    s.setAttribute("data-telegram-login", "jonairobot"); s.setAttribute("data-size", "medium");
    s.setAttribute("data-userpic", "false"); s.setAttribute("data-auth-url", window.location.origin + "/api/auth/telegram/callback");
    mount.appendChild(s);
  }

  async function loadDashboardData() {
    const metaEl = el("heroSyncMeta");
    if (metaEl) metaEl.textContent = "Yangilanmoqda...";
    try {
      const pId = encodeURIComponent(state.activeProjectId || "default");
      const url = "/api/marketing/capi/status?days=" + encodeURIComponent(state.days) + "&project_id=" + pId;
      const res = await fetch(url, { credentials: "same-origin", cache: "no-store" });
      if (res.status === 401 || res.status === 403) {
        if (el("authBanner")) el("authBanner").hidden = false;
        if (el("logoutBtn")) el("logoutBtn").hidden = true;
        if (metaEl) metaEl.textContent = "Avtorizatsiya kutilmoqda";
        mountTelegramWidget();
        return;
      }
      if (!res.ok) throw new Error("HTTP " + res.status);
      const raw = await res.json();
      if (el("authBanner")) el("authBanner").hidden = true;
      if (el("logoutBtn")) el("logoutBtn").hidden = false;
      state.model = M.normalizePayload(raw);
      renderAll(state.model);
    } catch (err) {
      if (metaEl) metaEl.textContent = "Xatolik: " + err.message;
    }
  }

  function renderOverview(m) {
    const ov = m.overview;
    const cfg = m.configuration;
    const isReady = Boolean((cfg.dataset_configured || cfg.configured) && cfg.enabled);
    if (el("ovStatusTitle")) el("ovStatusTitle").textContent = isReady ? "Meta CAPI Faol Ishlamoqda" : "Meta CAPI Sozlanmagan";
    if (el("ovStatusSub")) el("ovStatusSub").textContent = isReady ? "Pixel #" + (cfg.dataset_id || "Active") + " · Signallar Meta algoritmiga uzatilmoqda va reklama optimallashmoqda" : "Pixel ID va Access Token kiriting hamda saytingizga vidjetni o'rnating";
    if (el("ovTotalLeads")) el("ovTotalLeads").textContent = M.formatInt(ov.total_leads);
    if (el("ovTotalLeadsSub")) el("ovTotalLeadsSub").textContent = ov.spend_connected && ov.cpl_usd !== null ? "CPL: " + M.formatUsd(ov.cpl_usd) : M.formatInt(m.creatives.length) + " ta faol kreativdan";
    if (el("ovQualifiedLeads")) el("ovQualifiedLeads").textContent = M.formatInt(ov.qualified_leads);
    if (el("ovQualifiedLeadsSub")) el("ovQualifiedLeadsSub").textContent = "Sifat: " + M.formatPct(ov.qualified_rate_pct) + " · CAPI: " + M.formatInt(ov.capi_qualified_sent);
    if (el("ovWonDeals")) el("ovWonDeals").textContent = M.formatInt(ov.won_leads) + " ta";
    if (el("ovWonRevenue")) el("ovWonRevenue").textContent = M.formatUzs(ov.won_revenue_uzs);

    if (el("ovStepLeads")) el("ovStepLeads").textContent = M.formatInt(ov.total_leads) + " ta";
    const contacted = ov.active_pipeline_leads + ov.won_leads;
    if (el("ovStepContact")) el("ovStepContact").textContent = M.formatInt(contacted) + " ta";
    if (el("ovStepContactPct")) el("ovStepContactPct").textContent = ov.total_leads > 0 ? M.formatPct((contacted * 100) / ov.total_leads) : "0%";
    if (el("ovStepQualified")) el("ovStepQualified").textContent = M.formatInt(ov.qualified_leads) + " ta";
    if (el("ovStepQualPct")) el("ovStepQualPct").textContent = M.formatPct(ov.qualified_rate_pct);
    if (el("ovStepWon")) el("ovStepWon").textContent = M.formatInt(ov.won_leads) + " ta";
    if (el("ovStepWonSum")) el("ovStepWonSum").textContent = M.formatUzs(ov.won_revenue_uzs);
    if (el("ovGoToCreativesText")) el("ovGoToCreativesText").textContent = "Barcha " + M.formatInt(m.creatives.length) + " ta kreativ tahlilini ko'rish";

    const hasData = ov.total_leads > 0;
    if (el("ovDataGrid")) el("ovDataGrid").style.display = hasData ? "" : "none";
    if (el("ovOnboarding")) el("ovOnboarding").style.display = hasData ? "none" : "";

    const mount = el("ovTopCreativesMount");
    if (mount) {
      const sorted = [...m.creatives].sort((a, b) => (b.revenue_uzs - a.revenue_uzs) || (b.qualified_leads - a.qualified_leads) || (b.total_leads - a.total_leads));
      const top3 = sorted.slice(0, 3);
      const medals = ["🥇", "🥈", "🥉"];
      mount.innerHTML = !top3.length ? '<div class="top-creative-item"><span class="top-creative-meta">Hozircha reklama ma\'lumotlari mavjud emas.</span></div>' : top3.map((c, i) => {
        const title = M.cleanCreativeName(c.ad_name, c.ad_id);
        const wonText = c.revenue_uzs > 0 ? M.formatUzs(c.revenue_uzs) : M.formatInt(c.won_leads) + ' sotuv';
        return `<div class="top-creative-item is-clickable" data-ad-id="${esc(c.ad_id)}" data-ad-title="${esc(title)}"><span class="top-creative-rank">${medals[i]}</span><div class="top-creative-info"><span class="top-creative-title">${esc(title)}</span><span class="top-creative-meta">${M.formatInt(c.total_leads)} lid · ${M.formatInt(c.qualified_leads)} sifatli (${M.formatPct(c.qualified_rate_pct)})</span></div><div class="top-creative-stats"><span class="top-creative-val mono ${c.revenue_uzs > 0 ? 'stat-green' : ''}">${wonText}</span></div></div>`;
      }).join("");
    }
  }

  function renderAll(m) {
    const ov = m.overview;
    const cfg = m.configuration;
    const isReady = Boolean((cfg.dataset_configured || cfg.configured) && cfg.enabled);
    if (el("badgeMetaPixel")) el("badgeMetaPixel").textContent = isReady ? "#" + (cfg.dataset_id || "Active") : "Sozlanmagan";
    if (el("dotMetaCapi")) el("dotMetaCapi").className = "status-dot " + (isReady ? "is-ok" : "is-warn");
    if (el("badgeSpendSync")) el("badgeSpendSync").textContent = ov.spend_connected ? M.formatUsd(ov.total_spend_usd) : "Ulanmagan";
    if (el("dotMetaSpend")) el("dotMetaSpend").className = "status-dot " + (ov.spend_connected ? "is-ok" : "is-warn");
    if (el("badgeAmoPipeline")) el("badgeAmoPipeline").textContent = cfg.crm_pipeline_id ? "#" + cfg.crm_pipeline_id : "Ulangan";

    const snipBlock = el("snippetCodeBlock");
    if (snipBlock) snipBlock.textContent = `<script src="${window.location.origin}/api/marketing/capi/jon-capi.js" data-secret="${cfg.ingest_secret || 'CAPI_SECRET'}" async></` + 'script>';

    if (el("heroSyncMeta")) el("heroSyncMeta").textContent = `${state.days > 0 ? "Oxirgi " + state.days + " kun" : "Barcha davr"} · ${M.formatInt(ov.total_leads)} lid · ${M.formatInt(ov.capi_sent_total)} CAPI signal`;
    if (el("navCreativesCount")) el("navCreativesCount").textContent = M.formatInt(m.creatives.length);
    if (el("navLogsCount")) el("navLogsCount").textContent = M.formatInt(m.unifiedLogs.length);
    renderOverview(m); renderFunnelStages(m); renderLossAndWon(m); renderCreativesTable(m); renderCrmEventsTable(m); renderLogsTable(m);
  }

  function renderFunnelStages(m) {
    const mount = el("funnelStagesMount");
    if (!mount) return;
    mount.innerHTML = m.funnelStages.map((st) => {
      const sig = M.stageSignalMeta(st.capi_event), pct = Math.max(0, Math.min(100, Number(st.pct_of_total || 0)));
      return `<tr class="is-clickable" data-stage-key="${esc(st.key)}" data-stage-title="${esc(st.title)}" data-stage-sub="${esc(st.subtitle)}"><td><span class="cell-primary">${esc(st.title)}</span><span class="cell-sub">${esc(st.subtitle)}</span></td><td><span class="badge-neutral"><span class="status-dot ${sig.dotClass}"></span>${esc(sig.label)}</span></td><td class="num-col mono cell-primary">${M.formatInt(st.count)}</td><td class="num-col mono"><div class="inline-bar-wrap"><span>${M.formatPct(st.pct_of_total)}</span><div class="inline-bar"><div class="inline-bar-fill" style="width:${pct}%"></div></div></div></td><td class="num-col mono">${st.value_uzs > 0 ? M.formatUzs(st.value_uzs) : "-"}</td></tr>`;
    }).join("");
  }

  function renderLossAndWon(m) {
    const loss = m.lossAnalysis, totalLost = Math.max(1, Number(loss.total_lost || 0));
    const mktPct = Math.round((Number(loss.marketing_lost || 0) / totalLost) * 100), salesPct = Math.round((Number(loss.sales_lost || 0) / totalLost) * 100), unkPct = Math.max(0, 100 - mktPct - salesPct);
    if (el("lossTotalBadge")) el("lossTotalBadge").textContent = M.formatInt(loss.total_lost) + " ta yopilgan";
    if (el("lossMarketingVal")) el("lossMarketingVal").textContent = M.formatInt(loss.marketing_lost);
    if (el("lossMarketingPct")) el("lossMarketingPct").textContent = mktPct + "% · Reklama";
    if (el("lossSalesVal")) el("lossSalesVal").textContent = M.formatInt(loss.sales_lost);
    if (el("lossSalesPct")) el("lossSalesPct").textContent = salesPct + "% · Sotuv";
    if (el("lossUnknownVal")) el("lossUnknownVal").textContent = M.formatInt(loss.unknown_lost);
    if (el("lossUnknownPct")) el("lossUnknownPct").textContent = unkPct + "% · Kiritilmagan";
    if (el("barLossMarketing")) el("barLossMarketing").style.width = mktPct + "%";
    if (el("barLossSales")) el("barLossSales").style.width = salesPct + "%";
    if (el("barLossUnknown")) el("barLossUnknown").style.width = unkPct + "%";
    if (el("lossReasonsMount")) {
      el("lossReasonsMount").innerHTML = (loss.reasons || []).slice(0, 6).map((r) => {
        const dot = r.category === "marketing" ? "is-err" : r.category === "sales" ? "is-warn" : "is-muted";
        return `<div class="compact-row is-clickable" data-loss-reason="${esc(r.reason)}"><span><span class="status-dot ${dot}" style="margin-right:8px"></span>${esc(r.reason)}</span><span class="mono">${M.formatInt(r.count)} (${M.formatPct(r.pct)})</span></div>`;
      }).join("");
    }
    if (el("wonDealsMount")) {
      el("wonDealsMount").innerHTML = !m.wonDeals.length ? "<div class=\"compact-row\">Hozircha tasdiqlangan sotuvlar yo'q.</div>" : m.wonDeals.map((w) => {
        const link = w.lead_id && w.lead_id !== "-" ? `<a href="https://jonbranding.amocrm.ru/leads/detail/${encodeURIComponent(w.lead_id)}" target="_blank" rel="noopener" class="crm-link mono">#${esc(w.lead_id)} ↗</a>` : `<span class="cell-primary mono">#${esc(w.lead_id)}</span>`;
        return `<div class="compact-row"><div>${link} · ${esc(M.cleanCreativeName(w.ad_name, w.ad_id))}<span class="cell-sub">${esc(w.stage_name)} · ${esc(M.formatDateTime(w.created_at))}</span></div><strong class="mono cell-primary">${M.formatUzs(w.price_uzs)}</strong></div>`;
      }).join("");
    }
  }

  function renderCreativesTable(m) {
    const tbody = el("creativesTableBody");
    if (!tbody) return;
    const q = state.searchQuery, rows = m.creatives.filter((c) => !q || String(c.ad_name || "").toLowerCase().includes(q) || String(c.ad_id || "").toLowerCase().includes(q));
    tbody.innerHTML = !rows.length ? "<tr><td colspan=\"11\">Mos kreativ topilmadi.</td></tr>" : rows.map((c) => {
      const title = M.cleanCreativeName(c.ad_name, c.ad_id), adIdSub = c.ad_id && c.ad_id !== "unknown" ? "Ad ID: " + c.ad_id : "Ad ID biriktirilmagan";
      return `<tr class="is-clickable" data-ad-id="${esc(c.ad_id)}" data-ad-title="${esc(title)}"><td><span class="cell-primary">${esc(title)}</span><span class="cell-sub mono">${esc(adIdSub)}</span></td><td class="num-col mono cell-primary">${M.formatInt(c.total_leads)}</td><td class="num-col mono">${M.formatInt(c.active_leads)}</td><td class="num-col mono">${M.formatInt(c.meetings_set)}</td><td class="num-col mono cell-primary">${M.formatInt(c.qualified_leads)}</td><td class="num-col mono">${M.formatPct(c.qualified_rate_pct)}</td><td class="num-col mono cell-primary">${M.formatInt(c.won_leads)}</td><td class="num-col mono">${M.formatInt(c.lost_leads)}</td><td class="num-col mono">${M.formatInt(c.marketing_lost)}</td><td class="num-col mono">${c.spend_usd !== null ? M.formatUsd(c.spend_usd) : "-"}</td><td class="num-col mono cell-primary">${c.revenue_uzs > 0 ? M.formatUzs(c.revenue_uzs) : "-"}</td></tr>`;
    }).join("");
  }

  function renderCrmEventsTable(m) {
    const tbody = el("crmEventsTableBody");
    if (el("crmEventsCountBadge")) el("crmEventsCountBadge").textContent = M.formatInt(m.crmEvents.length) + " ta signal";
    if (!tbody) return;
    tbody.innerHTML = !m.crmEvents.length ? "<tr><td colspan=\"7\">CRM konversiya harakatlari topilmadi.</td></tr>" : m.crmEvents.slice(0, 25).map(function (ev) {
      const isOk = ev.success === true || ev.success === 1 || ev.status === "sent";
      const st = M.statusDotMeta(isOk ? "sent" : "failed");
      const ts = ev.sent_at || ev.updated_at || ev.created_at || "";
      const lid = ev.lead_id && ev.lead_id !== "-" ? `<a href="https://jonbranding.amocrm.ru/leads/detail/${encodeURIComponent(ev.lead_id)}" target="_blank" rel="noopener" class="crm-link mono">#${esc(ev.lead_id)} ↗</a>` : `#${esc(ev.lead_id || "-")}`;
      return `<tr><td class="mono cell-primary">${lid}<span class="cell-sub">${esc(ev.leadgen_id ? "leadgen: " + ev.leadgen_id : "amoCRM")}</span></td><td>${esc(M.cleanCreativeName(ev.ad_name, ev.ad_id))}</td><td>${esc(ev.amo_status_name || "-")}</td><td><span class="badge-neutral mono">${esc(ev.event_name)}</span></td><td class="num-col mono">${ev.lead_price > 0 ? M.formatUzs(ev.lead_price) : "-"}</td><td><span class="badge-neutral"><span class="status-dot ${st.dotClass}"></span>${esc(st.label)}</span></td><td class="num-col mono">${esc(M.formatDateTime(ts))}</td></tr>`;
    }).join("");
  }

  function renderLogsTable(m) {
    const tbody = el("logsTableBody");
    if (!tbody) return;
    const f = state.logFilter;
    const rows = m.unifiedLogs.filter((r) => f === "all" || String(r.status || "").toLowerCase() === f);
    tbody.innerHTML = !rows.length ? "<tr><td colspan=\"8\">Signallar topilmadi.</td></tr>" : rows.slice(0, 40).map(function (r) {
      const st = M.statusDotMeta(r.status);
      return `<tr><td class="mono cell-primary">${esc(r.id)}<span class="cell-sub">${esc(r.subId)}</span></td><td>${esc(r.source)}</td><td><span class="badge-neutral mono">${esc(r.eventName)}</span></td><td>${esc(r.adName)}</td><td class="num-col mono">${r.price > 0 ? M.formatUzs(r.price) : "-"}</td><td><span class="badge-neutral"><span class="status-dot ${st.dotClass}"></span>${esc(st.label)}</span></td><td class="mono">${esc(r.detail)}</td><td class="num-col mono">${esc(M.formatDateTime(r.timestamp))}</td></tr>`;
    }).join("");
  }

  function initDrilldownListeners() {
    const open = (m, t, s, f) => global.CapiDrilldown && global.CapiDrilldown.open(m, t, s, f);
    [
      ["ovTotalLeads", ".overview-stat-card", "total_leads", "Jami Meta Reklama Lidlari", "Instagram va Facebook reklamalaridan tushgan arizalar"],
      ["ovQualifiedLeads", ".overview-stat-card", "quality_attended", "Sifatli Lidlar (CAPI)", "Uchrashuvga kelgan va kelishuv bosqichidagi lidlar"],
      ["ovWonDeals", ".overview-stat-card", "won", "Tasdiqlangan Xaridlar (Won)", "To'lov amalga oshirilgan muvaffaqiyatli bitimlar"],
      ["ovWonRevenue", ".overview-stat-card", "won", "Tasdiqlangan Xaridlar (Won)", "To'lov amalga oshirilgan muvaffaqiyatli bitimlar"],
      ["ovFunnelStep1", null, "total_leads", "1. Reklama Lidi", "Instagram / FB forma arizalari"],
      ["ovFunnelStep2", null, "contacted", "2. Aloqaga Chiqildi (Faol + Sotuv)", "Rad etilmagan faol va muvaffaqiyatli mijozlar"],
      ["ovFunnelStep3", null, "quality_attended", "3. Sifatli Mijoz (QualifiedLead)", "Uchrashuvga kelgan va kelishuv bosqichidagi mijozlar"],
      ["ovFunnelStep4", null, "won", "4. Sotuv Bo'ldi (Purchase)", "Real xarid qilgan mijozlar"],
      ["lossCardMarketing", null, "loss_category", "Reklama sifati sababli yopilgan", "Sifatsiz raqam, adashib bosgan yoki maqsadsiz lidlar", "reklama"],
      ["lossCardSales", null, "loss_category", "Sotuv jarayonida yopilgan", "Narx, muddat yoki raqobatchi sababli rad etilganlar", "sotuv"],
      ["lossCardUnknown", null, "loss_category", "Sababsiz yopilgan lidlar", "amoCRM'da rad etish sababi kiritilmagan bitimlar", "noma'lum"],
    ].forEach(([id, sel, m, t, s, f]) => {
      const n = el(id), c = sel ? (n ? n.closest(sel) : null) : n;
      if (c) { c.classList.add("is-clickable"); c.onclick = () => open(m, t, s, f); }
    });
    ["creativesTableBody", "ovTopCreativesMount"].forEach((id) => {
      if (el(id)) el(id).addEventListener("click", (e) => {
        const r = e.target.closest("[data-ad-id]");
        if (r) open("creative", r.getAttribute("data-ad-title") || "Kreativ", "Ad ID: " + r.getAttribute("data-ad-id"), r.getAttribute("data-ad-id"));
      });
    });
    if (el("funnelStagesMount")) el("funnelStagesMount").addEventListener("click", (e) => {
      const r = e.target.closest("[data-stage-key]");
      if (r) open(r.getAttribute("data-stage-key"), r.getAttribute("data-stage-title"), r.getAttribute("data-stage-sub"));
    });
    if (el("lossReasonsMount")) el("lossReasonsMount").addEventListener("click", (e) => {
      const r = e.target.closest("[data-loss-reason]");
      if (r) open("loss_reason", "Rad etish: " + r.getAttribute("data-loss-reason"), "Sabab bo'yicha yopilgan bitimlar", r.getAttribute("data-loss-reason"));
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initTheme(); initTabs(); initFilters(); initProjects(); initAuthControls();
    if (global.CapiDrilldown) global.CapiDrilldown.init();
    initDrilldownListeners();
    loadDashboardData();
  });
})(window);
