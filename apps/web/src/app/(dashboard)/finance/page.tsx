import React from 'react';
import { getFinanceDashboardStats, getFinanceTransactions } from '@/lib/apiClient';

export default async function FinanceDashboard() {
  const stats = await getFinanceDashboardStats();
  const txData = await getFinanceTransactions();

  const balance = stats?.balance || 0;
  const income = stats?.monthly_income || 0;
  const expense = stats?.monthly_expense || 0;
  
  const transactions = txData?.transactions || [];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Moliya (Hisobchi AI)</h1>
        <div className="flex gap-3">
          <button className="rounded-xl bg-red-50 text-red-600 px-4 py-2 text-sm font-medium hover:bg-red-100 transition-colors">
            - Chiqim qo&apos;shish
          </button>
          <button className="rounded-xl bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 transition-colors">
            + Kirim qo&apos;shish
          </button>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-6">
        <div className="rounded-2xl border border-gray-100 bg-white p-6 shadow-sm">
          <p className="text-sm font-medium text-gray-500">Jami Balans</p>
          <p className="mt-2 text-3xl font-bold text-gray-900">${balance.toLocaleString()}</p>
        </div>
        <div className="rounded-2xl border border-gray-100 bg-white p-6 shadow-sm">
          <p className="text-sm font-medium text-gray-500">Bu oygi Kirim</p>
          <p className="mt-2 text-3xl font-bold text-green-600">+${income.toLocaleString()}</p>
        </div>
        <div className="rounded-2xl border border-gray-100 bg-white p-6 shadow-sm">
          <p className="text-sm font-medium text-gray-500">Bu oygi Chiqim</p>
          <p className="mt-2 text-3xl font-bold text-red-600">-${expense.toLocaleString()}</p>
        </div>
      </div>

      <div className="rounded-2xl border border-gray-100 bg-white shadow-sm overflow-hidden">
        <div className="border-b border-gray-100 px-6 py-4">
          <h2 className="font-semibold text-gray-900">Oxirgi Tranzaksiyalar</h2>
        </div>
        <table className="w-full text-left text-sm text-gray-600">
          <thead className="bg-gray-50 text-xs uppercase text-gray-500">
            <tr>
              <th className="px-6 py-3">Turi</th>
              <th className="px-6 py-3">Tavsif</th>
              <th className="px-6 py-3">Summa</th>
              <th className="px-6 py-3">Sana</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {transactions.length > 0 ? transactions.map((tx) => (
              <tr key={tx.id} className="hover:bg-gray-50 transition-colors">
                <td className="px-6 py-4">
                  <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                    tx.type === 'Kirim' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                  }`}>
                    {tx.type}
                  </span>
                </td>
                <td className="px-6 py-4 font-medium text-gray-900">{tx.description}</td>
                <td className={`px-6 py-4 font-medium ${tx.type === 'Kirim' ? 'text-green-600' : 'text-red-600'}`}>
                  {tx.amount}
                </td>
                <td className="px-6 py-4 text-gray-500">{tx.date}</td>
              </tr>
            )) : (
              <tr>
                <td colSpan={4} className="px-6 py-8 text-center text-gray-500">
                  Hozircha tranzaksiyalar yo&apos;q.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
