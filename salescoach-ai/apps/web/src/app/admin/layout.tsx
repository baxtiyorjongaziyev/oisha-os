'use client';
import Link from 'next/link';
import { ReactNode } from 'react';

export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-60 border-r border-[var(--border)] flex flex-col p-4 gap-1 shrink-0">
        <div className="px-3 py-4 mb-4">
          <h1 className="font-bold text-lg" style={{
            background: 'linear-gradient(90deg, #f59e0b, #ef4444)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
          }}>
            OISHA
          </h1>
          <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>Surgical COO</p>
        </div>

        <nav className="space-y-1 mb-4">
          <Link href="/admin">
            <div className="nav-item hover:bg-[var(--bg-hover)] px-3 py-2 rounded-lg cursor-pointer">📊 Dashboard</div>
          </Link>
          <Link href="/admin/deadlines">
            <div className="nav-item hover:bg-[var(--bg-hover)] px-3 py-2 rounded-lg cursor-pointer">📅 Deadlines</div>
          </Link>
          <Link href="/admin/crm">
            <div className="nav-item hover:bg-[var(--bg-hover)] px-3 py-2 rounded-lg cursor-pointer">💼 CRM</div>
          </Link>
          <Link href="/admin/reports">
            <div className="nav-item hover:bg-[var(--bg-hover)] px-3 py-2 rounded-lg cursor-pointer">📈 Reports</div>
          </Link>
        </nav>

        <div className="border-t border-[var(--border)] pt-4 mt-auto">
          <Link href="/dashboard">
            <div className="nav-item hover:bg-[var(--bg-hover)] px-3 py-2 rounded-lg text-sm cursor-pointer">
              ← SalesCoach AI
            </div>
          </Link>
        </div>

        <div className="px-3 py-2 text-xs" style={{ color: 'var(--text-muted)' }}>
          <div className="flex items-center gap-2 mt-4">
            <span className="w-2 h-2 rounded-full pulse-live" style={{ background: 'var(--accent-green)' }} />
            Live
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-y-auto p-8">
        {children}
      </main>
    </div>
  );
}
