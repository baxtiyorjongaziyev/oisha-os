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
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#7c3aed] dark:text-[#c084fc] bg-[#ede9fe] dark:bg-[#4c1d95] px-2.5 py-0.5 rounded-full">
              FROGAGENT INTELLIGENCE
            </span>
            <span className="text-xs text-[var(--text-secondary)]">• Eat The Frog (ROI Enforcer)</span>
          </div>
          <h1 className="mt-1 text-2xl md:text-3xl font-bold tracking-tight text-[var(--text-primary)]">
            Vazifalar & Jamoa Yuklamasi
          </h1>
          <p className="mt-0.5 text-xs text-[var(--text-secondary)]">
            Har kuni 09:00 da Telegram orqali eng yuqori daromad keltiruvchi vazifalar saralanadi.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button className="rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface-subtle)] px-4 py-2 text-xs font-bold text-[var(--text-primary)] hover:bg-[var(--bg-surface-active)] transition-all active:scale-[0.98]">
            🐸 Frog saralash
          </button>
          <button className="rounded-xl bg-[#7c3aed] text-white px-5 py-2 text-xs font-bold shadow-xs hover:opacity-90 transition-all active:scale-[0.98]">
            + Yangi Vazifa
          </button>
        </div>
      </div>

      {/* Google Keep / Linear Frog Hero Banner */}
      <div className="rounded-2xl border border-[#ede9fe] dark:border-[#4c1d95] bg-[var(--bg-surface)] p-5 md:p-6 shadow-xs">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-start gap-4">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[#ede9fe] dark:bg-[#4c1d95] text-2xl text-[#7c3aed] dark:text-[#c084fc] shadow-xs">
              🐸
            </div>
            <div>
              <span className="text-[9px] font-extrabold uppercase tracking-wider text-[#7c3aed] dark:text-[#c084fc]">
                Bugungi Kunning Asosiy Qurbaqasi (Eat The Frog)
              </span>
              <h3 className="text-sm md:text-base font-bold text-[var(--text-primary)] mt-0.5">
                &quot;Orzu Mebel&quot; bilan strategik brendbuk shartnomasini yopish
              </h3>
              <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                Kutilgan daromad: <strong className="text-[#059669] dark:text-[#34d399]">+$3,800</strong> • Mas&apos;ul: <strong>Baxtiyorjon</strong> • Muddat: <strong>Bugun, 18:00</strong>
              </p>
            </div>
          </div>

          <button className="rounded-xl bg-[#7c3aed] text-white px-4 py-2 text-xs font-bold hover:opacity-90 shadow-xs shrink-0 transition-all active:scale-[0.98]">
            ✓ Bajarildi deb belgilash
          </button>
        </div>
      </div>

      {/* 4 Task Tonal Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-5 shadow-xs">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-secondary)]">
            Kutilayotgan (Pending)
          </span>
          <div className="mt-2 text-3xl font-black tracking-tight text-[var(--accent-primary)]">
            {pendingCount}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-[var(--text-secondary)] border-t border-[var(--border-subtle)] pt-2.5">
            <span>Jamoa quvvati:</span>
            <strong className="text-[var(--text-primary)]">85% optimal</strong>
          </div>
        </div>

        <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-5 shadow-xs">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-secondary)]">
            Kechikkan (Overdue)
          </span>
          <div className="mt-2 text-3xl font-black tracking-tight text-[#059669] dark:text-[#34d399]">
            {overdueCount}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-[var(--text-secondary)] border-t border-[var(--border-subtle)] pt-2.5">
            <span>Intizom ko&apos;rsatkichi:</span>
            <strong className="text-[#059669] dark:text-[#34d399]">100% o&apos;z vaqtida</strong>
          </div>
        </div>

        <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-5 shadow-xs">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-secondary)]">
            Bugun Bajarildi
          </span>
          <div className="mt-2 text-3xl font-black tracking-tight text-[#7c3aed] dark:text-[#c084fc]">
            {doneCount}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-[var(--text-secondary)] border-t border-[var(--border-subtle)] pt-2.5">
            <span>Kunlik reja:</span>
            <strong className="text-[#7c3aed] dark:text-[#c084fc]">80% bajarildi</strong>
          </div>
        </div>

        <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-5 shadow-xs">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-secondary)]">
            Frog vazifalar ulushi
          </span>
          <div className="mt-2 text-3xl font-black tracking-tight text-[#d97706] dark:text-[#fbbf24]">
            75%
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-[var(--text-secondary)] border-t border-[var(--border-subtle)] pt-2.5">
            <span>Fokus daromadga:</span>
            <strong className="text-[#d97706] dark:text-[#fbbf24]">Yuqori ROI</strong>
          </div>
        </div>
      </div>

      {/* Task List Table */}
      <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] shadow-xs overflow-hidden">
        <div className="border-b border-[var(--border-default)] px-5 py-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="font-bold text-sm text-[var(--text-primary)]">Barcha Operatsion Vazifalar</h2>
            <p className="text-xs text-[var(--text-secondary)]">FrogAgent va Airtable orqali muvofiqlashtirilgan topshiriqlar</p>
          </div>
          <div className="flex items-center gap-2">
            <button className="rounded-xl bg-[#ede9fe] dark:bg-[#4c1d95] text-[#5b21b6] dark:text-[#c084fc] px-3 py-1 text-xs font-bold">
              Barchasi
            </button>
            <button className="rounded-xl px-3 py-1 text-xs font-semibold text-[var(--text-secondary)] hover:bg-[var(--bg-surface-subtle)]">
              🐸 Faqat Frog
            </button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[var(--bg-surface-subtle)] text-[10px] uppercase text-[var(--text-secondary)] font-bold tracking-wider border-b border-[var(--border-default)]">
              <tr>
                <th className="px-5 py-3">Vazifa Nomi</th>
                <th className="px-5 py-3">Yo&apos;nalish</th>
                <th className="px-5 py-3">Mas&apos;ul</th>
                <th className="px-5 py-3">Muhimlik / ROI</th>
                <th className="px-5 py-3">Muddat</th>
                <th className="px-5 py-3 text-right">Holat</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-subtle)]">
              {tasks.map((task) => (
                <tr key={task.id} className="hover:bg-[var(--bg-surface-subtle)] transition-colors">
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-2 font-bold text-[var(--text-primary)]">
                      {task.isFrog && <span className="text-sm">🐸</span>}
                      <span>{task.title}</span>
                    </div>
                  </td>
                  <td className="px-5 py-3.5 text-[var(--text-secondary)] font-medium">
                    {task.category}
                  </td>
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-2">
                      <div className="h-6 w-6 rounded-full bg-[#ede9fe] text-[#5b21b6] dark:bg-[#4c1d95] dark:text-[#c084fc] flex items-center justify-center text-[10px] font-bold">
                        {task.assignee.charAt(0)}
                      </div>
                      <span className="font-semibold text-[var(--text-primary)]">{task.assignee}</span>
                    </div>
                  </td>
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-2">
                      <span
                        className={`rounded-md px-2 py-0.5 text-[10px] font-bold ${
                          task.isFrog
                            ? 'bg-[#ede9fe] text-[#5b21b6] dark:bg-[#4c1d95] dark:text-[#c084fc]'
                            : 'bg-[var(--accent-primary-light)] text-[var(--accent-primary-on-light)]'
                        }`}
                      >
                        {task.priority}
                      </span>
                      <span className="font-bold text-[#059669] dark:text-[#34d399]">{task.profitEstimate}</span>
                    </div>
                  </td>
                  <td className="px-5 py-3.5 text-[var(--text-secondary)] font-mono">
                    {task.deadline}
                  </td>
                  <td className="px-5 py-3.5 text-right">
                    <span className="rounded-xl bg-[var(--bg-surface-subtle)] border border-[var(--border-default)] px-2.5 py-1 text-xs font-semibold text-[var(--text-primary)]">
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
