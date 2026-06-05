'use client';
import { useState } from 'react';
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, AreaChart, Area, PieChart, Pie, Cell, Legend,
} from 'recharts';
import { TrendingUp, TrendingDown, Brain, ChevronRight } from 'lucide-react';

const TABS = [
  'Umumiy ko\'rinish',
  'Sifat nazorati',
  'Jamoa malakasi',
  'Mijoz tahlili',
  'Faoliyat tahlili',
  'Lid analitikasi',
] as const;

const weeklyData = [
  { name: 'Du', calls: 38, scored: 6, quality: 68 },
  { name: 'Se', calls: 44, scored: 9, quality: 71 },
  { name: 'Ch', calls: 31, scored: 5, quality: 65 },
  { name: 'Pa', calls: 52, scored: 11, quality: 74 },
  { name: 'Ju', calls: 47, scored: 8, quality: 69 },
  { name: 'Sh', calls: 28, scored: 4, quality: 79 },
  { name: 'Ya', calls: 38, scored: 7, quality: 72 },
];

const objections = [
  { name: 'Narx qimmat', count: 4 },
  { name: 'Boshqa yechim', count: 3 },
  { name: 'Ishonch yo\'q', count: 2 },
  { name: 'Kerak emas', count: 2 },
  { name: 'O\'ylab ko\'raman', count: 1 },
  { name: 'Vaqt yo\'q', count: 1 },
];

const urgencyData = [
  { name: 'Hozir', value: 35 },
  { name: '1 hafta', value: 28 },
  { name: '1 oy', value: 22 },
  { name: 'Noaniq', value: 15 },
];

const PIE_COLORS = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b'];

const QUALITY_CRITERIA = [
  { code: 'A2', name: 'Murojaat manbasini aniqlash', score: 16, weak: 11, issue: 'Ko\'p hollarda umuman so\'ralmaydi', tip: 'Darhol "Qayerdan bildingiz?" deb so\'rang' },
  { code: 'E1', name: 'Brif yuborish', score: 17, weak: 10, issue: 'Keyingi qadam kelishilmaydi', tip: 'Har qo\'ng\'iroq oxirida aniq sana belgilang' },
  { code: 'A3', name: 'Suhbat maqsadini belgilash', score: 23, weak: 9, issue: 'Bevosita savdoga o\'tiladi', tip: 'Avval maqsadni aytib ruxsat oling' },
  { code: 'E3', name: 'Moliyaviy kelishuvni yakunlash', score: 31, weak: 8, issue: 'Narx muhokama qilinmaydi', tip: 'Narxni qiymatdan keyin aytish kerak' },
  { code: 'B3', name: 'Qaror va resurs holati', score: 38, weak: 7, issue: 'Qaror qabul qiluvchi aniqlanmaydi', tip: '"Qaror qabul qilishda kim qatnashadi?" deb so\'rang' },
];

const activityData = [
  { date: '28.05', calls: 42, connected: 28 },
  { date: '29.05', calls: 38, connected: 22 },
  { date: '30.05', calls: 51, connected: 34 },
  { date: '31.05', calls: 44, connected: 30 },
  { date: '01.06', calls: 47, connected: 31 },
  { date: '02.06', calls: 55, connected: 38 },
  { date: '03.06', calls: 39, connected: 24 },
];

const lidData = [
  { stage: 'Yangi so\'rov', count: 89 },
  { stage: 'Aloqa o\'rnatildi', count: 52 },
  { stage: 'Taklif yuborildi', count: 18 },
  { stage: 'Muzokara', count: 7 },
  { stage: 'Yopildi', count: 3 },
];

function StatBig({ label, value, sub, trend }: { label: string; value: string; sub?: string; trend?: number }) {
  return (
    <div className="stat-card">
      <div className="stat-label" style={{ marginBottom: 6 }}>{label}</div>
      <div className="stat-value">{value}</div>
      {sub && <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 3 }}>{sub}</div>}
      {trend !== undefined && (
        <div style={{ marginTop: 6, fontSize: '0.75rem', fontWeight: 600, color: trend >= 0 ? 'var(--accent-green)' : 'var(--accent-red)', display: 'flex', alignItems: 'center', gap: 3 }}>
          {trend >= 0 ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
          {trend >= 0 ? '+' : ''}{trend}%
        </div>
      )}
    </div>
  );
}

export default function AnalyticsPage() {
  const [tab, setTab] = useState<typeof TABS[number]>(TABS[0]);
  const [period, setPeriod] = useState('Hafta');

  return (
    <div style={{ padding: '24px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <h1 style={{ fontSize: '1.25rem', fontWeight: 700, letterSpacing: '-0.01em' }}>Analitika</h1>
        <div style={{ display: 'flex', gap: 4, background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 10, padding: 4 }}>
          {['Bugun','3 kun','Hafta','Oy'].map(p => (
            <button key={p} onClick={() => setPeriod(p)} className="btn" style={{ padding: '4px 12px', borderRadius: 7, fontSize: '0.8125rem', background: period === p ? 'var(--accent)' : 'transparent', color: period === p ? 'white' : 'var(--text-secondary)' }}>
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 2, borderBottom: '1px solid var(--border)', marginBottom: 24, overflowX: 'auto' }}>
        {TABS.map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            padding: '10px 16px', fontSize: '0.8125rem', fontWeight: 500, cursor: 'pointer',
            background: 'transparent', border: 'none', whiteSpace: 'nowrap',
            color: tab === t ? 'var(--accent)' : 'var(--text-secondary)',
            borderBottom: tab === t ? '2px solid var(--accent)' : '2px solid transparent',
            marginBottom: -1, transition: 'all 0.15s',
          }}>{t}</button>
        ))}
      </div>

      {/* Tab 1: Overview */}
      {tab === 'Umumiy ko\'rinish' && (
        <div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 14, marginBottom: 20 }}>
            <StatBig label="Sotuvlar" value="0" trend={-100} />
            <StatBig label="Lid konversiya" value="0.00%" trend={-100} />
            <StatBig label="Suhbat sifati" value="72%" trend={8} />
            <StatBig label="Yopilishga yaqin" value="7" sub="lid" trend={12} />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 14, marginBottom: 20 }}>
            <StatBig label="Bitim tushumi" value="0 UZS" />
            <StatBig label="O'rtacha bitim" value="—" />
            <StatBig label="Topshiriqlar" value="0" />
            <StatBig label="Bajarilishi" value="—" />
          </div>
          <div className="card" style={{ padding: 20 }}>
            <div style={{ fontWeight: 600, fontSize: '0.875rem', marginBottom: 16 }}>Konversiya va suhbat sifati trendi</div>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={weeklyData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="name" tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis yAxisId="left" tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis yAxisId="right" orientation="right" domain={[0,100]} tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ background: '#1e2230', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 12 }} />
                <Line yAxisId="left" type="monotone" dataKey="calls" stroke="#8b5cf6" strokeWidth={2} dot={false} name="Qo'ng'iroqlar" />
                <Line yAxisId="right" type="monotone" dataKey="quality" stroke="#3b82f6" strokeWidth={2} dot={false} name="Sifat %" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Tab 2: Quality */}
      {tab === 'Sifat nazorati' && (
        <div>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: 16 }}>Avval eng zaif mezonlardan boshlang</p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {QUALITY_CRITERIA.map(c => {
              const color = c.score >= 70 ? 'var(--accent-green)' : c.score >= 40 ? 'var(--accent-amber)' : 'var(--accent-red)';
              return (
                <div key={c.code} className="card" style={{ padding: 20 }}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 10 }}>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                        <span className="badge badge-gray" style={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>{c.code}</span>
                        <span style={{ fontWeight: 600, fontSize: '0.875rem' }}>{c.name}</span>
                      </div>
                      <div style={{ display: 'flex', gap: 8 }}>
                        <span className="badge badge-red" style={{ fontSize: '0.6875rem' }}>🔴 Hozir ko'p uchraydi: {c.issue}</span>
                      </div>
                    </div>
                    <div style={{ textAlign: 'right', flexShrink: 0 }}>
                      <div style={{ fontSize: '1.5rem', fontWeight: 800, color }}>{c.score}%</div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{c.weak} zaif holat</div>
                    </div>
                  </div>
                  <div className="progress-bar" style={{ marginBottom: 10 }}>
                    <div className="progress-fill" style={{ width: `${c.score}%`, background: color }} />
                  </div>
                  <div className="badge badge-green" style={{ fontSize: '0.75rem' }}>✅ Intilish kerak: {c.tip}</div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Tab 3: Coaching */}
      {tab === 'Jamoa malakasi' && (
        <div>
          <div className="card" style={{ padding: 24, marginBottom: 16, background: 'linear-gradient(135deg, rgba(139,92,246,0.08), rgba(59,130,246,0.08))' }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
              <div style={{ width: 40, height: 40, borderRadius: 10, background: 'rgba(139,92,246,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                <Brain size={20} style={{ color: '#a78bfa' }} />
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 700, fontSize: '1rem', marginBottom: 4 }}>AI Malaka oshirish tavsiyasi</div>
                <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 14 }}>
                  AI joriy jamoa natijalarini tahlil qilib, kim bilan va qaysi yo'nalishda ishlash kerakligini aniqladi.
                </p>
                <div style={{ background: 'var(--bg-card)', borderRadius: 12, padding: 16, marginBottom: 12 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                    <span className="badge badge-violet">1-Prioritet</span>
                    <span style={{ fontWeight: 600 }}>Baxtiyorjon Gaziyev</span>
                  </div>
                  <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                    Eng zaif tomonlar: ehtiyojni aniqlash (A2 — 16%) va yopish bosqichi (E1 — 17%).
                    Tavsiya: haftada 2 marta murojaat manbai bo'yicha mashq, har qo'ng'iroqni aniq keyingi qadam bilan yakunlash.
                  </p>
                  <div style={{ marginTop: 10 }}>
                    <button className="btn btn-primary" style={{ fontSize: '0.8125rem' }}>
                      Ko'rib chiqish qo'ng'irog'ini ochish <ChevronRight size={13} />
                    </button>
                  </div>
                </div>
                <button className="btn btn-ghost" style={{ fontSize: '0.8125rem', gap: 6 }}>
                  <Brain size={14} />AI tavsiyasini yangilash
                </button>
              </div>
            </div>
          </div>
          <div className="card" style={{ padding: 20 }}>
            <div style={{ fontWeight: 600, marginBottom: 12 }}>Jamoa fokuslari</div>
            {['Ehtiyojni aniqlash (BANT metodikasi)', 'Yopish texnikasi (trial close)', 'Murojaat manbai so\'rash', 'Narxni qiymatdan keyin aytish'].map((f, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
                <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--accent-amber)', flexShrink: 0 }} />
                <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>{f}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 4: Client analysis */}
      {tab === 'Mijoz tahlili' && (
        <div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginBottom: 20 }}>
            <StatBig label="Jami bitim summasi" value="0 UZS" />
            <StatBig label="Bitimlar soni" value="0" />
            <StatBig label="O'rtacha bitim" value="—" />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <div className="card" style={{ padding: 20 }}>
              <div style={{ fontWeight: 600, marginBottom: 16 }}>Top e'tirozlar</div>
              {objections.map(o => (
                <div key={o.name} style={{ marginBottom: 10 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>{o.name}</span>
                    <span style={{ fontWeight: 600, fontSize: '0.8125rem' }}>{o.count}</span>
                  </div>
                  <div className="progress-bar">
                    <div className="progress-fill red" style={{ width: `${(o.count / 4) * 100}%` }} />
                  </div>
                </div>
              ))}
            </div>
            <div className="card" style={{ padding: 20 }}>
              <div style={{ fontWeight: 600, marginBottom: 16 }}>Shoshilinchlik darajasi</div>
              <ResponsiveContainer width="100%" height={180}>
                <PieChart>
                  <Pie data={urgencyData} cx="50%" cy="50%" outerRadius={70} dataKey="value" label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`} labelLine={false} fontSize={10}>
                    {urgencyData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                  </Pie>
                  <Tooltip contentStyle={{ background: '#1e2230', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 12 }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}

      {/* Tab 5: Activity */}
      {tab === 'Faoliyat tahlili' && (
        <div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginBottom: 20 }}>
            <StatBig label="Jami qo'ng'iroqlar" value="278" trend={12} />
            <StatBig label="Ulangan" value="172" sub="62% bog'lanish darajasi" trend={5} />
            <StatBig label="Bog'lana olmagan" value="106" trend={-8} />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginBottom: 20 }}>
            <StatBig label="Tahlil qilingan" value="257" />
            <StatBig label="Baholangan savdo" value="17" />
            <StatBig label="O'rt. davomiylik" value="1:47" />
          </div>
          <div className="card" style={{ padding: 20 }}>
            <div style={{ fontWeight: 600, marginBottom: 16 }}>Bog'lana olmagan — Faollik tendensiyasi</div>
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={activityData}>
                <defs>
                  <linearGradient id="callGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="connGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="date" tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ background: '#1e2230', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 12 }} />
                <Area type="monotone" dataKey="calls" stroke="#3b82f6" strokeWidth={2} fill="url(#callGrad)" name="Jami" />
                <Area type="monotone" dataKey="connected" stroke="#10b981" strokeWidth={2} fill="url(#connGrad)" name="Ulangan" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Tab 6: Leads */}
      {tab === 'Lid analitikasi' && (
        <div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 14, marginBottom: 20 }}>
            <StatBig label="Jami yangi lidlar" value="89" trend={-65} />
            <StatBig label="Yutgan" value="0" trend={-100} />
            <StatBig label="Yo'qotilgan" value="8" />
            <StatBig label="Lid konversiya" value="0.00%" trend={-100} />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 14, marginBottom: 20 }}>
            <StatBig label="Faol lidlar" value="85" />
            <StatBig label="O'rtacha tsikl" value="82 kun" />
            <StatBig label="Lid sifati" value="24%" />
            <StatBig label="Yutgan summa" value="0 UZS" />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <div className="card" style={{ padding: 20 }}>
              <div style={{ fontWeight: 600, marginBottom: 16 }}>Sotuv voronkasi</div>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={lidData} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" horizontal={false} />
                  <XAxis type="number" tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis type="category" dataKey="stage" tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 11 }} axisLine={false} tickLine={false} width={110} />
                  <Tooltip contentStyle={{ background: '#1e2230', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 12 }} />
                  <Bar dataKey="count" fill="#3b82f6" radius={[0,4,4,0]} name="Lidlar" />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="card" style={{ padding: 20 }}>
              <div style={{ fontWeight: 600, marginBottom: 12 }}>Lid sifati taqsimoti</div>
              <div style={{ height: 12, borderRadius: 6, overflow: 'hidden', display: 'flex', marginBottom: 12 }}>
                <div style={{ width: '67%', background: 'var(--accent-red)' }} />
                <div style={{ width: '6%', background: 'var(--accent-amber)' }} />
                <div style={{ width: '27%', background: 'var(--accent-green)' }} />
              </div>
              <div style={{ display: 'flex', gap: 16 }}>
                {[
                  { label: 'Past sifatli', count: 12, pct: '67%', color: 'var(--accent-red)' },
                  { label: 'O\'rtacha', count: 1, pct: '6%', color: 'var(--accent-amber)' },
                  { label: 'Yaxshi', count: 5, pct: '28%', color: 'var(--accent-green)' },
                ].map(q => (
                  <div key={q.label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <div style={{ width: 8, height: 8, borderRadius: 2, background: q.color, flexShrink: 0 }} />
                    <div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{q.label}</div>
                      <div style={{ fontWeight: 700, fontSize: '0.875rem' }}>{q.count} <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>({q.pct})</span></div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
