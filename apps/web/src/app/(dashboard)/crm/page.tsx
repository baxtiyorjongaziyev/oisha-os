import React from 'react';
import { getCrmLeads, CrmLead } from '@/lib/apiClient';

export const dynamic = 'force-dynamic';

export default async function CRMDashboard() {
  const leadsData = await getCrmLeads();
  const leads = leadsData?.leads ?? [];

  return (
    <div className="space-y-6 pb-12">
      {/* Asosiy CRM: oddiy sahifa (amoCRM "Sotuv" voronkasi) */}
      <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-6 shadow-xs flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-[var(--text-primary)]">
            Mijozlar
          </h1>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            Mijoz qo&apos;shish, qo&apos;ng&apos;iroq yozish va bosqichni o&apos;zgartirish oddiy CRM sahifasida.
          </p>
        </div>
        <a
          href="/api/simple-crm/"
          className="rounded-xl bg-[var(--accent-primary)] text-white px-6 py-4 text-lg font-bold text-center hover:opacity-90"
        >
          CRM&apos;ni ochish
        </a>
      </div>

      {/* Leads Table */}
      <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] shadow-xs overflow-hidden">
        <div className="border-b border-[var(--border-default)] px-5 py-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="font-bold text-sm text-[var(--text-primary)]">Telegram foydalanuvchilari</h2>
            <p className="text-xs text-[var(--text-secondary)]">Bot bilan yozishgan foydalanuvchilar ({leads.length} ta). Bu amoCRM bitimlari emas.</p>
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
