/**
 * Jon Branding · Meta CAPI va Sotuv Analitikasi UI Controller
 */
(function (global) {
  "use strict";

  const M = global.CapiPlatformModel;
  const state = { days: 0, searchQuery: "", logFilter: "all", activeSection: "sec-all", model: null, activeProjectId: "default" };

  function el(id) { return document.getElementById(id); }
  function esc(str) { return String(str ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }

  async function loadProjects() {
    try {
      const res = await fetch("/api/marketing/capi/projects", { credentials: "same-origin" });
      if (!res.ok) return;
      const list = await res.json();
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
    if (sel) {
      sel.addEventListener("change", function () {
        state.activeProjectId = sel.value;
        loadDashboardData();
      });
    }
    const modal = el("newProjectModal");
    if (openBtn && modal) openBtn.onclick = () => modal.showModal();
    if (closeBtn && modal) closeBtn.onclick = () => modal.close();
    if (cancelBtn && modal) cancelBtn.onclick = () => modal.close();

    if (form && modal) {
      form.addEventListener("submit", async function (e) {
        e.preventDefault();
        const payload = {
          name: el("projNameInput").value, dataset_id: el("projDatasetInput").value,
          access_token: el("projTokenInput").value, crm_pipeline_id: el("projPipelineInput").value,
        };
        const res = await fetch("/api/marketing/capi/projects", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "same-origin",
          body: JSON.stringify(payload),
        });
        if (res.ok) {
          const created = await res.json();
          modal.close();
          form.reset();
          state.activeProjectId = created.id;
          await loadProjects();
          loadDashboardData();
        }
      });
    }
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("oisha_capi_theme", theme);
    const lbl = el("themeToggleLabel");
    if (lbl) lbl.textContent = theme === "dark" ? "Yorug' rejim" : "Qorong'u rejim";
  }

  function initTheme() {
    applyTheme(localStorage.getItem("oisha_capi_theme") || "light");
    const btn = el("themeToggleBtn");
    if (btn) {
      btn.addEventListener("click", function () {
        const cur = document.documentElement.getAttribute("data-theme") || "light";
        applyTheme(cur === "dark" ? "light" : "dark");
      });
    }
  }

  function initTabs() {
    const container = el("mainNavTabs");
    if (!container) return;
    const titles = {
      "sec-all": "Umumiy ko'rinish",
      "sec-funnel": "Sotuv voronkasi va yo'qotishlar",
      "sec-creatives": "Reklama kreativlari samaradorligi",
      "sec-bridge": "CRM va Meta CAPI integratsiyasi",
      "sec-logs": "Meta CAPI signallar jurnali",
      "sec-snippet": "Saytga ulash (Vidjet)",
    };
    container.addEventListener("click", function (e) {
      const btn = e.target.closest(".nav-item");
      if (!btn) return;
      const target = btn.getAttribute("data-section") || "sec-all";
      state.activeSection = target;
      container.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("is-active"));
      btn.classList.add("is-active");
      const titleEl = el("activeViewTitle");
      if (titleEl && titles[target]) titleEl.textContent = titles[target];
      for (const secId of ["sec-funnel", "sec-creatives", "sec-bridge", "sec-logs", "sec-snippet"]) {
        const node = el(secId);
        if (node) node.style.display = target === "sec-all" ? (secId === "sec-snippet" ? "none" : "") : (target === secId ? "" : "none");
      }
    });
  }

  function initFilters() {
    const periodGroup = el("periodFilterGroup");
    if (periodGroup) {
      periodGroup.addEventListener("click", function (e) {
        const btn = e.target.closest(".seg-btn");
        if (!btn) return;
        periodGroup.querySelectorAll(".seg-btn").forEach((b) => b.classList.remove("is-active"));
        btn.classList.add("is-active");
        state.days = Number(btn.getAttribute("data-days") || 0);
        loadDashboardData();
      });
    }
    const searchInput = el("creativeSearchInput");
    if (searchInput) {
      searchInput.addEventListener("input", function () {
        state.searchQuery = String(searchInput.value || "").trim().toLowerCase();
        if (state.model) renderCreativesTable(state.model);
      });
    }
    const logFilter = el("logStatusFilter");
    if (logFilter) {
      logFilter.addEventListener("change", function () {
        state.logFilter = logFilter.value || "all";
        if (state.model) renderLogsTable(state.model);
      });
    }
    const refreshBtn = el("refreshBtn");
    if (refreshBtn) refreshBtn.addEventListener("click", loadDashboardData);
    const dispatchBtn = el("dispatchBtn");
    if (dispatchBtn) {
      dispatchBtn.addEventListener("click", async function () {
        dispatchBtn.disabled = true;
        try {
          await fetch("/api/marketing/capi/dispatch", { method: "POST", credentials: "same-origin" });
          await loadDashboardData();
        } finally { dispatchBtn.disabled = false; }
      });
    }
    const copyBtn = el("copySnippetBtn");
    if (copyBtn) {
      copyBtn.addEventListener("click", function () {
        const blk = el("snippetCodeBlock");
        if (blk && navigator.clipboard) {
          navigator.clipboard.writeText(blk.textContent);
          const orig = copyBtn.innerHTML;
          copyBtn.innerHTML = "<span>Nusxalandi!</span>";
          setTimeout(() => { copyBtn.innerHTML = orig; }, 2000);
        }
      });
    }
  }

  function initAuthControls() {
    const form = el("tokenLoginForm");
    if (form) {
      form.addEventListener("submit", async function (e) {
        e.preventDefault();
        const tokenInput = el("tokenInput");
        const errEl = el("authErrorMsg");
        const token = tokenInput ? String(tokenInput.value || "").trim() : "";
        if (!token) return;
        if (errEl) errEl.hidden = true;
        const res = await fetch("/api/auth/token/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "same-origin",
          body: JSON.stringify({ token: token }),
        });
        if (res.ok) {
          if (tokenInput) tokenInput.value = "";
          loadDashboardData();
        } else if (errEl) {
          errEl.textContent = "Kirish kaliti noto'g'ri yoki ruxsat etilmagan.";
          errEl.hidden = false;
        }
      });
    }
    const magicBtn = el("sendTelegramMagicBtn");
    if (magicBtn) {
      magicBtn.addEventListener("click", async function () {
        const errEl = el("authErrorMsg");
        magicBtn.disabled = true;
        try {
          const res = await fetch("/api/auth/token/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "same-origin",
            body: JSON.stringify({ token: "__SEND_TELEGRAM_MAGIC__" }),
          });
          if (errEl) {
            errEl.style.color = res.ok ? "var(--dot-ok)" : "var(--dot-err)";
            errEl.textContent = res.ok
              ? "Telegram botingizga (@jonairobot) 1-bosishda kirish tugmasi yuborildi."
              : "Telegram xabar yuborishda xatolik yuz berdi.";
            errEl.hidden = false;
          }
        } finally {
          magicBtn.disabled = false;
        }
      });
    }
    const logoutBtn = el("logoutBtn");
    if (logoutBtn) logoutBtn.onclick = async () => { await fetch("/api/auth/logout", { method: "POST", credentials: "same-origin" }); loadDashboardData(); };
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

  function renderAll(m) {
    const ov = m.overview;
    const cfg = m.configuration;
    if (el("badgeMetaPixel")) el("badgeMetaPixel").textContent = cfg.dataset_configured ? "#" + (cfg.dataset_id || "Active") : "Sozlanmagan";
    if (el("dotMetaCapi")) el("dotMetaCapi").className = "status-dot " + (cfg.enabled && cfg.dataset_configured ? "is-ok" : "is-warn");
    if (el("badgeSpendSync")) el("badgeSpendSync").textContent = ov.spend_connected ? M.formatUsd(ov.total_spend_usd) : "Ulanmagan";
    if (el("dotMetaSpend")) el("dotMetaSpend").className = "status-dot " + (ov.spend_connected ? "is-ok" : "is-warn");
    if (el("badgeAmoPipeline")) el("badgeAmoPipeline").textContent = cfg.crm_pipeline_id ? "#" + cfg.crm_pipeline_id : "#11162698";

    // Render snippet code block
    const snipBlock = el("snippetCodeBlock");
    if (snipBlock) {
      const orig = window.location.origin;
      const sec = cfg.ingest_secret || "CAPI_SECRET";
      snipBlock.textContent = '<script src="' + orig + '/api/marketing/capi/jon-capi.js" data-secret="' + sec + '" async></' + 'script>';
    }

    if (el("heroSyncMeta")) {
      const pLabel = state.days > 0 ? "Oxirgi " + state.days + " kun" : "Barcha davr";
      el("heroSyncMeta").textContent = pLabel + " · " + M.formatInt(ov.total_leads) + " lid · " + M.formatInt(ov.capi_sent_total) + " CAPI signal";
    }
    if (el("navCreativesCount")) el("navCreativesCount").textContent = M.formatInt(m.creatives.length);
    if (el("navLogsCount")) el("navLogsCount").textContent = M.formatInt(m.unifiedLogs.length);

    el("kpiTotalLeads").textContent = M.formatInt(ov.total_leads); el("kpiTotalLeadsSub").textContent = ov.spend_connected && ov.cpl_usd !== null ? "CPL: " + M.formatUsd(ov.cpl_usd) : M.formatInt(m.creatives.length) + " ta faol kreativdan";
    el("kpiActivePipeline").textContent = M.formatInt(ov.active_pipeline_leads); el("kpiActivePipelineSub").textContent = M.formatUzs(ov.pipeline_value_uzs) + " potensial";
    el("kpiMeetingSet").textContent = M.formatInt(ov.meetings_set_leads); el("kpiMeetingSetSub").textContent = "Konversiya: " + M.formatPct(ov.meeting_rate_pct);
    el("kpiQualified").textContent = M.formatInt(ov.qualified_leads); el("kpiQualifiedSub").textContent = "Sifat: " + M.formatPct(ov.qualified_rate_pct) + " · CAPI: " + M.formatInt(ov.capi_qualified_sent);
    el("kpiWonDeals").textContent = M.formatInt(ov.won_leads); el("kpiWonRevenueSub").textContent = M.formatUzs(ov.won_revenue_uzs);
    el("kpiLostLeads").textContent = M.formatInt(ov.lost_leads); el("kpiLostLeadsSub").textContent = "Reklama: " + M.formatInt(m.lossAnalysis.marketing_lost) + " · Sotuv: " + M.formatInt(m.lossAnalysis.sales_lost);

    renderFunnelStages(m);
    renderLossAndWon(m);
    renderCreativesTable(m);
    renderCrmEventsTable(m);
    renderLogsTable(m);
  }

  function renderFunnelStages(m) {
    const mount = el("funnelStagesMount");
    if (!mount) return;
    mount.innerHTML = m.funnelStages.map(function (st) {
      const sig = M.stageSignalMeta(st.capi_event);
      const pct = Math.max(0, Math.min(100, Number(st.pct_of_total || 0)));
      return "<tr><td><span class=\"cell-primary\">" + esc(st.title) + "</span><span class=\"cell-sub\">" + esc(st.subtitle) + "</span></td>" +
        "<td><span class=\"badge-neutral\"><span class=\"status-dot " + sig.dotClass + "\"></span>" + esc(sig.label) + "</span></td>" +
        "<td class=\"num-col mono cell-primary\">" + M.formatInt(st.count) + "</td>" +
        "<td class=\"num-col mono\"><div class=\"inline-bar-wrap\"><span>" + M.formatPct(st.pct_of_total) + "</span><div class=\"inline-bar\"><div class=\"inline-bar-fill\" style=\"width:" + pct + "%\"></div></div></div></td>" +
        "<td class=\"num-col mono\">" + (st.value_uzs > 0 ? M.formatUzs(st.value_uzs) : "-") + "</td></tr>";
    }).join("");
  }

  function renderLossAndWon(m) {
    const loss = m.lossAnalysis;
    const totalLost = Math.max(1, Number(loss.total_lost || 0));
    const mktPct = Math.round((Number(loss.marketing_lost || 0) / totalLost) * 100);
    const salesPct = Math.round((Number(loss.sales_lost || 0) / totalLost) * 100);
    const unkPct = Math.max(0, 100 - mktPct - salesPct);

    el("lossTotalBadge").textContent = M.formatInt(loss.total_lost) + " ta yopilgan";
    el("lossMarketingVal").textContent = M.formatInt(loss.marketing_lost);
    el("lossMarketingPct").textContent = mktPct + "% · Reklama";
    el("lossSalesVal").textContent = M.formatInt(loss.sales_lost);
    el("lossSalesPct").textContent = salesPct + "% · Sotuv";
    el("lossUnknownVal").textContent = M.formatInt(loss.unknown_lost);
    el("lossUnknownPct").textContent = unkPct + "% · Kiritilmagan";
    el("barLossMarketing").style.width = mktPct + "%";
    el("barLossSales").style.width = salesPct + "%";
    el("barLossUnknown").style.width = unkPct + "%";

    if (el("lossReasonsMount")) {
      el("lossReasonsMount").innerHTML = (loss.reasons || []).slice(0, 6).map(function (r) {
        const dot = r.category === "marketing" ? "is-err" : r.category === "sales" ? "is-warn" : "is-muted";
        return "<div class=\"compact-row\"><span><span class=\"status-dot " + dot + "\" style=\"margin-right:8px\"></span>" + esc(r.reason) + "</span><span class=\"mono\">" + M.formatInt(r.count) + " (" + M.formatPct(r.pct) + ")</span></div>";
      }).join("");
    }
    if (el("wonDealsMount")) {
      el("wonDealsMount").innerHTML = !m.wonDeals.length
        ? "<div class=\"compact-row\">Hozircha tasdiqlangan sotuvlar yo'q.</div>"
        : m.wonDeals.map(function (w) {
            return "<div class=\"compact-row\"><div><span class=\"cell-primary mono\">#" + esc(w.lead_id) + "</span> · " + esc(M.cleanCreativeName(w.ad_name, w.ad_id)) + "<span class=\"cell-sub\">" + esc(w.stage_name) + " · " + esc(M.formatDateTime(w.created_at)) + "</span></div><strong class=\"mono cell-primary\">" + M.formatUzs(w.price_uzs) + "</strong></div>";
          }).join("");
    }
  }

  function renderCreativesTable(m) {
    const tbody = el("creativesTableBody");
    if (!tbody) return;
    const q = state.searchQuery;
    const rows = m.creatives.filter((c) => !q || String(c.ad_name || "").toLowerCase().includes(q) || String(c.ad_id || "").toLowerCase().includes(q));
    tbody.innerHTML = !rows.length ? "<tr><td colspan=\"11\">Mos kreativ topilmadi.</td></tr>" : rows.map(function (c) {
      const title = M.cleanCreativeName(c.ad_name, c.ad_id);
      const adIdSub = c.ad_id && c.ad_id !== "unknown" ? "Ad ID: " + c.ad_id : "Ad ID biriktirilmagan";
      return "<tr><td><span class=\"cell-primary\">" + esc(title) + "</span><span class=\"cell-sub mono\">" + esc(adIdSub) + "</span></td>" +
        "<td class=\"num-col mono cell-primary\">" + M.formatInt(c.total_leads) + "</td>" +
        "<td class=\"num-col mono\">" + M.formatInt(c.active_leads) + "</td>" +
        "<td class=\"num-col mono\">" + M.formatInt(c.meetings_set) + "</td>" +
        "<td class=\"num-col mono cell-primary\">" + M.formatInt(c.qualified_leads) + "</td>" +
        "<td class=\"num-col mono\">" + M.formatPct(c.qualified_rate_pct) + "</td>" +
        "<td class=\"num-col mono cell-primary\">" + M.formatInt(c.won_leads) + "</td>" +
        "<td class=\"num-col mono\">" + M.formatInt(c.lost_leads) + "</td>" +
        "<td class=\"num-col mono\">" + M.formatInt(c.marketing_lost) + "</td>" +
        "<td class=\"num-col mono\">" + (c.spend_usd !== null ? M.formatUsd(c.spend_usd) : "-") + "</td>" +
        "<td class=\"num-col mono cell-primary\">" + (c.revenue_uzs > 0 ? M.formatUzs(c.revenue_uzs) : "-") + "</td></tr>";
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
      return "<tr><td class=\"mono cell-primary\">#" + esc(ev.lead_id) + "<span class=\"cell-sub\">" + esc(ev.leadgen_id ? "leadgen: " + ev.leadgen_id : "amoCRM") + "</span></td>" +
        "<td>" + esc(M.cleanCreativeName(ev.ad_name, ev.ad_id)) + "</td><td>" + esc(ev.amo_status_name || "-") + "</td>" +
        "<td><span class=\"badge-neutral mono\">" + esc(ev.event_name) + "</span></td>" +
        "<td class=\"num-col mono\">" + (ev.lead_price > 0 ? M.formatUzs(ev.lead_price) : "-") + "</td>" +
        "<td><span class=\"badge-neutral\"><span class=\"status-dot " + st.dotClass + "\"></span>" + esc(st.label) + "</span></td>" +
        "<td class=\"num-col mono\">" + esc(M.formatDateTime(ts)) + "</td></tr>";
    }).join("");
  }

  function renderLogsTable(m) {
    const tbody = el("logsTableBody");
    if (!tbody) return;
    const f = state.logFilter;
    const rows = m.unifiedLogs.filter((r) => f === "all" || String(r.status || "").toLowerCase() === f);
    tbody.innerHTML = !rows.length ? "<tr><td colspan=\"8\">Signallar topilmadi.</td></tr>" : rows.slice(0, 40).map(function (r) {
      const st = M.statusDotMeta(r.status);
      return "<tr><td class=\"mono cell-primary\">" + esc(r.id) + "<span class=\"cell-sub\">" + esc(r.subId) + "</span></td>" +
        "<td>" + esc(r.source) + "</td><td><span class=\"badge-neutral mono\">" + esc(r.eventName) + "</span></td>" +
        "<td>" + esc(r.adName) + "</td><td class=\"num-col mono\">" + (r.price > 0 ? M.formatUzs(r.price) : "-") + "</td>" +
        "<td><span class=\"badge-neutral\"><span class=\"status-dot " + st.dotClass + "\"></span>" + esc(st.label) + "</span></td>" +
        "<td class=\"mono\">" + esc(r.detail) + "</td><td class=\"num-col mono\">" + esc(M.formatDateTime(r.timestamp)) + "</td></tr>";
    }).join("");
  }

  document.addEventListener("DOMContentLoaded", function () {
    initTheme(); initTabs(); initFilters(); initProjects(); initAuthControls(); loadDashboardData();
  });
})(window);
