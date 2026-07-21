import React from 'react';
import Link from 'next/link';
import { getCrmDashboardStats } from '@/lib/apiClient';

export const dynamic = 'force-dynamic';

export default async function HomePage() {
  const stats = await getCrmDashboardStats();

  const totalLeads = stats?.leads.total || 0;
  const inNegotiation = stats?.deals.total || 0;
  const closedThisMonth = stats?.deals.won || 0;
  const contactsToday = stats?.contacts.new_today || 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Bosh sahifa</h1>
        <p className="mt-1 text-sm text-gray-500">
          Oisha-OS tizimining umumiy analitik ko'rsatkichlari.
        </p>
      </div>

      {!stats ? (
        <div className="border border-rose-300 bg-rose-50 p-4 rounded-xl text-sm text-rose-700">
          Real backend bilan aloqa yo'q yoki xatolik yuz berdi. Backend (FastAPI) ishlayotganligini tekshiring.
        </div>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* Jami Lidlar */}
        <div className="rounded-2xl border border-gray-100 bg-white p-6 shadow-sm">
          <div className="text-sm font-medium text-gray-500">Jami Lidlar</div>
          <div className="mt-2 text-3xl font-bold text-gray-900">{totalLeads}</div>
        </div>

        {/* Muzokarada */}
        <div className="rounded-2xl border border-gray-100 bg-white p-6 shadow-sm">
          <div className="text-sm font-medium text-gray-500">Muzokarada</div>
          <div className="mt-2 text-3xl font-bold text-blue-600">{inNegotiation}</div>
        </div>

        {/* Yopilgan */}
        <div className="rounded-2xl border border-gray-100 bg-white p-6 shadow-sm">
          <div className="text-sm font-medium text-gray-500">Yopilgan (Oy)</div>
          <div className="mt-2 text-3xl font-bold text-green-600">{closedThisMonth}</div>
        </div>

        {/* Bugungi yangi kontaktlar */}
        <div className="rounded-2xl border border-gray-100 bg-white p-6 shadow-sm">
          <div className="text-sm font-medium text-gray-500">Bugungi yangi muloqotlar</div>
          <div className="mt-2 text-3xl font-bold text-purple-600">{contactsToday}</div>
        </div>
      </div>

      {stats?.amocrm?.status === "error" && (
        <div className="border border-amber-300 bg-amber-50 rounded-xl p-4 text-sm text-amber-800">
          AmoCRM bilan sinxronizatsiya muammosi: {stats.amocrm.error}
        </div>
      )}

      <section className="rounded-2xl border border-gray-100 bg-white shadow-sm overflow-hidden p-6 mt-6">
        <h2 className="text-lg font-bold text-gray-900 mb-4">Tezkor havolalar</h2>
        <div className="flex gap-4">
          <Link href="/crm" className="text-sm font-medium text-blue-600 hover:underline">
            → CRM bo'limiga o'tish
          </Link>
          <Link href="/calls" className="text-sm font-medium text-blue-600 hover:underline">
            → Qo'ng'iroqlar sifatini ko'rish
          </Link>
        </div>
      </section>
    </div>
  );
}
