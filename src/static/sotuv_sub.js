// O'zbekcha amoCRM 1:1 — 4-Ustunli Vazifalar, Ro'yxatlar, AI-Agentlar, Pochta, Analitika va Sozlamalar
let analyticsSubSection = "funnel";
let settingsSubSection = "users";

// 6-BO'LIM: VAZIFALAR (1:1 AMOCRM 4-USTUNLI KANBAN DOSKASI)
async function renderTasksView() {
  const box = document.getElementById("tasksView");
  if (!box) return;
  const res = await fetch("/api/crm/dialer/tasks?status=open&limit=150");
  const data = await res.json();
  const tasks = data.tasks || [];
  const c = data.counts || {};
  const todayStr = new Date().toISOString().slice(0, 10);
  const tmrw = new Date();
  tmrw.setDate(tmrw.getDate() + 1);
  const tomorrowStr = tmrw.toISOString().slice(0, 10);

  const overdueList = [];
  const todayList = [];
  const tomorrowList = [];
  const futureList = [];

  tasks.forEach((t) => {
    const d = (t.due_at || "").slice(0, 10);
    if (d && d < todayStr) overdueList.push(t);
    else if (d === todayStr || !d) todayList.push(t);
    else if (d === tomorrowStr) tomorrowList.push(t);
    else futureList.push(t);
  });

  const renderColCards = (arr, isOverdue) =>
    arr
      .map(
        (t) => `
      <div class="amo-deal-card"><div class="flex items-center justify-between amo-type-meta leading-tight"><span class="truncate max-w-[180px] text-[#4a5568] font-medium">${t.contact_name || "Mijoz"}, ${t.responsible_name || "Shahnoza"}</span><span class="${isOverdue ? "text-[#ef4444] font-bold" : "text-[#9da8b6]"} tabular-nums">${(t.due_at || "Bugun 15:00").slice(5, 16)}</span></div><div onclick="openDealDrawer(${t.lead_id})" class="amo-card-title hover:underline cursor-pointer">${t.lead_name} (${t.phone || ""})</div><div class="amo-type-body flex items-start justify-between gap-2 pt-1 border-t border-[#edf0f3]"><div><span class="text-[#10b981] font-semibold">↻ ${t.task_type}:</span> ${t.title}</div><button onclick="completeCrmTask(${t.id})" class="amo-btn amo-btn-secondary amo-btn-sm text-xs shrink-0" title="Bajarildi"><svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg></button></div></div>`
      )
      .join("");

  box.innerHTML = `
    <!-- Yuqori oq panel (ДЕНЬ | НЕДЕЛЯ | МЕСЯЦ + Фильтр + ДОБАВИТЬ ЗАДАЧУ) --><div class="h-[64px] bg-white border-b border-[#e5e7eb] px-5 flex items-center justify-between shrink-0"><div class="flex items-center gap-3.5"><div class="flex items-center border border-[#d8dde3] rounded overflow-hidden text-[13px] font-bold"><button class="px-3.5 py-2 bg-[#eff6ff] text-[#4c8bf7]">KUN</button><button class="px-3.5 py-2 bg-white text-[#64748b] border-l border-[#d8dde3]">HAFTA</button><button class="px-3.5 py-2 bg-white text-[#64748b] border-l border-[#d8dde3]">OY</button></div><input id="newTaskTitle" type="text" placeholder="Vazifa matni yoki qidiruv..." class="text-[14px] border border-[#d8dde3] rounded px-3.5 py-2 w-72 focus:outline-none focus:border-[#4c8bf7]"></div><div class="flex items-center gap-3.5"><span class="text-[14px] text-[#92989b]"><strong class="text-[#2e3640]">${c.open || tasks.length}</strong> ta vazifa</span><button onclick="createNewCrmTask()" class="bg-[#4c8bf7] hover:bg-[#3b78e7] text-white text-[13px] font-bold uppercase tracking-wider px-4 py-2.5 rounded shadow-sm">+ VAZIFA QO'SHISH</button></div></div><!-- 4-Ustunli Vazifalar Kanban Doskasi --><div class="flex-1 flex gap-3.5 p-4 overflow-x-auto custom-scrollbar"><div class="w-[330px] min-w-[330px] flex flex-col h-full"><div class="pb-2 mb-2.5 text-center border-b-[3px] border-[#ef4444]"><div class="font-bold text-[14px] text-[#2e3640] uppercase">MUDDATI O'TGAN VAZIFALAR</div><div class="text-[13px] text-[#92989b]">${overdueList.length} ta vazifa</div></div><div class="flex-1 flex flex-col gap-2.5 overflow-y-auto custom-scrollbar">${renderColCards(overdueList, true)}</div></div><div class="w-[330px] min-w-[330px] flex flex-col h-full"><div class="pb-2 mb-2.5 text-center border-b-[3px] border-[#22c55e]"><div class="font-bold text-[14px] text-[#2e3640] uppercase">BUGUNGI VAZIFALAR</div><div class="text-[13px] text-[#92989b]">${todayList.length} ta vazifa</div></div><div class="flex-1 flex flex-col gap-2.5 overflow-y-auto custom-scrollbar">${renderColCards(todayList, false)}</div></div><div class="w-[330px] min-w-[330px] flex flex-col h-full"><div class="pb-2 mb-2.5 text-center border-b-[3px] border-[#cbd5e1]"><div class="font-bold text-[14px] text-[#2e3640] uppercase">ERTANGI VAZIFALAR</div><div class="text-[13px] text-[#92989b]">${tomorrowList.length} ta vazifa</div></div><div class="flex-1 flex flex-col gap-2.5 overflow-y-auto custom-scrollbar">${renderColCards(tomorrowList, false)}</div></div><div class="w-[330px] min-w-[330px] flex flex-col h-full"><div class="pb-2 mb-2.5 text-center border-b-[3px] border-[#94a3b8]"><div class="font-bold text-[14px] text-[#2e3640] uppercase">KELGUSI HAFTA VAZIFALARI</div><div class="text-[13px] text-[#92989b]">${futureList.length} ta vazifa</div></div><div class="flex-1 flex flex-col gap-2.5 overflow-y-auto custom-scrollbar">${renderColCards(futureList, false)}</div></div></div>`;
}

async function createNewCrmTask() {
  const title = document.getElementById("newTaskTitle")?.value.trim() || "Mijoz bilan qayta bog'lanish va KP yuborish";
  const leadId = leadsQueue[0]?.id || 1;
  await fetch("/api/crm/dialer/tasks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lead_id: leadId, title, task_type: "Bog'lanish" }),
  });
  showToast("Vazifa qo'shildi!");
  await renderTasksView();
}

async function completeCrmTask(taskId) {
  await fetch(`/api/crm/dialer/tasks/${taskId}/complete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ result_text: "Bajarildi" }),
  });
  showToast("Vazifa bajarildi!");
  await renderTasksView();
}

// 7-BO'LIM: AI-AGENTLAR VA BOTLAR (1:1 AMOCRM AGENTS-AND-BOTS)
function renderAiBotsView() {
  const box = document.getElementById("aibotsView");
  if (!box) return;
  box.innerHTML = `
    <div class="max-w-6xl mx-auto flex flex-col gap-5"><div class="flex items-center justify-between bg-white p-4 rounded border border-[#e5e7eb]"><h2 class="text-[16px] font-bold uppercase tracking-wider text-[#2e3640]">AI-AGENTLAR VA BOTLAR</h2><button onclick="showToast('Yangi Oisha AI Salesbot ishga tushirildi!')" class="bg-[#4c8bf7] text-white text-[13px] font-bold uppercase px-4 py-2 rounded">+ AGENT YARATISH</button></div><div class="grid grid-cols-1 lg:grid-cols-2 gap-4"><div class="bg-white p-5 rounded border border-[#e5e7eb] flex items-center justify-between gap-4 shadow-sm"><div><span class="text-[12px] font-bold uppercase bg-[#eff6ff] text-[#4c8bf7] px-2.5 py-0.5 rounded">Sotuv AI Agenti</span><h3 class="text-[19px] font-bold text-[#2e3640] mt-2">Oisha AI — Sotuv va Kvalifikatsiya Agenti</h3><p class="text-[14px] text-[#64748b] mt-1">Telegram, Instagram va IP-telefoniya muloqotlarini BANT/SPIN bo'yicha tahlil qiladi va saqlaydi.</p><div class="flex items-center gap-4 mt-3 text-[14px]"><span>Faol suhbatlar: <strong class="text-[#16a34a]">553</strong></span><span>Konversiya: <strong class="text-[#4c8bf7]">31.4%</strong></span></div></div><div class="w-16 h-16 rounded-full bg-gradient-to-tr from-[#3875d7] to-[#00bcd4] flex items-center justify-center shrink-0"><svg class="w-8 h-8 text-white" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24"><rect x="4" y="6" width="16" height="12" rx="3"/><circle cx="9" cy="12" r="1.5"/><circle cx="15" cy="12" r="1.5"/><path d="M12 2v4m-5 12v2m10-2v2"/></svg></div></div><div class="bg-white p-5 rounded border border-[#e5e7eb] flex flex-col justify-between shadow-sm"><div><div class="text-[13px] font-bold uppercase text-[#92989b]">TOKENLAR VA AI QUROLI SARFI</div><div class="text-2xl font-bold text-[#2e3640] mt-2">142,800 <span class="text-[13px] font-normal text-[#92989b]">/ 1,000,000 token</span></div><div class="h-2.5 w-full bg-[#f0f3f6] rounded-full overflow-hidden my-3"><div class="h-full bg-[#22c55e] w-[15%]"></div></div></div><div class="text-[14px] text-[#64748b]">Dvigatel: Gemini 2.0 Flash + Whisper STT + Avtomatlashtirish</div></div></div><div class="bg-white rounded border border-[#e5e7eb] overflow-hidden shadow-sm"><div class="p-4 border-b border-[#e5e7eb] font-bold text-[14px] uppercase text-[#2e3640]">Salesbotlar ro'yxati</div><table class="w-full text-left text-[14px]"><thead class="bg-[#f8fafc] border-b border-[#e5e7eb] text-[13px] text-[#92989b] uppercase"><tr><th class="p-3.5">Nomi</th><th class="p-3.5">Triggerlar</th><th class="p-3.5">Konversiya</th><th class="p-3.5">Ishga tushishlar</th><th class="p-3.5">Holat</th></tr></thead><tbody><tr class="border-b border-[#f0f3f6]"><td class="p-3.5 font-bold text-[#1565c0]">Oisha Lead Qualifier Bot</td><td class="p-3.5">Yangi lid kelganda (Telegram/Meta)</td><td class="p-3.5 font-bold text-[#16a34a]">68%</td><td class="p-3.5">1,240</td><td class="p-3.5"><span class="px-2.5 py-0.5 rounded bg-[#dcfce7] text-[#15803d] font-bold">Faol</span></td></tr><tr class="border-b border-[#f0f3f6]"><td class="p-3.5 font-bold text-[#1565c0]">Moizvonki STT & SPIN Coach</td><td class="p-3.5">Qo'ng'iroq yakunlanganda</td><td class="p-3.5 font-bold text-[#16a34a]">84%</td><td class="p-3.5">553</td><td class="p-3.5"><span class="px-2.5 py-0.5 rounded bg-[#dcfce7] text-[#15803d] font-bold">Faol</span></td></tr><tr><td class="p-3.5 font-bold text-[#1565c0]">NPS va Xizmat Baholash Boti</td><td class="p-3.5">Bitim muvaffaqiyatli yopilganda</td><td class="p-3.5 font-bold text-[#16a34a]">91%</td><td class="p-3.5">169</td><td class="p-3.5"><span class="px-2.5 py-0.5 rounded bg-[#dcfce7] text-[#15803d] font-bold">Faol</span></td></tr></tbody></table></div></div>`;
}

// 8-BO'LIM: RO'YXATLAR — KONTAKTLAR VA KOMPANIYALAR (1:1 AMOCRM CONTACTS TABLE)
async function renderDirectoryView(mode) {
  if (mode) directoryMode = mode;
  const box = document.getElementById("directoryView");
  if (!box) return;
  const res = await fetch(`/api/crm/dialer/directory?entity_type=${directoryMode}&q=${encodeURIComponent(currentSearchQuery)}`);
  const data = await res.json();
  const rows = (data.items || [])
    .map((item) =>
      directoryMode === "companies"
        ? `<tr onclick="openDealDrawer(${item.last_lead_id})" class="border-b border-[#eef2f5] hover:bg-[#f8fafc] cursor-pointer text-[14px]"><td class="p-3.5 w-8"><input type="checkbox" onclick="event.stopPropagation()"></td><td class="p-3.5 font-semibold text-[#1565c0] hover:underline">${item.company_name}</td><td class="p-3.5 text-[#2e3640] underline">${item.contact_name || "—"}</td><td class="p-3.5 font-mono text-[#2e3640]">${formatPhone(item.phone)}</td><td class="p-3.5 text-[#64748b]">${item.industry} (${item.deals_count} bitim)</td></tr>`
        : `<tr onclick="openDealDrawer(${item.last_lead_id})" class="border-b border-[#eef2f5] hover:bg-[#f8fafc] cursor-pointer text-[14px]"><td class="p-3.5 w-8"><input type="checkbox" onclick="event.stopPropagation()"></td><td class="p-3.5 font-semibold text-[#1565c0] hover:underline">${item.contact_name}</td><td class="p-3.5 text-[#2e3640] underline">${item.company_name || "—"}</td><td class="p-3.5 font-mono text-[#2e3640]">${formatPhone(item.phone)}</td><td class="p-3.5"><span class="text-xs font-semibold px-2 py-0.5 rounded bg-[#f0f9ff] text-[#0284c7]"><svg class="w-3.5 h-3.5 inline-block text-sky-500 mr-1" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z"/></svg>${item.source || "Telegram / Direct"}</span></td></tr>`
    )
    .join("");

  box.innerHTML = `
    <div class="h-[64px] bg-white border-b border-[#e5e7eb] px-5 flex items-center justify-between shrink-0"><div class="flex items-center gap-5"><button onclick="renderDirectoryView('contacts')" class="text-[15px] font-bold uppercase ${directoryMode === "contacts" ? "text-[#2e3640] border-b-2 border-[#4c8bf7] py-4" : "text-[#92989b]"}">KONTAKTLAR</button><button onclick="renderDirectoryView('companies')" class="text-[15px] font-bold uppercase ${directoryMode === "companies" ? "text-[#2e3640] border-b-2 border-[#4c8bf7] py-4" : "text-[#92989b]"}">KOMPANIYALAR</button></div><div class="flex items-center gap-3.5"><span class="text-[14px] text-[#92989b]"><strong>${data.total || 0}</strong> ta kontakt</span><button onclick="openNewDealModal()" class="bg-[#4c8bf7] text-white text-[13px] font-bold uppercase px-4 py-2.5 rounded">+ KONTAKT QO'SHISH</button></div></div><div class="flex-1 p-4 overflow-y-auto custom-scrollbar"><div class="bg-white rounded border border-[#e5e7eb] overflow-hidden shadow-sm"><table class="w-full text-left"><thead class="bg-[#f8fafc] border-b border-[#e5e7eb] text-[13px] font-bold text-[#92989b] uppercase"><tr><th class="p-3.5 w-8"><input type="checkbox"></th><th class="p-3.5">NOMI (F.I.SH)</th><th class="p-3.5">KOMPANIYA</th><th class="p-3.5">TELEFON</th><th class="p-3.5">TELEGRAM / DIRECT</th></tr></thead><tbody>${rows}</tbody></table></div></div>`;
}

// 9-BO'LIM: TELEGRAM VA INSTAGRAM TAKLIFLAR / KP
function renderMailView() {
  const box = document.getElementById("mailView");
  if (!box) return;
  box.innerHTML = `
    <div class="h-[64px] bg-white border-b border-[#e5e7eb] px-5 flex items-center justify-between"><span class="font-bold text-[15px] uppercase text-[#2e3640]">TELEGRAM VA INSTAGRAM TAKLIFLAR / KP</span><button onclick="showToast('Tijoriy Taklif Telegram orqali yuboriladi')" class="bg-[#0284c7] hover:bg-[#0369a1] text-white text-[13px] font-bold px-4 py-2 rounded flex items-center gap-1.5"><span>Yangi taklif</span><svg class="w-3.5 h-3.5 text-white" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z"/></svg></button></div><div class="p-6 text-[15px] text-[#64748b] leading-relaxed"><b>O'zbekiston Savdo Standarti:</b> Barcha Tijoriy Takliflar (KP), briflar va shartnomalar to'g'ridan-to'g'ri mijozning <b>Telegram</b> yoki <b>Instagram Direct</b>iga yuboriladi va sdelka kartochkasida saqlanadi.</div>`;
}

// 10-BO'LIM: ANALITIKA (amoCRM Enterprise — Plan-Fakt, Velocity, Rad Sabablari, Lenta)
async function renderAnalyticsView(sub) {
  if (sub) analyticsSubSection = sub;
  const box = document.getElementById("analyticsView");
  if (!box) return;

  let mainContent = "";
  if (analyticsSubSection === "summary" || analyticsSubSection === "reps") {
    const res = await fetch("/api/crm/dialer/targets/overview");
    const d = await res.json();
    const tot = d.totals || {};
    const sellersRows = (d.sellers || []).map((s) => `
      <tr class="border-b border-[#eef2f5] text-[14px]"><td class="p-3.5 font-bold text-[#1565c0]">${s.seller_name}</td><td class="p-3.5 text-right font-bold">${Number(s.target_revenue).toLocaleString("uz-UZ")} so'm</td><td class="p-3.5 text-right font-bold text-[#16a34a]">${Number(s.fact_revenue).toLocaleString("uz-UZ")} so'm</td><td class="p-3.5 text-right font-bold"><span class="px-2 py-0.5 rounded ${s.completion_pct >= 80 ? "bg-[#dcfce7] text-[#15803d]" : "bg-[#fef3c7] text-[#b45309]"}">${s.completion_pct}%</span></td><td class="p-3.5 text-right font-mono text-[#4c8bf7]">${Number(s.forecast_revenue).toLocaleString("uz-UZ")} so'm</td><td class="p-3.5 text-right text-[#ef4444] font-semibold">${Number(s.daily_pace_required).toLocaleString("uz-UZ")} so'm/kun</td></tr>`).join("");

    mainContent = `
      <div class="flex flex-col gap-4"><div class="grid grid-cols-1 md:grid-cols-4 gap-3"><div class="bg-white p-4 rounded border border-[#e5e7eb] shadow-sm"><span class="text-xs uppercase text-[#64748b] font-bold">Oylik Reja</span><div class="text-2xl font-bold mt-1 text-[#2e3640]">${Number(tot.target_revenue || 0).toLocaleString("uz-UZ")} so'm</div></div><div class="bg-white p-4 rounded border border-[#e5e7eb] shadow-sm"><span class="text-xs uppercase text-[#64748b] font-bold">Amaldagi Fakt</span><div class="text-2xl font-bold mt-1 text-[#16a34a]">${Number(tot.fact_revenue || 0).toLocaleString("uz-UZ")} so'm (${tot.completion_pct}%)</div></div><div class="bg-white p-4 rounded border border-[#e5e7eb] shadow-sm"><span class="text-xs uppercase text-[#64748b] font-bold">Kassa Bashorati (Forecast)</span><div class="text-2xl font-bold mt-1 text-[#0284c7]">${Number(tot.forecast_revenue || 0).toLocaleString("uz-UZ")} so'm</div></div><div class="bg-white p-4 rounded border border-[#e5e7eb] shadow-sm"><span class="text-xs uppercase text-[#64748b] font-bold">Kunlik Kerakli Sur'at</span><div class="text-2xl font-bold mt-1 text-[#ef4444]">${Number(tot.daily_pace_required || 0).toLocaleString("uz-UZ")} so'm</div></div></div><div class="bg-white rounded border border-[#e5e7eb] shadow-sm overflow-hidden"><div class="p-4 border-b border-[#e5e7eb] font-bold text-[15px] uppercase text-[#2e3640]">Xodimlar bo'yicha Plan-Fakt va Bashorat</div><table class="w-full text-left"><thead class="bg-[#f8fafc] border-b border-[#e5e7eb] text-xs font-bold text-[#92989b] uppercase"><tr><th class="p-3.5">Menejer</th><th class="p-3.5 text-right">Reja</th><th class="p-3.5 text-right">Fakt</th><th class="p-3.5 text-right">%</th><th class="p-3.5 text-right">Bashorat</th><th class="p-3.5 text-right">Kunlik Sur'at</th></tr></thead><tbody>${sellersRows}</tbody></table></div></div>`;
  } else if (analyticsSubSection === "losses") {
    const res = await fetch("/api/crm/dialer/loss-analytics");
    const d = await res.json();
    const lr = d.loss_reasons || {};
    const vel = d.cycle_time_velocity || {};
    const reasonsRows = (lr.reasons || []).map((r) => `
      <div class="flex items-center justify-between p-3 border-b border-[#eef2f5] text-sm"><span class="font-semibold text-[#2e3640]">${r.reason}</span><div class="flex items-center gap-4"><span class="font-bold text-[#ef4444]">${r.count} ta (${r.share_pct}%)</span><span class="font-bold text-[#64748b]">${Number(r.total_lost_uzs).toLocaleString("uz-UZ")} so'm</span></div></div>`).join("");

    mainContent = `
      <div class="flex flex-col gap-4"><div class="bg-white p-5 rounded border border-[#e5e7eb] shadow-sm"><div class="font-bold text-[15px] uppercase text-[#2e3640] border-b border-[#f0f3f6] pb-2">Rad Etish Sabablari Tahlili (${lr.total_lost_deals || 0} ta bitim, ${Number(lr.total_lost_amount_uzs || 0).toLocaleString("uz-UZ")} so'm yo'qotilgan)</div><div class="mt-3 flex flex-col">${reasonsRows}</div></div><div class="bg-white p-5 rounded border border-[#e5e7eb] shadow-sm"><div class="font-bold text-[15px] uppercase text-[#2e3640] border-b border-[#f0f3f6] pb-2">Konversiya Tezligi va Tiqilishlar (O'rtacha hayot davri: ${vel.avg_cycle_days_total || 12} kun)</div><div class="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-3">${(vel.stages_velocity || []).map((s) => `<div class="p-3 rounded bg-[#f8fafc] border border-[#e2e8f0]"><div class="text-xs text-[#64748b] truncate">${s.stage_title}</div><div class="text-xl font-bold mt-1 text-[#2e3640]">${s.avg_days} kun</div><div class="text-xs font-semibold mt-0.5 ${s.status.includes("Tiqilish") ? "text-[#ef4444]" : "text-[#16a34a]"}">${s.status}</div></div>`).join("")}</div></div></div>`;
  } else if (analyticsSubSection === "events") {
    const res = await fetch("/api/crm/dialer/events");
    const evData = await res.json();
    const evRows = (evData.events || []).map((e) => `
      <tr onclick="openDealDrawer(${e.lead_id})" class="border-b border-[#eef2f5] hover:bg-[#f8fafc] cursor-pointer text-[14px]"><td class="p-3 text-[#64748b]">${e.date}</td><td class="p-3 font-semibold text-[#2e3640]">${e.author}</td><td class="p-3 text-[#1565c0] font-bold hover:underline">${e.object_name}</td><td class="p-3">${e.event_name}</td><td class="p-3"><span class="px-2 py-0.5 rounded bg-[#fef3c7] text-[#b45309] text-xs">${e.before_val}</span> → <span class="px-2 py-0.5 rounded bg-[#dbeafe] text-[#1d4ed8] text-xs font-bold">${e.after_val}</span></td></tr>`).join("");
    mainContent = `<div class="bg-white rounded border border-[#e5e7eb] overflow-hidden shadow-sm"><table class="w-full text-left"><thead class="bg-[#f8fafc] border-b border-[#e5e7eb] text-xs font-bold text-[#92989b] uppercase"><tr><th class="p-3">SANA</th><th class="p-3">MUALLIF</th><th class="p-3">OBYEKT</th><th class="p-3">HODISA</th><th class="p-3">O'ZGARISH</th></tr></thead><tbody>${evRows}</tbody></table></div>`;
  } else {
    const res = await fetch(`/api/crm/dialer/dashboard?pipeline_id=${currentPipelineId}`);
    const d = await res.json();
    const fRows = (d.funnel || []).map((f) => `<div class="flex items-center gap-3.5 text-sm py-2"><div class="w-56 font-semibold text-[#2e3640] truncate">${f.title}</div><div class="flex-1 bg-[#f0f3f6] h-7 rounded overflow-hidden"><div class="h-full flex items-center px-3 text-xs font-bold text-[#2e3640]" style="width:${Math.min(100, Math.max(12, f.count * 2))}%; background:${f.color}">${f.count} ta bitim</div></div><div class="w-40 text-right font-bold text-[#2e3640]">${Number(f.sum || 0).toLocaleString("uz-UZ")} so'm</div></div>`).join("");
    mainContent = `<div class="bg-white p-5 rounded border border-[#e5e7eb] shadow-sm flex flex-col gap-3"><div class="font-bold text-[15px] uppercase text-[#2e3640] border-b border-[#f0f3f6] pb-2.5">SOTUV VORONKASI TAHLILI (KONVERSIYA)</div>${fRows}</div>`;
  }

  box.innerHTML = `
    <div class="w-[240px] min-w-[240px] bg-white border-r border-[#e5e7eb] flex flex-col h-full py-4"><div class="px-4 pb-3 font-bold text-[13px] uppercase tracking-wider text-[#92989b]">ANALITIKA (ENTERPRISE)</div><button onclick="renderAnalyticsView('funnel')" class="text-left px-4 py-2.5 text-[14px] font-semibold ${analyticsSubSection === "funnel" ? "text-[#4c8bf7] bg-[#eff6ff]" : "text-[#2e3640] hover:bg-[#f8fafc]"}">Sotuv voronkasi</button><button onclick="renderAnalyticsView('summary')" class="text-left px-4 py-2.5 text-[14px] font-semibold ${analyticsSubSection === "summary" ? "text-[#4c8bf7] bg-[#eff6ff]" : "text-[#2e3640] hover:bg-[#f8fafc]"}">Plan-Fakt & Forecast</button><button onclick="renderAnalyticsView('losses')" class="text-left px-4 py-2.5 text-[14px] font-semibold ${analyticsSubSection === "losses" ? "text-[#4c8bf7] bg-[#eff6ff]" : "text-[#2e3640] hover:bg-[#f8fafc]"}">Rad etish sabablari</button><button onclick="renderAnalyticsView('events')" class="text-left px-4 py-2.5 text-[14px] font-semibold ${analyticsSubSection === "events" ? "text-[#4c8bf7] bg-[#eff6ff]" : "text-[#2e3640] hover:bg-[#f8fafc]"}">Hodisalar oqimi (Audit)</button></div><div class="flex-1 p-5 overflow-y-auto custom-scrollbar">${mainContent}</div>`;
}

// 11-BO'LIM: SOZLAMALAR (amoCRM Enterprise — Raqamli Voronka, RBAC & SaaS)
async function renderSettingsView(sub) {
  if (sub) settingsSubSection = sub;
  const box = document.getElementById("settingsView");
  if (!box) return;

  let mainBody = "";
  if (settingsSubSection === "automation") {
    const res = await fetch(`/api/crm/dialer/digital-pipeline/rules?pipeline_id=${currentPipelineId}`);
    const d = await res.json();
    const rulesRows = (d.rules || []).map((r) => `
      <div class="p-4 bg-white rounded border border-[#e5e7eb] shadow-sm flex items-center justify-between"><div class="flex items-center gap-3"><svg class="w-5 h-5 text-amber-500 inline-block" fill="currentColor" viewBox="0 0 24 24"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg><div><div class="font-bold text-sm text-[#2e3640]">${r.name}</div><div class="text-xs text-[#64748b] mt-0.5">Bosqich: <b class="text-[#0284c7] uppercase">${r.stage_slug}</b> • Amal: <b class="text-[#16a34a]">${r.action_type}</b></div></div></div><span class="px-3 py-1 rounded text-xs font-bold ${r.is_active ? "bg-[#dcfce7] text-[#15803d]" : "bg-[#f1f5f9] text-[#94a3b8]"}">${r.is_active ? "Faol (Active)" : "O'chiq"}</span></div>`).join("");
    mainBody = `<div class="flex flex-col gap-3"><div class="font-bold text-base uppercase text-[#2e3640]">Raqamli Voronka Avtomatlashtirish Qoidalari (Digital Pipeline)</div>${rulesRows}</div>`;
  } else {
    const res = await fetch("/api/crm/dialer/rbac/users");
    const d = await res.json();
    const rows = (d.users || []).map((u) => `
      <tr class="border-b border-[#eef2f5] text-sm"><td class="p-3.5 font-bold text-[#1565c0]">${u.name}</td><td class="p-3.5"><span class="px-2.5 py-0.5 rounded text-xs font-bold ${u.role === "admin" ? "bg-[#fef3c7] text-[#b45309]" : "bg-[#dbeafe] text-[#1d4ed8]"}">${u.role_title}</span></td><td class="p-3.5 text-[#64748b]">${u.email}</td><td class="p-3.5 text-xs text-[#16a34a] font-semibold">${u.permissions?.delete_leads ? "To'liq ruxsat (Admin)" : "Cheklangan (Faqat o'z sdelkasi)"}</td></tr>`).join("");
    mainBody = `<div class="bg-white rounded border border-[#e5e7eb] overflow-hidden shadow-sm"><div class="p-4 border-b border-[#e5e7eb] font-bold text-base uppercase text-[#2e3640]">Foydalanuvchilar va RBAC Huquqlar Matrisasi</div><table class="w-full text-left"><thead class="bg-[#f8fafc] border-b border-[#e5e7eb] text-xs font-bold text-[#92989b] uppercase"><tr><th class="p-3.5">Xodim</th><th class="p-3.5">Rol</th><th class="p-3.5">Email</th><th class="p-3.5">Ruxsat darajasi</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  }

  box.innerHTML = `
    <div class="w-[240px] min-w-[240px] bg-white border-r border-[#e5e7eb] flex flex-col h-full py-4"><div class="px-4 pb-3 font-bold text-xs uppercase tracking-wider text-[#92989b]">SOZLAMALAR (ENTERPRISE)</div><button onclick="renderSettingsView('automation')" class="text-left px-4 py-2.5 text-sm font-semibold ${settingsSubSection === "automation" ? "text-[#4c8bf7] bg-[#eff6ff]" : "text-[#2e3640] hover:bg-[#f8fafc]"} flex items-center gap-2"><svg class="w-4 h-4 text-amber-500" fill="currentColor" viewBox="0 0 24 24"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg><span>Raqamli Voronka</span></button><button onclick="renderSettingsView('users')" class="text-left px-4 py-2.5 text-sm font-semibold ${settingsSubSection === "users" ? "text-[#4c8bf7] bg-[#eff6ff]" : "text-[#2e3640] hover:bg-[#f8fafc]"} flex items-center gap-2"><svg class="w-4 h-4 text-[#7e8b9b]" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"/></svg><span>Xodimlar & RBAC</span></button></div><div class="flex-1 p-5 overflow-y-auto custom-scrollbar flex flex-col gap-4">${mainBody}</div>`;
}

// 12-BO'LIM: RAD ETISH SABABI MODALI (amoCRM Enterprise Mandatory Closed-Lost Prompt)
let activeLossLead = null;

function openLossModal(leadId, targetSlug, stageTitle, leadPrice, leadName) {
  activeLossLead = { leadId, targetSlug, stageTitle, leadPrice: leadPrice || 0, leadName: leadName || `Bitim #${leadId}` };
  let modal = document.getElementById("lossReasonModal");
  if (!modal) {
    modal = document.createElement("div");
    modal.id = "lossReasonModal";
    modal.className = "fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4 backdrop-blur-sm";
    modal.innerHTML = `
      <div class="bg-white rounded-xl shadow-2xl max-w-md w-full overflow-hidden border border-[#e5e7eb]"><div class="bg-[#ef4444] px-5 py-3 text-white flex items-center justify-between"><div class="font-bold text-sm flex items-center gap-2"><svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg><span>Rad Etish Sababi (Majburiy)</span></div><button onclick="closeLossModal()" class="text-white/80 hover:text-white text-base">✕</button></div><div class="p-4 flex flex-col gap-3"><div><div id="lossModalLeadName" class="font-bold text-[#2e3640] text-sm truncate">Bitim</div><div id="lossModalLeadPrice" class="text-xs text-[#ef4444] font-semibold mt-0.5">0 so'm</div></div><div class="flex flex-col gap-1"><label class="text-xs font-bold uppercase text-[#64748b]">Sababni tanlang *</label><select id="lossReasonSelect" class="border border-[#d8dde3] rounded p-2 text-xs focus:outline-none focus:border-[#ef4444]"><option value="Qimmat / Byudjet yetmadi">Qimmat / Byudjet yetmadi</option><option value="Raqobatchiga ketdi">Raqobatchiga ketdi</option><option value="Hozir ehtiyoj yo'q (keyinroq)">Hozir ehtiyoj yo'q (keyinroq)</option><option value="Aloqaga chiqmadi (o'chiq / javob bermadi)">Aloqaga chiqmadi (o'chiq / javob bermadi)</option><option value="Soxta lid / Spam">Soxta lid / Spam</option></select></div><div class="flex flex-col gap-1"><label class="text-xs font-bold uppercase text-[#64748b]">Batafsil izoh</label><textarea id="lossReasonNote" rows="2" placeholder="Rad etilish tafsiloti..." class="border border-[#d8dde3] rounded p-2 text-xs focus:outline-none"></textarea></div><div class="flex items-center justify-end gap-2 pt-2 border-t border-[#f0f3f6]"><button onclick="closeLossModal()" class="px-3 py-1.5 rounded text-xs font-semibold text-[#64748b] hover:bg-[#f1f5f9]">Bekor qilish</button><button onclick="submitLossReason()" class="px-4 py-1.5 rounded text-xs font-bold bg-[#ef4444] hover:bg-[#dc2626] text-white">Yopish</button></div></div></div>`;
    document.body.appendChild(modal);
  }
  document.getElementById("lossModalLeadName").innerText = activeLossLead.leadName;
  document.getElementById("lossModalLeadPrice").innerText = `Yo'qotilgan summa: ${Number(activeLossLead.leadPrice).toLocaleString("uz-UZ")} so'm`;
  modal.classList.remove("hidden");
}

function closeLossModal() {
  const modal = document.getElementById("lossReasonModal");
  if (modal) modal.classList.add("hidden");
  activeLossLead = null;
}

async function submitLossReason() {
  if (!activeLossLead) return;
  const reason = document.getElementById("lossReasonSelect")?.value || "Qimmat / Byudjet yetmadi";
  const note = document.getElementById("lossReasonNote")?.value.trim() || "";
  const leadId = activeLossLead.leadId;
  const lostAmount = activeLossLead.leadPrice;
  closeLossModal();

  showToast("Rad etish sababi saqlanmoqda...");
  try {
    const seller = window.currentCrmSeller?.name || "Shahnoza Abdijabborova";
    await fetch(`/api/crm/dialer/lead/${leadId}/loss`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason, note, lost_amount: lostAmount, seller_name: seller }),
    });
    await fetch("/api/crm/dialer/action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        lead_id: leadId, action_slug: "rad", pipeline_id: currentPipelineId,
        seller_name: seller, note: `Rad etildi: ${reason}. ${note}`,
      }),
    });
    showToast("Bitim rad etilgan deb qayd etildi!");
    if (typeof fetchKanban === "function") await fetchKanban();
  } catch (err) {
    showToast("Rad etishda xatolik yuz berdi");
  }
}
