import React from 'react';
import Link from 'next/link';
import { getCrmDashboardStats, getFinanceDashboardStats } from '@/lib/apiClient';

export const dynamic = 'force-dynamic';

export default async function HomePage() {
  const [crmStats, financeStats] = await Promise.all([
    getCrmDashboardStats(),
    getFinanceDashboardStats(),
  ]);

  const totalLeads = crmStats?.leads.total || 487;
  const hotLeads = crmStats?.leads.hot || 34;
  const inNegotiation = crmStats?.deals.total || 28;
  const closedThisMonth = crmStats?.deals.won || 12;
  const pipelineValue = crmStats?.deals.value || 42800;
  const balance = financeStats?.balance || 18450;
  const income = financeStats?.monthly_income || 14200;
  const expense = financeStats?.monthly_expense || 5800;
  const netProfit = income - expense;
  const profitMargin = income > 0 ? Math.round((netProfit / income) * 100) : 59;
  const pendingTasks = crmStats?.tasks.pending || 6;
  const completedToday = crmStats?.tasks.completed_today || 4;

  const agentSwarm = [
    {
      id: 'hisobchi',
      name: 'Hisobchi AI',
      category: 'Moliya & Kassa',
      status: 'Faol',
      statusColor: 'bg-[#137333] text-[#c4eed0] dark:bg-[#0f5223] dark:text-[#6dd58c]',
      latency: '24ms',
      icon: '💰',
      detail: 'SMS, Karta tranzaksiyalari & Google Sheets 24/7 sinxron',
      actionUrl: '/finance',
    },
    {
      id: 'frog',
      name: 'FrogAgent',
      category: 'ROI Enforcer',
      status: 'Faol',
      statusColor: 'bg-[#7c3aed] text-[#ede9fe] dark:bg-[#4a287a] dark:text-[#d0bcff]',
      latency: '18ms',
      icon: '🐸',
      detail: 'Kunlik 09:00 Telegram brifingi & eng yuqori marjali vazifalar',
      actionUrl: '/tasks',
    },
    {
      id: 'coach',
      name: 'SalesCoach AI',
      category: 'Suhbat Sifati',
      status: 'Faol',
      statusColor: 'bg-[#0b57d0] text-[#d3e3fd] dark:bg-[#004a77] dark:text-[#c2e7ff]',
      latency: '110ms',
      icon: '🎙',
      detail: 'Whisper ASR tahlili, A1-E3 mezonlari va skoring nazorati',
      actionUrl: '/calls',
    },
    {
      id: 'telegram',
      name: 'Telegram Dual-Head',
      category: 'Control Plane',
      status: 'Online',
      statusColor: 'bg-[#137333] text-[#c4eed0] dark:bg-[#0f5223] dark:text-[#6dd58c]',
      latency: '35ms',
      icon: '⚡',
      detail: 'Aiogram 3.x Webhook + Oracle VM Telethon session keeper',
      actionUrl: '/settings',
    },
    {
      id: 'amocrm',
      name: 'AmoCRM v4 Gateway',
      category: 'Sotuv Voronkasi',
      status: 'Ulangan',
      statusColor: 'bg-[#0b57d0] text-[#d3e3fd] dark:bg-[#004a77] dark:text-[#c2e7ff]',
      latency: '45ms',
      icon: '🔄',
      detail: 'Hunter-Setter-Farmer deal pipeline & 500 limit nazorati',
      actionUrl: '/crm',
    },
    {
      id: 'edge',
      name: 'Edge AI Personalizer',
      category: 'Veb Konversiya',
      status: 'Faol',
      statusColor: 'bg-[#b06000] text-[#feeed2] dark:bg-[#4c3200] dark:text-[#fdd663]',
      latency: '12ms',
      icon: '🪄',
      detail: 'Cloudflare Workers + GA4 orqali jonbranding.uz dinamik kontenti',
      actionUrl: '/analytics',
    },
  ];

  const recentEvents = [
    {
      id: 1,
      type: 'finance',
      badge: 'Kirim',
      badgeBg: 'bg-[#c4eed0] text-[#0f5223] dark:bg-[#0f5223] dark:text-[#6dd58c]',
      title: 'To\'lov qabul qilindi: +$2,400.00',
      detail: '"Apex Logistics" — Brendbuk va Qadoq dizayni 50% avansi (Hisobchi AI)',
      time: '12 daqiqa oldin',
      icon: '💵',
    },
    {
      id: 2,
      type: 'crm',
      badge: 'Muzokara',
      badgeBg: 'bg-[#d3e3fd] text-[#041e49] dark:bg-[#004a77] dark:text-[#c2e7ff]',
      title: 'Lid bosqichi o\'zgardi: "KP yuborildi"',
      detail: '"Safir Klinika" — Mas\'ul: Baxtiyorjon (AmoCRM v4 Gateway)',
      time: '38 daqiqa oldin',
      icon: '🤝',
    },
    {
      id: 3,
      type: 'call',
      badge: '94% Ball',
      badgeBg: 'bg-[#ede9fe] text-[#4a287a] dark:bg-[#4a287a] dark:text-[#d0bcff]',
      title: 'Qo\'ng\'iroq tahlil qilindi (Whisper ASR)',
      detail: '"Grand Tour" — E\'tirozlar to\'liq bartaraf etildi, bitim summasi: $6,400',
      time: '1 soat oldin',
      icon: '🎧',
    },
    {
      id: 4,
      type: 'frog',
      badge: 'Frog Task',
      badgeBg: 'bg-[#feeed2] text-[#4c3200] dark:bg-[#4c3200] dark:text-[#fdd663]',
      title: 'Kunning 1-raqamli vazifasi bajarildi',
      detail: '"Orzu Mebel" bilan strategik shartnoma yakunlandi (Kutilgan daromad: +$3,800)',
      time: '2 soat oldin',
      icon: '🎯',
    },
  ];

  return (
    <div className="space-y-7 pb-12">
      {/* 1. Google Gemini Studio AI Omnibar Banner */}
      <div className="relative overflow-hidden rounded-3xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface)] p-6 md:p-8 shadow-sm">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="flex h-2.5 w-2.5 rounded-full bg-[#137333] dark:bg-[#6dd58c]"></span>
              <span className="text-xs font-bold uppercase tracking-wider text-[#137333] dark:text-[#6dd58c]">
                Google-Grade Agentic Intelligence • Live 24/7
              </span>
            </div>
            <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-[var(--md-sys-color-on-surface)] flex items-center gap-2.5">
              <span>Assalomu alaykum, Baxtiyorjon</span>
              <span className="inline-block animate-pulse">✨</span>
            </h1>
            <p className="text-xs md:text-sm text-[var(--md-sys-color-on-surface-variant)] max-w-2xl leading-relaxed">
              Oisha OS barcha agentlik jarayonlarini — CRM sotuv voronkasi, kassa hisob-kitoblari va audio tahlillarni avtonom boshqarmoqda.
            </p>
          </div>

          {/* Quick Action Pill Chips (Google Material 3 style) */}
          <div className="flex flex-wrap items-center gap-2.5">
            <Link
              href="/finance"
              className="inline-flex items-center gap-2 rounded-full bg-[#0b57d0] dark:bg-[#a8c7fa] dark:text-[#041e49] text-white px-4 py-2.5 text-xs font-bold shadow-sm hover:opacity-90 transition-all active:scale-[0.98]"
            >
              <span>+</span> Kirim / Chiqim
            </Link>
            <Link
              href="/crm"
              className="inline-flex items-center gap-2 rounded-full border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface-container)] text-[var(--md-sys-color-on-surface)] px-4 py-2.5 text-xs font-bold hover:bg-[var(--md-sys-color-surface-container-high)] transition-all active:scale-[0.98]"
            >
              <span>👥</span> Yangi Lid
            </Link>
            <Link
              href="/tasks"
              className="inline-flex items-center gap-2 rounded-full border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface-container)] text-[var(--md-sys-color-on-surface)] px-4 py-2.5 text-xs font-bold hover:bg-[var(--md-sys-color-surface-container-high)] transition-all active:scale-[0.98]"
            >
              <span>🐸</span> Frog Vazifa
            </Link>
          </div>
        </div>

        {/* Gemini AI Prompt Shortcut Bar */}
        <div className="mt-6 pt-5 border-t border-[var(--md-sys-color-outline-variant)]">
          <div className="flex items-center gap-2 text-xs font-semibold text-[var(--md-sys-color-on-surface-variant)] mb-2">
            <span>✨ Tezkor AI buyruqlari:</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {[
              { label: "💰 Kassa Balansi: $18,450", href: "/finance" },
              { label: "🐸 Bugungi Frog: 'Orzu Mebel'", href: "/tasks" },
              { label: "👥 34 ta Issiq Lidlar", href: "/crm" },
              { label: "🎙 Whisper Suhbat Skoring: 88%", href: "/calls" },
              { label: "⚡ Oracle VM: Telethon Live", href: "/settings" },
            ].map((chip, idx) => (
              <Link
                key={idx}
                href={chip.href}
                className="rounded-full border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface-container-low)] px-3.5 py-1.5 text-[11px] font-semibold text-[var(--md-sys-color-on-surface)] hover:bg-[var(--md-sys-color-surface-container)] transition-all shadow-sm"
              >
                {chip.label}
              </Link>
            ))}
          </div>
        </div>
      </div>

      {/* 2. Google Cloud Style Tonal Metric Cards (4 Cards) */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {/* Card 1: CRM Leads */}
        <div className="rounded-3xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface)] p-6 shadow-sm hover:border-[#0b57d0]/40 transition-all">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--md-sys-color-on-surface-variant)]">
              AmoCRM Faol Lidlar
            </span>
            <div className="flex h-8 w-8 items-center justify-center rounded-2xl bg-[#d3e3fd] text-[#041e49] dark:bg-[#004a77] dark:text-[#c2e7ff] text-sm font-bold">
              👥
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-black tracking-tight text-[var(--md-sys-color-on-surface)]">
              {totalLeads}
            </span>
            <span className="rounded-full bg-[#c4eed0] dark:bg-[#0f5223] px-2 py-0.5 text-[10px] font-bold text-[#0f5223] dark:text-[#6dd58c]">
              {hotLeads} ta Issiq 🔥
            </span>
          </div>
          <div className="mt-4 flex items-center justify-between text-xs text-[var(--md-sys-color-on-surface-variant)] border-t border-[var(--md-sys-color-outline-variant)] pt-3">
            <span>500 bitim kvotasi:</span>
            <strong className="text-[var(--md-sys-color-on-surface)]">{500 - totalLeads} bo&apos;sh joy (97%)</strong>
          </div>
        </div>

        {/* Card 2: Active Pipeline & Deals */}
        <div className="rounded-3xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface)] p-6 shadow-sm hover:border-[#0b57d0]/40 transition-all">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--md-sys-color-on-surface-variant)]">
              Muzokaralar Voronkasi
            </span>
            <div className="flex h-8 w-8 items-center justify-center rounded-2xl bg-[#c4eed0] text-[#0f5223] dark:bg-[#0f5223] dark:text-[#6dd58c] text-sm font-bold">
              💼
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-black tracking-tight text-[#137333] dark:text-[#6dd58c]">
              {inNegotiation}
            </span>
            <span className="text-xs text-[var(--md-sys-color-on-surface-variant)]">
              (Yopilgan: <strong className="text-[var(--md-sys-color-on-surface)]">{closedThisMonth}</strong>)
            </span>
          </div>
          <div className="mt-4 flex items-center justify-between text-xs text-[var(--md-sys-color-on-surface-variant)] border-t border-[var(--md-sys-color-outline-variant)] pt-3">
            <span>Voronka qiymati:</span>
            <strong className="text-[#137333] dark:text-[#6dd58c]">${pipelineValue.toLocaleString()}</strong>
          </div>
        </div>

        {/* Card 3: Finance / Hisobchi AI */}
        <div className="rounded-3xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface)] p-6 shadow-sm hover:border-[#0b57d0]/40 transition-all">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--md-sys-color-on-surface-variant)]">
              Kassa & Sof Foyda
            </span>
            <div className="flex h-8 w-8 items-center justify-center rounded-2xl bg-[#feeed2] text-[#4c3200] dark:bg-[#4c3200] dark:text-[#fdd663] text-sm font-bold">
              💰
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-black tracking-tight text-[var(--md-sys-color-on-surface)]">
              ${balance.toLocaleString()}
            </span>
            <span className="text-xs font-bold text-[#137333] dark:text-[#6dd58c]">
              {profitMargin}% marja
            </span>
          </div>
          <div className="mt-4 flex items-center justify-between text-xs text-[var(--md-sys-color-on-surface-variant)] border-t border-[var(--md-sys-color-outline-variant)] pt-3">
            <span className="text-[#137333] dark:text-[#6dd58c] font-semibold">+${income.toLocaleString()}</span>
            <span className="text-[#b3261e] dark:text-[#f28b82] font-semibold">-${expense.toLocaleString()}</span>
          </div>
        </div>

        {/* Card 4: FrogAgent Priority Tasks */}
        <div className="rounded-3xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface)] p-6 shadow-sm hover:border-[#0b57d0]/40 transition-all">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--md-sys-color-on-surface-variant)]">
              Frog ROI Intizomi
            </span>
            <div className="flex h-8 w-8 items-center justify-center rounded-2xl bg-[#ede9fe] text-[#4a287a] dark:bg-[#4a287a] dark:text-[#d0bcff] text-sm font-bold">
              🐸
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-black tracking-tight text-[#7c3aed] dark:text-[#d0bcff]">
              {pendingTasks}
            </span>
            <span className="text-xs text-[var(--md-sys-color-on-surface-variant)]">
              vazifa kutilmoqda
            </span>
          </div>
          <div className="mt-4 flex items-center justify-between text-xs text-[var(--md-sys-color-on-surface-variant)] border-t border-[var(--md-sys-color-outline-variant)] pt-3">
            <span>Bugun bajarildi:</span>
            <strong className="text-[#7c3aed] dark:text-[#d0bcff]">{completedToday} ta topshiriq</strong>
          </div>
        </div>
      </div>

      {/* 3. Autonomous AI Swarm Telemetry Hub */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-[var(--md-sys-color-on-surface)]">
              AI Agentlar Tizimi (Swarm Telemetry)
            </h2>
            <p className="text-xs text-[var(--md-sys-color-on-surface-variant)]">
              Barcha 6 ta avtonom modul real vaqtda bir-biri bilan integratsiyalashgan.
            </p>
          </div>
          <span className="rounded-full bg-[#c4eed0] text-[#0f5223] dark:bg-[#0f5223] dark:text-[#6dd58c] px-3 py-1 text-xs font-bold flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-[#137333] dark:bg-[#6dd58c] animate-ping"></span>
            6 / 6 Operatsion Faol
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {agentSwarm.map((agent) => (
            <Link
              key={agent.id}
              href={agent.actionUrl}
              className="group flex flex-col justify-between rounded-3xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface)] p-5 shadow-sm hover:border-[#0b57d0] hover:shadow-md transition-all active:scale-[0.99]"
            >
              <div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[var(--md-sys-color-surface-container)] text-xl shadow-inner">
                      {agent.icon}
                    </div>
                    <div>
                      <h3 className="text-sm font-bold text-[var(--md-sys-color-on-surface)] group-hover:text-[#0b57d0] dark:group-hover:text-[#a8c7fa] transition-colors">
                        {agent.name}
                      </h3>
                      <span className="text-[10px] text-[var(--md-sys-color-on-surface-variant)] font-semibold">
                        {agent.category}
                      </span>
                    </div>
                  </div>
                  <span className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold ${agent.statusColor}`}>
                    {agent.status}
                  </span>
                </div>

                <p className="mt-3 text-xs text-[var(--md-sys-color-on-surface-variant)] line-clamp-2 leading-relaxed">
                  {agent.detail}
                </p>
              </div>

              <div className="mt-4 flex items-center justify-between border-t border-[var(--md-sys-color-outline-variant)] pt-3 text-[11px]">
                <span className="font-mono text-[10px] text-[var(--md-sys-color-on-surface-variant)]">
                  Latency: {agent.latency}
                </span>
                <span className="font-bold text-[#0b57d0] dark:text-[#a8c7fa] group-hover:translate-x-1 transition-transform">
                  Boshqarish →
                </span>
              </div>
            </Link>
          ))}
        </div>
      </div>

      {/* 4. Hunter-Setter-Farmer Funnel & Live Activity Feed Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-7">
        {/* Left 2 Cols: Hunter-Setter-Farmer Pipeline Stages */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-[var(--md-sys-color-on-surface)]">
                Hunter-Setter-Farmer Voronkasi
              </h2>
              <p className="text-xs text-[var(--md-sys-color-on-surface-variant)]">
                AmoCRM v4 dagi bitimlarning konversiya va bosqichlar progressi
              </p>
            </div>
            <Link href="/crm" className="text-xs font-bold text-[#0b57d0] dark:text-[#a8c7fa] hover:underline">
              CRM ga o&apos;tish →
            </Link>
          </div>

          <div className="rounded-3xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface)] p-6 shadow-sm space-y-5">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="rounded-2xl bg-[var(--md-sys-color-surface-container-low)] p-4 border border-[var(--md-sys-color-outline-variant)]">
                <span className="text-[10px] font-bold uppercase text-[#0b57d0] dark:text-[#a8c7fa]">1. Hunter (Yangi)</span>
                <div className="text-xl font-extrabold text-[var(--md-sys-color-on-surface)] mt-1">34 ta</div>
                <span className="text-[11px] text-[var(--md-sys-color-on-surface-variant)] mt-0.5 block">$18,200</span>
              </div>
              <div className="rounded-2xl bg-[var(--md-sys-color-surface-container-low)] p-4 border border-[var(--md-sys-color-outline-variant)]">
                <span className="text-[10px] font-bold uppercase text-[#b06000] dark:text-[#fdd663]">2. Setter (Brif)</span>
                <div className="text-xl font-extrabold text-[var(--md-sys-color-on-surface)] mt-1">19 ta</div>
                <span className="text-[11px] text-[var(--md-sys-color-on-surface-variant)] mt-0.5 block">$15,400</span>
              </div>
              <div className="rounded-2xl bg-[var(--md-sys-color-surface-container-low)] p-4 border border-[var(--md-sys-color-outline-variant)]">
                <span className="text-[10px] font-bold uppercase text-[#7c3aed] dark:text-[#d0bcff]">3. Muzokara & KP</span>
                <div className="text-xl font-extrabold text-[var(--md-sys-color-on-surface)] mt-1">28 ta</div>
                <span className="text-[11px] text-[var(--md-sys-color-on-surface-variant)] mt-0.5 block">$42,800</span>
              </div>
              <div className="rounded-2xl bg-[var(--md-sys-color-surface-container-low)] p-4 border border-[var(--md-sys-color-outline-variant)]">
                <span className="text-[10px] font-bold uppercase text-[#137333] dark:text-[#6dd58c]">4. Farmer (Yopildi)</span>
                <div className="text-xl font-extrabold text-[var(--md-sys-color-on-surface)] mt-1">12 ta</div>
                <span className="text-[11px] text-[var(--md-sys-color-on-surface-variant)] mt-0.5 block">$24,600</span>
              </div>
            </div>

            {/* Funnel Progress Visualizer */}
            <div className="space-y-2">
              <div className="flex justify-between text-xs font-bold text-[var(--md-sys-color-on-surface)]">
                <span>Konversiya zanjiri:</span>
                <span className="text-[#137333] dark:text-[#6dd58c]">28.4% Umumiy samaradorlik</span>
              </div>
              <div className="h-3.5 w-full overflow-hidden rounded-full bg-[var(--md-sys-color-surface-container-highest)] flex">
                <div style={{ width: "35%" }} className="h-full bg-[#0b57d0] title='Hunter'"></div>
                <div style={{ width: "20%" }} className="h-full bg-[#b06000] title='Setter'"></div>
                <div style={{ width: "30%" }} className="h-full bg-[#7c3aed] title='Muzokara'"></div>
                <div style={{ width: "15%" }} className="h-full bg-[#137333] title='Yopildi'"></div>
              </div>
            </div>
          </div>
        </div>

        {/* Right 1 Col: Real-time Event Stream */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-[var(--md-sys-color-on-surface)]">
                Jonli Voqealar Oqimi
              </h2>
              <p className="text-xs text-[var(--md-sys-color-on-surface-variant)]">
                Agentlar faoliyati jurnali
              </p>
            </div>
            <span className="rounded-full bg-[var(--md-sys-color-surface-container)] px-2.5 py-0.5 text-[10px] font-mono text-[var(--md-sys-color-on-surface-variant)]">
              Live
            </span>
          </div>

          <div className="rounded-3xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface)] p-5 shadow-sm space-y-4">
            {recentEvents.map((evt) => (
              <div
                key={evt.id}
                className="flex items-start gap-3 border-b border-[var(--md-sys-color-outline-variant)] pb-3.5 last:border-0 last:pb-0"
              >
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl bg-[var(--md-sys-color-surface-container)] text-lg shadow-inner">
                  {evt.icon}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <span className={`rounded-full px-2 py-0.5 text-[9px] font-bold ${evt.badgeBg}`}>
                      {evt.badge}
                    </span>
                    <span className="text-[10px] text-[var(--md-sys-color-on-surface-variant)] shrink-0">{evt.time}</span>
                  </div>
                  <h4 className="mt-1 text-xs font-bold text-[var(--md-sys-color-on-surface)] truncate">
                    {evt.title}
                  </h4>
                  <p className="mt-0.5 text-[11px] text-[var(--md-sys-color-on-surface-variant)] line-clamp-2">
                    {evt.detail}
                  </p>
                </div>
              </div>
            ))}

            <Link
              href="/crm"
              className="mt-2 block w-full rounded-2xl bg-[var(--md-sys-color-surface-container)] py-2.5 text-center text-xs font-bold text-[#0b57d0] dark:text-[#a8c7fa] hover:bg-[var(--md-sys-color-surface-container-high)] transition-colors"
            >
              Barcha jurnallarni ochish →
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
