"use client";

import React, { useState, useEffect } from 'react';
import { Card, Badge } from '@salescoach/ui';

export default function MarketingDashboard() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Demo maqsadida localhost API chaqiriladi yoki frontend tomondan mock datadan foydalaniladi
    fetch('http://localhost:8000/api/marketing/performance')
      .then(res => res.json())
      .then(d => {
        setData(d);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return <div className="p-8 text-center text-gray-500">Yuklanmoqda...</div>;
  }

  if (!data || !data.summary) {
    return <div className="p-8 text-center text-red-500">API bilan ulanishda xatolik yuz berdi.</div>;
  }

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-60 border-r border-[var(--border)] flex flex-col p-4 gap-1 shrink-0 bg-white">
        <div className="px-3 py-4 mb-4">
          <h1 className="font-bold text-lg" style={{
            background: 'linear-gradient(90deg, var(--accent-cyan), #c084fc)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
          }}>
            SALESCOACH AI
          </h1>
          <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>Autonomous Negotiations</p>
        </div>
        <a href="/dashboard">
          <div className="nav-item">📊 Dashboard</div>
        </a>
        <a href="/marketing">
          <div className="nav-item active">📈 Adtru AI</div>
        </a>
        <a href="/calls/upload">
          <div className="nav-item">⬆️ Upload Call</div>
        </a>
        <a href="/negotiate">
          <div className="nav-item">🤝 Negotiate</div>
        </a>
        <div className="nav-item">📈 Analytics</div>
        <div className="nav-item">⚙️ Settings</div>
        <div className="flex-1" />
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-y-auto p-8 bg-gray-50">
        <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Marketing Analytics</h1>
          <p className="text-gray-500">Ad performance overview (Meta Ads + AmoCRM)</p>
        </div>
        <div className="bg-white border rounded-md px-4 py-2 text-sm text-gray-600 shadow-sm">
          1 May 2026 - 31 May 2026
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 lg:grid-cols-8 gap-4 mb-8">
        <div className="bg-white p-4 rounded-lg shadow-sm border">
          <div className="text-xs text-gray-500 mb-1 font-semibold uppercase tracking-wider">Amount Spent</div>
          <div className="text-xl font-bold text-gray-900">${data.summary.amount_spent.toLocaleString()}</div>
        </div>
        <div className="bg-white p-4 rounded-lg shadow-sm border lg:col-span-2">
          <div className="text-xs text-gray-500 mb-1 font-semibold uppercase tracking-wider">Revenue</div>
          <div className="text-xl font-bold text-gray-900">${data.summary.revenue.toLocaleString()}</div>
          <div className="text-xs text-gray-400 mt-1">71% from Meta ads</div>
        </div>
        <div className="bg-white p-4 rounded-lg shadow-sm border">
          <div className="text-xs text-gray-500 mb-1 font-semibold uppercase tracking-wider">ROAS</div>
          <div className="text-xl font-bold text-gray-900">{data.summary.roas}x</div>
        </div>
        <div className="bg-white p-4 rounded-lg shadow-sm border">
          <div className="text-xs text-gray-500 mb-1 font-semibold uppercase tracking-wider">CAC</div>
          <div className="text-xl font-bold text-gray-900">${data.summary.cac}</div>
        </div>
        <div className="bg-white p-4 rounded-lg shadow-sm border">
          <div className="text-xs text-gray-500 mb-1 font-semibold uppercase tracking-wider">Conv. Rate</div>
          <div className="text-xl font-bold text-gray-900">{data.summary.conversion_rate}%</div>
        </div>
        <div className="bg-white p-4 rounded-lg shadow-sm border">
          <div className="text-xs text-gray-500 mb-1 font-semibold uppercase tracking-wider">Deal Time</div>
          <div className="text-xl font-bold text-gray-900">{data.summary.deal_time}</div>
        </div>
        <div className="bg-white p-4 rounded-lg shadow-sm border">
          <div className="text-xs text-gray-500 mb-1 font-semibold uppercase tracking-wider">Rev. Growth</div>
          <div className="text-xl font-bold text-green-600">+{data.summary.revenue_growth}%</div>
        </div>
      </div>

      {/* Data Table */}
      <div className="bg-white rounded-lg shadow-sm border overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left text-gray-500">
            <thead className="text-xs text-gray-700 uppercase bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3 text-right">Spend</th>
                <th className="px-4 py-3 text-right">Impressions</th>
                <th className="px-4 py-3 text-right">Clicks</th>
                <th className="px-4 py-3 text-right">Leads</th>
                <th className="px-4 py-3 text-right">CPL</th>
                <th className="px-4 py-3 text-right">Q. Leads</th>
                <th className="px-4 py-3 text-right">CPQL</th>
                <th className="px-4 py-3 text-right">Purchases</th>
                <th className="px-4 py-3 text-right">Revenue</th>
                <th className="px-4 py-3 text-right">ROAS</th>
              </tr>
            </thead>
            <tbody>
              {data.ad_sets.map((row: any, i: number) => (
                <tr key={i} className="border-b hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-900 flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-green-500"></span>
                    {row.name}
                  </td>
                  <td className="px-4 py-3 text-right">${row.spend.toFixed(2)}</td>
                  <td className="px-4 py-3 text-right">{row.impressions.toLocaleString()}</td>
                  <td className="px-4 py-3 text-right">{row.clicks}</td>
                  <td className="px-4 py-3 text-right">{row.leads}</td>
                  <td className="px-4 py-3 text-right">${row.cpl.toFixed(2)}</td>
                  <td className="px-4 py-3 text-right">{row.q_leads || '-'}</td>
                  <td className="px-4 py-3 text-right">{row.cpql ? `$${row.cpql.toFixed(2)}` : '-'}</td>
                  <td className="px-4 py-3 text-right">{row.purchases || '-'}</td>
                  <td className="px-4 py-3 text-right">{row.revenue ? `$${row.revenue.toLocaleString()}` : '-'}</td>
                  <td className="px-4 py-3 text-right">
                    {row.roas > 0 ? (
                      <span className={`px-2 py-1 rounded text-xs font-medium ${row.roas > 5 ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'}`}>
                        {row.roas.toFixed(2)}x
                      </span>
                    ) : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      </main>
    </div>
  );
}
