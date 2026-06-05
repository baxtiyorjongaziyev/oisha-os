'use client';
import { useState } from 'react';
import { AlertTriangle, Bell, CheckCircle, XCircle, User, Clock } from 'lucide-react';

const ALERTS = [
  { id: 1, type: 'inactive_manager', title: 'Faoliyatsiz menejer', desc: 'Baxtiyorjon Gaziyev bugun hali birorta qo\'ng\'iroq qilmadi. Kunlik norma: 20 ta qo\'ng\'iroq.', manager: 'Baxtiyorjon Gaziyev', time: '17 soat oldin', status: 'new', severity: 'amber' },
  { id: 2, type: 'low_performance', title: 'Past samaradorlik', desc: 'Haftalik norma atigi 40% bajarildi. Maqsad: 100 ta qo\'ng\'iroq, bajarildi: 40 ta.', manager: 'Baxtiyorjon Gaziyev', time: '1 kun oldin', status: 'new', severity: 'red' },
  { id: 3, type: 'inactive_manager', title: 'Faoliyatsiz menejer', desc: 'Kecha ham qo\'ng\'iroq normasiga yetilmadi. 15 ta o\'rniga 8 ta qo\'ng\'iroq.', manager: 'Baxtiyorjon Gaziyev', time: '2 kun oldin', status: 'new', severity: 'amber' },
  { id: 4, type: 'lead_alert', title: 'Lid javobsiz', desc: '+998973355900 raqamiga 3 marta urinish — hamon javob yo\'q. 3 kundan beri kutilmoqda.', manager: 'Baxtiyorjon Gaziyev', time: '3 kun oldin', status: 'read', severity: 'amber' },
  { id: 5, type: 'low_performance', title: 'Past sifat baho', desc: 'So\'nggi 5 qo\'ng\'iroqda o\'rtacha ball 58%. Maqsad: 70%.', manager: 'Baxtiyorjon Gaziyev', time: '3 kun oldin', status: 'read', severity: 'red' },
  { id: 6, type: 'inactive_manager', title: 'Faoliyatsiz menejer', desc: 'Dushanba kuni hech qanday qo\'ng\'iroq qayd etilmadi.', manager: 'Baxtiyorjon Gaziyev', time: '5 kun oldin', status: 'read', severity: 'amber' },
];

const TABS = ['Barchasi', 'Yangi', 'O\'qilgan', 'Bekor qilingan'] as const;
const TYPE_LABELS: Record<string, string> = {
  inactive_manager: 'Faoliyatsiz menejer',
  low_performance: 'Past samaradorlik',
  lead_alert: 'Lid ogohlantirish',
};

export default function AlertsPage() {
  const [tab, setTab] = useState<typeof TABS[number]>('Barchasi');
  const [alerts, setAlerts] = useState(ALERTS);

  const filtered = alerts.filter(a => {
    if (tab === 'Yangi') return a.status === 'new';
    if (tab === 'O\'qilgan') return a.status === 'read';
    if (tab === 'Bekor qilingan') return a.status === 'dismissed';
    return a.status !== 'dismissed';
  });

  const markRead = (id: number) => setAlerts(prev => prev.map(a => a.id === id ? { ...a, status: 'read' } : a));
  const dismiss = (id: number) => setAlerts(prev => prev.map(a => a.id === id ? { ...a, status: 'dismissed' } : a));
  const newCount = alerts.filter(a => a.status === 'new').length;

  return (
    <div style={{ padding: '24px', maxWidth: 800 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        <h1 style={{ fontSize: '1.25rem', fontWeight: 700, letterSpacing: '-0.01em' }}>Ogohlantirishlar</h1>
        {newCount > 0 && <span className="badge badge-red">{newCount} yangi</span>}
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, borderBottom: '1px solid var(--border)', marginBottom: 20 }}>
        {TABS.map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            padding: '8px 14px', fontSize: '0.8125rem', fontWeight: 500,
            cursor: 'pointer', background: 'transparent', border: 'none',
            color: tab === t ? 'var(--accent)' : 'var(--text-secondary)',
            borderBottom: tab === t ? '2px solid var(--accent)' : '2px solid transparent',
            marginBottom: -1,
          }}>{t}</button>
        ))}
      </div>

      {/* Alert cards */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {filtered.map(alert => (
          <div
            key={alert.id}
            className="card"
            style={{
              padding: 18,
              borderLeft: `3px solid ${alert.severity === 'red' ? 'var(--accent-red)' : 'var(--accent-amber)'}`,
              opacity: alert.status === 'read' ? 0.7 : 1,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
              <div style={{
                width: 36, height: 36, borderRadius: 10, flexShrink: 0,
                background: alert.severity === 'red' ? 'rgba(239,68,68,0.12)' : 'rgba(245,158,11,0.12)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <AlertTriangle size={16} style={{ color: alert.severity === 'red' ? 'var(--accent-red)' : 'var(--accent-amber)' }} />
              </div>

              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                  <span className={`badge ${alert.severity === 'red' ? 'badge-red' : 'badge-amber'}`}>
                    {TYPE_LABELS[alert.type]}
                  </span>
                  {alert.status === 'new' && <span className="badge badge-blue">Yangi</span>}
                </div>
                <div style={{ fontWeight: 600, fontSize: '0.875rem', marginBottom: 4 }}>{alert.title}</div>
                <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: 8 }}>{alert.desc}</p>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                    <div style={{ width: 20, height: 20, borderRadius: '50%', background: 'linear-gradient(135deg, var(--accent), var(--accent-violet))', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.6875rem', fontWeight: 700 }}>B</div>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{alert.manager}</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <Clock size={11} style={{ color: 'var(--text-muted)' }} />
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{alert.time}</span>
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flexShrink: 0 }}>
                {alert.status === 'new' && (
                  <button
                    onClick={() => markRead(alert.id)}
                    className="btn btn-ghost"
                    style={{ fontSize: '0.75rem', padding: '5px 10px', gap: 4 }}
                  >
                    <CheckCircle size={12} />O'qilgan
                  </button>
                )}
                <button
                  onClick={() => dismiss(alert.id)}
                  className="btn-icon"
                  style={{ width: 30, height: 30 }}
                >
                  <XCircle size={13} />
                </button>
              </div>
            </div>
          </div>
        ))}

        {filtered.length === 0 && (
          <div style={{ textAlign: 'center', padding: 48, color: 'var(--text-muted)' }}>
            <Bell size={32} style={{ margin: '0 auto 12px', opacity: 0.3 }} />
            <p>Ogohlantirishlar topilmadi</p>
          </div>
        )}
      </div>
    </div>
  );
}
