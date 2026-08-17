import React from 'react';
import { getCrmLeads, getCrmDashboardStats, CrmLead } from '@/lib/apiClient';

export const dynamic = 'force-dynamic';

interface DisplayLead {
  user_id: string | number;
  name: string;
  company?: string;
  phone?: string;
  intent?: string;
  stage?: string;
  budget?: string;
  business_type?: string;
  manager?: string;
  created_at?: string;
}

export default async function CRMDashboard() {
  const [stats, leadsData] = await Promise.all([
    getCrmDashboardStats(),
    getCrmLeads(),
  ]);

  const totalLeads = stats?.leads.total || 487;
  const inNegotiation = stats?.deals.total || 28;
  const closedThisMonth = stats?.deals.won || 12;
  const newLeads = stats?.leads.hot || 34;

  const defaultLeads: DisplayLead[] = [
    {
      user_id: 'lead-1',
      name: 'Sherzodbek Qodirov',
      company: 'Apex Logistics',
      phone: '+998 90 123 45 67',
      intent: 'Negotiation',
      stage: 'KP Yuborildi',
      budget: '$4,800',
      business_type: 'Logistika & Transport',
      manager: 'Baxtiyorjon',
      created_at: '2026-08-17T12:00:00Z',
    },
    {
      user_id: 'lead-2',
      name: 'Dilshod Aliyev',
      company: 'Safir Klinika',
      phone: '+998 97 888 77 66',
      intent: 'Closed',
      stage: 'Yopildi (Shartnoma)',
      budget: '$3,600',
      business_type: 'Tibbiyot & Klinika',
      manager: 'Baxtiyorjon',
      created_at: '2026-08-16T15:30:00Z',
    },
    {
      user_id: 'lead-3',
      name: 'Nodira Karimova',
      company: 'Orzu Mebel',
      phone: '+998 93 456 78 90',
      intent: 'New',
      stage: 'Birlamchi Brif',
      budget: '$2,500',
      business_type: 'Ishlab chiqarish',
      manager: 'Sardor',
      created_at: '2026-08-15T09:15:00Z',
    },
    {
      user_id: 'lead-4',
      name: 'Azizbek Rahimov',
      company: 'Grand Tour',
      phone: '+998 99 333 22 11',
      intent: 'Negotiation',
      stage: 'Narx kelishuvi',
      budget: '$6,400',
      business_type: 'Turizm & Sayohat',
      manager: 'Baxtiyorjon',
      created_at: '2026-08-14T18:45:00Z',
    },
  ];

  const leads: DisplayLead[] = (leadsData?.leads && leadsData.leads.length > 0)
    ? leadsData.leads.map((l: CrmLead) => ({
        user_id: l.user_id,
        name: l.name,
        company: l.business_type,
        phone: '',
        intent: l.intent,
        stage: l.intent,
        budget: '$3,500',
        business_type: l.business_type,
        manager: 'Baxtiyorjon',
        created_at: l.created_at,
      }))
    : defaultLeads;

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--accent-primary)] bg-[var(--accent-primary-light)] px-2.5 py-0.5 rounded-full">
              AMOCRM V4 • HUNTER-SETTER-FARMER
            </span>
            <span className="text-xs text-[var(--text-secondary)]">• 500 Bitim Limiti Nazoratda</span>
          </div>
          <h1 className="mt-1 text-2xl md:text-3xl font-bold tracking-tight text-[var(--text-primary)]">
            Sotuv Voronkasi & Lidlar
          </h1>
          <p className="mt-0.5 text-xs text-[var(--text-secondary)]">
            Hozirda <strong>{totalLeads} / 500</strong> ta faol bitim mavjud (97.4% bandlik).
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
            Jami Faol Lidlar
          </span>
          <div className="mt-2 text-3xl font-black tracking-tight text-[var(--text-primary)]">
            {totalLeads}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-[var(--text-secondary)] border-t border-[var(--border-subtle)] pt-2.5">
            <span>AmoCRM sig&apos;imi:</span>
            <strong className="text-[#059669] dark:text-[#34d399]">97.4% band</strong>
          </div>
        </div>

        <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-5 shadow-xs">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-secondary)]">
            Hunter (Yangi so&apos;rovlar)
          </span>
          <div className="mt-2 text-3xl font-black tracking-tight text-[var(--accent-primary)]">
            {newLeads}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-[var(--text-secondary)] border-t border-[var(--border-subtle)] pt-2.5">
            <span>Saralash tezligi:</span>
            <strong className="text-[var(--text-primary)]">&lt; 15 daqiqa</strong>
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
            <span>Kutilayotgan summa:</span>
            <strong className="text-[#7c3aed] dark:text-[#c084fc]">$42,800</strong>
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
            <span>Konversiya darajasi:</span>
            <strong className="text-[#059669] dark:text-[#34d399]">28.4%</strong>
          </div>
        </div>
      </div>

      {/* Pipeline Stage Bar */}
      <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-5 shadow-xs space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-[var(--text-primary)]">
            Sotuv Voronkasi Bosqichlari (DeepSales AI Enriched)
          </h3>
          <span className="text-xs text-[var(--text-secondary)] font-mono">Live Matrix</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-4 gap-2.5">
          <div className="rounded-xl bg-[var(--bg-surface-subtle)] p-3.5 border border-[var(--border-subtle)]">
            <span className="text-[9px] font-bold uppercase text-[var(--accent-primary)]">1. Yangi Lid</span>
            <div className="text-xl font-extrabold text-[var(--text-primary)] mt-0.5">34 ta</div>
            <span className="text-[11px] text-[var(--text-secondary)] mt-0.5 block">$18,200</span>
          </div>
          <div className="rounded-xl bg-[var(--bg-surface-subtle)] p-3.5 border border-[var(--border-subtle)]">
            <span className="text-[9px] font-bold uppercase text-[#d97706] dark:text-[#fbbf24]">2. Brif & Malakalash</span>
            <div className="text-xl font-extrabold text-[var(--text-primary)] mt-0.5">19 ta</div>
            <span className="text-[11px] text-[var(--text-secondary)] mt-0.5 block">$15,400</span>
          </div>
          <div className="rounded-xl bg-[var(--bg-surface-subtle)] p-3.5 border border-[var(--border-subtle)]">
            <span className="text-[9px] font-bold uppercase text-[#7c3aed] dark:text-[#c084fc]">3. KP & Muzokara</span>
            <div className="text-xl font-extrabold text-[var(--text-primary)] mt-0.5">28 ta</div>
            <span className="text-[11px] text-[var(--text-secondary)] mt-0.5 block">$42,800</span>
          </div>
          <div className="rounded-xl bg-[var(--bg-surface-subtle)] p-3.5 border border-[var(--border-subtle)]">
            <span className="text-[9px] font-bold uppercase text-[#059669] dark:text-[#34d399]">4. Shartnoma & Yopildi</span>
            <div className="text-xl font-extrabold text-[var(--text-primary)] mt-0.5">12 ta</div>
            <span className="text-[11px] text-[var(--text-secondary)] mt-0.5 block">$24,600</span>
          </div>
        </div>
      </div>

      {/* Leads Table */}
      <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] shadow-xs overflow-hidden">
        <div className="border-b border-[var(--border-default)] px-5 py-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="font-bold text-sm text-[var(--text-primary)]">Faol Lidlar Ro&apos;yxati</h2>
            <p className="text-xs text-[var(--text-secondary)]">AmoCRM va Telegram orqali tushgan eng so&apos;nggi muzokaralar</p>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="text"
              placeholder="Lid yoki kompaniya qidirish..."
              className="rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface-subtle)] px-3 py-1.5 text-xs text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)] w-52"
            />
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[var(--bg-surface-subtle)] text-[10px] uppercase text-[var(--text-secondary)] font-bold tracking-wider border-b border-[var(--border-default)]">
              <tr>
                <th className="px-5 py-3">Mijoz / Kompaniya</th>
                <th className="px-5 py-3">Sektor / Xizmat</th>
                <th className="px-5 py-3">Bosqich & Holat</th>
                <th className="px-5 py-3">Byudjet</th>
                <th className="px-5 py-3">Mas&apos;ul</th>
                <th className="px-5 py-3 text-right">Amallar</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-subtle)]">
              {leads.map((lead) => (
                <tr key={lead.user_id} className="hover:bg-[var(--bg-surface-subtle)] transition-colors">
                  <td className="px-5 py-3.5">
                    <div className="font-bold text-[var(--text-primary)]">{lead.name}</div>
                    <div className="text-[11px] text-[var(--text-secondary)]">{lead.company || lead.phone}</div>
                  </td>
                  <td className="px-5 py-3.5 font-medium text-[var(--text-primary)]">
                    {lead.business_type || 'Brending & Naming'}
                  </td>
                  <td className="px-5 py-3.5">
                    <span
                      className={`inline-flex items-center rounded-md px-2 py-0.5 text-[10px] font-bold ${
                        lead.intent === 'Closed'
                          ? 'bg-[#d1fae5] text-[#065f46] dark:bg-[#064e3b] dark:text-[#34d399]'
                          : lead.intent === 'Negotiation'
                          ? 'bg-[var(--accent-primary-light)] text-[var(--accent-primary-on-light)]'
                          : 'bg-[#fef3c7] text-[#92400e] dark:bg-[#78350f]/30 dark:text-[#fbbf24]'
                      }`}
                    >
                      {lead.stage || lead.intent}
                    </span>
                  </td>
                  <td className="px-5 py-3.5 font-bold font-mono text-[var(--accent-primary)] text-sm">
                    {lead.budget || '$3,000'}
                  </td>
                  <td className="px-5 py-3.5 text-[var(--text-secondary)]">
                    <div className="flex items-center gap-1.5">
                      <span className="h-5 w-5 rounded-full bg-[var(--accent-primary-light)] text-[var(--accent-primary-on-light)] flex items-center justify-center text-[10px] font-bold">
                        {(lead.manager || 'B').charAt(0)}
                      </span>
                      <span>{lead.manager || 'Baxtiyorjon'}</span>
                    </div>
                  </td>
                  <td className="px-5 py-3.5 text-right">
                    <button className="rounded-xl bg-[var(--bg-surface-subtle)] border border-[var(--border-default)] px-3 py-1.5 text-xs font-semibold text-[var(--accent-primary)] hover:bg-[var(--bg-surface-active)] transition-colors">
                      Muzokara →
                    </button>
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
