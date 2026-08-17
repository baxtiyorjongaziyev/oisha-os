import React from 'react';
import { getFinanceDashboardStats, getFinanceTransactions, FinanceTransaction } from '@/lib/apiClient';

export const dynamic = 'force-dynamic';

interface DisplayTransaction {
  id: string | number;
  type: string;
  amount: string;
  description: string;
  date: string;
  category?: string;
  source?: string;
}

export default async function FinanceDashboard() {
  const [stats, txData] = await Promise.all([
    getFinanceDashboardStats(),
    getFinanceTransactions(),
  ]);

  const balance = stats?.balance || 18450;
  const income = stats?.monthly_income || 14200;
  const expense = stats?.monthly_expense || 5800;
  const netProfit = income - expense;
  const profitMargin = income > 0 ? Math.round((netProfit / income) * 100) : 59;

  const defaultTransactions: DisplayTransaction[] = [
    {
      id: 'tx-1',
      type: 'Kirim',
      amount: '+$2,400.00',
      description: '"Apex Logistics" — Brendbuk va Qadoq dizayni 50% avansi',
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

  const transactions: DisplayTransaction[] = (txData?.transactions && txData.transactions.length > 0)
    ? txData.transactions.map((tx: FinanceTransaction) => ({
        id: tx.id,
        type: tx.type,
        amount: tx.amount,
        description: tx.description,
        date: tx.date,
        category: 'Xizmat haqi',
        source: 'Bank / Karta',
      }))
    : defaultTransactions;

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#059669] dark:text-[#34d399] bg-[#d1fae5] dark:bg-[#064e3b] px-2.5 py-0.5 rounded-full">
              STRIPE-GRADE FINANCIAL LEDGER
            </span>
            <span className="text-xs text-[var(--text-secondary)]">• Hisobchi AI (24/7 Sinxron)</span>
          </div>
          <h1 className="mt-1 text-2xl md:text-3xl font-bold tracking-tight text-[var(--text-primary)]">
            Moliya & Kassa Boshqaruvi
          </h1>
          <p className="mt-0.5 text-xs text-[var(--text-secondary)]">
            Telegram bot (@jonairobot), SMS bank bildirishnomalari va hisob-kitoblar avtomatlashgan.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button className="rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface-subtle)] text-[#dc2626] dark:text-[#f87171] px-4 py-2 text-xs font-bold hover:bg-[var(--bg-surface-active)] transition-all active:scale-[0.98]">
            - Chiqim kiritish
          </button>
          <button className="rounded-xl bg-[#059669] text-white px-5 py-2 text-xs font-bold shadow-xs hover:opacity-90 transition-all active:scale-[0.98]">
            + Kirim kiritish
          </button>
        </div>
      </div>

      {/* 4 Financial Tonal Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-5 shadow-xs">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-secondary)]">
            Jami Kassa Balansi
          </span>
          <div className="mt-2 text-3xl font-black tracking-tight text-[var(--text-primary)]">
            ${balance.toLocaleString()}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-[var(--text-secondary)] border-t border-[var(--border-subtle)] pt-2.5">
            <span>Bank: <strong>$12,300</strong></span>
            <span>Naqd: <strong>$6,150</strong></span>
          </div>
        </div>

        <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-5 shadow-xs">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-secondary)]">
            Oylik Kirim (Tushum)
          </span>
          <div className="mt-2 text-3xl font-black tracking-tight text-[#059669] dark:text-[#34d399]">
            +${income.toLocaleString()}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-[var(--text-secondary)] border-t border-[var(--border-subtle)] pt-2.5">
            <span>O&apos;sish sur&apos;ati:</span>
            <strong className="text-[#059669] dark:text-[#34d399]">+18% o&apos;tgan oydan</strong>
          </div>
        </div>

        <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-5 shadow-xs">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-secondary)]">
            Oylik Chiqim (Xarajat)
          </span>
          <div className="mt-2 text-3xl font-black tracking-tight text-[#dc2626] dark:text-[#f87171]">
            -${expense.toLocaleString()}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-[var(--text-secondary)] border-t border-[var(--border-subtle)] pt-2.5">
            <span>Byudjet chegarasi:</span>
            <strong className="text-[var(--text-primary)]">$8,000 gacha</strong>
          </div>
        </div>

        <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-5 shadow-xs">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-secondary)]">
            Sof Foyda (Net Profit)
          </span>
          <div className="mt-2 text-3xl font-black tracking-tight text-[var(--accent-primary)]">
            +${netProfit.toLocaleString()}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-[var(--text-secondary)] border-t border-[var(--border-subtle)] pt-2.5">
            <span>Rentabellik marjasi:</span>
            <strong className="text-[var(--accent-primary)]">{profitMargin}%</strong>
          </div>
        </div>
      </div>

      {/* Stripe Cashflow Ratio Visualizer */}
      <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-5 shadow-xs space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-bold text-[var(--text-primary)]">
              Kirim va Chiqim Nisbati (Stripe Cashflow Metric)
            </h3>
            <p className="text-xs text-[var(--text-secondary)]">
              Agentlik moliyaviy barqarorlik va oylik likvidlik darajasi
            </p>
          </div>
          <div className="flex items-center gap-4 text-xs font-bold">
            <span className="flex items-center gap-1.5 text-[#059669] dark:text-[#34d399]">
              <span className="h-2 w-2 rounded-full bg-[#059669]"></span> Kirim ({Math.round((income / (income + expense)) * 100)}%)
            </span>
            <span className="flex items-center gap-1.5 text-[#dc2626] dark:text-[#f87171]">
              <span className="h-2 w-2 rounded-full bg-[#dc2626]"></span> Chiqim ({Math.round((expense / (income + expense)) * 100)}%)
            </span>
          </div>
        </div>

        <div className="h-3 w-full overflow-hidden rounded-full bg-[#dc2626] flex">
          <div
            style={{ width: `${Math.round((income / (income + expense)) * 100)}%` }}
            className="h-full bg-[#059669] transition-all duration-500"
          ></div>
        </div>
      </div>

      {/* Transactions Table */}
      <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] shadow-xs overflow-hidden">
        <div className="border-b border-[var(--border-default)] px-5 py-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="font-bold text-sm text-[var(--text-primary)]">
              Oxirgi Tranzaksiyalar Jurnali
            </h2>
            <p className="text-xs text-[var(--text-secondary)]">
              Hisobchi AI va Telegram orqali ro&apos;yxatga olingan real operatsiyalar
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button className="rounded-xl bg-[var(--accent-primary-light)] text-[var(--accent-primary-on-light)] px-3 py-1 text-xs font-bold">
              Barchasi
            </button>
            <button className="rounded-xl px-3 py-1 text-xs font-semibold text-[var(--text-secondary)] hover:bg-[var(--bg-surface-subtle)]">
              Kirimlar
            </button>
            <button className="rounded-xl px-3 py-1 text-xs font-semibold text-[var(--text-secondary)] hover:bg-[var(--bg-surface-subtle)]">
              Chiqimlar
            </button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[var(--bg-surface-subtle)] text-[10px] uppercase text-[var(--text-secondary)] font-bold tracking-wider border-b border-[var(--border-default)]">
              <tr>
                <th className="px-5 py-3">Turi</th>
                <th className="px-5 py-3">Kategoriya</th>
                <th className="px-5 py-3">Tavsif / Mijoz</th>
                <th className="px-5 py-3">To&apos;lov Usuli</th>
                <th className="px-5 py-3">Summa</th>
                <th className="px-5 py-3 text-right">Sana</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-subtle)]">
              {transactions.map((tx) => (
                <tr key={tx.id} className="hover:bg-[var(--bg-surface-subtle)] transition-colors">
                  <td className="px-5 py-3.5">
                    <span
                      className={`inline-flex items-center rounded-md px-2 py-0.5 text-[10px] font-bold ${
                        tx.type === 'Kirim'
                          ? 'bg-[#d1fae5] text-[#065f46] dark:bg-[#064e3b] dark:text-[#34d399]'
                          : 'bg-[#fee2e2] text-[#991b1b] dark:bg-[#7f1d1d]/30 dark:text-[#f87171]'
                      }`}
                    >
                      {tx.type === 'Kirim' ? '↓ Kirim' : '↑ Chiqim'}
                    </span>
                  </td>
                  <td className="px-5 py-3.5 font-semibold text-[var(--text-primary)]">
                    {tx.category || 'Xizmat'}
                  </td>
                  <td className="px-5 py-3.5 font-medium text-[var(--text-primary)] max-w-xs truncate">
                    {tx.description}
                  </td>
                  <td className="px-5 py-3.5 text-[var(--text-secondary)]">
                    {tx.source || 'Bank / Karta'}
                  </td>
                  <td
                    className={`px-5 py-3.5 font-bold font-mono text-sm ${
                      tx.type === 'Kirim' ? 'text-[#059669] dark:text-[#34d399]' : 'text-[#dc2626] dark:text-[#f87171]'
                    }`}
                  >
                    {tx.amount}
                  </td>
                  <td className="px-5 py-3.5 text-right text-[var(--text-secondary)] font-mono">
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
