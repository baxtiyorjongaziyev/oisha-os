'use client';
import { useEffect, useState } from 'react';
import { api } from '@/lib/api';

interface Deadline {
  id: string;
  name: string;
  due_date: string;
  days_until_due: number;
  status: string;
  manager?: string;
  project_url?: string;
  notes?: string;
}

interface DeadlineResponse {
  deadlines: Deadline[];
  total_overdue: number;
  total_at_risk: number;
}

export default function DeadlinesPage() {
  const [data, setData] = useState<DeadlineResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<'all' | 'overdue' | 'at_risk' | 'on_track'>('all');

  useEffect(() => {
    const fetchDeadlines = async () => {
      try {
        const result = await api.get<DeadlineResponse>('/admin/deadlines');
        setData(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load deadlines');
      } finally {
        setLoading(false);
      }
    };

    fetchDeadlines();
    const interval = setInterval(fetchDeadlines, 60000); // Refresh every minute
    return () => clearInterval(interval);
  }, []);

  if (loading) return (
    <div className="flex items-center justify-center h-screen">
      <div className="text-[var(--text-secondary)]">Loading deadlines...</div>
    </div>
  );

  const filtered = data?.deadlines.filter(d => {
    if (filter === 'all') return true;
    return d.status === filter;
  }) || [];

  const statusColors: Record<string, string> = {
    overdue: 'var(--accent-red)',
    at_risk: 'var(--accent-amber)',
    on_track: 'var(--accent-green)',
  };

  const statusLabels: Record<string, string> = {
    overdue: '🔴 Overdue',
    at_risk: '🟡 At Risk',
    on_track: '🟢 On Track',
  };

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <h2 className="text-3xl font-bold mb-2">Project Deadlines</h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '.875rem' }}>
          Track Airtable projects and their due dates
        </p>
      </div>

      {error && (
        <div className="mb-4 p-4 bg-[var(--accent-red)] bg-opacity-10 border border-[var(--accent-red)] rounded-lg text-[var(--accent-red)]">
          {error}
        </div>
      )}

      {/* Status Summary */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        <div className="glass p-4">
          <p className="text-xs font-medium uppercase tracking-widest mb-2" style={{ color: 'var(--text-muted)' }}>
            Overdue
          </p>
          <p className="text-3xl font-bold" style={{ color: 'var(--accent-red)' }}>
            {data?.total_overdue ?? 0}
          </p>
        </div>
        <div className="glass p-4">
          <p className="text-xs font-medium uppercase tracking-widest mb-2" style={{ color: 'var(--text-muted)' }}>
            At Risk
          </p>
          <p className="text-3xl font-bold" style={{ color: 'var(--accent-amber)' }}>
            {data?.total_at_risk ?? 0}
          </p>
        </div>
        <div className="glass p-4">
          <p className="text-xs font-medium uppercase tracking-widest mb-2" style={{ color: 'var(--text-muted)' }}>
            Total
          </p>
          <p className="text-3xl font-bold" style={{ color: 'var(--accent-cyan)' }}>
            {data?.deadlines.length ?? 0}
          </p>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex gap-2 mb-6">
        {(['all', 'overdue', 'at_risk', 'on_track'] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              filter === f
                ? 'bg-[var(--accent-cyan)] text-white'
                : 'bg-[var(--bg-card)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]'
            }`}
          >
            {f.charAt(0).toUpperCase() + f.slice(1).replace('_', ' ')}
          </button>
        ))}
      </div>

      {/* Deadlines Table */}
      <div className="glass overflow-hidden">
        {filtered.length === 0 ? (
          <div className="p-8 text-center" style={{ color: 'var(--text-secondary)' }}>
            No {filter !== 'all' ? filter + ' ' : ''}deadlines found
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr style={{ color: 'var(--text-muted)', fontSize: '.75rem', letterSpacing: '.05em' }}>
                <th className="text-left px-6 py-3 font-medium uppercase">Project</th>
                <th className="text-left px-6 py-3 font-medium uppercase">Due Date</th>
                <th className="text-left px-6 py-3 font-medium uppercase">Days</th>
                <th className="text-left px-6 py-3 font-medium uppercase">Status</th>
                <th className="text-left px-6 py-3 font-medium uppercase">Manager</th>
                <th className="px-6 py-3" />
              </tr>
            </thead>
            <tbody>
              {filtered.map((deadline) => (
                <tr
                  key={deadline.id}
                  className="border-t border-[var(--border)] transition-colors hover:bg-[var(--bg-card-hover)]"
                >
                  <td className="px-6 py-4">
                    {deadline.project_url ? (
                      <a
                        href={deadline.project_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-medium hover:text-[var(--accent-cyan)] transition-colors"
                      >
                        {deadline.name} ↗
                      </a>
                    ) : (
                      <span className="font-medium">{deadline.name}</span>
                    )}
                  </td>
                  <td className="px-6 py-4 text-xs" style={{ color: 'var(--text-secondary)' }}>
                    {new Date(deadline.due_date).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4 font-semibold">
                    <span style={{ color: statusColors[deadline.status] }}>
                      {deadline.days_until_due > 0 ? `+${deadline.days_until_due}` : deadline.days_until_due} d
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <span
                      className="px-2 py-1 rounded-full text-xs font-medium"
                      style={{
                        background: `${statusColors[deadline.status]}20`,
                        color: statusColors[deadline.status],
                      }}
                    >
                      {statusLabels[deadline.status]}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm" style={{ color: 'var(--text-secondary)' }}>
                    {deadline.manager || '—'}
                  </td>
                  <td className="px-6 py-4 text-right">
                    {deadline.notes && (
                      <div
                        className="text-xs px-3 py-1.5 rounded-lg border border-[var(--border)] cursor-help hover:border-[var(--accent-cyan)] transition-colors"
                        title={deadline.notes}
                      >
                        📝
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
