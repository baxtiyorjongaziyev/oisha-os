/* DOM-safe renderers for Oisha-OS Sales Quality, Leaderboard & Checklist (<=400 lines) */
(function () {
  "use strict";

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function clearNode(node) {
    while (node && node.firstChild) node.removeChild(node.firstChild);
  }

  function formatMoney(n) {
    var val = Number(n) || 0;
    return val.toLocaleString("ru-RU").replace(/,/g, " ") + " soʻm";
  }

  function qualityColor(pct) {
    if (pct >= 70) return "bar-good";
    if (pct >= 50) return "bar-mid";
    return "bar-bad";
  }

  function renderOverviewKpis(host, d) {
    clearNode(host);
    if (!host) return;
    if (!d || !d.has_data) {
      host.appendChild(el("div", "card empty", "Tanlangan davrda baholangan qoʻngʻiroqlar topilmadi."));
      return;
    }
    var vol = d.volume || {};
    var trend = d.trend || {};
    var grid = el("div", "grid");

    var c1 = el("div", "card");
    c1.appendChild(el("h2", "", "Umumiy samaradorlik"));
    c1.appendChild(el("div", "big", (d.true_efficiency || 0) + "%"));
    var bar = el("div", "bar");
    var fill = el("i", "");
    fill.style.width = Math.min(100, Math.max(0, Number(d.true_efficiency) || 0)) + "%";
    bar.appendChild(fill);
    c1.appendChild(bar);
    c1.appendChild(el("div", "note", "Konvertirlangan / JAMI qoʻngʻiroqlar"));
    grid.appendChild(c1);

    var c2 = el("div", "card");
    c2.appendChild(el("h2", "", "Qoʻngʻiroqlar tahlili"));
    [
      ["Jami", vol.total || 0],
      ["Samarali", vol.answered || 0],
      ["Oʻtkazib yuborilgan", vol.missed || 0],
      ["Oʻrtacha davomiylik", vol.avg_duration || "0:00"]
    ].forEach(function (pair) {
      var r = el("div", "row");
      r.appendChild(el("span", "", pair[0]));
      r.appendChild(el("span", "", pair[1]));
      c2.appendChild(r);
    });
    grid.appendChild(c2);

    var c3 = el("div", "card");
    c3.appendChild(el("h2", "", "Konversiya va Tushum"));
    c3.appendChild(el("div", "big", (trend.current_rate !== undefined ? trend.current_rate : (d.conversion_rate || 0)) + "%"));
    var trendNote = trend.reliable
      ? ((trend.delta_pp >= 0 ? "+" : "") + trend.delta_pp + " pp " + (trend.delta_pp >= 0 ? "↗" : "↘"))
      : (trend.reason || "Solishtirish uchun namuna kam");
    c3.appendChild(el("div", "note", trendNote));
    [
      ["Yutilgan tushum", formatMoney(d.revenue_won)],
      ["Xavf ostida", formatMoney(d.revenue_at_risk)]
    ].forEach(function (pair) {
      var r = el("div", "row");
      r.appendChild(el("span", "", pair[0]));
      r.appendChild(el("span", "", pair[1]));
      c3.appendChild(r);
    });
    grid.appendChild(c3);
    host.appendChild(grid);
  }

  function renderLeaderboard(host, meta, data, onSelectManager) {
    clearNode(host);
    if (meta) {
      meta.textContent = data && data.last_analyzed_at
        ? "Har soatda yangilanadi · Oxirgi tahlil: " + data.last_analyzed_at
        : "Har soatda yangilanadi · Real baza holati";
    }
    if (!host) return;
    var managers = (data && data.managers) || [];
    if (!managers.length) {
      host.appendChild(el("div", "empty", "Ushbu davr uchun menejerlar reytingi maʼlumoti yoʻq."));
      return;
    }

    var table = el("table", "lb-table");
    var thead = el("thead");
    var hr = el("tr");
    ["Menejer", "Sotuvlar", "Lid konversiyasi", "Suhbat sifati", "Oʻrtacha davomiylik", "Holat / Tahlil"].forEach(function (h) {
      hr.appendChild(el("th", "", h));
    });
    thead.appendChild(hr);
    table.appendChild(thead);

    var tbody = el("tbody");
    managers.forEach(function (m) {
      var tr = el("tr", "lb-row");
      var tdMgr = el("td");
      var mgrWrap = el("div", "mgr-inline");
      mgrWrap.appendChild(el("span", "mgr-avatar", m.avatar || "??"));
      mgrWrap.appendChild(el("span", "mgr-name", m.manager_name));
      tdMgr.appendChild(mgrWrap);
      tr.appendChild(tdMgr);

      tr.appendChild(el("td", "num-strong", m.sales_count));
      tr.appendChild(el("td", "", Number(m.lead_conversion_pct || 0).toFixed(2) + "%"));

      var tdQual = el("td");
      var qWrap = el("div", "qual-cell");
      var qTrack = el("div", "qual-track");
      var qFill = el("div", "qual-fill " + qualityColor(Number(m.call_quality_pct) || 0));
      qFill.style.width = Math.min(100, Math.max(0, Number(m.call_quality_pct) || 0)) + "%";
      qTrack.appendChild(qFill);
      qWrap.appendChild(qTrack);
      qWrap.appendChild(el("span", "qual-num", Number(m.call_quality_pct || 0).toFixed(2) + "%"));
      tdQual.appendChild(qWrap);
      tr.appendChild(tdQual);

      tr.appendChild(el("td", "", m.avg_duration_label || "0:00"));

      var tdAct = el("td");
      var pillCls = m.diagnostic_tag === "sotyapti" ? "pill-good"
        : (m.diagnostic_tag === "faqat_gaplashyapti" ? "pill-warn" : "pill-muted");
      tdAct.appendChild(el("span", "pill " + pillCls, m.diagnostic_label));
      var btn = el("button", "mini-btn", "Mikro-%");
      btn.type = "button";
      btn.addEventListener("click", function () { onSelectManager(m.manager_name); });
      tdAct.appendChild(btn);
      tr.appendChild(tdAct);
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    host.appendChild(table);
  }

  function renderChecklist(host, titleEl, data) {
    clearNode(host);
    if (titleEl) {
      titleEl.textContent = "Jon Branding Mikro-Mezonlar Tahlili (%): " + ((data && data.manager_name) || "Jamoa");
    }
    if (!host) return;
    if (!data || !data.available) {
      host.appendChild(el("div", "empty", "Baholangan qoʻngʻiroqlar yoʻqligi sababli mikro-mezon foizlari hisoblanmadi."));
      return;
    }

    var cols = el("div", "chk-cols");
    var sBox = el("div", "chk-box");
    sBox.appendChild(el("h3", "chk-good-h", "Kuchli tomonlari (" + data.strengths.length + ")"));
    if (!data.strengths.length) sBox.appendChild(el("div", "note", "65%+ darajadagi kuchli mezon topilmadi."));
    data.strengths.forEach(function (item) {
      var row = el("div", "chk-item");
      var head = el("div", "chk-item-head");
      head.appendChild(el("b", "", item.title));
      head.appendChild(el("span", "pill pill-good", Math.round(item.pct) + "%"));
      row.appendChild(head);
      row.appendChild(el("div", "chk-desc", item.description));
      sBox.appendChild(row);
    });

    var wBox = el("div", "chk-box");
    wBox.appendChild(el("h3", "chk-bad-h", "Kuchsiz tomonlari (" + data.weaknesses.length + ")"));
    if (!data.weaknesses.length) wBox.appendChild(el("div", "note", "65% dan past mezon kuzatilmadi."));
    data.weaknesses.forEach(function (item) {
      var row = el("div", "chk-item");
      var head = el("div", "chk-item-head");
      head.appendChild(el("b", "", item.title));
      head.appendChild(el("span", "pill pill-bad", Math.round(item.pct) + "%"));
      row.appendChild(head);
      row.appendChild(el("div", "chk-desc", item.description));
      wBox.appendChild(row);
    });

    cols.appendChild(sBox);
    cols.appendChild(wBox);
    host.appendChild(cols);
  }

  function buildRadarSvg(axes) {
    var ns = "http://www.w3.org/2000/svg";
    var svg = document.createElementNS(ns, "svg");
    svg.setAttribute("width", "210");
    svg.setAttribute("height", "210");
    svg.setAttribute("viewBox", "0 0 200 200");
    var n = axes.length || 1;
    var cx = 100, cy = 100, R = 74;
    function pt(i, r) {
      var a = (Math.PI * 2 * i) / n - Math.PI / 2;
      return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
    }
    [0.25, 0.5, 0.75, 1].forEach(function (f) {
      var poly = document.createElementNS(ns, "polygon");
      poly.setAttribute("points", axes.map(function (_, i) { return pt(i, R * f).join(","); }).join(" "));
      poly.setAttribute("fill", "none");
      poly.setAttribute("stroke", "#1b2740");
      svg.appendChild(poly);
    });
    axes.forEach(function (ax, i) {
      var end = pt(i, R);
      var line = document.createElementNS(ns, "line");
      line.setAttribute("x1", String(cx));
      line.setAttribute("y1", String(cy));
      line.setAttribute("x2", String(end[0]));
      line.setAttribute("y2", String(end[1]));
      line.setAttribute("stroke", "#1b2740");
      svg.appendChild(line);
      var lblPos = pt(i, R + 16);
      var txt = document.createElementNS(ns, "text");
      txt.setAttribute("x", String(lblPos[0]));
      txt.setAttribute("y", String(lblPos[1]));
      txt.setAttribute("fill", "#8ba0c4");
      txt.setAttribute("font-size", "10");
      txt.setAttribute("text-anchor", "middle");
      txt.setAttribute("dominant-baseline", "middle");
      txt.textContent = String(ax.label || "");
      svg.appendChild(txt);
    });
    var dataPoly = document.createElementNS(ns, "polygon");
    dataPoly.setAttribute(
      "points",
      axes.map(function (ax, i) { return pt(i, R * ((Number(ax.score) || 0) / 100)).join(","); }).join(" ")
    );
    dataPoly.setAttribute("fill", "rgba(47,107,255,.32)");
    dataPoly.setAttribute("stroke", "#2f6bff");
    dataPoly.setAttribute("stroke-width", "2");
    svg.appendChild(dataPoly);
    return svg;
  }

  function renderManagerCards(host, d) {
    clearNode(host);
    if (!host) return;
    var managers = (d && d.managers) || [];
    if (!d || !d.real_data || !managers.length) {
      host.appendChild(el("div", "card empty", "Hali baholangan real qoʻngʻiroq yoʻq — kartochkalar shu yerda chiqadi."));
      return;
    }
    var grid = el("div", "mgr-grid");
    managers.forEach(function (m) {
      var card = el("div", "mgr-card");
      var head = el("div", "mgr-head");
      head.appendChild(el("div", "mgr-avatar", m.avatar || "??"));
      head.appendChild(el("div", "mgr-name", m.name));
      card.appendChild(head);

      var stats = el("div", "mgr-stats");
      [
        [m.qualified_leads, "Qual lid"],
        [(m.conversion_rate || 0) + "%", "Konv"],
        [m.sales_count, "Sotuv"],
        [formatMoney(m.total_sum), "Summa"]
      ].forEach(function (pair) {
        var st = el("div", "mgr-stat");
        st.appendChild(el("b", "", pair[0]));
        st.appendChild(el("span", "", pair[1]));
        stats.appendChild(st);
      });
      card.appendChild(stats);

      if (m.has_radar_data && Array.isArray(m.radar)) {
        var wrap = el("div", "radar-wrap");
        wrap.appendChild(buildRadarSvg(m.radar));
        card.appendChild(wrap);
      }
      var lastCall = (m.recent_calls || [])[0];
      if (lastCall && typeof lastCall.audio_url === "string" && /^https?:\/\//i.test(lastCall.audio_url)) {
        var link = el("a", "audio-link", "🎧 Tahlil audio");
        link.href = lastCall.audio_url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        card.appendChild(link);
      }
      grid.appendChild(card);
    });
    host.appendChild(grid);
  }

  window.OishaSalesRender = {
    el: el,
    clearNode: clearNode,
    renderOverviewKpis: renderOverviewKpis,
    renderLeaderboard: renderLeaderboard,
    renderChecklist: renderChecklist,
    renderManagerCards: renderManagerCards
  };
})();
