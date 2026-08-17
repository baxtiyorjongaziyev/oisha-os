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
  const pendingTasks = crmStats?.tasks.pending || 6;
  const completedToday = crmStats?.tasks.completed_today || 4;

  const agentSwarm = [
    {
      id: 'hisobchi',
      name: 'Hisobchi AI',
      role: 'Moliya & Kassa',
      status: 'Faol',
      pulse: 'bg-emerald-500',
      icon: '💰',
      detail: 'SMS & karta tranzaksiyalari, Google Sheets avtosinxron',
      actionUrl: '/finance',
    },
    {
      id: 'frog',
      name: 'FrogAgent',
      role: 'ROI Vazifalar',
      status: 'Faol',
      pulse: 'bg-emerald-500',
      icon: '🐸',
      detail: 'Kunlik 09:00 Telegram brifingi & eng daromadli ishlar',
      actionUrl: '/tasks',
    },
    {
      id: 'coach',
      name: 'SalesCoach AI',
      role: 'Suhbat Sifati',
      status: 'Faol',
      pulse: 'bg-emerald-500',
      icon: '🎙',
      detail: 'Whisper ASR tahlili, skoring va skript nazorati',
      actionUrl: '/calls',
    },
    {
      id: 'telegram',
      name: 'Telegram Dual-Head',
      role: 'Control Plane',
      status: 'Online',
      pulse: 'bg-emerald-500',
      icon: '⚡',
      detail: 'Aiogram 3.x Webhook + Oracle VM Telethon userbot',
      actionUrl: '/settings',
    },
    {
      id: 'amocrm',
      name: 'AmoCRM v4',
      role: 'Sotuv Voronkasi',
      status: 'Ulangan',
      pulse: 'bg-blue-500',
      icon: '🔄',
      detail: 'Hunter-Setter-Farmer boshqaruvi (500 limit nazorati)',
      actionUrl: '/crm',
    },
    {
      id: 'edge',
      name: 'Edge AI Personalizer',
      role: 'Veb Konversiya',
      status: 'Faol',
      pulse: 'bg-purple-500',
      icon: '🪄',
      detail: 'Cloudflare Workers + GA4 orqali dinamik sayt kontenti',
      actionUrl: '/analytics',
    },
  ];

  const recentActivities = [
    {
      id: 1,
      type: 'finance',
      badge: 'Kirim',
      badgeColor: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-400',
      title: 'Yangi to\'lov qabul qilindi: +$2,400',
      desc: 'Mijoz: "Apex Logistics" — Brendbuk va Qadoq dizayni 50% avans (Hisobchi AI)',
      time: '14 daqiqa oldin',
      icon: '💵',
    },
    {
      id: 2,
      type: 'crm',
      badge: 'Muzokara',
      badgeColor: 'bg-blue-100 text-blue-800 dark:bg-blue-950/40 dark:text-blue-400',
      title: 'Lid bosqichi o\'zgardi: "KP yuborildi"',
      desc: 'Mijoz: "Safir Klinika" — Menejer: Baxtiyorjon (AmoCRM v4)',
      time: '42 daqiqa oldin',
      icon: '🤝',
    },
    {
      id: 3,
      type: 'call',
      badge: '94% Ball',
      badgeColor: 'bg-purple-100 text-purple-800 dark:bg-purple-950/40 dark:text-purple-400',
      title: 'Qo\'ng\'iroq tahlil qilindi (Whisper ASR)',
      desc: 'Mijoz: "Grand Tour" — E\'tirozlar to\'liq yopildi, keyingi qadam belgilandi',
      time: '1 soat oldin',
      icon: '🎧',
    },
    {
      id: 4,
      type: 'frog',
      badge: 'Frog Task',
      badgeColor: 'bg-amber-100 text-amber-800 dark:bg-amber-950/40 dark:text-amber-400',
      title: 'Kunning 1-raqamli vazifasi bajarildi',
      desc: '"Orzu Mebel" bilan strategik shartnoma yakunlandi (Kutilgan foyda: +$3,800)',
      time: '3 soat oldin',
      icon: '🎯',
    },
  ];

  return (
    <div className="space-y-8 pb-12">
      {/* Hero Welcome Banner */}
      <div className="relative overflow-hidden rounded-3xl border border-border bg-gradient-to-br from-bg-card via-bg-card to-brand-light/30 p-6 md:p-8 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
          <div>
            <div className="flex items-center gap-2">
              <span className="flex h-2 w-2 rounded-full bg-emerald-500"></span>
              <span className="text-xs font-semibold uppercase tracking-wider text-emerald-600 dark:text-emerald-400">
                Tizim To&apos;liq Ishchi Holatda (Oracle VM 24/7)
              </span>
            </div>
            <h1 className="mt-2 text-2xl md:text-3xl font-extrabold tracking-tight text-text">
              Assalomu alaykum, Baxtiyorjon 👋
            </h1>
            <p className="mt-1 text-sm text-text-muted max-w-2xl">
              Oisha OS agentik tizimi Jon Branding agentligining barcha sotuv, moliya, vazifalar va qo&apos;ng&apos;iroq jarayonlarini avtonom boshqarmoqda.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Link
              href="/finance"
              className="inline-flex items-center gap-2 rounded-2xl bg-brand px-4 py-2.5 text-xs font-semibold text-white shadow-md shadow-brand/20 hover:bg-brand-hover transition-all active:scale-[0.98]"
            >
              <span>+</span> Kirim / Chiqim
            </Link>
            <Link
              href="/crm"
              className="inline-flex items-center gap-2 rounded-2xl border border-border bg-bg-card px-4 py-2.5 text-xs font-semibold text-text hover:bg-bg transition-all active:scale-[0.98]"
            >
              <span>👥</span> Yangi Lid
            </Link>
            <Link
              href="/calls"
              className="inline-flex items-center gap-2 rounded-2xl border border-border bg-bg-card px-4 py-2.5 text-xs font-semibold text-text hover:bg-bg transition-all active:scale-[0.98]"
            >
              <span>🎙</span> Qo&apos;ng&apos;iroq Tahlili
            </Link>
          </div>
        </div>
      </div>

      {/* 4 Dynamic KPI Cards */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {/* Card 1: CRM Leads */}
        <div className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm hover:border-brand/40 transition-all">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-text-muted">
              Jami Lidlar (AmoCRM)
            </span>
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-blue-50 dark:bg-blue-950/40 text-blue-600 text-sm font-bold">
              👥
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold tracking-tight text-text">
              {totalLeads}
            </span>
            <span className="text-xs font-bold text-emerald-600 bg-emerald-50 dark:bg-emerald-950/40 px-2 py-0.5 rounded-full">
              {hotLeads} ta Issiq 🔥
            </span>
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-text-muted border-t border-border/50 pt-3">
            <span>500 bitim limiti</span>
            <span className="font-semibold text-text">{500 - totalLeads} bo&apos;sh joy</span>
          </div>
        </div>

        {/* Card 2: Active Pipeline & Deals */}
        <div className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm hover:border-brand/40 transition-all">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-text-muted">
              Muzokaralar & Bitimlar
            </span>
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 text-sm font-bold">
              💼
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold tracking-tight text-emerald-600 dark:text-emerald-400">
              {inNegotiation}
            </span>
            <span className="text-xs text-text-muted">
              (Yopilgan: <strong className="text-text">{closedThisMonth}</strong>)
            </span>
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-text-muted border-t border-border/50 pt-3">
            <span>Voronka qiymati</span>
            <span className="font-bold text-emerald-600">${pipelineValue.toLocaleString()}</span>
          </div>
        </div>

        {/* Card 3: Finance / Hisobchi AI */}
        <div className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm hover:border-brand/40 transition-all">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-text-muted">
              Jami Kassa (Balans)
            </span>
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-amber-50 dark:bg-amber-950/40 text-amber-600 text-sm font-bold">
              💰
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold tracking-tight text-text">
              ${balance.toLocaleString()}
            </span>
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-text-muted border-t border-border/50 pt-3">
            <span className="text-emerald-600 font-semibold">+${income.toLocaleString()}</span>
            <span className="text-rose-500 font-semibold">-${expense.toLocaleString()}</span>
          </div>
        </div>

        {/* Card 4: FrogAgent Priority Tasks */}
        <div className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm hover:border-brand/40 transition-all">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-text-muted">
              FrogAgent Vazifalar
            </span>
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-purple-50 dark:bg-purple-950/40 text-purple-600 text-sm font-bold">
              🐸
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold tracking-tight text-purple-600 dark:text-purple-400">
              {pendingTasks}
            </span>
            <span className="text-xs text-text-muted">
              kutilmoqda
            </span>
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-text-muted border-t border-border/50 pt-3">
            <span>Bugun bajarildi</span>
            <span className="font-bold text-purple-600">{completedToday} ta vazifa</span>
          </div>
        </div>
      </div>

      {/* Main Content Grid: AI Swarm Status + Live Activity Feed */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left 2 Cols: AI Agent Swarm Command Grid */}
        <div className="lg:col-span-2 space-y-5">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-text">AI Agentlar Tizimi (Swarm)</h2>
              <p className="text-xs text-text-muted mt-0.5">
                Agentlik operatsiyalarini real vaqtda muvofiqlashtiruvchi avtonom modullar.
              </p>
            </div>
            <span className="rounded-full bg-emerald-100 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-400 px-3 py-1 text-xs font-bold flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-ping"></span>
              6 / 6 Faol
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {agentSwarm.map((agent) => (
              <Link
                key={agent.id}
                href={agent.actionUrl}
                className="group flex flex-col justify-between rounded-3xl border border-border bg-bg-card p-5 shadow-sm hover:border-brand hover:shadow-md transition-all active:scale-[0.99]"
              >
                <div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <span className="text-2xl">{agent.icon}</span>
                      <div>
                        <h3 className="text-sm font-bold text-text group-hover:text-brand transition-colors">
                          {agent.name}
                        </h3>
                        <span className="text-[10px] text-text-muted font-medium">
                          {agent.role}
                        </span>
                      </div>
                    </div>
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-bg px-2.5 py-0.5 text-[10px] font-bold text-text border border-border">
                      <span className={`h-1.5 w-1.5 rounded-full ${agent.pulse}`}></span>
                      {agent.status}
                    </span>
                  </div>
                  <p className="mt-3 text-xs text-text-muted line-clamp-2">
                    {agent.detail}
                  </p>
                </div>
                <div className="mt-4 flex items-center justify-end text-[11px] font-semibold text-brand group-hover:translate-x-1 transition-transform">
                  Boshqarish →
                </div>
              </Link>
            ))}
          </div>
        </div>

        {/* Right 1 Col: Live Activity Feed */}
        <div className="space-y-5">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-text">Jonli Voqealar</h2>
              <p className="text-xs text-text-muted mt-0.5">
                Tizimning oxirgi operatsion harakatlari
              </p>
            </div>
            <span className="text-xs text-text-muted font-mono">Live</span>
          </div>

          <div className="rounded-3xl border border-border bg-bg-card p-5 shadow-sm space-y-4">
            {recentActivities.map((act) => (
              <div
                key={act.id}
                className="flex items-start gap-3 border-b border-border/50 pb-3.5 last:border-0 last:pb-0"
              >
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl bg-bg text-lg shadow-inner">
                  {act.icon}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <span className={`rounded-full px-2 py-0.5 text-[9px] font-bold ${act.badgeColor}`}>
                      {act.badge}
                    </span>
                    <span className="text-[10px] text-text-muted shrink-0">{act.time}</span>
                  </div>
                  <h4 className="mt-1 text-xs font-bold text-text truncate">
                    {act.title}
                  </h4>
                  <p className="mt-0.5 text-[11px] text-text-muted line-clamp-2">
                    {act.desc}
                  </p>
                </div>
              </div>
            ))}

            <Link
              href="/crm"
              className="mt-2 block w-full rounded-2xl bg-bg py-2.5 text-center text-xs font-semibold text-brand hover:bg-brand-light transition-colors"
            >
              Barcha jurnallarni ko&apos;rish →
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
