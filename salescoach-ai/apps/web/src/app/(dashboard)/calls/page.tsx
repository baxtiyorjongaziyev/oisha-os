'use client';
import Link from 'next/link';
import { useState } from 'react';
import { Phone, Filter, Search, Eye, MoreHorizontal, PhoneIncoming, PhoneOutgoing, TrendingUp } from 'lucide-react';

const CALLS = [
  { id: '1', date: '2026-06-03 14:32', manager: 'Baxtiyorjon Gaziyev', direction: 'in', duration: '3:21', status: 'analyzed', score: 78, family: 'Lidni aniqlash', service: 'Logotip', phone: '+998901234567' },
  { id: '2', date: '2026-06-03 11:14', manager: 'Baxtiyorjon Gaziyev', direction: 'out', duration: '1:47', status: 'analyzed', score: 62, family: 'Yopish/muzokara', service: 'Brendbuk', phone: '+998973355900' },
  { id: '3', date: '2026-06-03 09:05', manager: 'Baxtiyorjon Gaziyev', direction: 'out', duration: '0:39', status: 'analyzed', score: null, family: 'Mijoz bilan koordinatsiya', service: 'Naming', phone: '+998901111111' },
  { id: '4', date: '2026-06-02 16:48', manager: 'Baxtiyorjon Gaziyev', direction: 'in', duration: '5:12', status: 'analyzed', score: 85, family: 'Yechim taqdimoti', service: 'Brendbuk', phone: '+998902222222' },
  { id: '5', date: '2026-06-02 13:20', manager: 'Baxtiyorjon Gaziyev', direction: 'out', duration: '2:03', status: 'error', score: null, family: null, service: null, phone: '+998903333333' },
  { id: '6', date: '2026-06-02 10:55', manager: 'Baxtiyorjon Gaziyev', direction: 'in', duration: '4:17', status: 'analyzed', score: 91, family: 'Yopish/muzokara', service: 'Qadoq dizayni', phone: '+998904444444' },
  { id: '7', date: '2026-06-01 15:30', manager: 'Baxtiyorjon Gaziyev', direction: 'out', duration: '0:12', status: 'no_answer', score: null, family: null, service: null, phone: '+998905555555' },
  { id: '8', date: '2026-06-01 12:11', manager: 'Baxtiyorjon Gaziyev', direction: 'in', duration: '7:44', status: 'analyzed', score: 67, family: 'Lidni aniqlash', service: 'Logotip', phone: '+998906666666' },
  { id: '9', date: '2026-05-31 17:02', manager: 'Baxtiyorjon Gaziyev', direction: 'out', duration: '2:58', status: 'analyzed', score: 73, family: 'Sotuvdan keyingi jarayon', service: 'Brendbuk', phone: '+998907777777' },
  { id: '10', date: '2026-05-31 09:40', manager: 'Baxtiyorjon Gaziyev', direction: 'in', duration: '1:22', status: 'analyzed', score: 55, family: 'Moliya/admin', service: 'Naming', phone: '+998908888888' },
];

const STATUS_MAP: Record<string, { label: string; cls: string }> = {
  analyzed:  { label: 'Tahlil qilingan', cls: 'badge-green' },
  pending:   { label: 'Kutilmoqda',       cls: 'badge-amber' },
  analyzing: { label: 'Tahlil qilinmoqda', cls: 'badge-blue' },
  error:     { label: 'Xatolik',          cls: 'badge-red'   },
  no_answer: { label: 'Javobsiz',         cls: 'badge-gray'  },
};

function scoreColor(s: number | null) {
  if (s === null) return 'var(--text-muted)';
  if (s >= 80) return 'var(--accent-green)';
  if (s >= 60) return 'var(--accent-amber)';
  return 'var(--accent-red)';
}

export default function CallsPage() {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  const filtered = CALLS.filter(c => {
    if (statusFilter !== 'all' && c.status !== statusFilter) return false;
    if (search && !c.phone.includes(search) && !c.manager.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  return (
    <div style={{ padding: '24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <div>
          <h1 style={{ fontSize: '1.25rem', fontWeight: 700, letterSpacing: '-0.01em' }}>Qo'ng'iroqlar</h1>
          <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginTop: 2 }}>Jami {CALLS.length} ta yozuv</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <div style={{ position: 'relative' }}>
            <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input
              className="input"
              placeholder="Telefon yoki ism..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{ paddingLeft: 32, width: 220, height: 36 }}
            />
          </div>
        </div>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        {[
          { v: 'all', l: 'Barchasi' },
          { v: 'analyzed', l: 'Tahlil qilingan' },
          { v: 'pending', l: 'Kutilmoqda' },
          { v: 'error', l: 'Xatolik' },
          { v: 'no_answer', l: 'Javobsiz' },
        ].map(f => (
          <button
            key={f.v}
            className="btn btn-ghost"
            onClick={() => setStatusFilter(f.v)}
            style={{
              padding: '5px 12px', height: 32, fontSize: '0.8rem',
              background: statusFilter === f.v ? 'var(--accent-muted)' : undefined,
              color: statusFilter === f.v ? 'var(--accent)' : undefined,
              borderColor: statusFilter === f.v ? 'var(--border-accent)' : undefined,
            }}
          >
            {f.l}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="card" style={{ overflow: 'hidden' }}>
        {/* Header row */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: '160px 1fr 90px 80px 160px 90px 160px 80px',
          padding: '10px 20px',
          borderBottom: '1px solid var(--border)',
          background: 'rgba(255,255,255,0.02)',
        }}>
          {['Sana', 'Menejer', 'Yo\'nalish', 'Davomiylik', 'Holat', 'Sifat', 'Qo\'ng\'iroq oilasi', ''].map(h => (
            <div key={h} style={{ fontSize: '0.6875rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{h}</div>
          ))}
        </div>

        {filtered.map(call => {
          const st = STATUS_MAP[call.status] ?? { label: 'Kutilmoqda', cls: 'badge-amber' };
          return (
            <div
              key={call.id}
              style={{
                display: 'grid',
                gridTemplateColumns: '160px 1fr 90px 80px 160px 90px 160px 80px',
                padding: '12px 20px',
                borderBottom: '1px solid var(--border)',
                alignItems: 'center',
                transition: 'background 0.1s',
                cursor: 'pointer',
              }}
              onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.02)')}
              onMouseLeave={e => (e.currentTarget.style.background = '')}
            >
              <div>
                <div style={{ fontSize: '0.8125rem' }}>{call.date.split(' ')[0]}</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{call.date.split(' ')[1]}</div>
              </div>
              <div style={{ fontSize: '0.8125rem' }}>{call.manager}</div>
              <div>
                {call.direction === 'in'
                  ? <span className="badge badge-blue" style={{ gap: 4 }}><PhoneIncoming size={10} />Kiruvchi</span>
                  : <span className="badge badge-violet" style={{ gap: 4 }}><PhoneOutgoing size={10} />Chiquvchi</span>
                }
              </div>
              <div style={{ fontSize: '0.8125rem', fontFamily: 'monospace' }}>{call.duration}</div>
              <div><span className={`badge ${st.cls}`}>{st.label}</span></div>
              <div style={{ fontWeight: 700, color: scoreColor(call.score) }}>
                {call.score !== null ? `${call.score}%` : '—'}
              </div>
              <div>
                {call.family
                  ? <span className="badge badge-gray" style={{ fontSize: '0.6875rem' }}>{call.family}</span>
                  : <span style={{ color: 'var(--text-muted)', fontSize: '0.8125rem' }}>—</span>
                }
              </div>
              <div style={{ display: 'flex', gap: 4 }}>
                <Link href={`/calls/${call.id}` as any}>
                  <button className="btn-icon" style={{ width: 30, height: 30 }}>
                    <Eye size={13} />
                  </button>
                </Link>
                <button className="btn-icon" style={{ width: 30, height: 30 }}>
                  <MoreHorizontal size={13} />
                </button>
              </div>
            </div>
          );
        })}

        {filtered.length === 0 && (
          <div style={{ padding: 48, textAlign: 'center', color: 'var(--text-muted)' }}>
            <Phone size={32} style={{ margin: '0 auto 12px', opacity: 0.3 }} />
            <p>Qo'ng'iroqlar topilmadi</p>
          </div>
        )}
      </div>
    </div>
  );
}
