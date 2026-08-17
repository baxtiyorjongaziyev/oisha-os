import React from 'react';
import { getCrmDashboardStats } from '@/lib/apiClient';

export const dynamic = 'force-dynamic';

export default async function TasksDashboard() {
  const stats = await getCrmDashboardStats();

  const pendingCount = stats?.tasks.pending || 6;
  const overdueCount = stats?.tasks.overdue || 0;
  const doneCount = stats?.tasks.completed_today || 4;

  const tasks = [
    {
      id: 1,
      title: '"Orzu Mebel" bilan strategik brendbuk shartnomasini yopish',
      category: 'Sotuv & Bitim',
      assignee: 'Baxtiyorjon',
      priority: 'Frog (1-O\'rin)',
      isFrog: true,
      profitEstimate: '+$3,800',
      status: 'In Progress',
      deadline: 'Bugun, 18:00',
    },
    {
      id: 2,
      title: '"Apex Logistics" uchun 3D vizualizatsiyalar va qadoq namunalarini taqdim etish',
      category: 'Dizayn & Ishlab chiqarish',
      assignee: 'Madina',
      priority: 'Yuqori',
      isFrog: false,
      profitEstimate: '+$2,400',
      status: 'Review',
      deadline: 'Ertaga, 12:00',
    },
    {
      id: 3,
      title: 'AmoCRM v4 500 limitidan ortiqcha sovuq kontaktlarni arxivlash',
      category: 'Tizim & CRM',
      assignee: 'Sardor',
      priority: 'O\'rta',
      isFrog: false,
      profitEstimate: 'Operatsion',
      status: 'Todo',
      deadline: '18-Avgust',
    },
    {
      id: 4,
      title: '"Safir Klinika" uchun Naming patent arizalarini topshirish',
      category: 'Yuridik & Patent',
      assignee: 'Bekzod',
      priority: 'Yuqori',
      isFrog: false,
      profitEstimate: '+$1,200',
      status: 'In Progress',
      deadline: '19-Avgust',
    },
  ];

  return (
    <div className="space-y-8 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold uppercase tracking-wider text-purple-600 bg-purple-50 dark:bg-purple-950/40 px-2.5 py-0.5 rounded-full">
              FROGAGENT INTELLIGENCE
            </span>
            <span className="text-xs text-text-muted">• Eat The Frog (ROI Enforcer)</span>
          </div>
          <h1 className="mt-1 text-2xl md:text-3xl font-extrabold tracking-tight text-text">
            Vazifalar & Jamoa Yuklamasi
          </h1>
          <p className="mt-0.5 text-xs text-text-muted">
            Har kuni 09:00 da Telegram orqali eng yuqori daromad keltiruvchi vazifalar saralanadi.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button className="rounded-2xl border border-border bg-bg-card px-4 py-2.5 text-xs font-bold text-text hover:bg-bg transition-all active:scale-[0.98]">
            🐸 Frog saralash
          </button>
          <button className="rounded-2xl bg-brand text-white px-4 py-2.5 text-xs font-bold hover:bg-brand-hover shadow-md shadow-brand/20 transition-all active:scale-[0.98]">
            + Yangi Vazifa
          </button>
        </div>
      </div>

      {/* Frog Hero Banner */}
      <div className="rounded-3xl border border-purple-200 dark:border-purple-900/50 bg-gradient-to-r from-purple-50/80 via-bg-card to-brand-light/30 p-6 md:p-7 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-start gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-purple-600 text-2xl text-white shadow-md shadow-purple-600/20">
              🐸
            </div>
            <div>
              <span className="text-[10px] font-extrabold uppercase tracking-wider text-purple-600 dark:text-purple-400">
                Bugungi Kunning Asosiy Qurbaqasi (Eat The Frog)
              </span>
              <h3 className="text-base md:text-lg font-bold text-text mt-0.5">
                &quot;Orzu Mebel&quot; bilan strategik brendbuk shartnomasini yopish
              </h3>
              <p className="text-xs text-text-muted mt-1">
                Kutilgan daromad: <strong className="text-emerald-600 dark:text-emerald-400">+$3,800</strong> • Mas&apos;ul: <strong>Baxtiyorjon</strong> • Muddat: <strong>Bugun, 18:00</strong>
              </p>
            </div>
          </div>

          <button className="rounded-2xl bg-purple-600 text-white px-5 py-2.5 text-xs font-bold hover:bg-purple-700 shadow-md shadow-purple-600/20 shrink-0 transition-all active:scale-[0.98]">
            ✓ Bajarildi deb belgilash
          </button>
        </div>
      </div>

      {/* 4 Task Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <div className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm">
          <span className="text-xs font-bold uppercase tracking-wider text-text-muted">
            Kutilayotgan (Pending)
          </span>
          <div className="mt-2 text-3xl font-black tracking-tight text-blue-600 dark:text-blue-400">
            {pendingCount}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-text-muted border-t border-border/50 pt-3">
            <span>Jamoa quvvati:</span>
            <span className="font-semibold text-text">85% optimal</span>
          </div>
        </div>

        <div className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm">
          <span className="text-xs font-bold uppercase tracking-wider text-text-muted">
            Kechikkan (Overdue)
          </span>
          <div className="mt-2 text-3xl font-black tracking-tight text-emerald-600 dark:text-emerald-400">
            {overdueCount}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-text-muted border-t border-border/50 pt-3">
            <span>Intizom ko&apos;rsatkichi:</span>
            <span className="font-bold text-emerald-600">100% o&apos;z vaqtida</span>
          </div>
        </div>

        <div className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm">
          <span className="text-xs font-bold uppercase tracking-wider text-text-muted">
            Bugun Bajarildi
          </span>
          <div className="mt-2 text-3xl font-black tracking-tight text-purple-600 dark:text-purple-400">
            {doneCount}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-text-muted border-t border-border/50 pt-3">
            <span>Kunlik reja:</span>
            <span className="font-bold text-purple-600">80% bajarildi</span>
          </div>
        </div>

        <div className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm">
          <span className="text-xs font-bold uppercase tracking-wider text-text-muted">
            Frog vazifalar ulushi
          </span>
          <div className="mt-2 text-3xl font-black tracking-tight text-brand">
            75%
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-text-muted border-t border-border/50 pt-3">
            <span>Fokus daromadga:</span>
            <span className="font-bold text-brand">Yuqori ROI</span>
          </div>
        </div>
      </div>

      {/* Task List Table */}
      <div className="rounded-3xl border border-border bg-bg-card shadow-sm overflow-hidden">
        <div className="border-b border-border px-6 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="font-bold text-base text-text">Barcha Operatsion Vazifalar</h2>
            <p className="text-xs text-text-muted">FrogAgent va Airtable orqali muvofiqlashtirilgan topshiriqlar</p>
          </div>
          <div className="flex items-center gap-2">
            <button className="rounded-xl bg-brand-light px-3 py-1.5 text-xs font-bold text-brand">
              Barchasi
            </button>
            <button className="rounded-xl px-3 py-1.5 text-xs font-medium text-text-muted hover:bg-bg">
              🐸 Faqat Frog
            </button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-bg text-[10px] uppercase text-text-muted font-bold tracking-wider border-b border-border">
              <tr>
                <th className="px-6 py-3.5">Vazifa Nomi</th>
                <th className="px-6 py-3.5">Yo&apos;nalish</th>
                <th className="px-6 py-3.5">Mas&apos;ul</th>
                <th className="px-6 py-3.5">Muhimlik / ROI</th>
                <th className="px-6 py-3.5">Muddat</th>
                <th className="px-6 py-3.5 text-right">Holat</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/60">
              {tasks.map((task) => (
                <tr key={task.id} className="hover:bg-bg/50 transition-colors">
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2 font-bold text-text">
                      {task.isFrog && <span className="text-base">🐸</span>}
                      <span>{task.title}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-text-muted font-medium">
                    {task.category}
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      <div className="h-6 w-6 rounded-full bg-brand-light text-brand flex items-center justify-center text-[10px] font-bold">
                        {task.assignee.charAt(0)}
                      </div>
                      <span className="font-semibold text-text">{task.assignee}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      <span
                        className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold ${
                          task.isFrog
                            ? 'bg-purple-100 text-purple-800 dark:bg-purple-950/40 dark:text-purple-400 ring-1 ring-purple-400'
                            : 'bg-blue-100 text-blue-800 dark:bg-blue-950/40 dark:text-blue-400'
                        }`}
                      >
                        {task.priority}
                      </span>
                      <span className="font-bold text-emerald-600">{task.profitEstimate}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-text-muted font-mono">
                    {task.deadline}
                  </td>
                  <td className="px-6 py-4 text-right">
                    <span className="rounded-xl bg-bg border border-border px-3 py-1 text-xs font-semibold text-text">
                      {task.status}
                    </span>
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
