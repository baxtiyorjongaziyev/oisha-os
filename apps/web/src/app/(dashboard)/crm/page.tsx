import React from 'react';

export default function CRMDashboard() {
  const dummyLeads = [
    { id: 1, name: 'Anvar Sobirov', status: 'Negotiation', amount: '$1,200', date: '2026-07-20' },
    { id: 2, name: 'Zarina Rustamova', status: 'Qualify', amount: '$850', date: '2026-07-19' },
    { id: 3, name: 'Behzod Aliyev', status: 'Closed', amount: '$3,400', date: '2026-07-18' },
  ];

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
          <p className="mt-2 text-3xl font-bold text-gray-900">142</p>
        </div>
        <div className="rounded-2xl border border-gray-100 bg-white p-6 shadow-sm">
          <p className="text-sm font-medium text-gray-500">Muzokarada</p>
          <p className="mt-2 text-3xl font-bold text-blue-600">38</p>
        </div>
        <div className="rounded-2xl border border-gray-100 bg-white p-6 shadow-sm">
          <p className="text-sm font-medium text-gray-500">Yopilgan (Bu oy)</p>
          <p className="mt-2 text-3xl font-bold text-green-600">24</p>
        </div>
      </div>

      <div className="rounded-2xl border border-gray-100 bg-white shadow-sm overflow-hidden">
        <div className="border-b border-gray-100 px-6 py-4">
          <h2 className="font-semibold text-gray-900">So'nggi Lidlar</h2>
        </div>
        <table className="w-full text-left text-sm text-gray-600">
          <thead className="bg-gray-50 text-xs uppercase text-gray-500">
            <tr>
              <th className="px-6 py-3">Mijoz Ismi</th>
              <th className="px-6 py-3">Holat</th>
              <th className="px-6 py-3">Summa</th>
              <th className="px-6 py-3">Sana</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {dummyLeads.map((lead) => (
              <tr key={lead.id} className="hover:bg-gray-50 transition-colors">
                <td className="px-6 py-4 font-medium text-gray-900">{lead.name}</td>
                <td className="px-6 py-4">
                  <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                    lead.status === 'Closed' ? 'bg-green-100 text-green-800' :
                    lead.status === 'Negotiation' ? 'bg-blue-100 text-blue-800' :
                    'bg-yellow-100 text-yellow-800'
                  }`}>
                    {lead.status}
                  </span>
                </td>
                <td className="px-6 py-4">{lead.amount}</td>
                <td className="px-6 py-4">{lead.date}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
