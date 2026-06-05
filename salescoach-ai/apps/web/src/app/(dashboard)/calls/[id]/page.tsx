'use client';
import { useState } from 'react';
import Link from 'next/link';
import {
  ArrowLeft, ExternalLink, Share2, Play, Pause, SkipBack, SkipForward,
  PhoneIncoming, User, Building2, CheckCircle2, XCircle, Volume2,
  TrendingUp, Mic, Zap, ChevronDown, ChevronUp, Info,
} from 'lucide-react';

const MOCK_CALL = {
  id: '4',
  date: '2026-06-02 16:48',
  duration: '5:12',
  direction: 'in',
  status: 'analyzed',
  score: 85,
  manager: 'Baxtiyorjon Gaziyev',
  phone: '+998902222222',
  family: 'Yechim taqdimoti',
  service: 'Brendbuk',
  summary: "Mijoz yangi brendbuk loyihasi uchun murojaat qildi. Menejer ehtiyojlarni to'liq aniqladi va narx taklifini berdi. Mijoz qaror qabul qilish uchun hamkori bilan maslahatlashishi kerak. Keyingi qadam: 3 kun ichida qayta bog'lanish.",
  nextStep: "3 kun ichida mijozga qo'ng'iroq qilish va hamkor bilan birgalikda qaror qabul qilish",
  progressedSale: true,
  agreements: { client: ['Narxni ko\'rib chiqaman', '3 kunda javob beraman'], manager: ['3 kun ichida qayta bog\'lanaman', 'Namuna ishlarni yuboraman'] },
  clientName: 'Hasanboy Gaziyev',
  clientCompany: 'TechCorp LLC',
  isDecisionMaker: true,
  managerRatio: 49,
  clientRatio: 51,
  transcript: [
    { time: '0:01', role: 'client', text: 'Assalomu alaykum, jonbranding agentligiga murojaat qildim.' },
    { time: '0:04', role: 'manager', text: 'Va alaykum assalom! Baxtiyorjon, Jon Branding agency. Qanday yordam bera olaman?' },
    { time: '0:09', role: 'client', text: 'Bizga brendbuk kerak bo\'ldi. Yangi kompaniyani brand qilmoqchimiz.' },
    { time: '0:15', role: 'manager', text: 'Ajoyib! Kompaniyangiz qaysi sohada faoliyat yuritadi?' },
    { time: '0:20', role: 'client', text: 'IT sohasida, dasturiy ta\'minot ishlab chiqamiz. 15 nafar xodimimiz bor.' },
    { time: '0:28', role: 'manager', text: 'Brendbuk uchun bizda 3 ta paket mavjud. Asosiy, Standart va Premium. Sizga qaysi biri mos keladi?' },
    { time: '0:37', role: 'client', text: 'Narxlarini aytib bering avval.' },
    { time: '0:41', role: 'manager', text: 'Asosiy — 2 mln, Standart — 3.5 mln, Premium — 6 mln so\'m. Premium da animatsiya ham kiritiladi.' },
    { time: '0:52', role: 'client', text: 'Qiziq. Men hamkorim bilan maslahatlashib, 3 kunda javob beraman.' },
    { time: '1:00', role: 'manager', text: 'Albatta! Men ham 3 kun ichida siz bilan bog\'lanaman va namuna ishlarimizni yuboraman.' },
    { time: '1:07', role: 'client', text: 'Yaxshi, kutamiz.' },
    { time: '1:10', role: 'manager', text: 'Rahmat, Hasanboy. Ko\'rishguncha!' },
  ],
  metrics: [
    { code: 'A1', label: 'O\'zini tanishtirish', score: 3 },
    { code: 'A2', label: 'Murojaat manbai', score: 2 },
    { code: 'B1', label: 'Ehtiyoj aniqlash', score: 3 },
    { code: 'B2', label: 'Yo\'nalish', score: 2 },
    { code: 'C1', label: 'Qiymat tushuntirish', score: 3 },
    { code: 'E1', label: 'Keyingi qadam', score: 3 },
    { code: 'E3', label: 'Urgentlik', score: 1 },
  ],
  voice: { diction: 90, tone: 'Do\'stona', speed: '80 so\'z/daqiqa', energy: 'O\'rtacha' },
  signals: { urgency: 'Hozir', budgetReaction: 'Muhokama qilinmadi' },
};

export default function CallDetailPage({ params }: { params: { id: string } }) {
  const call = MOCK_CALL;
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState('1x');
  const [showFullTranscript, setShowFullTranscript] = useState(false);
  const [progress, setProgress] = useState(22);

  const visibleLines = showFullTranscript ? call.transcript : call.transcript.slice(0, 5);
  const hiddenCount = call.transcript.length - 5;

  return (
    <div style={{ padding: '24px', maxWidth: 1100 }}>
      {/* Top bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <Link href="/calls">
            <button className="btn-icon"><ArrowLeft size={15} /></button>
          </Link>
          <span className="badge badge-green">Tahlil qilingan</span>
          <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>{call.date} · {call.duration}</span>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-ghost" style={{ gap: 6 }}>
            <ExternalLink size={14} />Lid tafsilotlari
          </button>
          <button className="btn btn-ghost" style={{ gap: 6 }}>
            <Share2 size={14} />Ulashish
          </button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 20, alignItems: 'start' }}>
        {/* Left column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Summary */}
          <div className="card" style={{ padding: 20 }}>
            <h2 style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 10 }}>
              Suhbatda nima bo'ldi va bu nimani anglatadi
            </h2>
            <p style={{ fontSize: '0.875rem', lineHeight: 1.7, color: 'var(--text-secondary)', marginBottom: 14 }}>{call.summary}</p>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <span className="badge badge-blue">{call.family}</span>
              <span className="badge badge-green">Biznesga tegishli</span>
              <span className="badge badge-violet">{call.service}</span>
              <span className="badge badge-gray" style={{ gap: 4 }}>
                <span style={{ opacity: 0.5 }}>AmoCRM</span>
                <ExternalLink size={10} />
              </span>
            </div>
          </div>

          {/* 3 cards */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
            <div className="card" style={{ padding: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
                {call.progressedSale
                  ? <CheckCircle2 size={14} style={{ color: 'var(--accent-green)' }} />
                  : <XCircle size={14} style={{ color: 'var(--accent-red)' }} />}
                <span style={{ fontSize: '0.6875rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Sotuvni oldinga surdi</span>
              </div>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                Siljish bor, ammo keyingi aloqa mustahkam emas
              </p>
              <div style={{ marginTop: 8 }}>
                <span className="badge badge-green">2 kelishuv</span>
              </div>
            </div>
            <div className="card" style={{ padding: 16 }}>
              <div style={{ fontSize: '0.6875rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
                Keyingi qadam
              </div>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>{call.nextStep}</p>
            </div>
            <div className="card" style={{ padding: 16 }}>
              <div style={{ fontSize: '0.6875rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
                Qo'ng'iroq konteksti
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {[
                  ['Sana', call.date],
                  ['Davomiylik', call.duration],
                  ['Yo\'nalish', call.direction === 'in' ? 'Kiruvchi' : 'Chiquvchi'],
                  ['Menejer', call.manager.split(' ')[0]],
                ].map(([k, v]) => (
                  <div key={k} style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{k}</span>
                    <span style={{ fontSize: '0.75rem', fontWeight: 500 }}>{v}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Talk ratio */}
          <div className="card" style={{ padding: 20 }}>
            <div style={{ fontWeight: 600, fontSize: '0.875rem', marginBottom: 14 }}>Suhbat dinamikasi</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10 }}>
              <span style={{ width: 80, fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Menejer {call.managerRatio}%</span>
              <div style={{ flex: 1, height: 10, borderRadius: 5, overflow: 'hidden', background: 'rgba(255,255,255,0.05)', display: 'flex' }}>
                <div style={{ width: `${call.managerRatio}%`, background: 'var(--accent-amber)', borderRadius: '5px 0 0 5px' }} />
                <div style={{ width: `${call.clientRatio}%`, background: 'var(--accent-green)', borderRadius: '0 5px 5px 0' }} />
              </div>
              <span style={{ width: 80, fontSize: '0.8rem', color: 'var(--text-secondary)', textAlign: 'right' }}>Mijoz {call.clientRatio}%</span>
            </div>
            <div style={{ display: 'flex', gap: 12 }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, background: 'var(--accent-amber)' }} /> Menejer
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, background: 'var(--accent-green)' }} /> Mijoz
              </span>
            </div>
          </div>

          {/* Audio player */}
          <div className="card" style={{ padding: 20 }}>
            <div style={{ fontWeight: 600, fontSize: '0.875rem', marginBottom: 14 }}>Yozuv</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <button
                className="btn-icon"
                onClick={() => setPlaying(v => !v)}
                style={{ width: 40, height: 40, background: 'var(--accent)', borderColor: 'var(--accent)', color: 'white' }}
              >
                {playing ? <Pause size={16} /> : <Play size={16} />}
              </button>
              <div style={{ flex: 1 }}>
                <div style={{ height: 4, borderRadius: 2, background: 'rgba(255,255,255,0.08)', cursor: 'pointer', marginBottom: 4 }} onClick={e => {
                  const rect = e.currentTarget.getBoundingClientRect();
                  setProgress(Math.round(((e.clientX - rect.left) / rect.width) * 100));
                }}>
                  <div style={{ height: '100%', width: `${progress}%`, background: 'var(--accent)', borderRadius: 2 }} />
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.6875rem', color: 'var(--text-muted)' }}>
                  <span>0:{Math.round(progress * 3.12).toString().padStart(2,'0')}</span>
                  <span>5:12</span>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 4 }}>
                {['1x','1.25x','1.5x','2x'].map(s => (
                  <button
                    key={s}
                    className="btn"
                    onClick={() => setSpeed(s)}
                    style={{
                      padding: '3px 8px', fontSize: '0.75rem', borderRadius: 6,
                      background: speed === s ? 'var(--accent-muted)' : 'rgba(255,255,255,0.04)',
                      color: speed === s ? 'var(--accent)' : 'var(--text-muted)',
                    }}
                  >{s}</button>
                ))}
              </div>
            </div>
          </div>

          {/* Transcript */}
          <div className="card" style={{ padding: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
              <div style={{ fontWeight: 600, fontSize: '0.875rem' }}>Transkript</div>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{call.transcript.length} qator</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {visibleLines.map((line, i) => (
                <div key={i} style={{
                  display: 'flex', gap: 10,
                  justifyContent: line.role === 'manager' ? 'flex-end' : 'flex-start',
                }}>
                  {line.role === 'client' && (
                    <div style={{ width: 28, height: 28, borderRadius: '50%', background: 'rgba(255,255,255,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                      <User size={13} />
                    </div>
                  )}
                  <div style={{
                    maxWidth: '70%', padding: '8px 12px', borderRadius: 10,
                    background: line.role === 'manager' ? 'var(--accent-muted)' : 'var(--bg-surface)',
                    border: `1px solid ${line.role === 'manager' ? 'var(--border-accent)' : 'var(--border)'}`,
                  }}>
                    <div style={{ fontSize: '0.8125rem', lineHeight: 1.5 }}>{line.text}</div>
                    <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', marginTop: 3 }}>{line.time}</div>
                  </div>
                  {line.role === 'manager' && (
                    <div style={{ width: 28, height: 28, borderRadius: '50%', background: 'var(--accent-muted)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                      <Mic size={13} style={{ color: 'var(--accent)' }} />
                    </div>
                  )}
                </div>
              ))}
            </div>
            {hiddenCount > 0 && (
              <button
                onClick={() => setShowFullTranscript(v => !v)}
                style={{ width: '100%', marginTop: 12, padding: '8px', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text-secondary)', fontSize: '0.8125rem', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}
              >
                {showFullTranscript ? <><ChevronUp size={14} />Yig'ish</> : <><ChevronDown size={14} />Yana {hiddenCount} qatorni ko'rsatish</>}
              </button>
            )}
          </div>
        </div>

        {/* Right column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Score */}
          <div className="card" style={{ padding: 20, textAlign: 'center' }}>
            <div style={{ fontSize: '0.6875rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 12 }}>
              Sifat baho
            </div>
            <div style={{
              width: 88, height: 88, borderRadius: '50%', margin: '0 auto 12px',
              background: `conic-gradient(var(--accent-green) ${call.score}%, rgba(255,255,255,0.05) 0)`,
              display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative',
            }}>
              <div style={{ position: 'absolute', inset: 9, borderRadius: '50%', background: 'var(--bg-card)' }} />
              <span style={{ position: 'relative', fontWeight: 800, fontSize: '1.25rem', color: 'var(--accent-green)' }}>{call.score}%</span>
            </div>
            <span className="badge badge-green">Yaxshi</span>
          </div>

          {/* Criteria scores */}
          <div className="card" style={{ padding: 20 }}>
            <div style={{ fontWeight: 600, fontSize: '0.875rem', marginBottom: 12 }}>Mezonlar</div>
            {call.metrics.map(m => (
              <div key={m.code} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--border)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontSize: '0.6875rem', fontFamily: 'monospace', color: 'var(--text-muted)', width: 28 }}>{m.code}</span>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{m.label}</span>
                </div>
                <div style={{ display: 'flex', gap: 2 }}>
                  {[1,2,3].map(d => (
                    <div key={d} style={{ width: 8, height: 8, borderRadius: 2, background: d <= m.score ? 'var(--accent)' : 'rgba(255,255,255,0.08)' }} />
                  ))}
                </div>
              </div>
            ))}
          </div>

          {/* Client info */}
          <div className="card" style={{ padding: 20 }}>
            <div style={{ fontWeight: 600, fontSize: '0.875rem', marginBottom: 12 }}>Mijoz ma'lumotlari</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <User size={14} style={{ color: 'var(--text-muted)' }} />
                <span style={{ fontSize: '0.8125rem' }}>{call.clientName}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Building2 size={14} style={{ color: 'var(--text-muted)' }} />
                <span style={{ fontSize: '0.8125rem' }}>{call.clientCompany}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Info size={14} style={{ color: 'var(--text-muted)' }} />
                <span style={{ fontSize: '0.8125rem' }}>Qaror qabul qiluvchi: </span>
                <span className={`badge ${call.isDecisionMaker ? 'badge-green' : 'badge-amber'}`}>
                  {call.isDecisionMaker ? 'Ha' : 'Yo\'q'}
                </span>
              </div>
            </div>
          </div>

          {/* Voice analysis */}
          <div className="card" style={{ padding: 20 }}>
            <div style={{ fontWeight: 600, fontSize: '0.875rem', marginBottom: 12 }}>Ovoz tahlili</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              {[
                { label: 'Diksiya', value: `${call.voice.diction}%`, color: 'var(--accent-green)' },
                { label: 'Ohang', value: call.voice.tone },
                { label: 'Tezlik', value: call.voice.speed },
                { label: 'Energiya', value: call.voice.energy },
              ].map(v => (
                <div key={v.label} style={{ background: 'var(--bg-surface)', borderRadius: 8, padding: '10px 12px' }}>
                  <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', marginBottom: 3 }}>{v.label}</div>
                  <div style={{ fontSize: '0.875rem', fontWeight: 600, color: v.color || 'var(--text-primary)' }}>{v.value}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Agreements */}
          <div className="card" style={{ padding: 20 }}>
            <div style={{ fontWeight: 600, fontSize: '0.875rem', marginBottom: 12 }}>Kelishuvlar</div>
            <div style={{ marginBottom: 10 }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: 6 }}>Mijoz</div>
              {call.agreements.client.map((a, i) => (
                <span key={i} className="badge badge-green" style={{ marginRight: 4, marginBottom: 4 }}>{a}</span>
              ))}
            </div>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: 6 }}>Menejer</div>
              {call.agreements.manager.map((a, i) => (
                <span key={i} className="badge badge-blue" style={{ marginRight: 4, marginBottom: 4 }}>{a}</span>
              ))}
            </div>
          </div>

          {/* Signals */}
          <div className="card" style={{ padding: 20 }}>
            <div style={{ fontWeight: 600, fontSize: '0.875rem', marginBottom: 12 }}>Signallar</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Shoshilinchlik</span>
                <span className="badge badge-amber">{call.signals.urgency}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Byudjet reaktsiyasi</span>
                <span className="badge badge-gray">{call.signals.budgetReaction}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
