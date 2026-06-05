'use client';
import { useState } from 'react';
import { ChevronLeft, ChevronRight, Brain, TrendingUp, TrendingDown, Users, Phone, Star, AlertTriangle, CheckCircle } from 'lucide-react';

const DATES = ['5 Iyun, Juma', '4 Iyun, Payshanba', '3 Iyun, Chorshanba'];

const DAILY_DATA = {
  '5 Iyun, Juma': {
    ai_summary: 'Bugun 12 ta qo\'ng\'iroq amalga oshirildi. Sifat o\'rtacha — 68%. Yopish bosqichi (E1) eng zaif nuqta: 17%. Baxtiyorjon Gaziyev bugungi sessiyadan so\'ng yopish texnikasini takrorlashi kerak. 3 ta yangi lid ulandi, 1 ta bitim muzokara bosqichiga o\'tdi.',
    score: 68,
    score_delta: -4,
    calls: 12,
    calls_delta: -3,
    connected: 9,
    analyzed: 10,
    duration_avg: '3:42',
    managers: [
      { name: 'Baxtiyorjon Gaziyev', calls: 12, score: 68, delta: -4, trend: 'down' },
    ],
    weak_criteria: [
      { code: 'E1', name: 'Yopish urinishi', score: 17, tip: 'Yopish savolini qo\'ying: "Qachon boshlaymiz?"' },
      { code: 'E2', name: 'Shartnoma', score: 22, tip: 'Shartnoma yuborish vaqtini aniq belgilang.' },
      { code: 'A2', name: 'Muammo aniqlash', score: 31, tip: 'Mijozning og\'riq nuqtasini 2 savol bilan kashf eting.' },
    ],
    strong_criteria: [
      { code: 'A1', name: 'Salomlashish va rapport', score: 90 },
      { code: 'C1', name: 'Mahsulot taqdimoti', score: 85 },
      { code: 'F1', name: 'Nutq tezligi', score: 82 },
    ],
    recommendations: [
      { priority: 'high', text: 'Yopish bosqichi (E1) bo\'yicha bugun 30 daqiqalik trening o\'tkazing.' },
      { priority: 'medium', text: 'Baxtiyorjon bilan yopish skriptini birga ko\'rib chiqing.' },
      { priority: 'low', text: '+998973355900 lidiga ertaga qayta qo\'ng\'iroq qiling — 3 kundan beri javob yo\'q.' },
    ],
    pipeline: [
      { stage: 'Yangi so\'rov', count: 89 },
      { stage: 'Aloqa o\'rnatildi', count: 52 },
      { stage: 'Taklif yuborildi', count: 18 },
      { stage: 'Muzokara', count: 7 },
      { stage: 'Yopildi', count: 3 },
    ],
  },
};

const PRIORITY_COLORS: Record<string, string> = {
  high: 'var(--accent-red)',
  medium: 'var(--accent-amber)',
  low: 'var(--accent-green)',
};

export default function DailySummaryPage() {
  const [dateIdx, setDateIdx] = useState(0);
  const date = DATES[dateIdx] ?? DATES[0]!;
  const data = DAILY_DATA['5 Iyun, Juma'];

  return (
    <div style={{ padding: '24px', maxWidth: 900 }}>
      {/* Header + date nav */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: '1.25rem', fontWeight: 700, letterSpacing: '-0.01em' }}>Kunlik Hisobot</h1>
          <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginTop: 2 }}>AI tahlili va tavsiyalar</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button className="btn-icon" style={{ width: 32, height: 32 }} onClick={() => setDateIdx(i => Math.min(i + 1, DATES.length - 1))} disabled={dateIdx === DATES.length - 1}>
            <ChevronLeft size={15} />
          </button>
          <span style={{ fontWeight: 600, fontSize: '0.9rem', minWidth: 160, textAlign: 'center' }}>{date}</span>
          <button className="btn-icon" style={{ width: 32, height: 32 }} onClick={() => setDateIdx(i => Math.max(i - 1, 0))} disabled={dateIdx === 0}>
            <ChevronRight size={15} />
          </button>
        </div>
      </div>

      {/* AI Summary */}
      <div className="card" style={{ padding: 20, marginBottom: 16, borderLeft: '3px solid var(--accent-violet)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
          <Brain size={16} style={{ color: 'var(--accent-violet)' }} />
          <span style={{ fontWeight: 600, fontSize: '0.875rem' }}>AI Xulosasi</span>
        </div>
        <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', lineHeight: 1.7 }}>{data.ai_summary}</p>
      </div>

      {/* KPI row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 16 }}>
        {[
          { label: 'O\'rtacha sifat', value: `${data.score}%`, delta: data.score_delta, icon: Star },
          { label: 'Qo\'ng\'iroqlar', value: `${data.calls} ta`, delta: data.calls_delta, icon: Phone },
          { label: 'Ulangan', value: `${data.connected} ta`, delta: 0, icon: CheckCircle },
          { label: 'O\'rt. davomiylik', value: data.duration_avg, delta: 0, icon: Users },
        ].map(({ label, value, delta, icon: Icon }) => (
          <div key={label} className="card stat-card">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{label}</span>
              <Icon size={14} style={{ color: 'var(--accent)' }} />
            </div>
            <div style={{ fontSize: '1.5rem', fontWeight: 800, letterSpacing: '-0.02em' }}>{value}</div>
            {delta !== 0 && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginTop: 4 }}>
                {delta > 0 ? <TrendingUp size={12} style={{ color: 'var(--accent-green)' }} /> : <TrendingDown size={12} style={{ color: 'var(--accent-red)' }} />}
                <span style={{ fontSize: '0.75rem', color: delta > 0 ? 'var(--accent-green)' : 'var(--accent-red)' }}>
                  {delta > 0 ? '+' : ''}{delta} kechagidan
                </span>
              </div>
            )}
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
        {/* Weak criteria */}
        <div className="card" style={{ padding: 20 }}>
          <div style={{ fontWeight: 600, marginBottom: 14, display: 'flex', alignItems: 'center', gap: 6 }}>
            <AlertTriangle size={14} style={{ color: 'var(--accent-red)' }} />
            Zaif Mezonlar
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {data.weak_criteria.map(c => (
              <div key={c.code} style={{ padding: '10px 12px', background: 'rgba(239,68,68,0.06)', borderRadius: 8, border: '1px solid rgba(239,68,68,0.12)' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span style={{ fontWeight: 700, fontSize: '0.8125rem' }}>{c.code} — {c.name}</span>
                  <span style={{ fontWeight: 700, color: 'var(--accent-red)', fontSize: '0.875rem' }}>{c.score}%</span>
                </div>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>{c.tip}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Strong criteria */}
        <div className="card" style={{ padding: 20 }}>
          <div style={{ fontWeight: 600, marginBottom: 14, display: 'flex', alignItems: 'center', gap: 6 }}>
            <Star size={14} style={{ color: 'var(--accent-green)' }} />
            Kuchli Tomonlar
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {data.strong_criteria.map(c => (
              <div key={c.code} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ width: 32, fontSize: '0.75rem', fontWeight: 700, color: 'var(--accent)', flexShrink: 0 }}>{c.code}</span>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span style={{ fontSize: '0.8125rem' }}>{c.name}</span>
                    <span style={{ fontWeight: 700, color: 'var(--accent-green)', fontSize: '0.8125rem' }}>{c.score}%</span>
                  </div>
                  <div style={{ height: 4, background: 'rgba(255,255,255,0.06)', borderRadius: 2 }}>
                    <div style={{ height: '100%', width: `${c.score}%`, background: 'var(--accent-green)', borderRadius: 2, transition: 'width 0.6s ease' }} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Recommendations */}
      <div className="card" style={{ padding: 20, marginBottom: 16 }}>
        <div style={{ fontWeight: 600, marginBottom: 14 }}>Tavsiyalar</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {data.recommendations.map((r, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '10px 12px', background: 'var(--bg-surface)', borderRadius: 8 }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: PRIORITY_COLORS[r.priority] ?? 'var(--accent)', marginTop: 5, flexShrink: 0 }} />
              <span style={{ fontSize: '0.8125rem', lineHeight: 1.6, color: 'var(--text-secondary)' }}>{r.text}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Pipeline snapshot */}
      <div className="card" style={{ padding: 20 }}>
        <div style={{ fontWeight: 600, marginBottom: 14 }}>Pipeline Holati</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {data.pipeline.map((p, i) => {
            const max = data.pipeline[0]?.count ?? 1;
            const pct = Math.round((p.count / max) * 100);
            return (
              <div key={p.stage} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', width: 160, flexShrink: 0 }}>{p.stage}</span>
                <div style={{ flex: 1, height: 6, background: 'rgba(255,255,255,0.06)', borderRadius: 3 }}>
                  <div style={{
                    height: '100%', width: `${pct}%`,
                    background: i === data.pipeline.length - 1 ? 'var(--accent-green)' : 'var(--accent)',
                    borderRadius: 3, transition: 'width 0.6s ease',
                  }} />
                </div>
                <span style={{ fontWeight: 700, fontSize: '0.875rem', width: 36, textAlign: 'right' }}>{p.count}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
