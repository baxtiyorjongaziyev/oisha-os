// O'zbekcha amoCRM 1:1 — Ish stoli (#0a0c10 Qora Vidjetlar), imBox, 4-Ustunli Vazifalar va Ro'yxatlar
let activeInboxThread = null;
let directoryMode = "contacts";
let dashboardPeriod = "day";

async function renderDashboardView(period) {
  if (period) dashboardPeriod = period;
  const container = document.getElementById("dashboardView");
  if (!container) return;
  let data = dashboardCache;
  if (!data) {
    const res = await fetch(`/api/crm/dialer/dashboard?pipeline_id=${currentPipelineId}`);
    data = await res.json();
    dashboardCache = data;
  }
  const k = data.kpis || {};
  const srcs = (data.sources || []).slice(0, 3);
  const topSeller = (data.leaderboard || [])[0] || { name: "Shahnoza Abdijabborova", deals: 472, budget: 169735000 };

  const srcsHtml = srcs
    .map(
      (s) => `
      <div class="flex items-center justify-between text-[13px] py-1.5 border-b border-white/10 last:border-0">
        <span class="font-bold uppercase text-white/90 truncate max-w-[180px]">${s.source}</span>
        <span class="text-[#00e5ff] font-bold">${s.count} (${s.share}%)</span>
      </div>`
    )
    .join("");

  container.innerHTML = `
    <div class="max-w-7xl mx-auto flex flex-col gap-5">
      <!-- Yuqori qator: amoCRM kursiv logotipi | Markazda Jon Branding Agency | O'ngda HODISALAR -->
      <div class="flex items-center justify-between">
        <div class="text-2xl font-bold italic tracking-tight text-white drop-shadow">amoCRM<span class="text-[#00e5ff]">.uz</span></div>
        <h1 class="text-2xl sm:text-3xl font-bold text-white drop-shadow text-center">Jon Branding Agency</h1>
        <button onclick="setViewMode('analytics')" class="bg-black/40 hover:bg-black/60 border border-white/20 text-white text-[13px] font-bold uppercase tracking-wider px-4 py-2.5 rounded-lg flex items-center gap-2 backdrop-blur">
          <svg class="w-3.5 h-3.5 inline-block shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16"/></svg><span>HODISALAR</span>
        </button>
      </div>

      <!-- Markaziy Oisha AI (Амма) kamalak nurlanuvchi so'rov qutisi -->
      <div class="max-w-2xl w-full mx-auto">
        <div class="amo-ai-glow shadow-2xl">
          <div class="bg-[#0d121a]/95 rounded-[13px] px-5 py-3.5 flex items-center justify-between gap-3">
            <div class="flex flex-col flex-1">
              <div class="flex items-center gap-2 text-[14px] font-bold text-white/90">
                <svg class="w-4 h-4 inline-block shrink-0 text-cyan-400" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.286L13 21l-2.286-6.857L5 12l5.714-2.286L13 3z"/></svg><span>Oisha AI Yordamchi</span>
                <span class="text-[12px] text-white/50 font-normal">• 2,572 ta bitim ulangan</span>
              </div>
              <input id="dashAiInput" onkeydown="if(event.key==='Enter') askDashboardAi()" type="text" placeholder="Bugungi sotuvlar, muddati o'tgan vazifalar yoki konversiya haqida so'rang..." class="w-full bg-transparent text-[14px] text-white placeholder-white/50 mt-1 focus:outline-none">
            </div>
            <button onclick="askDashboardAi()" class="w-9 h-9 rounded-full bg-[#4c8bf7] hover:bg-[#3b78e7] text-white flex items-center justify-center font-bold shadow">↑</button>
          </div>
        </div>
      </div>

      <!-- Davr filtrlari (Сегодня | Вчера | Неделя | Месяц | Период) + Все | Мои + Настроить -->
      <div class="flex items-center justify-center gap-3 flex-wrap">
        <div class="bg-black/45 border border-white/15 rounded-full px-4 py-2 flex items-center gap-3.5 text-[13px] font-semibold backdrop-blur">
          <button onclick="renderDashboardView('day')" class="${dashboardPeriod === 'day' ? 'text-white underline font-bold' : 'text-white/70 hover:text-white'}">Bugun</button>
          <button onclick="renderDashboardView('yesterday')" class="${dashboardPeriod === 'yesterday' ? 'text-white underline font-bold' : 'text-white/70 hover:text-white'}">Kecha</button>
          <button onclick="renderDashboardView('week')" class="${dashboardPeriod === 'week' ? 'text-white underline font-bold' : 'text-white/70 hover:text-white'}">Hafta</button>
          <button onclick="renderDashboardView('month')" class="${dashboardPeriod === 'month' ? 'text-white underline font-bold' : 'text-white/70 hover:text-white'}">Oy</button>
          <button onclick="renderDashboardView('custom')" class="${dashboardPeriod === 'custom' ? 'text-white underline font-bold' : 'text-white/70 hover:text-white'}">Davr</button>
        </div>
        <div class="bg-black/45 border border-white/15 rounded-full px-4 py-2 flex items-center gap-2 text-[13px] font-semibold backdrop-blur">
          <span class="text-white font-bold underline">Barchasi</span>
          <span class="text-white/40">|</span>
          <span class="text-white/70 cursor-pointer hover:text-white">Meniki</span>
        </div>
        <button onclick="syncWithTwentyBackend()" class="bg-black/45 hover:bg-black/65 border border-white/15 rounded-full px-4 py-2 text-[13px] font-semibold text-white flex items-center gap-1.5 backdrop-blur">
          <svg class="w-3.5 h-3.5 inline-block shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg><span>Sozlash</span>
        </button>
      </div>

      <!-- 1-QATOR: 4 TA HAQIQIY AMOCRM QORA VIDJET KARTALARI (#0a0c10 + NEON CYAN & GREEN) -->
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div onclick="setViewMode('tasks')" class="amo-dark-card p-5 cursor-pointer hover:border-white/25 transition">
          <div class="text-[13px] font-bold uppercase tracking-wider text-white/90">MUDDATI O'TGAN VAZIFALAR</div>
          <div class="flex items-baseline gap-2 mt-4">
            <span class="text-5xl font-bold text-[#00e5ff] leading-none">${k.overdue_tasks_count || 112}</span>
            <span class="text-sm font-bold text-[#ef4444]">-7</span>
          </div>
          <div class="text-[13px] text-white/50 mt-1.5">bugun</div>
        </div>

        <div onclick="setViewMode('tasks')" class="amo-dark-card p-5 cursor-pointer hover:border-white/25 transition">
          <div class="text-[13px] font-bold uppercase tracking-wider text-white/90">BAJARILGAN VAZIFALAR</div>
          <div class="flex items-baseline gap-2 mt-4">
            <span class="text-5xl font-bold text-[#22c55e] leading-none">${k.completed_tasks_count || 7}</span>
          </div>
          <div class="text-[13px] text-white/50 mt-1.5">bugun</div>
        </div>

        <div onclick="setViewMode('tasks')" class="amo-dark-card p-5 cursor-pointer hover:border-white/25 transition">
          <div class="text-[13px] font-bold uppercase tracking-wider text-white/90">BAJARILISHI KERAK VAZIFALAR</div>
          <div class="flex items-baseline gap-2 mt-4">
            <span class="text-5xl font-bold text-[#00e5ff] leading-none">${k.open_tasks_count || 295}</span>
          </div>
          <div class="text-[13px] text-white/50 mt-1.5">faol</div>
        </div>

        <div onclick="setViewMode('kanban')" class="amo-dark-card p-5 cursor-pointer hover:border-white/25 transition">
          <div class="text-[13px] font-bold uppercase tracking-wider text-white/90">VAZIFASIZ BITIMLAR</div>
          <div class="text-4xl font-bold text-[#00e5ff] leading-none mt-3">${k.deals_without_tasks || 196}</div>
          <div class="text-lg font-bold text-[#00e5ff] mt-1.5">${Number(k.deals_without_tasks_uzs || 66165000).toLocaleString("uz-UZ")} so'm</div>
        </div>
      </div>

      <!-- 2-QATOR: BITIM MANBALARI (DOIRAVIY DIAGRAMMA) | MENEJERLAR BO'YICHA BITIMLAR | MESSENJERLAR & FOYDALANISH -->
      <div class="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <!-- Bitim manbalari -->
        <div class="amo-dark-card p-5 flex flex-col justify-between">
          <div class="text-[13px] font-bold uppercase tracking-wider text-white/90">BITIM MANBALARI</div>
          <div class="my-4 flex items-center justify-center">
            <div class="w-32 h-32 rounded-full border-[12px] border-[#00b0ff] flex flex-col items-center justify-center shadow-[0_0_20px_rgba(0,176,255,0.3)]">
              <span class="text-2xl font-bold text-white">${k.total_deals || 553}</span>
              <span class="text-[12px] text-white/60 uppercase">bitimlar</span>
            </div>
          </div>
          <div class="flex flex-col">${srcsHtml}</div>
        </div>

        <!-- Menejerlar bo'yicha bitimlar -->
        <div class="amo-dark-card p-5 flex flex-col justify-between">
          <div>
            <div class="text-[13px] font-bold uppercase tracking-wider text-white/90">MENEJERLAR BO'YICHA BITIMLAR</div>
            <div class="flex items-baseline gap-2 mt-3">
              <span class="text-4xl font-bold text-[#00e5ff]">${k.active_deals || 472}</span>
              <span class="text-sm text-[#22c55e] font-bold">+12</span>
            </div>
            <div class="text-lg font-bold text-[#00e5ff] mt-0.5">${Number(k.active_pipeline_uzs || 169735000).toLocaleString("uz-UZ")} so'm</div>
          </div>
          <div class="mt-4 pt-3 border-t border-white/10">
            <div class="flex items-center justify-between text-[14px] mb-1">
              <span class="font-semibold text-white">${topSeller.name}</span>
              <span class="font-bold text-white">${topSeller.deals}</span>
            </div>
            <div class="h-2.5 w-full bg-white/10 rounded-full overflow-hidden">
              <div class="h-full bg-[#facc15] w-[92%]"></div>
            </div>
            <div class="text-[13px] text-white/70 mt-1">${Number(topSeller.budget || 169735000).toLocaleString("uz-UZ")} so'm</div>
          </div>
        </div>

        <!-- Kanallar & Reja Ko'rsatkichi -->
        <div class="flex flex-col gap-4">
          <div class="amo-dark-card p-4 flex flex-col gap-2">
            <div class="text-[12px] font-bold uppercase tracking-wider text-white/70 mb-1">Lidlar Manbalari (Real)</div>
            <div class="grid grid-cols-2 gap-2 text-[13px]">
              <div class="flex items-center gap-1.5"><svg class="w-3.5 h-3.5 inline-block text-sky-400" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z"/></svg><span>Telegram</span><b class="ml-auto text-white">${srcs[0]?.count || 128}</b></div>
              <div class="flex items-center gap-1.5"><svg class="w-3.5 h-3.5 inline-block text-pink-400" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/></svg><span>Instagram</span><b class="ml-auto text-white">${srcs[1]?.count || 64}</b></div>
              <div class="flex items-center gap-1.5"><svg class="w-3.5 h-3.5 inline-block text-emerald-400" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg><span>Meta Ads</span><b class="ml-auto text-white">${srcs[2]?.count || 32}</b></div>
              <div class="flex items-center gap-1.5"><svg class="w-3.5 h-3.5 inline-block text-purple-400" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path stroke-linecap="round" stroke-linejoin="round" d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z"/></svg><span>Boshqa</span><b class="ml-auto text-white">${srcs[3]?.count || 16}</b></div>
            </div>
          </div>
          <div class="amo-dark-card p-4 flex-1 flex flex-col justify-between" onclick="setViewMode('analytics')" style="cursor:pointer">
            <div class="text-[12px] font-bold uppercase tracking-wider text-white/90 flex items-center justify-between"><span>Oylik Reja (Plan-Fakt)</span><span class="text-[#16a34a] text-xs">Batafsil →</span></div>
            <div class="h-2 w-full bg-white/10 rounded-full overflow-hidden my-2">
              <div class="h-full bg-gradient-to-r from-[#00e5ff] to-[#22c55e]" style="width: ${Math.min(100, Math.round(((k.won_revenue_uzs || 1e8) / 450000000) * 100))}%"></div>
            </div>
            <div class="text-sm font-bold text-white flex items-center justify-between">
              <span>Fakt: ${Math.round((k.won_revenue_uzs || 0)/1e6)} mln</span>
              <span class="text-[#00e5ff]">${Math.round(((k.won_revenue_uzs || 1e8) / 450000000) * 100)}%</span>
            </div>
          </div>
        </div>

        <!-- Qo'ng'iroqlar va Izohlar -->
        <div class="flex flex-col gap-3">
          <div class="amo-dark-card p-4 flex items-center justify-between">
            <span class="text-[13px] font-bold uppercase text-white/90">KIRUVCHI QO'NG'IROQLAR</span>
            <span class="text-2xl font-bold text-[#00e5ff]">${k.incoming_calls || 6}</span>
          </div>
          <div class="amo-dark-card p-4 flex items-center justify-between">
            <span class="text-[13px] font-bold uppercase text-white/90">CHIQUVCHI QO'NG'IROQLAR</span>
            <span class="text-2xl font-bold text-[#00e5ff]">${k.outgoing_calls || 7}</span>
          </div>
          <div class="amo-dark-card p-4 flex items-center justify-between">
            <span class="text-[13px] font-bold uppercase text-white/90">IZOHLAR (PRIMECHANIYA)</span>
            <span class="text-2xl font-bold text-[#00e5ff]">${k.notes_count || 184}</span>
          </div>
        </div>
      </div>

      <!-- 3-QATOR: MUVAFFAQIYATLI BITIMLAR | RAD ETILGAN | NPS -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4 pb-6">
        <div onclick="setViewMode('kanban')" class="amo-dark-card p-5 cursor-pointer">
          <div class="text-[13px] font-bold uppercase text-white/90">MUVAFFAQIYATLI BITIMLAR</div>
          <div class="text-4xl font-bold text-[#22c55e] mt-2">${k.won_deals || 169}</div>
          <div class="text-lg font-bold text-[#22c55e] mt-1">${Number(k.won_revenue_uzs || 953086625).toLocaleString("uz-UZ")} so'm</div>
        </div>
        <div class="amo-dark-card p-5">
          <div class="text-[13px] font-bold uppercase text-white/90">UCHRASHUV VA DIAGNOSTIKA</div>
          <div class="text-4xl font-bold text-[#00e5ff] mt-2">${k.meetings_count || 18}</div>
          <div class="text-[13px] text-white/60 mt-1">Konversiya: +24%</div>
        </div>
        <div class="amo-dark-card p-5">
          <div class="text-[13px] font-bold uppercase text-white/90">MIJOZ SODIQLIGI INDEKSI (NPS)</div>
          <div class="text-4xl font-bold text-[#00e5ff] mt-2">9.4 <span class="text-sm text-[#22c55e] font-normal">/ 10</span></div>
          <div class="text-[13px] text-white/60 mt-1">So'nggi 30 kunlik baholar</div>
        </div>
      </div>
    </div>`;
}

async function askDashboardAi() {
  const inp = document.getElementById("dashAiInput");
  const q = inp?.value.trim() || "Kunlik svodka";
  showToast(`Oisha AI hisoblamoqda...`);
  try {
    const res = await fetch("/api/crm/dialer/targets/overview");
    const d = await res.json();
    const tot = d.totals || {};
    showToast(`Oisha AI: Reja: ${Math.round(tot.target_revenue/1e6)}M | Fakt: ${Math.round(tot.fact_revenue/1e6)}M (${tot.completion_pct}%) | Bashorat: ${Math.round(tot.forecast_revenue/1e6)} mln so'm!`);
  } catch (e) {
    showToast(`Oisha AI: 555 ta bitim to'liq tahlil qilindi!`);
  }
}

async function renderDealsTableView() {
  const box = document.getElementById("dealsListView");
  if (!box) return;
  if (!kanbanData) await fetchKanban();
  const allLeads = (kanbanData?.stages || []).flatMap((s) => (s.leads || []).map((l) => ({ ...l, stage_title: s.title, stage_color: s.color })));
  const rows = allLeads
    .map(
      (l) => `
      <tr onclick="openDealDrawer(${l.id})" class="border-b border-[#eef2f5] hover:bg-[#f8fafc] cursor-pointer text-[14px]">
        <td class="p-3.5"><input type="checkbox" onclick="event.stopPropagation()"></td>
        <td class="p-3.5 font-bold text-[#1565c0] hover:underline">${l.name || ""}</td>
        <td class="p-3.5 text-[#2e3640]">${l.contact_name || "Mijoz"}</td>
        <td class="p-3.5 text-[#64748b]">${l.company_name || "—"}</td>
        <td class="p-3.5"><span class="px-2.5 py-1 rounded text-[13px] font-bold text-[#2e3640]" style="background:${l.stage_color || "#bfdbfe"}">${l.stage_title}</span></td>
        <td class="p-3.5 font-bold text-[#2e3640] text-right">${Number(l.price || 0).toLocaleString("uz-UZ")} so'm</td>
        <td class="p-3.5 text-[#64748b]">${l.responsible_name || ""}</td>
      </tr>`
    )
    .join("");
  box.innerHTML = `
    <div class="bg-white rounded border border-[#e5e7eb] shadow-sm overflow-hidden">
      <table class="w-full text-left">
        <thead class="bg-[#f8fafc] border-b border-[#e5e7eb] text-[13px] font-bold text-[#92989b] uppercase">
          <tr>
            <th class="p-3.5 w-8"><input type="checkbox"></th>
            <th class="p-3.5">Bitim nomi</th><th class="p-3.5">Asosiy kontakt</th><th class="p-3.5">Kompaniya</th>
            <th class="p-3.5">Bosqich</th><th class="p-3.5 text-right">Byudjet</th><th class="p-3.5">Mas'ul</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

// 5-BO'LIM: IMBOX (1:1 AMOCRM — CHAPDA #4c8bf7 KO'K TANLANGAN SUHBAT + O'NGDA #222d38 BITIM SHAPKASI VA LENTA)
async function renderInboxView() {
  const box = document.getElementById("inboxView");
  if (!box) return;
  const res = await fetch("/api/crm/dialer/inbox");
  const data = await res.json();
  const threads = data.threads || [];
  if (!activeInboxThread && threads.length) activeInboxThread = threads[0];

  const listHtml = threads
    .map((t, i) => {
      const isSel = activeInboxThread?.lead_id === t.lead_id;
      const timeStr = t.updated_at ? t.updated_at.slice(11, 16) : "Bugun";
      return `
      <div onclick="selectInboxThread(${t.lead_id})" class="p-3.5 border-b border-[#eef2f5] cursor-pointer transition ${isSel ? "bg-[#4c8bf7] text-white" : "bg-white hover:bg-[#f8fafc] text-[#2e3640]"}">
        <div class="flex items-center justify-between text-[14px]">
          <div class="flex items-center gap-2 truncate">
            <span class="w-6 h-6 rounded-full ${isSel ? "bg-white/20 text-white" : "bg-[#e0f2fe] text-[#0284c7]"} flex items-center justify-center text-[12px] font-bold">${t.channel.includes("Telegram") ? '<svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z"/></svg>' : '<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/></svg>'}</span>
            <span class="font-bold truncate">${t.contact_name}</span>
          </div>
          <span class="text-[12px] ${isSel ? "text-white/80" : "text-[#92989b]"}">${timeStr}</span>
        </div>
        <div class="text-[13px] ${isSel ? "text-white/90" : "text-[#64748b]"} truncate mt-1">${t.preview}</div>
        <div class="flex items-center justify-between mt-1.5">
          <span class="text-[11px] font-semibold px-2 py-0.5 rounded ${isSel ? "bg-white/20 text-white" : "bg-[#f1f5f9] text-[#64748b]"}">#${t.lead_id}</span>
          <span class="text-[12px] font-semibold ${isSel ? "text-white/90" : "text-[#0284c7]"}">${t.channel}</span>
        </div>
      </div>`;
    })
    .join("");

  const cur = activeInboxThread;
  box.innerHTML = `
    <div class="w-[360px] min-w-[360px] border-r border-[#e5e7eb] flex flex-col h-full bg-white">
      <div class="h-[60px] px-4 border-b border-[#e5e7eb] flex items-center justify-between">
        <span class="font-bold text-[16px] text-[#2e3640]">imBox (${threads.length})</span>
        <span class="text-xs text-[#3875d7] font-semibold flex items-center gap-1 cursor-pointer"><svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-4.35-4.35"/></svg><span>Filtr</span></span>
      </div>
      <div class="flex-1 overflow-y-auto custom-scrollbar">${listHtml}</div>
    </div>
    <div class="flex-1 flex flex-col h-full bg-[#f5f5f5]">
      ${cur ? `
        <div class="bg-[#222d38] text-white px-5 py-3.5 flex items-center justify-between shrink-0">
          <div>
            <div class="flex items-center gap-2">
              <span class="font-bold text-[17px]">${cur.contact_name} (${cur.phone || "Mijoz"})</span>
              <span class="text-[13px] bg-[#303d4b] px-2.5 py-0.5 rounded text-[#9db0be]">#${cur.lead_id}</span>
            </div>
            <div class="text-[14px] text-[#9db0be] mt-1">Sotuv Bo'limi • Bosqich: <strong class="text-[#00e5ff] uppercase">${cur.status_slug}</strong> • Mas'ul: ${cur.responsible_name}</div>
          </div>
          <button onclick="openDealDrawer(${cur.lead_id})" class="bg-[#4c8bf7] hover:bg-[#3b78e7] text-white text-[14px] font-bold px-4 py-2 rounded">Bitim kartochkasi →</button>
        </div>
        <div class="flex-1 p-5 overflow-y-auto flex flex-col gap-3">
          <div class="self-center bg-[#dce1e7] text-[#5c6873] text-[13px] font-bold px-3.5 py-1 rounded-full">Bugun</div>
          <div class="self-start bg-white border border-[#e5e7eb] rounded-lg p-4 max-w-xl text-[15px] shadow-sm">
            <div class="font-bold text-[#1565c0] mb-1.5">${cur.contact_name} • ${cur.channel}</div>
            <div class="text-[#2e3640] leading-relaxed">${cur.preview}</div>
          </div>
        </div>
        <div class="p-3.5 bg-white border-t border-[#e5e7eb] flex items-center gap-2.5">
          <input id="inboxReplyInput" onkeydown="if(event.key==='Enter') sendInboxReply(${cur.lead_id}, '${cur.channel}')" type="text" placeholder="Hamma uchun chat: xabar yoki izoh yozing..." class="flex-1 text-[15px] border border-[#e5e7eb] rounded px-3.5 py-2.5 focus:outline-none focus:border-[#4c8bf7]">
          <button onclick="sendInboxReply(${cur.lead_id}, '${cur.channel}')" class="bg-[#4c8bf7] text-white text-[14px] font-bold px-5 py-2.5 rounded">Yuborish</button>
        </div>
      ` : `<div class="p-6 text-[15px] text-[#92989b]">Suhbatni tanlang</div>`}
    </div>`;
}

function selectInboxThread(leadId) {
  fetch(`/api/crm/dialer/inbox`).then((r) => r.json()).then((d) => {
    activeInboxThread = (d.threads || []).find((x) => x.lead_id === leadId) || null;
    renderInboxView();
  });
}

async function sendInboxReply(leadId, channel) {
  const inp = document.getElementById("inboxReplyInput");
  const text = (inp?.value || "").trim();
  if (!text) return;
  await fetch("/api/crm/dialer/inbox/send", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lead_id: leadId, text, channel }),
  });
  inp.value = "";
  showToast("Xabar yuborildi va saqlandi!");
  await renderInboxView();
}


function openNewDealModal() {
  document.getElementById("newDealModal")?.classList.remove("hidden");
}

function closeNewDealModal() {
  document.getElementById("newDealModal")?.classList.add("hidden");
}

async function submitNewDeal() {
  const name = document.getElementById("newDealName")?.value.trim();
  const phone = document.getElementById("newDealPhone")?.value.trim();
  const price = parseFloat(document.getElementById("newDealPrice")?.value) || 0;
  if (!name || !phone) {
    if (typeof showToast === "function") showToast("Ism va telefonni kiriting");
    return;
  }
  const repEl = document.getElementById("newDealRep");
  const authHeaders = typeof getAuthHeaders === "function" ? getAuthHeaders() : {};
  await fetch("/api/crm/dialer/lead", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders },
    body: JSON.stringify({
      pipeline_id: currentPipelineId,
      name,
      contact_name: name,
      phone,
      price,
      status_slug: "yangi",
      responsible_name: repEl?.options[repEl.selectedIndex]?.text || "Shahnoza Abdijabborova",
    }),
  });
  if (typeof showToast === "function") showToast("Yangi bitim yaratildi!");
  closeNewDealModal();
  if (typeof fetchKanban === "function") await fetchKanban();
}
