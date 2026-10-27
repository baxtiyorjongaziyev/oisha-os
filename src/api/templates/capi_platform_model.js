/**
 * Jon Branding · Meta CAPI va Sotuv Voronkasi Data Model
 * Real backend API javoblarini UI uchun formatlash va normalizatsiya qilish.
 */
(function (global) {
  "use strict";

  const uzNumber = new Intl.NumberFormat("uz-UZ");
  const usdNumber = new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

  function formatInt(val) {
    const n = Number(val || 0);
    return Number.isFinite(n) ? uzNumber.format(Math.round(n)) : "0";
  }

  function formatUzs(val) {
    const n = Number(val || 0);
    if (!Number.isFinite(n) || n === 0) return "0 UZS";
    return uzNumber.format(Math.round(n)) + " UZS";
  }

  function formatUsd(val) {
    if (val === null || val === undefined || val === "") return "Ulanmagan";
    const n = Number(val);
    if (!Number.isFinite(n) || n <= 0) return "$0.00";
    return "$" + usdNumber.format(n);
  }

  function formatPct(val) {
    const n = Number(val || 0);
    if (!Number.isFinite(n)) return "0%";
    return (Math.round(n * 10) / 10).toFixed(1).replace(/\.0$/, "") + "%";
  }

  function cleanCreativeName(rawName, adId) {
    const text = String(rawName || "").trim();
    const cleaned = text.replace(/^[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\s]+/gu, "").trim();
    if (cleaned) return cleaned;
    if (adId && adId !== "unknown") return "Meta Ad #" + String(adId).slice(-6);
    return "Meta Lead Form (Ad ID biriktirilmagan)";
  }

  function formatDateTime(raw) {
    if (!raw) return "-";
    let d;
    if (typeof raw === "number" || /^\d+$/.test(String(raw))) {
      const num = Number(raw);
      d = new Date(num < 1e12 ? num * 1000 : num);
    } else {
      const iso = String(raw).includes("T") ? String(raw) : String(raw).replace(" ", "T") + "Z";
      d = new Date(iso);
    }
    if (Number.isNaN(d.getTime())) return String(raw).slice(0, 16);
    const pad = (n) => String(n).padStart(2, "0");
    return (
      pad(d.getDate()) +
      "." +
      pad(d.getMonth() + 1) +
      "." +
      d.getFullYear() +
      " " +
      pad(d.getHours()) +
      ":" +
      pad(d.getMinutes())
    );
  }

  function statusDotMeta(status) {
    const s = String(status || "").toLowerCase();
    if (s === "sent" || s === "ok" || s === "1" || s === "true") {
      return { label: "Sent", dotClass: "is-ok" };
    }
    if (s === "queued" || s === "sending" || s === "pending") {
      return { label: "Queued", dotClass: "is-warn" };
    }
    if (s === "failed" || s === "error" || s === "expired" || s === "0") {
      return { label: "Failed", dotClass: "is-err" };
    }
    return { label: s || "Noma'lum", dotClass: "is-muted" };
  }

  function stageSignalMeta(capiEvent) {
    const ev = String(capiEvent || "");
    if (ev.includes("Purchase")) {
      return { label: "Purchase", dotClass: "is-ok" };
    }
    if (ev.includes("QualifiedLead")) {
      return { label: "QualifiedLead", dotClass: "is-ok" };
    }
    if (ev.includes("Kutish")) {
      return { label: "Kutishda (Uchrashuv)", dotClass: "is-warn" };
    }
    if (ev.includes("Lead")) {
      return { label: "Lead", dotClass: "is-ok" };
    }
    if (ev.includes("Yuborilmaydi")) {
      return { label: "O'tkazib yuboriladi", dotClass: "is-muted" };
    }
    return { label: "CRM ichki bosqich", dotClass: "is-muted" };
  }

  function normalizePayload(raw) {
    const data = raw || {};
    const rawCfg = data.configuration || {};
    const isConfigured = Boolean(
      rawCfg.dataset_configured ?? rawCfg.configured ?? (rawCfg.dataset_id && rawCfg.enabled)
    );
    const cfg = {
      ...rawCfg,
      configured: isConfigured,
      dataset_configured: isConfigured,
      enabled: rawCfg.enabled !== false,
      dataset_id: rawCfg.dataset_id || "1134785364752294",
    };
    const analytics = data.analytics || {};
    const rawOv = analytics.overview || {};
    const spend = rawOv.spend || {};

    const totalLeads = Number(rawOv.total_leads ?? rawOv.total_meta_leads ?? 0);
    const meetingsSet = Number(rawOv.meetings_set_leads ?? rawOv.meeting_scheduled_count ?? 0);
    const qualifiedLeads = Number(rawOv.qualified_leads ?? rawOv.quality_attended_count ?? 0);
    const wonLeads = Number(rawOv.won_leads ?? rawOv.won_count ?? 0);
    const lostLeads = Number(rawOv.lost_leads ?? rawOv.lost_count ?? 0);
    const activeLeads = Number(rawOv.active_pipeline_leads ?? rawOv.active_in_pipeline ?? Math.max(0, totalLeads - wonLeads - lostLeads));
    const qualSent = Number(rawOv.capi_qualified_sent ?? 0);
    const purchSent = Number(rawOv.capi_purchase_sent ?? 0);
    const leadSent = Number(rawOv.capi_lead_sent ?? 0);

    const isSpendConnected = Boolean(
      rawOv.spend_connected ?? spend.connected ?? (spend.total_spend !== null && Number(spend.total_spend) > 0)
    );
    const totalSpend = rawOv.total_spend_usd ?? spend.total_spend ?? null;

    const overview = {
      total_leads: totalLeads,
      active_pipeline_leads: activeLeads,
      pipeline_value_uzs: Number(rawOv.pipeline_value_uzs ?? rawOv.active_pipeline_value ?? 0),
      meetings_set_leads: meetingsSet,
      meeting_rate_pct: rawOv.meeting_rate_pct ?? (totalLeads > 0 ? ((meetingsSet + qualifiedLeads) * 100) / totalLeads : 0),
      qualified_leads: qualifiedLeads,
      qualified_rate_pct: rawOv.qualified_rate_pct ?? (totalLeads > 0 ? (qualifiedLeads * 100) / totalLeads : 0),
      won_leads: wonLeads,
      won_revenue_uzs: Number(rawOv.won_revenue_uzs ?? rawOv.revenue_won ?? 0),
      lost_leads: lostLeads,
      capi_qualified_sent: qualSent,
      capi_sent_total: Number(rawOv.capi_sent_total ?? (qualSent + purchSent + leadSent)),
      spend_connected: isSpendConnected,
      total_spend_usd: totalSpend,
      cpl_usd: rawOv.cpl_usd ?? (totalSpend && totalLeads > 0 ? totalSpend / totalLeads : null),
    };

    const funnelStages = (Array.isArray(analytics.funnel_stages) ? analytics.funnel_stages : []).map(function (st) {
      return {
        key: st.key || "total_leads",
        title: st.title || st.step || "-",
        subtitle: st.subtitle || st.stage_hint || "",
        count: Number(st.count || 0),
        pct_of_total: Number(st.pct_of_total ?? st.pct ?? 0),
        value_uzs: Number(st.value_uzs ?? st.amount_uzs ?? 0),
        capi_event: st.capi_event || "",
      };
    });

    const creatives = (Array.isArray(analytics.creatives) ? analytics.creatives : []).map(function (c) {
      const cTotal = Number(c.total_leads || 0);
      const cQual = Number(c.qualified_leads ?? c.quality_attended ?? 0);
      return {
        ad_id: c.ad_id || "unknown",
        ad_name: c.ad_name || "",
        total_leads: cTotal,
        active_leads: Number(c.active_leads ?? c.active ?? 0),
        meetings_set: Number(c.meetings_set ?? c.meeting_scheduled ?? 0),
        qualified_leads: cQual,
        qualified_rate_pct: Number(c.qualified_rate_pct ?? (cTotal > 0 ? (cQual * 100) / cTotal : 0)),
        won_leads: Number(c.won_leads ?? c.won ?? 0),
        lost_leads: Number(c.lost_leads ?? c.lost ?? 0),
        marketing_lost: Number(c.marketing_lost ?? 0),
        spend_usd: c.spend_usd ?? null,
        revenue_uzs: Number(c.revenue_uzs ?? c.revenue_won ?? 0),
      };
    });

    const rawLoss = analytics.loss_analysis || {};
    const lossAnalysis = {
      total_lost: Number(rawLoss.total_lost ?? rawLoss.total ?? lostLeads),
      marketing_lost: Number(rawLoss.marketing_lost ?? rawLoss.ad_fault ?? 0),
      sales_lost: Number(rawLoss.sales_lost ?? rawLoss.sales_fault ?? 0),
      unknown_lost: Number(rawLoss.unknown_lost ?? rawLoss.unknown_fault ?? 0),
      reasons: (Array.isArray(rawLoss.reasons) ? rawLoss.reasons : []).map(function (r) {
        const cat = String(r.category || "");
        return {
          reason: r.reason || r.name || "Sabab ko'rsatilmagan",
          category: cat === "reklama" || cat === "marketing" ? "marketing" : cat === "sotuv" || cat === "sales" ? "sales" : "unknown",
          count: Number(r.count || 0),
          pct: Number(r.pct || 0),
        };
      }),
    };

    const wonDeals = (Array.isArray(analytics.won_deals) ? analytics.won_deals : []).map(function (w) {
      return {
        lead_id: w.lead_id || "-",
        ad_id: w.ad_id || "",
        ad_name: w.ad_name || "Meta Ads",
        stage_name: w.stage_name || "Sotuv bo'ldi (#142)",
        price_uzs: Number(w.price_uzs ?? w.price ?? 0),
        created_at: w.created_at || "",
      };
    });

    const crmEvents = Array.isArray(data.crm_events) ? data.crm_events : [];
    const platformEvents = Array.isArray(data.events) ? data.events : [];
    const unifiedLogs = [];

    for (const ev of crmEvents) {
      const lid = ev.lead_id || ev.amo_lead_id || "-";
      ev.lead_id = lid;
      const isOk = ev.success === true || ev.success === 1 || ev.status === "sent";
      unifiedLogs.push({
        id: "Lead #" + lid,
        subId: ev.leadgen_id ? "leadgen: " + ev.leadgen_id : "amoCRM deal",
        source: "amoCRM -> Meta",
        eventName: ev.event_name || "Lead",
        adName: cleanCreativeName(ev.ad_name || "Meta Ads", ev.ad_id),
        price: Number(ev.lead_price || 0),
        status: isOk ? "sent" : "failed",
        detail: ev.response ? String(ev.response).slice(0, 72) : "events_received: 1",
        timestamp: ev.sent_at || ev.updated_at || ev.created_at || "",
      });
    }
    for (const pev of platformEvents) {
      unifiedLogs.push({
        id: pev.event_id || "-",
        subId: pev.dataset_id ? "dataset: " + pev.dataset_id : "platform",
        source: pev.source || "website",
        eventName: pev.event_name || "Lead",
        adName: "Web / Console",
        price: 0,
        status: pev.status || "queued",
        detail: pev.error ? String(pev.error).slice(0, 72) : "Attempts: " + (pev.attempts || 0),
        timestamp: pev.updated_at || pev.created_at || "",
      });
    }

    return {
      configuration: cfg,
      overview: overview,
      funnelStages: funnelStages,
      creatives: creatives,
      lossAnalysis: lossAnalysis,
      wonDeals: wonDeals,
      crmEvents: crmEvents,
      unifiedLogs: unifiedLogs,
    };
  }

  global.CapiPlatformModel = {
    formatInt: formatInt,
    formatUzs: formatUzs,
    formatUsd: formatUsd,
    formatPct: formatPct,
    cleanCreativeName: cleanCreativeName,
    formatDateTime: formatDateTime,
    statusDotMeta: statusDotMeta,
    stageSignalMeta: stageSignalMeta,
    normalizePayload: normalizePayload,
  };
})(window);
