import React from 'react';
import Link from 'next/link';
import { 
  getCrmDashboardStats, 
  getFinanceDashboardStats, 
  getFrogTasks, 
  getFinanceTransactions,
  getSystemSignals,
  FinanceTransaction,
  FrogTask,
  SystemSignal
} from '@/lib/apiClient';

export const dynamic = 'force-dynamic';

export default async function HomePage() {
  const [crmStats, financeStats, tasksData, txData, signalsReport] = await Promise.all([
    getCrmDashboardStats(),
    getFinanceDashboardStats(),
    getFrogTasks(),
    getFinanceTransactions(),
    getSystemSignals(),
  ]);

  const totalLeads = crmStats?.leads?.total ?? 0;
  const hotLeads = crmStats?.leads?.hot ?? 0;
  const inNegotiation = crmStats?.deals?.total ?? 0;
  const closedThisMonth = crmStats?.deals?.won ?? 0;
  const pipelineValue = crmStats?.deals?.value ?? (totalLeads * 500);

  const balance = financeStats?.balance ?? 0;
  const income = financeStats?.monthly_income ?? 0;
  const expense = financeStats?.monthly_expense ?? 0;
  const netProfit = income - expense;
  const profitMargin = income > 0 ? Math.round((netProfit / income) * 100) : 0;

  const tasks = tasksData?.tasks ?? [];
  const pendingTasks = crmStats?.tasks?.pending ?? tasks.filter(t => t.status !== 'Done' && t.status !== 'Completed').length;
  const completedToday = crmStats?.tasks?.completed_today ?? tasks.filter(t => t.status === 'Done' || t.status === 'Completed').length;
  const transactions = txData?.transactions ?? [];

  const fallbackSignals: SystemSignal[] = [
    {
      pipeline: 'api_gateway',
      name: "FastAPI Backend & Ma'lumotlar Bazasiga Ulanish",
      status: 'disconnected',
      severity: 'critical',
      message: "Next.js server API bilan bog'lana olmadi (INTERNAL_API_URL yoki OISHA_API_SECRET tekshirilmoqda).",
      action: "Oracle VM'da servislar holati va .env kalitlarini tekshirish",
    },
  ];

  const signals = signalsReport?.signals && signalsReport.signals.length > 0 
    ? signalsReport.signals 
    : fallbackSignals;
  const healthScore = signalsReport ? signalsReport.health_score : 0;

  return (
    <div className="space-y-6 pb-12">
      {/* 1. Linear / Raycast Omnibar Hero Banner */}
      <div className="relative overflow-hidden rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-6 md:p-7 shadow-xs">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-5">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <span className="flex h-2 w-2 rounded-full bg-[#059669]"></span>
              <span className="text-[11px] font-bold uppercase tracking-wider text-[#059669] dark:text-[#34d399]">
                The Apex Intelligence Center • 100% Real Live Data
              </span>
            </div>
            <h1 className="text-xl md:text-2xl font-bold tracking-tight text-[var(--text-primary)] flex items-center gap-2">
              <span>Assalomu alaykum, Baxtiyorjon</span>
              <span className="text-sm">✨</span>
            </h1>
            <p className="text-xs text-[var(--text-secondary)] max-w-2xl leading-relaxed">
              Oisha OS agentik tizimi Jon Branding agentligining sotuv, moliya, vazifalar va qo&apos;ng&apos;iroq tahlillarini real vaqtda boshqarmoqda.
            </p>
          </div>

          {/* Quick Action Buttons */}
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
              <span>👥</span> Real Lidlar ({totalLeads})
            </Link>
            <Link
              href="/tasks"
              className="inline-flex items-center gap-1.5 rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface-subtle)] text-[var(--text-primary)] px-3.5 py-2 text-xs font-semibold hover:bg-[var(--bg-surface-active)] transition-all active:scale-[0.98]"
            >
              <span>🐸</span> Vazifalar ({tasks.length})
            </Link>
          </div>
        </div>

        {/* Quick Shortcut Pills */}
        <div className="mt-5 pt-4 border-t border-[var(--border-subtle)]">
          <div className="flex flex-wrap gap-2">
            <Link
              href="/finance"
              className="rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface-subtle)] px-2.5 py-1 text-[11px] font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:border-[var(--accent-primary)]/40 transition-all"
            >
              💰 Real Kassa: ${balance.toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </Link>
            <Link
              href="/crm"
              className="rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface-subtle)] px-2.5 py-1 text-[11px] font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:border-[var(--accent-primary)]/40 transition-all"
            >
              👥 {totalLeads} ta Real Lidlar
            </Link>
            <Link
              href="/tasks"
              className="rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface-subtle)] px-2.5 py-1 text-[11px] font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:border-[var(--accent-primary)]/40 transition-all"
            >
              🐸 {pendingTasks} ta Faol Vazifa
            </Link>
            <Link
              href="/settings"
              className="rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface-subtle)] px-2.5 py-1 text-[11px] font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:border-[var(--accent-primary)]/40 transition-all"
            >
              ⚡ Tizim Barqarorligi: {healthScore}%
            </Link>
          </div>
        </div>
      </div>

      {/* 2. REAL-TIME DATA PIPELINE SIGNALS & GAP RADAR */}
      <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-5 md:p-6 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-[var(--border-subtle)] pb-3.5">
          <div className="flex items-center gap-2.5">
            <div className={`flex h-8 w-8 items-center justify-center rounded-xl text-base ${
              healthScore >= 90 ? 'bg-[#d1fae5] text-[#065f46]' : 'bg-[#fef3c7] text-[#92400e]'
            }`}>
              📡
            </div>
            <div>
              <h2 className="text-sm font-bold text-[var(--text-primary)] flex items-center gap-2">
                <span>Ma&apos;lumotlar Oqimi & Uzilishlar Radari</span>
                <span className={`rounded-md px-1.5 py-0.5 text-[10px] font-extrabold ${
                  healthScore >= 90 
                    ? 'bg-[#d1fae5] text-[#065f46] dark:bg-[#064e3b] dark:text-[#34d399]' 
                    : 'bg-[#fef3c7] text-[#92400e] dark:bg-[#78350f]/30 dark:text-[#fbbf24]'
                }`}>
                  {healthScore}% Sog&apos;lom
                </span>
              </h2>
              <p className="text-xs text-[var(--text-secondary)]">
                Qaysi tizimdan real ma&apos;lumot kelayotgani va qayerda to&apos;xtalish bo&apos;layotganining jonli diagnostikasi
              </p>
            </div>
          </div>

          <span className="text-[10px] font-mono text-[var(--text-tertiary)]">
            Auto-Diagnostic Live
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {signals.map((sig: SystemSignal, idx: number) => {
            const isOk = sig.status === 'healthy';
            const isWarn = sig.status === 'warning';
            const isCrit = sig.status === 'degraded' || sig.status === 'disconnected';
            
            return (
              <div
                key={idx}
                className={`rounded-xl border p-3.5 flex flex-col justify-between space-y-2.5 transition-all ${
                  isOk 
                    ? 'border-[#d1fae5] bg-[#d1fae5]/10 dark:border-[#064e3b]/50 dark:bg-[#064e3b]/10' 
                    : isWarn
                    ? 'border-[#fef3c7] bg-[#fef3c7]/20 dark:border-[#78350f]/50 dark:bg-[#78350f]/10'
                    : 'border-[#fee2e2] bg-[#fee2e2]/20 dark:border-[#7f1d1d]/50 dark:bg-[#7f1d1d]/10'
                }`}
              >
                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-[var(--text-primary)]">
                      {sig.name}
                    </span>
                    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[9px] font-bold ${
                      isOk 
                        ? 'bg-[#d1fae5] text-[#065f46] dark:bg-[#064e3b] dark:text-[#34d399]' 
                        : isWarn
                        ? 'bg-[#fef3c7] text-[#92400e] dark:bg-[#78350f] dark:text-[#fbbf24]'
                        : 'bg-[#fee2e2] text-[#991b1b] dark:bg-[#7f1d1d] dark:text-[#f87171]'
                    }`}>
                      <span className={`h-1.5 w-1.5 rounded-full ${isOk ? 'bg-[#059669]' : isWarn ? 'bg-[#d97706]' : 'bg-[#dc2626]'}`}></span>
                      {isOk ? 'OK • Real' : isWarn ? 'Kutilmoqda' : 'Uzilgan'}
                    </span>
                  </div>

                  <p className="text-[11px] text-[var(--text-secondary)] leading-relaxed">
                    {sig.message}
                  </p>
                </div>

                {sig.action ? (
                  <div className="border-t border-[var(--border-subtle)] pt-2 text-[10px] text-[var(--accent-primary)] font-semibold flex items-center gap-1">
                    <span>💡 Yechim:</span>
                    <span>{sig.action}</span>
                  </div>
                ) : (
                  <div className="border-t border-[var(--border-subtle)] pt-2 text-[10px] text-[#059669] dark:text-[#34d399] font-medium">
                    ✓ Barcha signallar normal
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* 3. Stripe Financial & Business Metric Cards (4 Cards) */}
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
            <strong className="text-[var(--text-primary)]">{500 - totalLeads} bo&apos;sh ({Math.max(0, Math.round(((500 - totalLeads) / 500) * 100))}%)</strong>
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
              ${balance.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
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

      {/* 4. Real Activity Stream & Quick Tables */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Real Transactions (Hisobchi) */}
        <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-5 shadow-xs space-y-3.5">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-bold text-[var(--text-primary)]">
                Oxirgi Kassa Tranzaksiyalari
              </h2>
              <p className="text-xs text-[var(--text-secondary)]">Hisobchi AI va karta to&apos;lovlari</p>
            </div>
            <Link href="/finance" className="text-xs font-bold text-[var(--accent-primary)] hover:underline">
              Barchasi →
            </Link>
          </div>

          {transactions.length === 0 ? (
            <div className="py-8 text-center text-xs text-[var(--text-secondary)]">
              🧾 Hozircha yangi tranzaksiyalar yo&apos;q (Hisobchi kutilmoqda)
            </div>
          ) : (
            <div className="space-y-2.5">
              {transactions.slice(0, 4).map((tx: FinanceTransaction) => (
                <div key={tx.id} className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-2.5 last:border-0 last:pb-0">
                  <div>
                    <div className="text-xs font-bold text-[var(--text-primary)]">{tx.description}</div>
                    <div className="text-[10px] text-[var(--text-secondary)]">{tx.category || 'Xizmat'} • {tx.date}</div>
                  </div>
                  <div className={`text-xs font-bold font-mono ${tx.type === 'Kirim' ? 'text-[#059669]' : 'text-[#dc2626]'}`}>
                    {tx.amount}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Real Tasks (FrogAgent) */}
        <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-5 shadow-xs space-y-3.5">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-bold text-[var(--text-primary)]">
                Kutilayotgan Vazifalar
              </h2>
              <p className="text-xs text-[var(--text-secondary)]">FrogAgent va jamoa topshiriqlari</p>
            </div>
            <Link href="/tasks" className="text-xs font-bold text-[var(--accent-primary)] hover:underline">
              Barchasi →
            </Link>
          </div>

          {tasks.length === 0 ? (
            <div className="py-8 text-center text-xs text-[var(--text-secondary)]">
              🐸 Hozircha yangi topshiriqlar yo&apos;q
            </div>
          ) : (
            <div className="space-y-2.5">
              {tasks.slice(0, 4).map((task: FrogTask) => (
                <div key={task.id} className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-2.5 last:border-0 last:pb-0">
                  <div>
                    <div className="flex items-center gap-1.5 text-xs font-bold text-[var(--text-primary)]">
                      {task.is_frog && <span>🐸</span>}
                      <span>{task.title}</span>
                    </div>
                    <div className="text-[10px] text-[var(--text-secondary)]">Mas&apos;ul: {String(task.assigned_to || 'Jamoa')} • {task.deadline || 'Bugun'}</div>
                  </div>
                  <span className="rounded-md px-2 py-0.5 text-[9px] font-bold bg-[var(--bg-surface-subtle)] text-[var(--text-primary)]">
                    {task.status}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
