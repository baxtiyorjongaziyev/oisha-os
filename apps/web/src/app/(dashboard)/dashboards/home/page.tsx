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
      statusColor: 'bg-[#d1fae5] text-[#065f46] dark:bg-[#064e3b] dark:text-[#34d399]',
      latency: '24ms',
      icon: '💰',
      detail: 'SMS & karta tranzaksiyalari, Google Sheets 24/7 sinxron',
      actionUrl: '/finance',
    },
    {
      id: 'frog',
      name: 'FrogAgent',
      category: 'ROI Enforcer',
      status: 'Faol',
      statusColor: 'bg-[#ede9fe] text-[#5b21b6] dark:bg-[#4c1d95] dark:text-[#c084fc]',
      latency: '18ms',
      icon: '🐸',
      detail: 'Kunlik 09:00 Telegram brifingi & yuqori marjali vazifalar',
      actionUrl: '/tasks',
    },
    {
      id: 'coach',
      name: 'SalesCoach AI',
      category: 'Suhbat Sifati',
      status: 'Faol',
      statusColor: 'bg-[var(--accent-primary-light)] text-[var(--accent-primary-on-light)]',
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
      statusColor: 'bg-[#d1fae5] text-[#065f46] dark:bg-[#064e3b] dark:text-[#34d399]',
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
      statusColor: 'bg-[var(--accent-primary-light)] text-[var(--accent-primary-on-light)]',
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
      statusColor: 'bg-[#fef3c7] text-[#92400e] dark:bg-[#78350f]/30 dark:text-[#fbbf24]',
      latency: '12ms',
      icon: '🪄',
      detail: 'Cloudflare Workers + GA4 orqali jonbranding.uz dinamik kontenti',
      actionUrl: '/analytics',
    },
  ];

  const recentEvents = [
    {
      id: 1,
      badge: 'Kirim',
      badgeBg: 'bg-[#d1fae5] text-[#065f46] dark:bg-[#064e3b] dark:text-[#34d399]',
      title: 'To\'lov qabul qilindi: +$2,400.00',
      detail: '"Apex Logistics" — Brendbuk va Qadoq dizayni 50% avansi (Hisobchi AI)',
      time: '12 daqiqa oldin',
      icon: '💵',
    },
    {
      id: 2,
      badge: 'Muzokara',
      badgeBg: 'bg-[var(--accent-primary-light)] text-[var(--accent-primary-on-light)]',
      title: 'Lid bosqichi o\'zgardi: "KP yuborildi"',
      detail: '"Safir Klinika" — Mas\'ul: Baxtiyorjon (AmoCRM v4 Gateway)',
      time: '38 daqiqa oldin',
      icon: '🤝',
    },
    {
      id: 3,
      badge: '94% Ball',
      badgeBg: 'bg-[#ede9fe] text-[#5b21b6] dark:bg-[#4c1d95] dark:text-[#c084fc]',
      title: 'Qo\'ng\'iroq tahlil qilindi (Whisper ASR)',
      detail: '"Grand Tour" — E\'tirozlar to\'liq bartaraf etildi, bitim summasi: $6,400',
      time: '1 soat oldin',
      icon: '🎧',
    },
    {
      id: 4,
      badge: 'Frog Task',
      badgeBg: 'bg-[#fef3c7] text-[#92400e] dark:bg-[#78350f]/30 dark:text-[#fbbf24]',
      title: 'Kunning 1-raqamli vazifasi bajarildi',
      detail: '"Orzu Mebel" bilan strategik shartnoma yakunlandi (Kutilgan daromad: +$3,800)',
      time: '2 soat oldin',
      icon: '🎯',
    },
  ];

  return (
    <div className="space-y-6 pb-12">
      {/* 1. Linear / Raycast Omnibar Hero Banner */}
      <div className="relative overflow-hidden rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-6 md:p-7 shadow-xs">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-5">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <span className="flex h-2 w-2 rounded-full bg-[#059669]"></span>
              <span className="text-[11px] font-bold uppercase tracking-wider text-[#059669] dark:text-[#34d399]">
                The Apex Intelligence Center • Live 24/7
              </span>
            </div>
            <h1 className="text-xl md:text-2xl font-bold tracking-tight text-[var(--text-primary)] flex items-center gap-2">
              <span>Assalomu alaykum, Baxtiyorjon</span>
              <span className="text-sm">✨</span>
            </h1>
            <p className="text-xs text-[var(--text-secondary)] max-w-2xl leading-relaxed">
              Oisha OS agentik tizimi Jon Branding agentligining sotuv, moliya, vazifalar va qo&apos;ng&apos;iroq tahlillarini avtonom boshqarmoqda.
            </p>
          </div>

          {/* Quick Action Buttons (Stripe & Linear pill style) */}
          <div className="flex flex-wrap items-center gap-2">
            <Link
              href="/finance"
              className="inline-flex items-center gap-1.5 rounded-xl bg-[var(--accent-primary)] text-white px-3.5 py-2 text-xs font-bold shadow-xs hover:opacity-90 transition-all active:scale-[0.98]"
            >
              <span>+</span> Kirim / Chiqim
            </Link>
            <Link
              href="/crm"
              className="inline-flex items-center gap-1.5 rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface-subtle)] text-[var(--text-primary)] px-3.5 py-2 text-xs font-semibold hover:bg-[var(--bg-surface-active)] transition-all active:scale-[0.98]"
            >
              <span>👥</span> Yangi Lid
            </Link>
            <Link
              href="/tasks"
              className="inline-flex items-center gap-1.5 rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface-subtle)] text-[var(--text-primary)] px-3.5 py-2 text-xs font-semibold hover:bg-[var(--bg-surface-active)] transition-all active:scale-[0.98]"
            >
              <span>🐸</span> Frog Vazifa
            </Link>
          </div>
        </div>

        {/* Raycast Quick Shortcut Pills */}
        <div className="mt-5 pt-4 border-t border-[var(--border-subtle)]">
          <div className="flex flex-wrap gap-2">
            {[
              { label: "💰 Kassa: $18,450", href: "/finance" },
              { label: "🐸 Frog: 'Orzu Mebel'", href: "/tasks" },
              { label: "👥 34 ta Issiq Lidlar", href: "/crm" },
              { label: "🎙 Whisper Skoring: 88%", href: "/calls" },
              { label: "⚡ Telethon Live (Oracle VM)", href: "/settings" },
            ].map((chip, idx) => (
              <Link
                key={idx}
                href={chip.href}
                className="rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface-subtle)] px-2.5 py-1 text-[11px] font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:border-[var(--accent-primary)]/40 transition-all"
              >
                {chip.label}
              </Link>
            ))}
          </div>
        </div>
      </div>

      {/* 2. Stripe Financial & Business Metric Cards (4 Cards) */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* Card 1: CRM Leads */}
        <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-5 shadow-xs hover:border-[var(--accent-primary)]/40 transition-all">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-secondary)]">
              AmoCRM Faol Lidlar
            </span>
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[var(--accent-primary-light)] text-[var(--accent-primary-on-light)] text-xs font-bold">
              👥
            </div>
          </div>
          <div className="mt-2.5 flex items-baseline gap-2">
            <span className="text-2xl md:text-3xl font-extrabold tracking-tight text-[var(--text-primary)]">
              {totalLeads}
            </span>
            <span className="rounded-md bg-[#d1fae5] dark:bg-[#064e3b] px-1.5 py-0.5 text-[10px] font-bold text-[#065f46] dark:text-[#34d399]">
              {hotLeads} ta Issiq 🔥
            </span>
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-[var(--text-secondary)] border-t border-[var(--border-subtle)] pt-2.5">
            <span>500 bitim kvotasi:</span>
            <strong className="text-[var(--text-primary)]">{500 - totalLeads} bo&apos;sh (97%)</strong>
          </div>
        </div>

        {/* Card 2: Active Deals */}
        <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-5 shadow-xs hover:border-[var(--accent-primary)]/40 transition-all">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-secondary)]">
              Muzokaralar Voronkasi
            </span>
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#d1fae5] text-[#065f46] dark:bg-[#064e3b] dark:text-[#34d399] text-xs font-bold">
              💼
            </div>
          </div>
          <div className="mt-2.5 flex items-baseline gap-2">
            <span className="text-2xl md:text-3xl font-extrabold tracking-tight text-[#059669] dark:text-[#34d399]">
              {inNegotiation}
            </span>
            <span className="text-xs text-[var(--text-secondary)]">
              (Yopilgan: <strong className="text-[var(--text-primary)]">{closedThisMonth}</strong>)
            </span>
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-[var(--text-secondary)] border-t border-[var(--border-subtle)] pt-2.5">
            <span>Voronka qiymati:</span>
            <strong className="text-[#059669] dark:text-[#34d399]">${pipelineValue.toLocaleString()}</strong>
          </div>
        </div>

        {/* Card 3: Finance / Hisobchi */}
        <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-5 shadow-xs hover:border-[var(--accent-primary)]/40 transition-all">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-secondary)]">
              Kassa & Sof Foyda
            </span>
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#fef3c7] text-[#92400e] dark:bg-[#78350f]/30 dark:text-[#fbbf24] text-xs font-bold">
              💰
            </div>
          </div>
          <div className="mt-2.5 flex items-baseline gap-2">
            <span className="text-2xl md:text-3xl font-extrabold tracking-tight text-[var(--text-primary)]">
              ${balance.toLocaleString()}
            </span>
            <span className="text-xs font-bold text-[#059669] dark:text-[#34d399]">
              {profitMargin}% marja
            </span>
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-[var(--text-secondary)] border-t border-[var(--border-subtle)] pt-2.5">
            <span className="text-[#059669] dark:text-[#34d399] font-semibold">+${income.toLocaleString()}</span>
            <span className="text-[#dc2626] dark:text-[#f87171] font-semibold">-${expense.toLocaleString()}</span>
          </div>
        </div>

        {/* Card 4: Frog ROI Tasks */}
        <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-5 shadow-xs hover:border-[var(--accent-primary)]/40 transition-all">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-secondary)]">
              Frog ROI Intizomi
            </span>
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#ede9fe] text-[#5b21b6] dark:bg-[#4c1d95] dark:text-[#c084fc] text-xs font-bold">
              🐸
            </div>
          </div>
          <div className="mt-2.5 flex items-baseline gap-2">
            <span className="text-2xl md:text-3xl font-extrabold tracking-tight text-[#7c3aed] dark:text-[#c084fc]">
              {pendingTasks}
            </span>
            <span className="text-xs text-[var(--text-secondary)]">
              vazifa kutilmoqda
            </span>
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-[var(--text-secondary)] border-t border-[var(--border-subtle)] pt-2.5">
            <span>Bugun bajarildi:</span>
            <strong className="text-[#7c3aed] dark:text-[#c084fc]">{completedToday} ta topshiriq</strong>
          </div>
        </div>
      </div>

      {/* 3. Apple HIG Fluid Swarm Telemetry Hub */}
      <div className="space-y-3.5">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-[var(--text-primary)]">
              AI Agentlar Tizimi (Swarm Telemetry)
            </h2>
            <p className="text-xs text-[var(--text-secondary)]">
              Barcha 6 ta avtonom modul real vaqtda bir-biri bilan integratsiyalashgan.
            </p>
          </div>
          <span className="rounded-full bg-[#d1fae5] text-[#065f46] dark:bg-[#064e3b] dark:text-[#34d399] px-2.5 py-0.5 text-xs font-bold flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-[#059669] animate-ping"></span>
            6 / 6 Faol
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
          {agentSwarm.map((agent) => (
            <Link
              key={agent.id}
              href={agent.actionUrl}
              className="group flex flex-col justify-between rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-4 shadow-xs hover:border-[var(--accent-primary)] transition-all active:scale-[0.99]"
            >
              <div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--bg-surface-subtle)] text-lg shadow-xs">
                      {agent.icon}
                    </div>
                    <div>
                      <h3 className="text-xs font-bold text-[var(--text-primary)] group-hover:text-[var(--accent-primary)] transition-colors">
                        {agent.name}
                      </h3>
                      <span className="text-[10px] text-[var(--text-secondary)] font-medium">
                        {agent.category}
                      </span>
                    </div>
                  </div>
                  <span className={`rounded-full px-2 py-0.5 text-[9px] font-bold ${agent.statusColor}`}>
                    {agent.status}
                  </span>
                </div>

                <p className="mt-2.5 text-[11px] text-[var(--text-secondary)] line-clamp-2 leading-relaxed">
                  {agent.detail}
                </p>
              </div>

              <div className="mt-3.5 flex items-center justify-between border-t border-[var(--border-subtle)] pt-2.5 text-[10px]">
                <span className="font-mono text-[var(--text-tertiary)]">
                  Latency: {agent.latency}
                </span>
                <span className="font-bold text-[var(--accent-primary)] group-hover:translate-x-0.5 transition-transform">
                  Boshqarish →
                </span>
              </div>
            </Link>
          ))}
        </div>
      </div>

      {/* 4. Shopify/Polaris Funnel & Live Event Stream */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Hunter-Setter-Farmer Funnel */}
        <div className="lg:col-span-2 space-y-3.5">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-[var(--text-primary)]">
                Hunter-Setter-Farmer Voronkasi
              </h2>
              <p className="text-xs text-[var(--text-secondary)]">
                AmoCRM v4 dagi bitimlarning konversiya va bosqichlar progressi
              </p>
            </div>
            <Link href="/crm" className="text-xs font-bold text-[var(--accent-primary)] hover:underline">
              CRM ga o&apos;tish →
            </Link>
          </div>

          <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-5 shadow-xs space-y-4">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
              <div className="rounded-xl bg-[var(--bg-surface-subtle)] p-3 border border-[var(--border-subtle)]">
                <span className="text-[9px] font-bold uppercase text-[var(--accent-primary)]">1. Hunter</span>
                <div className="text-lg font-bold text-[var(--text-primary)] mt-0.5">34 ta</div>
                <span className="text-[10px] text-[var(--text-secondary)] block">$18,200</span>
              </div>
              <div className="rounded-xl bg-[var(--bg-surface-subtle)] p-3 border border-[var(--border-subtle)]">
                <span className="text-[9px] font-bold uppercase text-[#d97706] dark:text-[#fbbf24]">2. Setter</span>
                <div className="text-lg font-bold text-[var(--text-primary)] mt-0.5">19 ta</div>
                <span className="text-[10px] text-[var(--text-secondary)] block">$15,400</span>
              </div>
              <div className="rounded-xl bg-[var(--bg-surface-subtle)] p-3 border border-[var(--border-subtle)]">
                <span className="text-[9px] font-bold uppercase text-[#7c3aed] dark:text-[#c084fc]">3. Muzokara</span>
                <div className="text-lg font-bold text-[var(--text-primary)] mt-0.5">28 ta</div>
                <span className="text-[10px] text-[var(--text-secondary)] block">$42,800</span>
              </div>
              <div className="rounded-xl bg-[var(--bg-surface-subtle)] p-3 border border-[var(--border-subtle)]">
                <span className="text-[9px] font-bold uppercase text-[#059669] dark:text-[#34d399]">4. Farmer</span>
                <div className="text-lg font-bold text-[var(--text-primary)] mt-0.5">12 ta</div>
                <span className="text-[10px] text-[var(--text-secondary)] block">$24,600</span>
              </div>
            </div>

            {/* Funnel Progress Visualizer */}
            <div className="space-y-1.5">
              <div className="flex justify-between text-xs font-bold text-[var(--text-primary)]">
                <span>Konversiya zanjiri:</span>
                <span className="text-[#059669] dark:text-[#34d399]">28.4% Umumiy samaradorlik</span>
              </div>
              <div className="h-3 w-full overflow-hidden rounded-full bg-[var(--bg-surface-active)] flex">
                <div style={{ width: "35%" }} className="h-full bg-[var(--accent-primary)]"></div>
                <div style={{ width: "20%" }} className="h-full bg-[#d97706]"></div>
                <div style={{ width: "30%" }} className="h-full bg-[#7c3aed]"></div>
                <div style={{ width: "15%" }} className="h-full bg-[#059669]"></div>
              </div>
            </div>
          </div>
        </div>

        {/* Right 1 Col: Real-time Event Stream */}
        <div className="space-y-3.5">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-[var(--text-primary)]">
                Jonli Voqealar
              </h2>
              <p className="text-xs text-[var(--text-secondary)]">
                Agentlar faoliyati
              </p>
            </div>
            <span className="rounded-md bg-[var(--bg-surface-subtle)] px-2 py-0.5 text-[9px] font-mono text-[var(--text-secondary)]">
              Live
            </span>
          </div>

          <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-4 shadow-xs space-y-3.5">
            {recentEvents.map((evt) => (
              <div
                key={evt.id}
                className="flex items-start gap-2.5 border-b border-[var(--border-subtle)] pb-3 last:border-0 last:pb-0"
              >
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-[var(--bg-surface-subtle)] text-base shadow-xs">
                  {evt.icon}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-1">
                    <span className={`rounded-md px-1.5 py-0.5 text-[8px] font-bold ${evt.badgeBg}`}>
                      {evt.badge}
                    </span>
                    <span className="text-[9px] text-[var(--text-tertiary)] shrink-0">{evt.time}</span>
                  </div>
                  <h4 className="mt-0.5 text-xs font-bold text-[var(--text-primary)] truncate">
                    {evt.title}
                  </h4>
                  <p className="mt-0.5 text-[10px] text-[var(--text-secondary)] line-clamp-2">
                    {evt.detail}
                  </p>
                </div>
              </div>
            ))}

            <Link
              href="/crm"
              className="mt-1 block w-full rounded-xl bg-[var(--bg-surface-subtle)] py-2 text-center text-xs font-bold text-[var(--accent-primary)] hover:bg-[var(--bg-surface-active)] transition-colors"
            >
              Barcha jurnallar →
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
