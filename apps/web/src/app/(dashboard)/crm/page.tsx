import React from 'react';
import { getCrmLeads, getCrmDashboardStats } from '@/lib/apiClient';

export default async function CRMDashboard() {
  const stats = await getCrmDashboardStats();
  const leadsData = await getCrmLeads();

  const totalLeads = stats?.leads.total || 0;
  // TODO: Use more specific backend fields if available
  const inNegotiation = stats?.deals.total || 0; 
  const closedThisMonth = stats?.deals.won || 0;
  
  const leads = leadsData?.leads || [];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">CRM & Lidlar</h1>
        <button className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors">
          + Yangi Lid
        </button>
      </div>

      <div className="grid grid-cols-3 gap-6">
        <div className="rounded-2xl border border-gray-100 bg-white p-6 shadow-sm">
          <p className="text-sm font-medium text-gray-500">Jami Lidlar</p>
          <p className="mt-2 text-3xl font-bold text-gray-900">{totalLeads}</p>
        </div>
        <div className="rounded-2xl border border-gray-100 bg-white p-6 shadow-sm">
          <p className="text-sm font-medium text-gray-500">Muzokarada</p>
          <p className="mt-2 text-3xl font-bold text-blue-600">{inNegotiation}</p>
        </div>
        <div className="rounded-2xl border border-gray-100 bg-white p-6 shadow-sm">
          <p className="text-sm font-medium text-gray-500">Yopilgan (Bu oy)</p>
          <p className="mt-2 text-3xl font-bold text-green-600">{closedThisMonth}</p>
        </div>
      </div>

      <div className="rounded-2xl border border-gray-100 bg-white shadow-sm overflow-hidden">
        <div className="border-b border-gray-100 px-6 py-4">
          <h2 className="font-semibold text-gray-900">So&apos;nggi Lidlar</h2>
        </div>
        <table className="w-full text-left text-sm text-gray-600">
          <thead className="bg-gray-50 text-xs uppercase text-gray-500">
            <tr>
              <th className="px-6 py-3">Mijoz Ismi</th>
              <th className="px-6 py-3">Holat / Intent</th>
              <th className="px-6 py-3">Biznes Turi</th>
              <th className="px-6 py-3">Sana</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {leads.length > 0 ? leads.map((lead) => (
              <tr key={lead.user_id} className="hover:bg-gray-50 transition-colors">
                <td className="px-6 py-4 font-medium text-gray-900">{lead.name || 'Noma\'lum'}</td>
                <td className="px-6 py-4">
                  <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                    lead.intent === 'Closed' ? 'bg-green-100 text-green-800' :
                    lead.intent === 'Negotiation' ? 'bg-blue-100 text-blue-800' :
                    'bg-yellow-100 text-yellow-800'
                  }`}>
                    {lead.intent || 'New'}
                  </span>
                </td>
                <td className="px-6 py-4">{lead.business_type || '-'}</td>
                <td className="px-6 py-4">
                  {lead.created_at ? new Date(lead.created_at).toLocaleDateString('uz-UZ') : '-'}
                </td>
              </tr>
            )) : (
              <tr>
                <td colSpan={4} className="px-6 py-8 text-center text-gray-500">
                  Hozircha ma&apos;lumot yo&apos;q.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
