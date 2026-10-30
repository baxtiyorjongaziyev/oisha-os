// Oisha ERP — Direktor paneli ma'lumotini GET /api/erp/dashboard (ERPSnapshot) dan to'ldiradi.
// Sozlash (URL parametrlari):
//   ?api=https://oisha.jonbranding.uz  — API manzili (bo'lmasa — shu sahifaning o'z domeni)
//   ?period=2026-10                    — davr (bo'lmasa — joriy oy)
//   ?demo=1                            — API o'rniga sample-erp-snapshot.json (lokal ko'rish uchun)
// Kalit (OISHA_API_SECRET) URL'da emas, formadan olinadi va faqat sessionStorage'da turadi.
(function () {
  'use strict';

  var TOKEN_KEY = 'oisha-api-token';
  var STATUS = {
    healthy: ['success', 'Sog‘lom'],
    warning: ['warning', 'Diqqat talab qiladi'],
    critical: ['error', 'Xavfli: zarar'],
  };

  var params = new URLSearchParams(location.search);
  var root;

  function money(n) {
    return Number(n || 0).toLocaleString('ru-RU').replace(/ |,/g, ' ');
  }

  function set(field, text) {
    root.querySelectorAll('[data-f="' + field + '"]').forEach(function (el) { el.textContent = text; });
  }

  function html(field, markup) {
    root.querySelectorAll('[data-f="' + field + '"]').forEach(function (el) { el.innerHTML = markup; });
  }

  function getToken() {
    try { return sessionStorage.getItem(TOKEN_KEY) || ''; } catch (e) { return ''; }
  }

  function show(sel, on) {
    var el = root.querySelector(sel);
    if (el) el.hidden = !on;
  }

  function fail(message) {
    root.setAttribute('aria-busy', 'false');
    set('updated', 'yangilanmadi');
    set('error', message);
    show('[data-oisha-error]', true);
  }

  function render(d) {
    var st = STATUS[d.cash_flow_status];
    set('period', d.period);
    set('updated', 'yangilandi ' + new Date().toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' }));
    set('net_profit', money(d.net_profit));
    set('total_revenue', money(d.total_revenue));
    set('total_expenses', money(d.total_expenses));
    set('payroll_cost', money(d.payroll_cost));
    set('outstanding_amount', money(d.outstanding_amount));
    set('outstanding_invoices', String(d.outstanding_invoices));
    set('active_projects', String(d.active_projects));
    set('pipeline_value', money(d.pipeline_value));
    set('pending_advances', String(d.pending_advances));
    set('pending_advance_total', money(d.pending_advance_total));
    set('active_employees', String(d.active_employees));
    html('status', st
      ? '<span class="eco-badge eco-badge--' + st[0] + ' eco-badge--dot">' + st[1] + '</span>'
      : '<span class="eco-badge eco-badge--dot">Noaniq</span>');
    html('overdue_badge', d.overdue_projects > 0
      ? '<span class="eco-status eco-status--error">Muddati o‘tgan: ' + d.overdue_projects + '</span>'
      : '<span class="eco-status eco-status--success">Hammasi muddatida</span>');

    var slot = root.querySelector('[data-oisha-chart="top_expenses"]');
    var items = (d.top_expenses || []).filter(function (x) { return x.total > 0; });
    if (!items.length) {
      slot.innerHTML = '<div class="eco-empty eco-empty--compact"><p class="eco-empty__title">Bu davrda xarajat yozilmagan</p></div>';
    } else {
      var spec = {
        type: 'bar',
        label: 'Eng katta xarajatlar, ' + d.period,
        x: items.map(function (x) { return x.category; }),
        series: [{ name: 'Xarajat', v: items.map(function (x) { return Math.round(x.total / 1e5) / 10; }) }],
        unit: 'mln so‘m',
        dp: 1,
        xName: 'Toifa',
      };
      var chart = document.createElement('div');
      chart.className = 'eco-chart';
      chart.setAttribute('data-eco-chart', JSON.stringify(spec));
      slot.replaceChildren(chart);
      if (window.PDPUI && window.PDPUI.refresh) window.PDPUI.refresh(slot);
    }
    root.setAttribute('aria-busy', 'false');
  }

  function load() {
    show('[data-oisha-error]', false);
    show('[data-oisha-auth]', false);
    root.setAttribute('aria-busy', 'true');
    set('updated', 'yuklanmoqda…');

    var url, opts = {};
    if (params.get('demo') === '1') {
      url = 'sample-erp-snapshot.json';
    } else {
      var token = getToken();
      if (!token) {
        root.setAttribute('aria-busy', 'false');
        set('updated', 'kalit kiritilmagan');
        show('[data-oisha-auth]', true);
        return;
      }
      var base = (params.get('api') || '').replace(/\/$/, '');
      var period = params.get('period') || '';
      url = base + '/api/erp/dashboard' + (period ? '?period=' + encodeURIComponent(period) : '');
      opts.headers = { Authorization: 'Bearer ' + token };
    }

    fetch(url, opts)
      .then(function (r) {
        if (r.status === 401 || r.status === 403) {
          try { sessionStorage.removeItem(TOKEN_KEY); } catch (e) {}
          throw new Error('Kalit noto‘g‘ri yoki ruxsat yo‘q (HTTP ' + r.status + ').');
        }
        if (!r.ok) throw new Error('Server xatosi (HTTP ' + r.status + '). Keyinroq qayta urinib ko‘ring.');
        return r.json();
      })
      .then(render)
      .catch(function (e) {
        fail(e.message || 'Tarmoq xatosi: API manziliga ulanib bo‘lmadi.');
        if (!getToken() && params.get('demo') !== '1') show('[data-oisha-auth]', true);
      });
  }

  document.addEventListener('DOMContentLoaded', function () {
    root = document.querySelector('[data-oisha-erp]');
    if (!root) return;
    root.querySelector('[data-oisha-reload]').addEventListener('click', load);
    root.querySelector('[data-oisha-auth]').addEventListener('submit', function (ev) {
      ev.preventDefault();
      var v = ev.target.elements.token.value.trim();
      try { sessionStorage.setItem(TOKEN_KEY, v); } catch (e) {}
      ev.target.reset();
      load();
    });
    load();
  });
})();
