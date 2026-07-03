'use client';
import { useState } from 'react';

export default function ReportsPage() {
  const [selectedReport, setSelectedReport] = useState<string | null>(null);

  const reports = [
    {
      id: 'daily_briefing',
      label: '📋 Daily Briefing',
      description: 'ROI, KPI, and team efficiency summary',
      frequency: 'Sent daily at 09:00',
    },
    {
      id: 'team_efficiency',
      label: '👥 Team Efficiency Report',
      description: 'Manager performance, conversion rates, deal velocity',
      frequency: 'Updated every 30 minutes',
    },
    {
      id: 'deadline_audit',
      label: '📅 Deadline Audit',
      description: 'Overdue projects, at-risk deadlines, responsibilities',
      frequency: 'Sent when deadlines change',
    },
    {
      id: 'crm_audit',
      label: '🔍 CRM Audit',
      description: 'Lead quality, pipeline health, anomalies',
      frequency: 'Weekly on Mondays',
    },
  ];

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <h2 className="text-3xl font-bold mb-2">Automation Reports</h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '.875rem' }}>
          Autonomous reporting and team intelligence
        </p>
      </div>

      {/* Reports Grid */}
      <div className="grid grid-cols-2 gap-6 mb-8">
        {reports.map((report) => (
          <div
            key={report.id}
            className="glass p-6 cursor-pointer transition-all hover:scale-105"
            onClick={() => setSelectedReport(report.id)}
          >
            <h3 className="text-lg font-semibold mb-2">{report.label}</h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '.875rem', marginBottom: '1rem' }}>
              {report.description}
            </p>
            <p className="text-xs" style={{ color: 'var(--accent-cyan)' }}>
              🔄 {report.frequency}
            </p>
          </div>
        ))}
      </div>

      {/* Automation Status */}
      <div className="glass p-6 mb-8">
        <div className="flex items-center gap-2 mb-4">
          <span className="w-3 h-3 rounded-full" style={{ background: 'var(--accent-green)' }} />
          <h3 className="font-semibold">Automation Status</h3>
        </div>
        <div className="space-y-3">
          <div className="flex justify-between items-center pb-3 border-b border-[var(--border)]">
            <span>Daily Briefing (09:00 UTC+5)</span>
            <span className="px-2 py-1 rounded-full text-xs font-medium badge-green">Active</span>
          </div>
          <div className="flex justify-between items-center pb-3 border-b border-[var(--border)]">
            <span>Deadline Monitoring (every 5 min)</span>
            <span className="px-2 py-1 rounded-full text-xs font-medium badge-green">Active</span>
          </div>
          <div className="flex justify-between items-center">
            <span>CRM Sync (every 15 min)</span>
            <span className="px-2 py-1 rounded-full text-xs font-medium badge-green">Active</span>
          </div>
        </div>
      </div>

      {/* Configuration */}
      <div className="glass p-6">
        <h3 className="font-semibold mb-4">⚙️ Configuration</h3>
        <div className="space-y-4">
          <div>
            <label className="text-sm font-medium">Briefing Time (UTC+5)</label>
            <input
              type="time"
              defaultValue="09:00"
              className="mt-2 w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--bg-input)]"
              style={{ color: 'var(--text-primary)' }}
            />
          </div>
          <div>
            <label className="text-sm font-medium">Owner ID</label>
            <input
              type="text"
              placeholder="Telegram user ID"
              className="mt-2 w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--bg-input)]"
              style={{ color: 'var(--text-primary)' }}
            />
          </div>
          <button
            className="w-full px-4 py-2 rounded-lg font-medium text-white mt-4"
            style={{ background: 'linear-gradient(135deg, var(--accent-cyan), #0ea5e9)' }}
          >
            Save Configuration
          </button>
        </div>
      </div>
    </div>
  );
}
