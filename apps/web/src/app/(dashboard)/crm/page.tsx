import React from 'react';
import { getCrmLeads, getCrmDashboardStats, CrmLead } from '@/lib/apiClient';

export const dynamic = 'force-dynamic';

export default async function CRMDashboard() {
  const [stats, leadsData] = await Promise.all([
    getCrmDashboardStats(),
    getCrmLeads(),
  ]);

  const totalLeads = stats?.leads?.total ?? leadsData?.total ?? 0;
  const newLeads = stats?.leads?.hot ?? 0;
  const inNegotiation = stats?.deals?.total ?? 0;
  const closedThisMonth = stats?.deals?.won ?? 0;
  const leads = leadsData?.leads ?? [];

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--accent-primary)] bg-[var(--accent-primary-light)] px-2.5 py-0.5 rounded-full">
              AMOCRM V4 & TURSO DB
            </span>
            <span className="text-xs text-[var(--text-secondary)]">• 100% Real Lidlar Bazasi</span>
          </div>
          <h1 className="mt-1 text-2xl md:text-3xl font-bold tracking-tight text-[var(--text-primary)]">
            Sotuv Voronkasi & Lidlar
          </h1>
          <p className="mt-0.5 text-xs text-[var(--text-secondary)]">
            Bazada jami <strong>{totalLeads}</strong> ta foydalanuvchi/lid ro&apos;yxatga olingan. 500 bitim limiti nazoratda.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button className="rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface-subtle)] px-4 py-2 text-xs font-bold text-[var(--text-primary)] hover:bg-[var(--bg-surface-active)] transition-all active:scale-[0.98]">
            🔄 Sinxronlash
          </button>
          <button className="rounded-xl bg-[var(--accent-primary)] text-white px-5 py-2 text-xs font-bold shadow-xs hover:opacity-90 transition-all active:scale-[0.98]">
            + Yangi Lid qo&apos;shish
          </button>
        </div>
      </div>

      {/* 4 Pipeline Tonal Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-5 shadow-xs">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-secondary)]">
            Jami Real Lidlar
          </span>
          <div className="mt-2 text-3xl font-black tracking-tight text-[var(--text-primary)]">
            {totalLeads}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-[var(--text-secondary)] border-t border-[var(--border-subtle)] pt-2.5">
            <span>500 Limit bandligi:</span>
            <strong className="text-[#059669] dark:text-[#34d399]">{((totalLeads / 500) * 100).toFixed(1)}%</strong>
          </div>
        </div>

        <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-5 shadow-xs">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-secondary)]">
            Hunter (Yangi & Issiq)
          </span>
          <div className="mt-2 text-3xl font-black tracking-tight text-[var(--accent-primary)]">
            {newLeads}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-[var(--text-secondary)] border-t border-[var(--border-subtle)] pt-2.5">
            <span>Bugun qo&apos;shilgan:</span>
            <strong className="text-[var(--text-primary)]">{stats?.contacts?.new_today ?? 0} ta</strong>
          </div>
        </div>

        <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-5 shadow-xs">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-secondary)]">
            Setter (Muzokarada)
          </span>
          <div className="mt-2 text-3xl font-black tracking-tight text-[#7c3aed] dark:text-[#c084fc]">
            {inNegotiation}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-[var(--text-secondary)] border-t border-[var(--border-subtle)] pt-2.5">
            <span>Kutilayotgan vazifalar:</span>
            <strong className="text-[#7c3aed] dark:text-[#c084fc]">{stats?.tasks?.pending ?? 0} ta</strong>
          </div>
        </div>

        <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-5 shadow-xs">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-secondary)]">
            Farmer (Yopilgan & LTV)
          </span>
          <div className="mt-2 text-3xl font-black tracking-tight text-[#059669] dark:text-[#34d399]">
            {closedThisMonth}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-[var(--text-secondary)] border-t border-[var(--border-subtle)] pt-2.5">
            <span>Mijozlar bazasi:</span>
            <strong className="text-[#059669] dark:text-[#34d399]">Doimiy monitoring</strong>
          </div>
        </div>
      </div>

      {/* Leads Table */}
      <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] shadow-xs overflow-hidden">
        <div className="border-b border-[var(--border-default)] px-5 py-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="font-bold text-sm text-[var(--text-primary)]">Faol Lidlar Ro&apos;yxati</h2>
            <p className="text-xs text-[var(--text-secondary)]">Turso bazasidagi real Telegram foydalanuvchilari va so&apos;rovlari ({leads.length} ta)</p>
          </div>
        </div>

        {leads.length === 0 ? (
          <div className="py-14 text-center">
            <div className="text-3xl mb-2">👥</div>
            <h3 className="font-bold text-sm text-[var(--text-primary)]">Hozircha lidlar mavjud emas</h3>
            <p className="text-xs text-[var(--text-secondary)] mt-1 max-w-sm mx-auto">
              Telegram bot orqali yangi foydalanuvchi yozganda yoki AmoCRM dan sinxronlanganda bu yerda real vaqtda ko&apos;rinadi.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[var(--bg-surface-subtle)] text-[10px] uppercase text-[var(--text-secondary)] font-bold tracking-wider border-b border-[var(--border-default)]">
                <tr>
                  <th className="px-5 py-3">Mijoz / Foydalanuvchi</th>
                  <th className="px-5 py-3">Niyat / Kategoriya</th>
                  <th className="px-5 py-3">Hudud</th>
                  <th className="px-5 py-3">Mas&apos;ul</th>
                  <th className="px-5 py-3 text-right">Ro&apos;yxatdan o&apos;tgan sana</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-subtle)]">
                {leads.map((lead: CrmLead) => (
                  <tr key={lead.user_id} className="hover:bg-[var(--bg-surface-subtle)] transition-colors">
                    <td className="px-5 py-3.5">
                      <div className="font-bold text-[var(--text-primary)]">{lead.name}</div>
                      <div className="text-[11px] text-[var(--text-secondary)]">ID: #{lead.user_id} • {lead.business_type}</div>
                    </td>
                    <td className="px-5 py-3.5">
                      <span className="inline-flex items-center rounded-md px-2 py-0.5 text-[10px] font-bold bg-[var(--accent-primary-light)] text-[var(--accent-primary-on-light)]">
                        {lead.intent || "Yangi lid"}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 font-medium text-[var(--text-primary)]">
                      {lead.region || "O'zbekiston"}
                    </td>
                    <td className="px-5 py-3.5 text-[var(--text-secondary)]">
                      <div className="flex items-center gap-1.5">
                        <span className="h-5 w-5 rounded-full bg-[var(--accent-primary-light)] text-[var(--accent-primary-on-light)] flex items-center justify-center text-[10px] font-bold">
                          {(lead.assigned_to || 'O').charAt(0)}
                        </span>
                        <span>{lead.assigned_to || 'Oisha AI'}</span>
                      </div>
                    </td>
                    <td className="px-5 py-3.5 text-right font-mono text-[var(--text-secondary)]">
                      {lead.created_at ? lead.created_at.slice(0, 16).replace('T', ' ') : '—'}
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
