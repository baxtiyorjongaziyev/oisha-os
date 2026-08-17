import React from 'react';
import { getFinanceDashboardStats, getFinanceTransactions, FinanceTransaction } from '@/lib/apiClient';

export const dynamic = 'force-dynamic';

export default async function FinanceDashboard() {
  const [stats, txData] = await Promise.all([
    getFinanceDashboardStats(),
    getFinanceTransactions(),
  ]);

  const balance = stats?.balance ?? 0;
  const income = stats?.monthly_income ?? 0;
  const expense = stats?.monthly_expense ?? 0;
  const netProfit = income - expense;
  const totalFlow = income + expense;
  const profitMargin = income > 0 ? Math.round((netProfit / income) * 100) : 0;
  const transactions = txData?.transactions ?? [];

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#059669] dark:text-[#34d399] bg-[#d1fae5] dark:bg-[#064e3b] px-2.5 py-0.5 rounded-full">
              STRIPE-GRADE FINANCIAL LEDGER
            </span>
            <span className="text-xs text-[var(--text-secondary)]">• 100% Real Turso DB & Hisobchi AI</span>
          </div>
          <h1 className="mt-1 text-2xl md:text-3xl font-bold tracking-tight text-[var(--text-primary)]">
            Moliya & Kassa Boshqaruvi
          </h1>
          <p className="mt-0.5 text-xs text-[var(--text-secondary)]">
            Telegram bot (@jonairobot), karta SMS to&apos;lovlari va kassa yozuvlari bilan to&apos;liq real vaqtda bog&apos;langan.
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
            ${balance.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-[var(--text-secondary)] border-t border-[var(--border-subtle)] pt-2.5">
            <span>Holat:</span>
            <strong className="text-[#059669] dark:text-[#34d399]">Real Vaqt (Turso)</strong>
          </div>
        </div>

        <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-5 shadow-xs">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-secondary)]">
            Jami Kirim (Tushum)
          </span>
          <div className="mt-2 text-3xl font-black tracking-tight text-[#059669] dark:text-[#34d399]">
            +${income.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-[var(--text-secondary)] border-t border-[var(--border-subtle)] pt-2.5">
            <span>Kirimlar soni:</span>
            <strong className="text-[var(--text-primary)]">
              {transactions.filter(t => t.type === 'Kirim').length} ta
            </strong>
          </div>
        </div>

        <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-5 shadow-xs">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-secondary)]">
            Jami Chiqim (Xarajat)
          </span>
          <div className="mt-2 text-3xl font-black tracking-tight text-[#dc2626] dark:text-[#f87171]">
            -${expense.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-[var(--text-secondary)] border-t border-[var(--border-subtle)] pt-2.5">
            <span>Chiqimlar soni:</span>
            <strong className="text-[var(--text-primary)]">
              {transactions.filter(t => t.type === 'Chiqim').length} ta
            </strong>
          </div>
        </div>

        <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-5 shadow-xs">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-secondary)]">
            Sof Foyda (Net Profit)
          </span>
          <div className={`mt-2 text-3xl font-black tracking-tight ${netProfit >= 0 ? 'text-[var(--accent-primary)]' : 'text-[#dc2626]'}`}>
            {netProfit >= 0 ? '+' : '-'}${Math.abs(netProfit).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-[var(--text-secondary)] border-t border-[var(--border-subtle)] pt-2.5">
            <span>Rentabellik marjasi:</span>
            <strong className="text-[var(--accent-primary)]">{profitMargin}%</strong>
          </div>
        </div>
      </div>

      {/* Stripe Cashflow Ratio Visualizer */}
      {totalFlow > 0 ? (
        <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-5 shadow-xs space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <h3 className="text-sm font-bold text-[var(--text-primary)]">
                Kirim va Chiqim Nisbati (Stripe Cashflow Metric)
              </h3>
              <p className="text-xs text-[var(--text-secondary)]">
                Real tranzaksiyalar asosidagi pul oqimi
              </p>
            </div>
            <div className="flex items-center gap-4 text-xs font-bold">
              <span className="flex items-center gap-1.5 text-[#059669] dark:text-[#34d399]">
                <span className="h-2 w-2 rounded-full bg-[#059669]"></span> Kirim ({Math.round((income / totalFlow) * 100)}%)
              </span>
              <span className="flex items-center gap-1.5 text-[#dc2626] dark:text-[#f87171]">
                <span className="h-2 w-2 rounded-full bg-[#dc2626]"></span> Chiqim ({Math.round((expense / totalFlow) * 100)}%)
              </span>
            </div>
          </div>

          <div className="h-3 w-full overflow-hidden rounded-full bg-[#dc2626] flex">
            <div
              style={{ width: `${Math.round((income / totalFlow) * 100)}%` }}
              className="h-full bg-[#059669] transition-all duration-500"
            ></div>
          </div>
        </div>
      ) : null}

      {/* Transactions Table */}
      <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] shadow-xs overflow-hidden">
        <div className="border-b border-[var(--border-default)] px-5 py-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="font-bold text-sm text-[var(--text-primary)]">
              Oxirgi Tranzaksiyalar Jurnali
            </h2>
            <p className="text-xs text-[var(--text-secondary)]">
              Turso libSQL va Hisobchi AI orqali yozilgan real operatsiyalar ({transactions.length} ta)
            </p>
          </div>
        </div>

        {transactions.length === 0 ? (
          <div className="py-14 text-center">
            <div className="text-3xl mb-2">🧾</div>
            <h3 className="font-bold text-sm text-[var(--text-primary)]">Hozircha tranzaksiyalar mavjud emas</h3>
            <p className="text-xs text-[var(--text-secondary)] mt-1 max-w-sm mx-auto">
              Telegram orqali /kirim yoki /chiqim buyruqlari bilan yozilgan yozuvlar shu yerda real vaqtda aks etadi.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[var(--bg-surface-subtle)] text-[10px] uppercase text-[var(--text-secondary)] font-bold tracking-wider border-b border-[var(--border-default)]">
                <tr>
                  <th className="px-5 py-3">Turi</th>
                  <th className="px-5 py-3">Kategoriya</th>
                  <th className="px-5 py-3">Tavsif / Mijoz</th>
                  <th className="px-5 py-3">To&apos;lov Manbasi</th>
                  <th className="px-5 py-3">Summa</th>
                  <th className="px-5 py-3 text-right">Sana</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-subtle)]">
                {transactions.map((tx: FinanceTransaction) => (
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
        )}
      </div>
    </div>
  );
}
