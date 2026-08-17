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
    <div className="space-y-7 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold uppercase tracking-wider text-[#7c3aed] dark:text-[#d0bcff] bg-[#ede9fe] dark:bg-[#4a287a] px-2.5 py-0.5 rounded-full">
              FROGAGENT INTELLIGENCE
            </span>
            <span className="text-xs text-[var(--md-sys-color-on-surface-variant)]">• Eat The Frog (ROI Enforcer)</span>
          </div>
          <h1 className="mt-1 text-2xl md:text-3xl font-bold tracking-tight text-[var(--md-sys-color-on-surface)]">
            Vazifalar & Jamoa Yuklamasi
          </h1>
          <p className="mt-0.5 text-xs text-[var(--md-sys-color-on-surface-variant)]">
            Har kuni 09:00 da Telegram orqali eng yuqori daromad keltiruvchi vazifalar saralanadi.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button className="rounded-full border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface-container)] px-4 py-2.5 text-xs font-bold text-[var(--md-sys-color-on-surface)] hover:bg-[var(--md-sys-color-surface-container-high)] transition-all active:scale-[0.98]">
            🐸 Frog saralash
          </button>
          <button className="rounded-full bg-[#7c3aed] dark:bg-[#d0bcff] dark:text-[#041e49] text-white px-5 py-2.5 text-xs font-bold shadow-sm hover:opacity-90 transition-all active:scale-[0.98]">
            + Yangi Vazifa
          </button>
        </div>
      </div>

      {/* Google Keep / Tasks Frog Hero Banner */}
      <div className="rounded-3xl border border-[#ede9fe] dark:border-[#4a287a] bg-[var(--md-sys-color-surface)] p-6 md:p-7 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-start gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-[#ede9fe] dark:bg-[#4a287a] text-2xl text-[#7c3aed] dark:text-[#d0bcff] shadow-inner">
              🐸
            </div>
            <div>
              <span className="text-[10px] font-extrabold uppercase tracking-wider text-[#7c3aed] dark:text-[#d0bcff]">
                Bugungi Kunning Asosiy Qurbaqasi (Eat The Frog)
              </span>
              <h3 className="text-base md:text-lg font-bold text-[var(--md-sys-color-on-surface)] mt-0.5">
                &quot;Orzu Mebel&quot; bilan strategik brendbuk shartnomasini yopish
              </h3>
              <p className="text-xs text-[var(--md-sys-color-on-surface-variant)] mt-1">
                Kutilgan daromad: <strong className="text-[#137333] dark:text-[#6dd58c]">+$3,800</strong> • Mas&apos;ul: <strong>Baxtiyorjon</strong> • Muddat: <strong>Bugun, 18:00</strong>
              </p>
            </div>
          </div>

          <button className="rounded-full bg-[#7c3aed] dark:bg-[#d0bcff] dark:text-[#041e49] text-white px-5 py-2.5 text-xs font-bold hover:opacity-90 shadow-sm shrink-0 transition-all active:scale-[0.98]">
            ✓ Bajarildi deb belgilash
          </button>
        </div>
      </div>

      {/* 4 Task Tonal Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <div className="rounded-3xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface)] p-6 shadow-sm">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--md-sys-color-on-surface-variant)]">
            Kutilayotgan (Pending)
          </span>
          <div className="mt-2 text-3xl font-black tracking-tight text-[#0b57d0] dark:text-[#a8c7fa]">
            {pendingCount}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-[var(--md-sys-color-on-surface-variant)] border-t border-[var(--md-sys-color-outline-variant)] pt-3">
            <span>Jamoa quvvati:</span>
            <strong className="text-[var(--md-sys-color-on-surface)]">85% optimal</strong>
          </div>
        </div>

        <div className="rounded-3xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface)] p-6 shadow-sm">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--md-sys-color-on-surface-variant)]">
            Kechikkan (Overdue)
          </span>
          <div className="mt-2 text-3xl font-black tracking-tight text-[#137333] dark:text-[#6dd58c]">
            {overdueCount}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-[var(--md-sys-color-on-surface-variant)] border-t border-[var(--md-sys-color-outline-variant)] pt-3">
            <span>Intizom ko&apos;rsatkichi:</span>
            <strong className="text-[#137333] dark:text-[#6dd58c]">100% o&apos;z vaqtida</strong>
          </div>
        </div>

        <div className="rounded-3xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface)] p-6 shadow-sm">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--md-sys-color-on-surface-variant)]">
            Bugun Bajarildi
          </span>
          <div className="mt-2 text-3xl font-black tracking-tight text-[#7c3aed] dark:text-[#d0bcff]">
            {doneCount}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-[var(--md-sys-color-on-surface-variant)] border-t border-[var(--md-sys-color-outline-variant)] pt-3">
            <span>Kunlik reja:</span>
            <strong className="text-[#7c3aed] dark:text-[#d0bcff]">80% bajarildi</strong>
          </div>
        </div>

        <div className="rounded-3xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface)] p-6 shadow-sm">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--md-sys-color-on-surface-variant)]">
            Frog vazifalar ulushi
          </span>
          <div className="mt-2 text-3xl font-black tracking-tight text-[#b06000] dark:text-[#fdd663]">
            75%
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-[var(--md-sys-color-on-surface-variant)] border-t border-[var(--md-sys-color-outline-variant)] pt-3">
            <span>Fokus daromadga:</span>
            <strong className="text-[#b06000] dark:text-[#fdd663]">Yuqori ROI</strong>
          </div>
        </div>
      </div>

      {/* Task List Table */}
      <div className="rounded-3xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface)] shadow-sm overflow-hidden">
        <div className="border-b border-[var(--md-sys-color-outline)] px-6 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="font-bold text-base text-[var(--md-sys-color-on-surface)]">Barcha Operatsion Vazifalar</h2>
            <p className="text-xs text-[var(--md-sys-color-on-surface-variant)]">FrogAgent va Airtable orqali muvofiqlashtirilgan topshiriqlar</p>
          </div>
          <div className="flex items-center gap-2">
            <button className="rounded-full bg-[#ede9fe] dark:bg-[#4a287a] text-[#4a287a] dark:text-[#d0bcff] px-3.5 py-1.5 text-xs font-bold">
              Barchasi
            </button>
            <button className="rounded-full px-3.5 py-1.5 text-xs font-semibold text-[var(--md-sys-color-on-surface-variant)] hover:bg-[var(--md-sys-color-surface-container)]">
              🐸 Faqat Frog
            </button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[var(--md-sys-color-surface-container-low)] text-[10px] uppercase text-[var(--md-sys-color-on-surface-variant)] font-bold tracking-wider border-b border-[var(--md-sys-color-outline)]">
              <tr>
                <th className="px-6 py-3.5">Vazifa Nomi</th>
                <th className="px-6 py-3.5">Yo&apos;nalish</th>
                <th className="px-6 py-3.5">Mas&apos;ul</th>
                <th className="px-6 py-3.5">Muhimlik / ROI</th>
                <th className="px-6 py-3.5">Muddat</th>
                <th className="px-6 py-3.5 text-right">Holat</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--md-sys-color-outline-variant)]">
              {tasks.map((task) => (
                <tr key={task.id} className="hover:bg-[var(--md-sys-color-surface-container-low)] transition-colors">
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2 font-bold text-[var(--md-sys-color-on-surface)]">
                      {task.isFrog && <span className="text-base">🐸</span>}
                      <span>{task.title}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-[var(--md-sys-color-on-surface-variant)] font-medium">
                    {task.category}
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      <div className="h-6 w-6 rounded-full bg-[#ede9fe] text-[#4a287a] dark:bg-[#4a287a] dark:text-[#d0bcff] flex items-center justify-center text-[10px] font-bold">
                        {task.assignee.charAt(0)}
                      </div>
                      <span className="font-semibold text-[var(--md-sys-color-on-surface)]">{task.assignee}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      <span
                        className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold ${
                          task.isFrog
                            ? 'bg-[#ede9fe] text-[#4a287a] dark:bg-[#4a287a] dark:text-[#d0bcff]'
                            : 'bg-[#d3e3fd] text-[#041e49] dark:bg-[#004a77] dark:text-[#c2e7ff]'
                        }`}
                      >
                        {task.priority}
                      </span>
                      <span className="font-bold text-[#137333] dark:text-[#6dd58c]">{task.profitEstimate}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-[var(--md-sys-color-on-surface-variant)] font-mono">
                    {task.deadline}
                  </td>
                  <td className="px-6 py-4 text-right">
                    <span className="rounded-full bg-[var(--md-sys-color-surface-container)] border border-[var(--md-sys-color-outline)] px-3 py-1 text-xs font-semibold text-[var(--md-sys-color-on-surface)]">
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
