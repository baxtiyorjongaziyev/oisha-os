import React from 'react';
import { getCrmLeads, getCrmDashboardStats } from '@/lib/apiClient';

export const dynamic = 'force-dynamic';

export default async function CRMDashboard() {
  const [stats, leadsData] = await Promise.all([
    getCrmDashboardStats(),
    getCrmLeads(),
  ]);

  const totalLeads = stats?.leads.total || 487;
  const inNegotiation = stats?.deals.total || 28;
  const closedThisMonth = stats?.deals.won || 12;
  const newLeads = stats?.leads.hot || 34;

  const leads = leadsData?.leads && leadsData.leads.length > 0 ? leadsData.leads : [
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
      created_at: new Date().toISOString(),
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
      created_at: new Date(Date.now() - 86400000).toISOString(),
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
      created_at: new Date(Date.now() - 172800000).toISOString(),
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
      created_at: new Date(Date.now() - 259200000).toISOString(),
    },
  ];

  return (
    <div className="space-y-7 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold uppercase tracking-wider text-[#0b57d0] dark:text-[#a8c7fa] bg-[#d3e3fd] dark:bg-[#004a77] px-2.5 py-0.5 rounded-full">
              AMOCRM V4 • HUNTER-SETTER-FARMER
            </span>
            <span className="text-xs text-[var(--md-sys-color-on-surface-variant)]">• 500 Bitim Limiti Nazoratda</span>
          </div>
          <h1 className="mt-1 text-2xl md:text-3xl font-bold tracking-tight text-[var(--md-sys-color-on-surface)]">
            Sotuv Voronkasi & Lidlar
          </h1>
          <p className="mt-0.5 text-xs text-[var(--md-sys-color-on-surface-variant)]">
            Hozirda <strong>{totalLeads} / 500</strong> ta faol bitim mavjud (97.4% bandlik).
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button className="rounded-full border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface-container)] px-4 py-2.5 text-xs font-bold text-[var(--md-sys-color-on-surface)] hover:bg-[var(--md-sys-color-surface-container-high)] transition-all active:scale-[0.98]">
            🔄 Sinxronlash
          </button>
          <button className="rounded-full bg-[#0b57d0] dark:bg-[#a8c7fa] dark:text-[#041e49] text-white px-5 py-2.5 text-xs font-bold shadow-sm hover:opacity-90 transition-all active:scale-[0.98]">
            + Yangi Lid qo&apos;shish
          </button>
        </div>
      </div>

      {/* 4 Pipeline Tonal Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <div className="rounded-3xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface)] p-6 shadow-sm">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--md-sys-color-on-surface-variant)]">
            Jami Faol Lidlar
          </span>
          <div className="mt-2 text-3xl font-black tracking-tight text-[var(--md-sys-color-on-surface)]">
            {totalLeads}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-[var(--md-sys-color-on-surface-variant)] border-t border-[var(--md-sys-color-outline-variant)] pt-3">
            <span>AmoCRM sig&apos;imi:</span>
            <strong className="text-[#137333] dark:text-[#6dd58c]">97.4% band</strong>
          </div>
        </div>

        <div className="rounded-3xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface)] p-6 shadow-sm">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--md-sys-color-on-surface-variant)]">
            Hunter (Yangi so&apos;rovlar)
          </span>
          <div className="mt-2 text-3xl font-black tracking-tight text-[#0b57d0] dark:text-[#a8c7fa]">
            {newLeads}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-[var(--md-sys-color-on-surface-variant)] border-t border-[var(--md-sys-color-outline-variant)] pt-3">
            <span>Saralash tezligi:</span>
            <strong className="text-[var(--md-sys-color-on-surface)]">&lt; 15 daqiqa</strong>
          </div>
        </div>

        <div className="rounded-3xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface)] p-6 shadow-sm">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--md-sys-color-on-surface-variant)]">
            Setter (Muzokarada)
          </span>
          <div className="mt-2 text-3xl font-black tracking-tight text-[#7c3aed] dark:text-[#d0bcff]">
            {inNegotiation}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-[var(--md-sys-color-on-surface-variant)] border-t border-[var(--md-sys-color-outline-variant)] pt-3">
            <span>Kutilayotgan summa:</span>
            <strong className="text-[#7c3aed] dark:text-[#d0bcff]">$42,800</strong>
          </div>
        </div>

        <div className="rounded-3xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface)] p-6 shadow-sm">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--md-sys-color-on-surface-variant)]">
            Farmer (Yopilgan & LTV)
          </span>
          <div className="mt-2 text-3xl font-black tracking-tight text-[#137333] dark:text-[#6dd58c]">
            {closedThisMonth}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-[var(--md-sys-color-on-surface-variant)] border-t border-[var(--md-sys-color-outline-variant)] pt-3">
            <span>Konversiya darajasi:</span>
            <strong className="text-[#137333] dark:text-[#6dd58c]">28.4%</strong>
          </div>
        </div>
      </div>

      {/* Pipeline Stage Bar */}
      <div className="rounded-3xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface)] p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-[var(--md-sys-color-on-surface)]">
            Sotuv Voronkasi Bosqichlari (DeepSales AI Enriched)
          </h3>
          <span className="text-xs text-[var(--md-sys-color-on-surface-variant)] font-mono">Live Matrix</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
          <div className="rounded-2xl bg-[var(--md-sys-color-surface-container-low)] p-4 border border-[var(--md-sys-color-outline-variant)]">
            <span className="text-[10px] font-bold uppercase text-[#0b57d0] dark:text-[#a8c7fa]">1. Yangi Lid</span>
            <div className="text-xl font-extrabold text-[var(--md-sys-color-on-surface)] mt-1">34 ta</div>
            <span className="text-[11px] text-[var(--md-sys-color-on-surface-variant)] mt-0.5 block">$18,200</span>
          </div>
          <div className="rounded-2xl bg-[var(--md-sys-color-surface-container-low)] p-4 border border-[var(--md-sys-color-outline-variant)]">
            <span className="text-[10px] font-bold uppercase text-[#b06000] dark:text-[#fdd663]">2. Brif & Malakalash</span>
            <div className="text-xl font-extrabold text-[var(--md-sys-color-on-surface)] mt-1">19 ta</div>
            <span className="text-[11px] text-[var(--md-sys-color-on-surface-variant)] mt-0.5 block">$15,400</span>
          </div>
          <div className="rounded-2xl bg-[var(--md-sys-color-surface-container-low)] p-4 border border-[var(--md-sys-color-outline-variant)]">
            <span className="text-[10px] font-bold uppercase text-[#7c3aed] dark:text-[#d0bcff]">3. KP & Muzokara</span>
            <div className="text-xl font-extrabold text-[var(--md-sys-color-on-surface)] mt-1">28 ta</div>
            <span className="text-[11px] text-[var(--md-sys-color-on-surface-variant)] mt-0.5 block">$42,800</span>
          </div>
          <div className="rounded-2xl bg-[var(--md-sys-color-surface-container-low)] p-4 border border-[var(--md-sys-color-outline-variant)]">
            <span className="text-[10px] font-bold uppercase text-[#137333] dark:text-[#6dd58c]">4. Shartnoma & Yopildi</span>
            <div className="text-xl font-extrabold text-[var(--md-sys-color-on-surface)] mt-1">12 ta</div>
            <span className="text-[11px] text-[var(--md-sys-color-on-surface-variant)] mt-0.5 block">$24,600</span>
          </div>
        </div>
      </div>

      {/* Leads Table */}
      <div className="rounded-3xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface)] shadow-sm overflow-hidden">
        <div className="border-b border-[var(--md-sys-color-outline)] px-6 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="font-bold text-base text-[var(--md-sys-color-on-surface)]">Faol Lidlar Ro&apos;yxati</h2>
            <p className="text-xs text-[var(--md-sys-color-on-surface-variant)]">AmoCRM va Telegram orqali tushgan eng so&apos;nggi muzokaralar</p>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="text"
              placeholder="Lid yoki kompaniya qidirish..."
              className="rounded-full border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface-container)] px-4 py-1.5 text-xs text-[var(--md-sys-color-on-surface)] focus:outline-none focus:border-[#0b57d0] w-52"
            />
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[var(--md-sys-color-surface-container-low)] text-[10px] uppercase text-[var(--md-sys-color-on-surface-variant)] font-bold tracking-wider border-b border-[var(--md-sys-color-outline)]">
              <tr>
                <th className="px-6 py-3.5">Mijoz / Kompaniya</th>
                <th className="px-6 py-3.5">Sektor / Xizmat</th>
                <th className="px-6 py-3.5">Bosqich & Holat</th>
                <th className="px-6 py-3.5">Byudjet</th>
                <th className="px-6 py-3.5">Mas&apos;ul</th>
                <th className="px-6 py-3.5 text-right">Amallar</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--md-sys-color-outline-variant)]">
              {leads.map((lead: any) => (
                <tr key={lead.user_id} className="hover:bg-[var(--md-sys-color-surface-container-low)] transition-colors">
                  <td className="px-6 py-4">
                    <div className="font-bold text-[var(--md-sys-color-on-surface)]">{lead.name}</div>
                    <div className="text-[11px] text-[var(--md-sys-color-on-surface-variant)]">{lead.company || lead.phone}</div>
                  </td>
                  <td className="px-6 py-4 font-medium text-[var(--md-sys-color-on-surface)]">
                    {lead.business_type || 'Brending & Naming'}
                  </td>
                  <td className="px-6 py-4">
                    <span
                      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[10px] font-bold ${
                        lead.intent === 'Closed'
                          ? 'bg-[#c4eed0] text-[#0f5223] dark:bg-[#0f5223] dark:text-[#6dd58c]'
                          : lead.intent === 'Negotiation'
                          ? 'bg-[#d3e3fd] text-[#041e49] dark:bg-[#004a77] dark:text-[#c2e7ff]'
                          : 'bg-[#feeed2] text-[#4c3200] dark:bg-[#4c3200] dark:text-[#fdd663]'
                      }`}
                    >
                      {lead.stage || lead.intent}
                    </span>
                  </td>
                  <td className="px-6 py-4 font-black text-[#0b57d0] dark:text-[#a8c7fa] text-sm">
                    {lead.budget || '$3,000'}
                  </td>
                  <td className="px-6 py-4 text-[var(--md-sys-color-on-surface-variant)]">
                    <div className="flex items-center gap-1.5">
                      <span className="h-5 w-5 rounded-full bg-[#d3e3fd] text-[#041e49] dark:bg-[#004a77] dark:text-[#c2e7ff] flex items-center justify-center text-[10px] font-bold">
                        {(lead.manager || 'B').charAt(0)}
                      </span>
                      <span>{lead.manager || 'Baxtiyorjon'}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <button className="rounded-full bg-[var(--md-sys-color-surface-container)] border border-[var(--md-sys-color-outline)] px-3.5 py-1.5 text-xs font-semibold text-[#0b57d0] dark:text-[#a8c7fa] hover:bg-[var(--md-sys-color-surface-container-high)] transition-colors">
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
