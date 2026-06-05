'use client';
import Link from 'next/link';
import { useState } from 'react';
import {
  TrendingUp, TrendingDown, Phone, Target, Clock, AlertCircle,
  BarChart2, Users, Star, ChevronRight, Activity, ArrowUpRight, ArrowDownRight,
} from 'lucide-react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Area, AreaChart,
} from 'recharts';

const PERIODS = ['Bugun', 'Hafta', 'Oy'] as const;

const qualityData = [
  { name: 'Du', score: 62, conv: 1.2 },
  { name: 'Se', score: 71, conv: 2.1 },
  { name: 'Ch', score: 65, conv: 1.8 },
  { name: 'Pa', score: 74, conv: 3.2 },
  { name: 'Ju', score: 68, conv: 2.5 },
  { name: 'Sh', score: 79, conv: 4.1 },
  { name: 'Ya', score: 72, conv: 3.6 },
];

const METRICS = [
  { code: 'A1', label: 'Kompaniya tanishtirish',  score: 78, weak: 3, trend: 'up'   },
  { code: 'A2', label: 'Murojaat manbasini aniqlash', score: 16, weak: 11, trend: 'down' },
  { code: 'A3', label: 'Suhbat maqsadini belgilash', score: 23, weak: 9, trend: 'up'   },
  { code: 'B1', label: 'Mijoz vaziyati ochildi',  score: 54, weak: 5, trend: 'up'   },
  { code: 'B2', label: 'Yo\'nalish aniqlandi',     score: 61, weak: 4, trend: 'up'   },
  { code: 'B3', label: 'Qaror va resurs holati',  score: 38, weak: 7, trend: 'down' },
  { code: 'E1', label: 'Brif yuborish',           score: 17, weak: 10, trend: 'down' },
  { code: 'E3', label: 'Moliyaviy kelishuv',      score: 31, weak: 8, trend: 'down' },
];

const ALERTS = [
  { type: 'amber', title: 'Faoliyatsiz menejer', desc: 'Baxtiyorjon bugun hali qo\'ng\'iroq qilmadi', time: '17 soat oldin' },
  { type: 'red',   title: 'Past samaradorlik',   desc: 'Haftalik norma 40% bajarildi', time: '1 kun oldin' },
  { type: 'amber', title: 'Lid javobsiz',        desc: '+998901234567 raqamiga 3 marta urinish — javob yo\'q', time: '2 kun oldin' },
];

const TOP_MANAGERS = [
  { name: 'Baxtiyorjon Gaziyev', calls: 47, score: 72, trend: +5 },
];

function StatCard({ label, value, sub, trend, icon: Icon, color }: {
  label: string; value: string; sub?: string;
  trend?: number; icon: any; color?: string;
}) {
  return (
    <div className="stat-card" style={{ position: 'relative', overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div>
          <div className="stat-label">{label}</div>
          <div className="stat-value" style={{ marginTop: 6 }}>{value}</div>
          {sub && <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 3 }}>{sub}</div>}
          {trend !== undefined && (
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: 3,
              marginTop: 6, fontSize: '0.75rem', fontWeight: 600,
              color: trend >= 0 ? 'var(--accent-green)' : 'var(--accent-red)',
            }}>
              {trend >= 0 ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
              {trend >= 0 ? '+' : ''}{trend}%
            </div>
          )}
        </div>
        <div style={{
          width: 40, height: 40, borderRadius: 10,
          background: color || 'var(--accent-muted)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Icon size={18} style={{ color: color ? 'white' : 'var(--accent)' }} />
        </div>
      </div>
    </div>
  );
}

function ScoreBar({ code, label, score, weak, trend }: typeof METRICS[0]) {
  const color = score >= 70 ? 'var(--accent-green)' : score >= 40 ? 'var(--accent-amber)' : 'var(--accent-red)';
  return (
    <div style={{ padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span className="badge badge-gray" style={{ fontFamily: 'monospace' }}>{code}</span>
          <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>{label}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{weak} zaif</span>
          <span style={{ fontWeight: 700, fontSize: '0.875rem', color }}>{score}%</span>
          {trend === 'up' ? <TrendingUp size={13} style={{ color: 'var(--accent-green)' }} /> : <TrendingDown size={13} style={{ color: 'var(--accent-red)' }} />}
        </div>
      </div>
      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${score}%`, background: color }} />
      </div>
    </div>
  );
}

export default function HomePage() {
  const [period, setPeriod] = useState<typeof PERIODS[number]>('Hafta');

  return (
    <div style={{ padding: '24px', maxWidth: 1400 }}>
      {/* Period selector */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: '1.25rem', fontWeight: 700, letterSpacing: '-0.01em' }}>Bosh sahifa</h1>
          <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginTop: 2 }}>Jon Branding agency</p>
        </div>
        <div style={{ display: 'flex', gap: 4, background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 10, padding: 4 }}>
          {PERIODS.map(p => (
            <button
              key={p}
              className="btn"
              onClick={() => setPeriod(p)}
              style={{
                padding: '5px 14px', borderRadius: 7, fontSize: '0.8125rem',
                background: period === p ? 'var(--accent)' : 'transparent',
                color: period === p ? 'white' : 'var(--text-secondary)',
              }}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* Biznes Pulsi */}
      <div className="card" style={{ padding: '20px', marginBottom: 20, background: 'linear-gradient(135deg, rgba(59,130,246,0.06), rgba(139,92,246,0.06))' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
          <Activity size={16} style={{ color: 'var(--accent)' }} />
          <span style={{ fontWeight: 600, fontSize: '0.875rem' }}>Biznes Pulsi</span>
          <span className="badge badge-green">Barqaror</span>
          <span className="badge badge-gray">{period}</span>
        </div>
        <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 16 }}>
          Suhbat sifati o'rtacha darajada. Eng zaif tomonlar: mijoz ehtiyojini aniqlash (A2 — 16%) va yopish bosqichi (E1 — 17%).
          Menejer faolligi {period === 'Bugun' ? 'past' : 'qoniqarli'}, ammo konversiya ko'rsatkichi oshirish kerak.
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12 }}>
          {[
            { l: 'Lid konversiya', v: '0.00%' },
            { l: 'Suhbat sifati', v: '72%' },
            { l: 'Topshiriqlar', v: '0' },
            { l: 'Bajarilishi', v: '–' },
          ].map(({ l, v }) => (
            <div key={l} style={{ background: 'var(--bg-card)', borderRadius: 10, padding: '12px 16px' }}>
              <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{l}</div>
              <div style={{ fontSize: '1.25rem', fontWeight: 700, marginTop: 4 }}>{v}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Stats grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 16, marginBottom: 20 }}>
        <StatCard label="Jami qo'ng'iroqlar" value="278" sub="172 ulangan" icon={Phone} trend={12} />
        <StatCard label="Tahlil qilingan" value="257" sub="17 baholangan" icon={BarChart2} trend={8} />
        <StatCard label="O'rt. davomiylik" value="1:47" sub="daqiqa" icon={Clock} />
        <StatCard label="Menejerlar" value="1" sub="1 faol" icon={Users} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
        {/* Quality trend chart */}
        <div className="card" style={{ padding: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
            <div style={{ fontWeight: 600, fontSize: '0.875rem' }}>Sifat trendi</div>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>So'nggi 7 kun</span>
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={qualityData}>
              <defs>
                <linearGradient id="scoreGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
              <XAxis dataKey="name" tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 11 }} axisLine={false} tickLine={false} domain={[0, 100]} />
              <Tooltip
                contentStyle={{ background: '#1e2230', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 12 }}
                labelStyle={{ color: 'rgba(255,255,255,0.6)' }}
              />
              <Area type="monotone" dataKey="score" stroke="#3b82f6" strokeWidth={2} fill="url(#scoreGrad)" name="Sifat %" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Alerts */}
        <div className="card" style={{ padding: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontWeight: 600, fontSize: '0.875rem' }}>Ogohlantirishlar</span>
              <span className="badge badge-red">25</span>
            </div>
            <Link href="/alerts" style={{ fontSize: '0.75rem', color: 'var(--accent)', display: 'flex', alignItems: 'center', gap: 2 }}>
              Ko'rish <ChevronRight size={12} />
            </Link>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {ALERTS.map((a, i) => (
              <div key={i} style={{
                display: 'flex', gap: 12, padding: '10px 12px',
                background: 'var(--bg-surface)', borderRadius: 8,
                borderLeft: `3px solid ${a.type === 'red' ? 'var(--accent-red)' : 'var(--accent-amber)'}`,
              }}>
                <AlertCircle size={15} style={{ color: a.type === 'red' ? 'var(--accent-red)' : 'var(--accent-amber)', flexShrink: 0, marginTop: 1 }} />
                <div>
                  <div style={{ fontSize: '0.8125rem', fontWeight: 600 }}>{a.title}</div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 2 }}>{a.desc}</div>
                  <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', marginTop: 4 }}>{a.time}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 16 }}>
        {/* Sifat trendi (mezonlar) */}
        <div className="card" style={{ padding: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
            <div style={{ fontWeight: 600, fontSize: '0.875rem' }}>Sotuv mezonlari bajarilishi</div>
            <Link href="/analytics/quality" style={{ fontSize: '0.75rem', color: 'var(--accent)', display: 'flex', alignItems: 'center', gap: 2 }}>
              Barchasi <ChevronRight size={12} />
            </Link>
          </div>
          <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: 8 }}>Avval eng zaif mezonlardan boshlang</p>
          {METRICS.map(m => <ScoreBar key={m.code} {...m} />)}
        </div>

        {/* Top managers */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="card" style={{ padding: 20 }}>
            <div style={{ fontWeight: 600, fontSize: '0.875rem', marginBottom: 16 }}>Menejerlar reytingi</div>
            {TOP_MANAGERS.map((m, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 12,
                padding: '12px 14px', background: 'var(--bg-surface)', borderRadius: 10,
              }}>
                <div style={{
                  width: 36, height: 36, borderRadius: '50%', flexShrink: 0,
                  background: 'linear-gradient(135deg, var(--accent), var(--accent-violet))',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontWeight: 700, fontSize: '0.875rem',
                }}>B</div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: '0.8125rem', fontWeight: 600 }}>{m.name}</div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 1 }}>{m.calls} qo'ng'iroq</div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontWeight: 700, color: 'var(--accent-green)' }}>{m.score}%</div>
                  <div style={{ fontSize: '0.6875rem', color: 'var(--accent-green)' }}>+{m.trend}%</div>
                </div>
              </div>
            ))}
          </div>

          {/* Nima uchun yo'qotyapmiz */}
          <div className="card" style={{ padding: 20 }}>
            <div style={{ fontWeight: 600, fontSize: '0.875rem', marginBottom: 12 }}>Nima uchun yo'qotyapmiz</div>
            {[
              { reason: 'Narx qimmat', count: 4, pct: 50 },
              { reason: 'Boshqa yechim bor', count: 3, pct: 38 },
              { reason: 'Ishonch yo\'q', count: 2, pct: 25 },
            ].map(r => (
              <div key={r.reason} style={{ marginBottom: 10 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{r.reason}</span>
                  <span style={{ fontSize: '0.75rem', fontWeight: 600 }}>{r.count}</span>
                </div>
                <div className="progress-bar">
                  <div className="progress-fill red" style={{ width: `${r.pct}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
