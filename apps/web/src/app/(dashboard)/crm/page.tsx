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
    <div className="space-y-8 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold uppercase tracking-wider text-blue-600 bg-blue-50 dark:bg-blue-950/40 px-2.5 py-0.5 rounded-full">
              AMOCRM V4 PIPELINE
            </span>
            <span className="text-xs text-text-muted">• Hunter-Setter-Farmer</span>
          </div>
          <h1 className="mt-1 text-2xl md:text-3xl font-extrabold tracking-tight text-text">
            Sotuv Voronkasi & Lidlar
          </h1>
          <p className="mt-0.5 text-xs text-text-muted">
            500 ta bitim limiti qat&apos;iy nazoratda: Hozirda <strong>{totalLeads} / 500</strong> ta faol bitim mavjud.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button className="rounded-2xl border border-border bg-bg-card px-4 py-2.5 text-xs font-bold text-text hover:bg-bg transition-all active:scale-[0.98]">
            🔄 Sinxronlash
          </button>
          <button className="rounded-2xl bg-brand text-white px-4 py-2.5 text-xs font-bold hover:bg-brand-hover shadow-md shadow-brand/20 transition-all active:scale-[0.98]">
            + Yangi Lid qo&apos;shish
          </button>
        </div>
      </div>

      {/* 4 Pipeline Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <div className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm">
          <span className="text-xs font-bold uppercase tracking-wider text-text-muted">
            Jami Faol Lidlar
          </span>
          <div className="mt-2 text-3xl font-black tracking-tight text-text">
            {totalLeads}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-text-muted border-t border-border/50 pt-3">
            <span>AmoCRM sig&apos;imi:</span>
            <span className="font-bold text-emerald-600">97.4% band</span>
          </div>
        </div>

        <div className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm">
          <span className="text-xs font-bold uppercase tracking-wider text-text-muted">
            Hunter (Yangi so&apos;rovlar)
          </span>
          <div className="mt-2 text-3xl font-black tracking-tight text-blue-600 dark:text-blue-400">
            {newLeads}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-text-muted border-t border-border/50 pt-3">
            <span>Saralash tezligi:</span>
            <span className="font-semibold text-text">&lt; 15 daqiqa</span>
          </div>
        </div>

        <div className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm">
          <span className="text-xs font-bold uppercase tracking-wider text-text-muted">
            Setter (Muzokarada)
          </span>
          <div className="mt-2 text-3xl font-black tracking-tight text-purple-600 dark:text-purple-400">
            {inNegotiation}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-text-muted border-t border-border/50 pt-3">
            <span>Kutilayotgan summa:</span>
            <span className="font-bold text-purple-600">$42,800</span>
          </div>
        </div>

        <div className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm">
          <span className="text-xs font-bold uppercase tracking-wider text-text-muted">
            Farmer (Yopilgan & LTV)
          </span>
          <div className="mt-2 text-3xl font-black tracking-tight text-emerald-600 dark:text-emerald-400">
            {closedThisMonth}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-text-muted border-t border-border/50 pt-3">
            <span>Konversiya darajasi:</span>
            <span className="font-bold text-emerald-600">28.4%</span>
          </div>
        </div>
      </div>

      {/* Pipeline Stage Bar */}
      <div className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-text">Sotuv Voronkasi Bosqichlari</h3>
          <span className="text-xs text-text-muted font-mono">DeepSales AI Enriched</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
          <div className="rounded-2xl bg-blue-50 dark:bg-blue-950/20 border border-blue-100 dark:border-blue-900/40 p-4">
            <span className="text-[10px] font-bold uppercase text-blue-600">1. Yangi Lid</span>
            <div className="text-xl font-extrabold text-text mt-1">34 ta</div>
            <span className="text-[11px] text-text-muted mt-0.5 block">$18,200</span>
          </div>
          <div className="rounded-2xl bg-amber-50 dark:bg-amber-950/20 border border-amber-100 dark:border-amber-900/40 p-4">
            <span className="text-[10px] font-bold uppercase text-amber-600">2. Brif & Malakalash</span>
            <div className="text-xl font-extrabold text-text mt-1">19 ta</div>
            <span className="text-[11px] text-text-muted mt-0.5 block">$15,400</span>
          </div>
          <div className="rounded-2xl bg-purple-50 dark:bg-purple-950/20 border border-purple-100 dark:border-purple-900/40 p-4">
            <span className="text-[10px] font-bold uppercase text-purple-600">3. KP & Muzokara</span>
            <div className="text-xl font-extrabold text-text mt-1">28 ta</div>
            <span className="text-[11px] text-text-muted mt-0.5 block">$42,800</span>
          </div>
          <div className="rounded-2xl bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-100 dark:border-emerald-900/40 p-4">
            <span className="text-[10px] font-bold uppercase text-emerald-600">4. Shartnoma & Yopildi</span>
            <div className="text-xl font-extrabold text-text mt-1">12 ta</div>
            <span className="text-[11px] text-text-muted mt-0.5 block">$24,600</span>
          </div>
        </div>
      </div>

      {/* Leads Table */}
      <div className="rounded-3xl border border-border bg-bg-card shadow-sm overflow-hidden">
        <div className="border-b border-border px-6 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="font-bold text-base text-text">Faol Lidlar Ro&apos;yxati</h2>
            <p className="text-xs text-text-muted">AmoCRM va Telegram orqali tushgan eng so&apos;nggi muzokaralar</p>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="text"
              placeholder="Lid yoki kompaniya qidirish..."
              className="rounded-xl border border-border bg-bg px-3 py-1.5 text-xs text-text focus:outline-none focus:border-brand w-48"
            />
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-bg text-[10px] uppercase text-text-muted font-bold tracking-wider border-b border-border">
              <tr>
                <th className="px-6 py-3.5">Mijoz / Kompaniya</th>
                <th className="px-6 py-3.5">Sektor / Xizmat</th>
                <th className="px-6 py-3.5">Bosqich & Holat</th>
                <th className="px-6 py-3.5">Byudjet</th>
                <th className="px-6 py-3.5">Mas&apos;ul</th>
                <th className="px-6 py-3.5 text-right">Amallar</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/60">
              {leads.map((lead: any) => (
                <tr key={lead.user_id} className="hover:bg-bg/50 transition-colors">
                  <td className="px-6 py-4">
                    <div className="font-bold text-text">{lead.name}</div>
                    <div className="text-[11px] text-text-muted">{lead.company || lead.phone}</div>
                  </td>
                  <td className="px-6 py-4 font-medium text-text">
                    {lead.business_type || 'Brending & Naming'}
                  </td>
                  <td className="px-6 py-4">
                    <span
                      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[10px] font-bold ${
                        lead.intent === 'Closed'
                          ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-400'
                          : lead.intent === 'Negotiation'
                          ? 'bg-blue-100 text-blue-800 dark:bg-blue-950/40 dark:text-blue-400'
                          : 'bg-amber-100 text-amber-800 dark:bg-amber-950/40 dark:text-amber-400'
                      }`}
                    >
                      {lead.stage || lead.intent}
                    </span>
                  </td>
                  <td className="px-6 py-4 font-extrabold text-brand text-sm">
                    {lead.budget || '$3,000'}
                  </td>
                  <td className="px-6 py-4 text-text-muted">
                    <div className="flex items-center gap-1.5">
                      <span className="h-5 w-5 rounded-full bg-brand-light text-brand flex items-center justify-center text-[10px] font-bold">
                        {(lead.manager || 'B').charAt(0)}
                      </span>
                      <span>{lead.manager || 'Baxtiyorjon'}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <button className="rounded-xl bg-bg border border-border px-3 py-1.5 text-xs font-semibold text-brand hover:bg-brand-light transition-colors">
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
