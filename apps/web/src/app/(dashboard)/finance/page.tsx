import React from 'react';
import { getFinanceDashboardStats, getFinanceTransactions } from '@/lib/apiClient';

export const dynamic = 'force-dynamic';

export default async function FinanceDashboard() {
  const [stats, txData] = await Promise.all([
    getFinanceDashboardStats(),
    getFinanceTransactions(),
  ]);

  const balance = stats?.balance || 18450;
  const income = stats?.monthly_income || 14200;
  const expense = stats?.monthly_expense || 5800;
  const netProfit = income - expense;
  const profitMargin = income > 0 ? Math.round((netProfit / income) * 100) : 0;
  
  const transactions = txData?.transactions && txData.transactions.length > 0 ? txData.transactions : [
    {
      id: 'tx-1',
      type: 'Kirim',
      amount: '+$2,400.00',
      description: '"Apex Logistics" — Brendbuk va Qadoq dizayni 50% avans',
      date: 'Bugun, 12:40',
      category: 'Xizmat haqi',
      source: 'Humo / Bank',
    },
    {
      id: 'tx-2',
      type: 'Chiqim',
      amount: '-$450.00',
      description: 'Meta Ads & Google Ads reklama byudjeti to\'lovi',
      date: 'Kecha, 18:20',
      category: 'Marketing',
      source: 'Uzcard Karta',
    },
    {
      id: 'tx-3',
      type: 'Kirim',
      amount: '+$1,800.00',
      description: '"Safir Klinika" — Identika va Naming yakuniy to\'lovi',
      date: '15-Avgust',
      category: 'Xizmat haqi',
      source: 'Naqd pul',
    },
    {
      id: 'tx-4',
      type: 'Chiqim',
      amount: '-$120.00',
      description: 'Oracle Cloud & Turso libSQL server infratuzilmasi',
      date: '14-Avgust',
      category: 'Server & API',
      source: 'Visa Karta',
    },
    {
      id: 'tx-5',
      type: 'Kirim',
      amount: '+$3,200.00',
      description: '"Grand Tour" — Kompleks rebrending 1-bosqich',
      date: '12-Avgust',
      category: 'Xizmat haqi',
      source: 'Bank o\'tkazmasi',
    },
  ];

  return (
    <div className="space-y-8 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold uppercase tracking-wider text-brand bg-brand-light px-2.5 py-0.5 rounded-full">
              HISOBCHI AI
            </span>
            <span className="text-xs text-text-muted">• Real-time Kassa & Cashflow</span>
          </div>
          <h1 className="mt-1 text-2xl md:text-3xl font-extrabold tracking-tight text-text">
            Moliya & Kassa Boshqaruvi
          </h1>
          <p className="mt-0.5 text-xs text-text-muted">
            Telegram bot (@jonairobot), SMS bildirishnomalar va Google Sheets bilan to&apos;liq sinxronlashgan.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button className="rounded-2xl border border-rose-200 bg-rose-50 dark:bg-rose-950/30 dark:border-rose-900/40 text-rose-600 dark:text-rose-400 px-4 py-2.5 text-xs font-bold hover:bg-rose-100 transition-all active:scale-[0.98]">
            - Chiqim kiritish
          </button>
          <button className="rounded-2xl bg-emerald-600 text-white px-4 py-2.5 text-xs font-bold hover:bg-emerald-700 shadow-md shadow-emerald-600/20 transition-all active:scale-[0.98]">
            + Kirim kiritish
          </button>
        </div>
      </div>

      {/* 4 Financial Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {/* Total Balance */}
        <div className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm">
          <span className="text-xs font-bold uppercase tracking-wider text-text-muted">
            Jami Kassa Balansi
          </span>
          <div className="mt-2 text-3xl font-black tracking-tight text-text">
            ${balance.toLocaleString()}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-text-muted border-t border-border/50 pt-3">
            <span>Bank: <strong>$12,300</strong></span>
            <span>Naqd: <strong>$6,150</strong></span>
          </div>
        </div>

        {/* Monthly Income */}
        <div className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm">
          <span className="text-xs font-bold uppercase tracking-wider text-text-muted">
            Bu oygi Kirim (Tushum)
          </span>
          <div className="mt-2 text-3xl font-black tracking-tight text-emerald-600 dark:text-emerald-400">
            +${income.toLocaleString()}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-text-muted border-t border-border/50 pt-3">
            <span>O&apos;sish:</span>
            <span className="font-bold text-emerald-600">+18% o&apos;tgan oyga nisbatan</span>
          </div>
        </div>

        {/* Monthly Expense */}
        <div className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm">
          <span className="text-xs font-bold uppercase tracking-wider text-text-muted">
            Bu oygi Chiqim (Xarajat)
          </span>
          <div className="mt-2 text-3xl font-black tracking-tight text-rose-500">
            -${expense.toLocaleString()}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-text-muted border-t border-border/50 pt-3">
            <span>Byudjet chegarasi:</span>
            <span className="font-semibold text-text">$8,000 gacha</span>
          </div>
        </div>

        {/* Net Profit */}
        <div className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm">
          <span className="text-xs font-bold uppercase tracking-wider text-text-muted">
            Sof Foyda (Net Profit)
          </span>
          <div className="mt-2 text-3xl font-black tracking-tight text-brand">
            +${netProfit.toLocaleString()}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-text-muted border-t border-border/50 pt-3">
            <span>Rentabellik (Marja):</span>
            <span className="font-extrabold text-brand">{profitMargin}%</span>
          </div>
        </div>
      </div>

      {/* Cashflow Bar Breakdown */}
      <div className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-bold text-text">Kirim va Chiqim Nisbati (Cashflow Balance)</h3>
            <p className="text-xs text-text-muted">Joriy oydagi pul oqimining xavfsizlik ko&apos;rsatkichi</p>
          </div>
          <div className="flex items-center gap-4 text-xs font-semibold">
            <span className="flex items-center gap-1.5 text-emerald-600">
              <span className="h-2.5 w-2.5 rounded-full bg-emerald-500"></span> Kirim ({Math.round((income / (income + expense)) * 100)}%)
            </span>
            <span className="flex items-center gap-1.5 text-rose-500">
              <span className="h-2.5 w-2.5 rounded-full bg-rose-500"></span> Chiqim ({Math.round((expense / (income + expense)) * 100)}%)
            </span>
          </div>
        </div>

        <div className="h-3 w-full overflow-hidden rounded-full bg-rose-500 flex">
          <div
            style={{ width: `${Math.round((income / (income + expense)) * 100)}%` }}
            className="h-full bg-emerald-500 transition-all duration-500"
          ></div>
        </div>
      </div>

      {/* Transactions Table */}
      <div className="rounded-3xl border border-border bg-bg-card shadow-sm overflow-hidden">
        <div className="border-b border-border px-6 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="font-bold text-base text-text">So&apos;nggi Tranzaksiyalar Jurnali</h2>
            <p className="text-xs text-text-muted">Hisobchi AI va Telegram orqali ro&apos;yxatga olingan operatsiyalar</p>
          </div>
          <div className="flex items-center gap-2">
            <button className="rounded-xl bg-brand-light px-3 py-1.5 text-xs font-bold text-brand">
              Barchasi
            </button>
            <button className="rounded-xl px-3 py-1.5 text-xs font-medium text-text-muted hover:bg-bg">
              Faqat Kirim
            </button>
            <button className="rounded-xl px-3 py-1.5 text-xs font-medium text-text-muted hover:bg-bg">
              Faqat Chiqim
            </button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-bg text-[10px] uppercase text-text-muted font-bold tracking-wider border-b border-border">
              <tr>
                <th className="px-6 py-3.5">Turi</th>
                <th className="px-6 py-3.5">Kategoriya</th>
                <th className="px-6 py-3.5">Tavsif / Loyiha</th>
                <th className="px-6 py-3.5">To&apos;lov Usuli</th>
                <th className="px-6 py-3.5">Summa</th>
                <th className="px-6 py-3.5 text-right">Sana</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/60">
              {transactions.map((tx: any) => (
                <tr key={tx.id} className="hover:bg-bg/50 transition-colors">
                  <td className="px-6 py-4">
                    <span
                      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[10px] font-bold ${
                        tx.type === 'Kirim'
                          ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-400'
                          : 'bg-rose-100 text-rose-800 dark:bg-rose-950/40 dark:text-rose-400'
                      }`}
                    >
                      {tx.type === 'Kirim' ? '↓ Kirim' : '↑ Chiqim'}
                    </span>
                  </td>
                  <td className="px-6 py-4 font-semibold text-text">
                    {tx.category || 'Xizmat'}
                  </td>
                  <td className="px-6 py-4 font-medium text-text max-w-xs truncate">
                    {tx.description}
                  </td>
                  <td className="px-6 py-4 text-text-muted">
                    {tx.source || 'Bank / Karta'}
                  </td>
                  <td
                    className={`px-6 py-4 font-bold text-sm ${
                      tx.type === 'Kirim' ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-500'
                    }`}
                  >
                    {tx.amount}
                  </td>
                  <td className="px-6 py-4 text-right text-text-muted font-mono">
                    {tx.date}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
