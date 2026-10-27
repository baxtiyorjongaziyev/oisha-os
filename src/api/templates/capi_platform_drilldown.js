/**
 * Jon Branding · Meta CAPI Drilldown Controller (capi_platform_drilldown.js)
 * Atom darajadagi mijozlar ro'yxatini yuklash va Drawerda ko'rsatish
 */
(function (global) {
  "use strict";

  const M = global.CapiPlatformModel;
  let currentLeads = [];

  function el(id) { return document.getElementById(id); }
  function esc(str) { return String(str ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }

  function closeDrawer() {
    const drawer = el("drilldownDrawer");
    const backdrop = el("drawerBackdrop");
    if (drawer) drawer.classList.remove("is-open");
    if (backdrop) backdrop.style.display = "none";
  }

  function renderDrawerTable(leads) {
    const tbody = el("drawerTableBody");
    const empty = el("drawerEmpty");
    const badge = el("drawerCountBadge");
    if (badge) badge.textContent = (leads ? leads.length : 0) + " ta";
    if (!tbody) return;
    if (!leads || !leads.length) {
      tbody.innerHTML = "";
      if (empty) empty.style.display = "block";
      return;
    }
    if (empty) empty.style.display = "none";
    tbody.innerHTML = leads.map(function (lead) {
      const price = Number(lead.lead_price || 0);
      const priceFmt = price > 0 ? (M ? M.formatUzs(price) : price.toLocaleString() + " so'm") : "-";
      const crmLink = lead.crm_url
        ? `<a href="${esc(lead.crm_url)}" target="_blank" rel="noopener" class="crm-link">amoCRM ↗</a>`
        : "-";
      return `<tr>
        <td class="mono cell-sub">${esc(lead.created_at || "-")}</td>
        <td class="mono cell-primary">#${esc(lead.lead_id || lead.leadgen_id || "Lead")}</td>
        <td><span class="cell-primary">${esc(lead.ad_name || "Meta Ads")}</span></td>
        <td><span class="badge-neutral">${esc(lead.status_name || "Yangi")}</span></td>
        <td class="num-col mono cell-primary">${priceFmt}</td>
        <td>${crmLink}</td>
      </tr>`;
    }).join("");
  }

  async function openDrilldown(metric, title, subtitle, filterVal) {
    const drawer = el("drilldownDrawer");
    const backdrop = el("drawerBackdrop");
    const titleEl = el("drawerTitle");
    const subEl = el("drawerSubtitle");
    const loading = el("drawerLoading");
    const tbody = el("drawerTableBody");
    const empty = el("drawerEmpty");

    if (titleEl) titleEl.textContent = title || "Mijozlar ro'yxati";
    if (subEl) subEl.textContent = subtitle || "Batafsil ma'lumotlar";
    if (drawer) drawer.classList.add("is-open");
    if (backdrop) backdrop.style.display = "block";
    if (loading) loading.style.display = "block";
    if (empty) empty.style.display = "none";
    if (tbody) tbody.innerHTML = "";

    try {
      const days = (global.CapiPlatformState && global.CapiPlatformState.days) || 0;
      const projId = (global.CapiPlatformState && global.CapiPlatformState.activeProjectId) || "default";
      let url = `/api/marketing/capi/drilldown?metric=${encodeURIComponent(metric || "total_leads")}&project_id=${encodeURIComponent(projId)}`;
      if (days) url += `&days=${encodeURIComponent(days)}`;
      if (filterVal) url += `&filter_val=${encodeURIComponent(filterVal)}`;

      const res = await fetch(url, { credentials: "same-origin" });
      if (!res.ok) throw new Error("Yuklab bo'lmadi");
      const data = await res.json();
      currentLeads = data.leads || [];
      if (loading) loading.style.display = "none";
      renderDrawerTable(currentLeads);
    } catch (_) {
      if (loading) loading.style.display = "none";
      if (empty) {
        empty.textContent = "Ma'lumotlarni yuklashda xatolik yuz berdi.";
        empty.style.display = "block";
      }
    }
  }

  function initDrilldown() {
    const closeBtn = el("closeDrawerBtn");
    const backdrop = el("drawerBackdrop");
    const searchInput = el("drawerSearchInput");

    if (closeBtn) closeBtn.onclick = closeDrawer;
    if (backdrop) backdrop.onclick = closeDrawer;

    if (searchInput) {
      searchInput.addEventListener("input", function () {
        const q = (searchInput.value || "").trim().toLowerCase();
        if (!q) {
          renderDrawerTable(currentLeads);
          return;
        }
        const filtered = currentLeads.filter(function (l) {
          return String(l.lead_id || "").includes(q) ||
            String(l.leadgen_id || "").includes(q) ||
            String(l.ad_name || "").toLowerCase().includes(q) ||
            String(l.status_name || "").toLowerCase().includes(q) ||
            String(l.campaign_name || "").toLowerCase().includes(q);
        });
        renderDrawerTable(filtered);
      });
    }
  }

  global.CapiDrilldown = {
    open: openDrilldown,
    close: closeDrawer,
    init: initDrilldown,
  };
})(window);
