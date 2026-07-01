'use client';
import { useEffect, useState } from 'react';
import { api } from '@/lib/api';

interface KPIMetric {
  label: string;
  value: string;
  unit?: string;
  trend?: string;
  status: string;
}

interface DashboardStats {
  roi_metrics: KPIMetric[];
  kpi_metrics: KPIMetric[];
  team_efficiency: Record<string, any>;
  updated_at: string;
}

export default function AdminDashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const data = await api.get<DashboardStats>('/admin/dashboard/stats');
        setStats(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load dashboard');
      } finally {
        setLoading(false);
      }
    };

    fetchStats();
    const interval = setInterval(fetchStats, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  if (loading) return (
    <div className="flex items-center justify-center h-screen">
      <div className="text-[var(--text-secondary)]">Loading Oisha Dashboard...</div>
    </div>
  );

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h2 className="text-3xl font-bold">Surgical Operations Dashboard</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '.875rem', marginTop: '4px' }}>
            Real-time operational intelligence
            {stats?.updated_at && ` · Updated ${new Date(stats.updated_at).toLocaleTimeString()}`}
          </p>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-4 bg-[var(--accent-red)] bg-opacity-10 border border-[var(--accent-red)] rounded-lg text-[var(--accent-red)]">
          {error}
        </div>
      )}

      {/* ROI Metrics */}
      <div className="mb-8">
        <h3 className="text-lg font-semibold mb-4">ROI & Revenue</h3>
        <div className="grid grid-cols-3 gap-4">
          {stats?.roi_metrics.map((metric) => (
            <MetricCard key={metric.label} metric={metric} />
          ))}
        </div>
      </div>

      {/* KPI Metrics */}
      <div className="mb-8">
        <h3 className="text-lg font-semibold mb-4">Team Performance</h3>
        <div className="grid grid-cols-3 gap-4">
          {stats?.kpi_metrics.map((metric) => (
            <MetricCard key={metric.label} metric={metric} />
          ))}
        </div>
      </div>

      {/* Team Efficiency */}
      {stats?.team_efficiency && Object.keys(stats.team_efficiency).length > 0 && (
        <div className="glass p-6">
          <h3 className="text-lg font-semibold mb-4">Team Efficiency</h3>
          <div className="space-y-3">
            {Object.entries(stats.team_efficiency).map(([key, value]) => (
              <div key={key} className="flex justify-between items-center">
                <span style={{ color: 'var(--text-secondary)' }}>{key}</span>
                <span className="font-semibold">{String(value)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Action Buttons */}
      <div className="mt-8 flex gap-3">
        <ActionButton
          label="📊 Send Briefing"
          onClick={async () => {
            try {
              await api.post('/admin/actions/send_briefing', {});
              alert('Briefing sent to owner');
            } catch (err) {
              alert('Failed to send briefing');
            }
          }}
        />
        <ActionButton
          label="📋 Export to Sheets"
          onClick={async () => {
            try {
              await api.post('/admin/actions/export_tez_natija_sheets', {});
              alert('Exported to Google Sheets');
            } catch (err) {
              alert('Failed to export');
            }
          }}
        />
        <ActionButton
          label="💼 Export to AmoCRM"
          onClick={async () => {
            try {
              await api.post('/admin/actions/export_tez_natija_amocrm', {});
              alert('Exported to AmoCRM');
            } catch (err) {
              alert('Failed to export');
            }
          }}
        />
      </div>
    </div>
  );
}

function MetricCard({ metric }: { metric: KPIMetric }) {
  const statusColors: Record<string, string> = {
    success: 'var(--accent-green)',
    warning: 'var(--accent-amber)',
    danger: 'var(--accent-red)',
  };

  return (
    <div className="glass p-5">
      <p className="text-xs font-medium uppercase tracking-widest mb-3" style={{ color: 'var(--text-muted)' }}>
        {metric.label}
      </p>
      <div className="flex items-end gap-2">
        <span className="font-bold text-3xl" style={{ color: statusColors[metric.status] || 'var(--text-primary)' }}>
          {metric.value}
        </span>
        {metric.unit && <span className="text-xs mb-1" style={{ color: 'var(--text-muted)' }}>{metric.unit}</span>}
      </div>
      {metric.trend && (
        <div className="text-xs mt-2" style={{ color: metric.trend === 'up' ? 'var(--accent-green)' : 'var(--accent-red)' }}>
          {metric.trend === 'up' ? '📈' : '📉'} {metric.trend}
        </div>
      )}
    </div>
  );
}

function ActionButton({ label, onClick }: { label: string; onClick: () => Promise<void> }) {
  const [loading, setLoading] = useState(false);

  const handleClick = async () => {
    setLoading(true);
    try {
      await onClick();
    } finally {
      setLoading(false);
    }
  };

  return (
    <button
      onClick={handleClick}
      disabled={loading}
      className="px-4 py-2 rounded-lg font-medium text-sm transition-all hover:opacity-90 disabled:opacity-50"
      style={{ background: 'linear-gradient(135deg, var(--accent-amber), var(--accent-red))', color: '#fff' }}
    >
      {loading ? 'Processing...' : label}
    </button>
  );
}
