'use client';
import { useState } from 'react';
import { Search, Phone, PhoneIncoming, PhoneOutgoing, Clock, TrendingUp, User, ChevronRight, MessageSquare } from 'lucide-react';

const LEADS = [
  {
    id: '1', name: 'Anvar Toshmatov', phone: '+998901234567', status: 'muzokara',
    service: 'Brendbuk', budget: '~12M UZS', source: 'Instagram',
    last_call: '2026-06-04', calls_count: 5, last_score: 85,
    summary: 'Mijoz brendbuk dizayn buyurtmasiga qiziqyapti. Kompaniya uchun to\'liq brendbuk: logotip, ranglar, shriftlar va qo\'llanma. Byudjet aniqlangan — 12M UZS atrofida. Ertaga final taklif kutmoqda.',
    next_action: 'Bugun soat 17:00 gacha taklif yuborish.',
    stage: 4, sentiment: 'positive',
  },
  {
    id: '2', name: 'Dilnoza Yusupova', phone: '+998973355900', status: 'sovuq',
    service: 'Logotip', budget: '~2M UZS', source: 'Referral',
    last_call: '2026-06-01', calls_count: 3, last_score: null,
    summary: '3 marta urinish — hamon javob yo\'q. Referral orqali kelgan. Logotip dizayn kerak deydi, lekin vaqt topa olmayapti.',
    next_action: '3 kun kutib, Telegram orqali murojaat qiling.',
    stage: 1, sentiment: 'neutral',
  },
  {
    id: '3', name: 'Sardor Karimov', phone: '+998902222222', status: 'faol',
    service: 'Naming', budget: '~3.5M UZS', source: 'Website',
    last_call: '2026-06-05', calls_count: 2, last_score: 72,
    summary: 'Yangi brend uchun ism kerak. 3 ta variant so\'radi. Qarorni keyingi haftaga qoldirdi. Kompaniya — IT startup.',
    next_action: '8 iyun, dushanba kuni qayta qo\'ng\'iroq.',
    stage: 2, sentiment: 'positive',
  },
  {
    id: '4', name: 'Malika Xasanova', phone: '+998903333333', status: 'yopildi',
    service: 'Qadoq dizayni', budget: '8M UZS', source: 'TikTok',
    last_call: '2026-06-02', calls_count: 7, last_score: 91,
    summary: 'Bitim yopildi! Qadoq dizayni uchun 8M UZS shartnoma imzolandi. Boshlanish — 10 iyun.',
    next_action: 'Oldindan to\'lov (50%) kuzatib boring.',
    stage: 5, sentiment: 'positive',
  },
  {
    id: '5', name: 'Jamshid Normatov', phone: '+998904444444', status: 'taklif',
    service: 'Brendbuk', budget: '~18M UZS', source: 'Instagram',
    last_call: '2026-06-03', calls_count: 4, last_score: 67,
    summary: 'Yirik restoran tarmog\'i. Brendbuk, menyu dizayni, uniform grafika kerak. Byudjet katta, lekin qaror jamoaviy.',
    next_action: 'Taklif yuborildi. 3 kun kutish.',
    stage: 3, sentiment: 'neutral',
  },
];

const STATUS_STYLES: Record<string, { label: string; cls: string }> = {
  muzokara: { label: 'Muzokara', cls: 'badge-violet' },
  sovuq:    { label: 'Sovuq lid', cls: 'badge-gray' },
  faol:     { label: 'Faol', cls: 'badge-blue' },
  yopildi:  { label: 'Yopildi ✓', cls: 'badge-green' },
  taklif:   { label: 'Taklif', cls: 'badge-amber' },
};

const SENTIMENT_ICON: Record<string, string> = { positive: '😊', neutral: '😐', negative: '😟' };

export default function LeadSummariesPage() {
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<string | null>('1');

  const filtered = LEADS.filter(l =>
    l.name.toLowerCase().includes(search.toLowerCase()) ||
    l.phone.includes(search) ||
    l.service.toLowerCase().includes(search.toLowerCase())
  );

  const lead = selected ? LEADS.find(l => l.id === selected) : null;

  return (
    <div style={{ height: '100%', display: 'flex', gap: 0, overflow: 'hidden' }}>
      {/* Left panel: lead list */}
      <div style={{ width: 320, borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ padding: '20px 16px 12px', borderBottom: '1px solid var(--border)' }}>
          <h1 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: 10 }}>Lid Xulosalari</h1>
          <div style={{ position: 'relative' }}>
            <Search size={13} style={{ position: 'absolute', left: 9, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input
              className="input"
              placeholder="Ism, telefon, xizmat..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{ paddingLeft: 28, height: 34, fontSize: '0.8125rem' }}
            />
          </div>
        </div>

        <div style={{ flex: 1, overflow: 'auto' }}>
          {filtered.map(l => {
            const st = STATUS_STYLES[l.status] ?? { label: l.status, cls: 'badge-gray' };
            return (
              <div
                key={l.id}
                onClick={() => setSelected(l.id)}
                style={{
                  padding: '12px 16px',
                  borderBottom: '1px solid var(--border)',
                  cursor: 'pointer',
                  background: selected === l.id ? 'rgba(59,130,246,0.08)' : 'transparent',
                  borderLeft: selected === l.id ? '2px solid var(--accent)' : '2px solid transparent',
                  transition: 'all 0.1s',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 4 }}>
                  <span style={{ fontWeight: 600, fontSize: '0.875rem' }}>{l.name}</span>
                  <span className={`badge ${st.cls}`} style={{ fontSize: '0.625rem' }}>{st.label}</span>
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: 4 }}>{l.phone}</div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.6875rem', color: 'var(--accent)', background: 'var(--accent-muted)', padding: '2px 6px', borderRadius: 4 }}>{l.service}</span>
                  <span style={{ fontSize: '0.6875rem', color: 'var(--text-muted)' }}>{l.calls_count} ta qo'ng'iroq</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Right panel: detail */}
      {lead ? (
        <div style={{ flex: 1, overflow: 'auto', padding: 24 }}>
          {/* Lead header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
                <div style={{ width: 40, height: 40, borderRadius: '50%', background: 'linear-gradient(135deg, var(--accent), var(--accent-violet))', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: '1.125rem' }}>
                  {lead.name[0]}
                </div>
                <div>
                  <h2 style={{ fontWeight: 700, fontSize: '1.125rem' }}>{lead.name}</h2>
                  <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>{lead.phone}</div>
                </div>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn btn-ghost" style={{ height: 34, fontSize: '0.8125rem', gap: 6 }}>
                <Phone size={13} />Qo'ng'iroq
              </button>
              <button className="btn btn-ghost" style={{ height: 34, fontSize: '0.8125rem', gap: 6 }}>
                <MessageSquare size={13} />Xabar
              </button>
            </div>
          </div>

          {/* Info grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 16 }}>
            {[
              { label: 'Xizmat', value: lead.service },
              { label: 'Byudjet', value: lead.budget },
              { label: 'Manba', value: lead.source },
              { label: 'Sentiment', value: `${SENTIMENT_ICON[lead.sentiment] ?? ''} ${lead.sentiment}` },
            ].map(({ label, value }) => (
              <div key={label} className="card" style={{ padding: '10px 12px' }}>
                <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', marginBottom: 3 }}>{label}</div>
                <div style={{ fontWeight: 600, fontSize: '0.875rem' }}>{value}</div>
              </div>
            ))}
          </div>

          {/* Pipeline progress */}
          <div className="card" style={{ padding: 16, marginBottom: 16 }}>
            <div style={{ fontWeight: 600, fontSize: '0.875rem', marginBottom: 12 }}>Savdo Bosqichi</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 0 }}>
              {['Yangi', 'Aloqa', 'Taklif', 'Muzokara', 'Yopildi'].map((s, i) => (
                <div key={s} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', width: '100%' }}>
                    {i > 0 && <div style={{ flex: 1, height: 2, background: i < lead.stage ? 'var(--accent)' : 'var(--border)' }} />}
                    <div style={{
                      width: 24, height: 24, borderRadius: '50%', flexShrink: 0,
                      background: i < lead.stage ? 'var(--accent)' : i === lead.stage - 1 ? 'var(--accent)' : 'var(--bg-surface)',
                      border: `2px solid ${i < lead.stage ? 'var(--accent)' : 'var(--border)'}`,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                      {i < lead.stage && <span style={{ fontSize: '0.625rem', color: 'white', fontWeight: 700 }}>✓</span>}
                    </div>
                    {i < 4 && <div style={{ flex: 1, height: 2, background: i < lead.stage - 1 ? 'var(--accent)' : 'var(--border)' }} />}
                  </div>
                  <span style={{ fontSize: '0.625rem', color: i < lead.stage ? 'var(--accent)' : 'var(--text-muted)', marginTop: 4, textAlign: 'center' }}>{s}</span>
                </div>
              ))}
            </div>
          </div>

          {/* AI summary */}
          <div className="card" style={{ padding: 16, marginBottom: 16, borderLeft: '3px solid var(--accent-violet)' }}>
            <div style={{ fontWeight: 600, fontSize: '0.875rem', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
              AI Xulosasi
            </div>
            <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', lineHeight: 1.7 }}>{lead.summary}</p>
          </div>

          {/* Next action */}
          <div className="card" style={{ padding: 16, marginBottom: 16, background: 'rgba(16,185,129,0.06)', border: '1px solid rgba(16,185,129,0.2)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <ChevronRight size={15} style={{ color: 'var(--accent-green)' }} />
              <span style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--accent-green)' }}>Keyingi qadam:</span>
              <span style={{ fontSize: '0.875rem' }}>{lead.next_action}</span>
            </div>
          </div>

          {/* Call stats */}
          <div className="card" style={{ padding: 16 }}>
            <div style={{ fontWeight: 600, fontSize: '0.875rem', marginBottom: 12 }}>Qo'ng'iroqlar</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
              {[
                { label: 'Jami qo\'ng\'iroq', value: `${lead.calls_count} ta` },
                { label: 'Oxirgi sifat', value: lead.last_score !== null ? `${lead.last_score}%` : '—' },
                { label: 'Oxirgi aloqa', value: lead.last_call },
              ].map(({ label, value }) => (
                <div key={label} style={{ background: 'var(--bg-surface)', borderRadius: 8, padding: '10px 12px' }}>
                  <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', marginBottom: 3 }}>{label}</div>
                  <div style={{ fontWeight: 700, fontSize: '1rem' }}>{value}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
          <p>Lid tanlang</p>
        </div>
      )}
    </div>
  );
}
