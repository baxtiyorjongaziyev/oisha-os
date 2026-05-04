'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api';

interface CallSummary {
  id: string;
  customerName: string | null;
  direction: string;
  status: string;
  createdAt: string;
  durationSec: number | null;
  scorecard: { overallScore: number } | null;
}

interface PipelineInsights {
  period: string;
  totalCalls: number;
  scoredCalls: number;
  avgScore: number;
  topRiskFlags: { flag: string; count: number }[];
}

export default function DashboardPage() {
  const [calls, setCalls] = useState<CallSummary[]>([]);
  const [insights, setInsights] = useState<PipelineInsights | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get<CallSummary[]>('/calls'),
      api.get<PipelineInsights>('/negotiations/pipeline-insights').catch(() => null),
    ]).then(([c, ins]) => {
      setCalls(c);
      setInsights(ins);
    }).finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="flex items-center justify-center h-screen">
      <div className="text-[var(--text-secondary)]">Loading...</div>
    </div>
  );

  const avgScore = insights?.avgScore ?? 0;
  const scoreColor = avgScore >= 80 ? 'var(--accent-green)' : avgScore >= 60 ? 'var(--accent-amber)' : 'var(--accent-red)';

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-60 border-r border-[var(--border)] flex flex-col p-4 gap-1 shrink-0">
        <div className="px-3 py-4 mb-4">
          <h1 className="font-bold text-lg" style={{
            background: 'linear-gradient(90deg, var(--accent-cyan), #c084fc)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
          }}>
            SALESCOACH AI
          </h1>
          <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>Autonomous Negotiations</p>
        </div>
        <Link href="/dashboard">
          <div className="nav-item active">📊 Dashboard</div>
        </Link>
        <Link href="/calls/upload">
          <div className="nav-item">⬆️ Upload Call</div>
        </Link>
        <Link href="/negotiate">
          <div className="nav-item">🤝 Negotiate</div>
        </Link>
        <div className="nav-item">📈 Analytics</div>
        <div className="nav-item">⚙️ Settings</div>
        <div className="flex-1" />
        <div className="px-3 py-2 text-xs" style={{ color: 'var(--text-muted)' }}>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full pulse-live" style={{ background: 'var(--accent-green)' }} />
            System Online
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-y-auto p-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h2 className="text-2xl font-bold">Dashboard</h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '.875rem', marginTop: '4px' }}>
              Last 7 days · {insights?.totalCalls ?? 0} calls analyzed
            </p>
          </div>
          <Link href="/calls/upload">
            <button className="px-4 py-2 rounded-xl font-medium text-sm transition-all hover:opacity-90"
              style={{ background: 'linear-gradient(135deg, var(--accent-violet), var(--accent-cyan))', color: '#fff' }}>
              + Upload Call
            </button>
          </Link>
        </div>

        {/* KPI row */}
        <div className="grid grid-cols-4 gap-4 mb-8">
          <KPICard
            label="AVG SCORE"
            value={`${Math.round(avgScore)}`}
            sub="/ 100"
            color={scoreColor}
            pct={avgScore}
          />
          <KPICard
            label="CALLS ANALYZED"
            value={`${insights?.scoredCalls ?? 0}`}
            sub={`of ${insights?.totalCalls ?? 0}`}
            color="var(--accent-cyan)"
          />
          <KPICard
            label="TOP RISK"
            value={insights?.topRiskFlags?.[0]?.flag?.replace(/_/g, ' ') ?? '—'}
            sub={insights?.topRiskFlags?.[0] ? `×${insights.topRiskFlags[0].count}` : 'none'}
            color="var(--accent-red)"
            small
          />
          <KPICard
            label="LIVE SESSIONS"
            value="0"
            sub="right now"
            color="var(--accent-green)"
          />
        </div>

        {/* Calls table */}
        <div className="glass overflow-hidden">
          <div className="px-6 py-4 border-b border-[var(--border)] flex items-center justify-between">
            <h3 className="font-semibold">Recent Calls</h3>
            <span className="text-xs px-2 py-1 rounded-full badge-cyan">{calls.length} total</span>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ color: 'var(--text-muted)', fontSize: '.75rem', letterSpacing: '.05em' }}>
                <th className="text-left px-6 py-3 font-medium uppercase">Customer</th>
                <th className="text-left px-6 py-3 font-medium uppercase">Direction</th>
                <th className="text-left px-6 py-3 font-medium uppercase">Status</th>
                <th className="text-left px-6 py-3 font-medium uppercase">AI Score</th>
                <th className="text-left px-6 py-3 font-medium uppercase">Date</th>
                <th className="px-6 py-3" />
              </tr>
            </thead>
            <tbody>
              {calls.map((call) => (
                <tr key={call.id} className="border-t border-[var(--border)] transition-colors hover:bg-[var(--bg-card-hover)]">
                  <td className="px-6 py-4">
                    <Link href={`/calls/${call.id}`}
                      className="font-medium hover:text-[var(--accent-cyan)] transition-colors">
                      {call.customerName ?? 'Unknown'}
                    </Link>
                  </td>
                  <td className="px-6 py-4" style={{ color: 'var(--text-secondary)' }}>
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                      call.direction === 'OUTBOUND' ? 'badge-cyan' : 'badge-violet'
                    }`}>
                      {call.direction}
                    </span>
                  </td>
                  <td className="px-6 py-4"><StatusBadge status={call.status} /></td>
                  <td className="px-6 py-4">
                    {call.scorecard
                      ? <ScoreDisplay score={call.scorecard.overallScore} />
                      : <span style={{ color: 'var(--text-muted)' }}>—</span>}
                  </td>
                  <td className="px-6 py-4 text-xs" style={{ color: 'var(--text-secondary)' }}>
                    {new Date(call.createdAt).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4 text-right">
                    <Link href={`/calls/${call.id}`}
                      className="text-xs px-3 py-1.5 rounded-lg border border-[var(--border)] hover:border-[var(--accent-cyan)] hover:text-[var(--accent-cyan)] transition-colors">
                      View →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {calls.length === 0 && (
            <div className="text-center py-16" style={{ color: 'var(--text-secondary)' }}>
              No calls yet.{' '}
              <Link href="/calls/upload" className="hover:text-[var(--accent-cyan)] underline">
                Upload your first recording
              </Link>
            </div>
          )}
        </div>

        {/* Risk flags */}
        {(insights?.topRiskFlags?.length ?? 0) > 0 && (
          <div className="mt-6 glass-accent p-6">
            <h3 className="font-semibold mb-4 flex items-center gap-2">
              <span>⚠️</span> Top Risk Flags (7d)
            </h3>
            <div className="flex flex-wrap gap-2">
              {insights!.topRiskFlags.map(({ flag, count }) => (
                <div key={flag} className="flex items-center gap-2 px-3 py-1.5 rounded-full badge-red text-xs font-medium">
                  <span>{flag.replace(/_/g, ' ')}</span>
                  <span className="opacity-60">×{count}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────

function KPICard({ label, value, sub, color, pct, small }: {
  label: string; value: string; sub: string;
  color: string; pct?: number; small?: boolean;
}) {
  return (
    <div className="glass p-5 slide-up">
      <p className="text-xs font-medium uppercase tracking-widest mb-3" style={{ color: 'var(--text-muted)' }}>
        {label}
      </p>
      <div className="flex items-end gap-2">
        <span className={`font-bold ${small ? 'text-lg' : 'text-3xl'}`} style={{ color }}>
          {value}
        </span>
        <span className="text-xs mb-1" style={{ color: 'var(--text-muted)' }}>{sub}</span>
      </div>
      {pct !== undefined && (
        <div className="progress-bar mt-3">
          <div className="progress-fill" style={{ width: `${pct}%` }} />
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const cls: Record<string, string> = {
    UPLOADED: 'badge-amber', TRANSCRIBING: 'badge-amber',
    SCORING: 'badge-cyan', DONE: 'badge-green', FAILED: 'badge-red',
  };
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${cls[status] ?? 'badge-amber'}`}>
      {status}
    </span>
  );
}

function ScoreDisplay({ score }: { score: number }) {
  const color = score >= 80 ? 'var(--accent-green)' : score >= 60 ? 'var(--accent-amber)' : 'var(--accent-red)';
  return (
    <div className="flex items-center gap-2">
      <span className="font-bold text-base" style={{ color }}>{Math.round(score)}</span>
      <div className="flex-1 max-w-16 progress-bar">
        <div className="progress-fill" style={{ width: `${score}%` }} />
      </div>
    </div>
  );
}
