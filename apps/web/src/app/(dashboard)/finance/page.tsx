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
    <div className="space-y-7 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold uppercase tracking-wider text-[#137333] dark:text-[#6dd58c] bg-[#c4eed0] dark:bg-[#0f5223] px-2.5 py-0.5 rounded-full">
              HISOBCHI AI • REAL-TIME
            </span>
            <span className="text-xs text-[var(--md-sys-color-on-surface-variant)]">• Google Sheets & SMS Sync</span>
          </div>
          <h1 className="mt-1 text-2xl md:text-3xl font-bold tracking-tight text-[var(--md-sys-color-on-surface)]">
            Moliya & Kassa Boshqaruvi
          </h1>
          <p className="mt-0.5 text-xs text-[var(--md-sys-color-on-surface-variant)]">
            Telegram bot (@jonairobot), SMS bank bildirishnomalari va hisob-kitoblar avtomatlashgan.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button className="rounded-full border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface-container)] text-[#b3261e] dark:text-[#f28b82] px-4 py-2.5 text-xs font-bold hover:bg-[var(--md-sys-color-surface-container-high)] transition-all active:scale-[0.98]">
            - Chiqim kiritish
          </button>
          <button className="rounded-full bg-[#137333] dark:bg-[#6dd58c] dark:text-[#041e49] text-white px-5 py-2.5 text-xs font-bold shadow-sm hover:opacity-90 transition-all active:scale-[0.98]">
            + Kirim kiritish
          </button>
        </div>
      </div>

      {/* 4 Financial Tonal Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <div className="rounded-3xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface)] p-6 shadow-sm">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--md-sys-color-on-surface-variant)]">
            Jami Kassa Balansi
          </span>
          <div className="mt-2 text-3xl font-black tracking-tight text-[var(--md-sys-color-on-surface)]">
            ${balance.toLocaleString()}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-[var(--md-sys-color-on-surface-variant)] border-t border-[var(--md-sys-color-outline-variant)] pt-3">
            <span>Bank: <strong>$12,300</strong></span>
            <span>Naqd: <strong>$6,150</strong></span>
          </div>
        </div>

        <div className="rounded-3xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface)] p-6 shadow-sm">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--md-sys-color-on-surface-variant)]">
            Oylik Kirim (Tushum)
          </span>
          <div className="mt-2 text-3xl font-black tracking-tight text-[#137333] dark:text-[#6dd58c]">
            +${income.toLocaleString()}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-[var(--md-sys-color-on-surface-variant)] border-t border-[var(--md-sys-color-outline-variant)] pt-3">
            <span>O&apos;sish sur&apos;ati:</span>
            <strong className="text-[#137333] dark:text-[#6dd58c]">+18% o&apos;tgan oydan</strong>
          </div>
        </div>

        <div className="rounded-3xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface)] p-6 shadow-sm">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--md-sys-color-on-surface-variant)]">
            Oylik Chiqim (Xarajat)
          </span>
          <div className="mt-2 text-3xl font-black tracking-tight text-[#b3261e] dark:text-[#f28b82]">
            -${expense.toLocaleString()}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-[var(--md-sys-color-on-surface-variant)] border-t border-[var(--md-sys-color-outline-variant)] pt-3">
            <span>Byudjet chegarasi:</span>
            <strong className="text-[var(--md-sys-color-on-surface)]">$8,000 gacha</strong>
          </div>
        </div>

        <div className="rounded-3xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface)] p-6 shadow-sm">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--md-sys-color-on-surface-variant)]">
            Sof Foyda (Net Profit)
          </span>
          <div className="mt-2 text-3xl font-black tracking-tight text-[#0b57d0] dark:text-[#a8c7fa]">
            +${netProfit.toLocaleString()}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-[var(--md-sys-color-on-surface-variant)] border-t border-[var(--md-sys-color-outline-variant)] pt-3">
            <span>Rentabellik marjasi:</span>
            <strong className="text-[#0b57d0] dark:text-[#a8c7fa]">{profitMargin}%</strong>
          </div>
        </div>
      </div>

      {/* Cashflow Ratio Visualizer */}
      <div className="rounded-3xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface)] p-6 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-bold text-[var(--md-sys-color-on-surface)]">
              Kirim va Chiqim Oqimi (Cashflow Balance)
            </h3>
            <p className="text-xs text-[var(--md-sys-color-on-surface-variant)]">
              Agentlik moliyaviy barqarorlik va oylik likvidlik darajasi
            </p>
          </div>
          <div className="flex items-center gap-4 text-xs font-bold">
            <span className="flex items-center gap-1.5 text-[#137333] dark:text-[#6dd58c]">
              <span className="h-2.5 w-2.5 rounded-full bg-[#137333] dark:bg-[#6dd58c]"></span> Kirim ({Math.round((income / (income + expense)) * 100)}%)
            </span>
            <span className="flex items-center gap-1.5 text-[#b3261e] dark:text-[#f28b82]">
              <span className="h-2.5 w-2.5 rounded-full bg-[#b3261e] dark:bg-[#f28b82]"></span> Chiqim ({Math.round((expense / (income + expense)) * 100)}%)
            </span>
          </div>
        </div>

        <div className="h-3.5 w-full overflow-hidden rounded-full bg-[#b3261e] dark:bg-[#f28b82] flex">
          <div
            style={{ width: `${Math.round((income / (income + expense)) * 100)}%` }}
            className="h-full bg-[#137333] dark:bg-[#6dd58c] transition-all duration-500"
          ></div>
        </div>
      </div>

      {/* Transactions Table */}
      <div className="rounded-3xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface)] shadow-sm overflow-hidden">
        <div className="border-b border-[var(--md-sys-color-outline)] px-6 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="font-bold text-base text-[var(--md-sys-color-on-surface)]">
              Oxirgi Tranzaksiyalar Jurnali
            </h2>
            <p className="text-xs text-[var(--md-sys-color-on-surface-variant)]">
              Hisobchi AI va Telegram orqali ro&apos;yxatga olingan real operatsiyalar
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button className="rounded-full bg-[#d3e3fd] dark:bg-[#004a77] text-[#041e49] dark:text-[#c2e7ff] px-3.5 py-1.5 text-xs font-bold">
              Barchasi
            </button>
            <button className="rounded-full px-3.5 py-1.5 text-xs font-semibold text-[var(--md-sys-color-on-surface-variant)] hover:bg-[var(--md-sys-color-surface-container)]">
              Kirimlar
            </button>
            <button className="rounded-full px-3.5 py-1.5 text-xs font-semibold text-[var(--md-sys-color-on-surface-variant)] hover:bg-[var(--md-sys-color-surface-container)]">
              Chiqimlar
            </button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[var(--md-sys-color-surface-container-low)] text-[10px] uppercase text-[var(--md-sys-color-on-surface-variant)] font-bold tracking-wider border-b border-[var(--md-sys-color-outline)]">
              <tr>
                <th className="px-6 py-3.5">Turi</th>
                <th className="px-6 py-3.5">Kategoriya</th>
                <th className="px-6 py-3.5">Tavsif / Mijoz</th>
                <th className="px-6 py-3.5">To&apos;lov Usuli</th>
                <th className="px-6 py-3.5">Summa</th>
                <th className="px-6 py-3.5 text-right">Sana</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--md-sys-color-outline-variant)]">
              {transactions.map((tx) => (
                <tr key={tx.id} className="hover:bg-[var(--md-sys-color-surface-container-low)] transition-colors">
                  <td className="px-6 py-4">
                    <span
                      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[10px] font-bold ${
                        tx.type === 'Kirim'
                          ? 'bg-[#c4eed0] text-[#0f5223] dark:bg-[#0f5223] dark:text-[#6dd58c]'
                          : 'bg-[#ffdad6] text-[#601410] dark:bg-[#601410] dark:text-[#f28b82]'
                      }`}
                    >
                      {tx.type === 'Kirim' ? '↓ Kirim' : '↑ Chiqim'}
                    </span>
                  </td>
                  <td className="px-6 py-4 font-semibold text-[var(--md-sys-color-on-surface)]">
                    {tx.category || 'Xizmat'}
                  </td>
                  <td className="px-6 py-4 font-medium text-[var(--md-sys-color-on-surface)] max-w-xs truncate">
                    {tx.description}
                  </td>
                  <td className="px-6 py-4 text-[var(--md-sys-color-on-surface-variant)]">
                    {tx.source || 'Bank / Karta'}
                  </td>
                  <td
                    className={`px-6 py-4 font-black text-sm ${
                      tx.type === 'Kirim' ? 'text-[#137333] dark:text-[#6dd58c]' : 'text-[#b3261e] dark:text-[#f28b82]'
                    }`}
                  >
                    {tx.amount}
                  </td>
                  <td className="px-6 py-4 text-right text-[var(--md-sys-color-on-surface-variant)] font-mono">
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
