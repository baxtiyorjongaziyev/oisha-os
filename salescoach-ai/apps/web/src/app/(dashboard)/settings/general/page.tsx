'use client';
import { useState } from 'react';
import { Globe, Clock, Building, Palette, Moon } from 'lucide-react';

const TIMEZONES = ['Asia/Tashkent (UTC+5)', 'Europe/Moscow (UTC+3)', 'Asia/Almaty (UTC+6)'];
const LANGUAGES = ['O\'zbekcha', 'Русский', 'English'];
const THEMES = ['Qora (Dark)', 'Oq (Light)', 'Tizimdan'];

export default function GeneralSettingsPage() {
  const [tz, setTz] = useState(TIMEZONES[0]!);
  const [lang, setLang] = useState(LANGUAGES[0]!);
  const [theme, setTheme] = useState(THEMES[0]!);
  const [workStart, setWorkStart] = useState('09:00');
  const [workEnd, setWorkEnd] = useState('18:00');
  const [saved, setSaved] = useState(false);

  const save = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div style={{ padding: '32px', maxWidth: 600 }}>
      <h2 style={{ fontSize: '1.125rem', fontWeight: 700, marginBottom: 4 }}>Umumiy sozlamalar</h2>
      <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginBottom: 24 }}>Platforma xatti-harakati va interfeys</p>

      {/* Business */}
      <div className="card" style={{ padding: 20, marginBottom: 16 }}>
        <div style={{ fontWeight: 600, marginBottom: 14, display: 'flex', alignItems: 'center', gap: 6 }}>
          <Building size={14} style={{ color: 'var(--accent)' }} />
          Biznes nomi
        </div>
        <input className="input" defaultValue="Jon Branding Agency" />
        <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 6 }}>Hisobotlarda va shartnomalardan ko'rinadi</p>
      </div>

      {/* Language */}
      <div className="card" style={{ padding: 20, marginBottom: 16 }}>
        <div style={{ fontWeight: 600, marginBottom: 14, display: 'flex', alignItems: 'center', gap: 6 }}>
          <Globe size={14} style={{ color: 'var(--accent)' }} />
          Til
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {LANGUAGES.map(l => (
            <button
              key={l}
              onClick={() => setLang(l)}
              className="btn btn-ghost"
              style={{
                height: 36, fontSize: '0.8125rem',
                background: lang === l ? 'var(--accent-muted)' : undefined,
                color: lang === l ? 'var(--accent)' : undefined,
                borderColor: lang === l ? 'var(--border-accent)' : undefined,
              }}
            >{l}</button>
          ))}
        </div>
      </div>

      {/* Theme */}
      <div className="card" style={{ padding: 20, marginBottom: 16 }}>
        <div style={{ fontWeight: 600, marginBottom: 14, display: 'flex', alignItems: 'center', gap: 6 }}>
          <Moon size={14} style={{ color: 'var(--accent)' }} />
          Mavzu
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {THEMES.map(t => (
            <button
              key={t}
              onClick={() => setTheme(t)}
              className="btn btn-ghost"
              style={{
                height: 36, fontSize: '0.8125rem',
                background: theme === t ? 'var(--accent-muted)' : undefined,
                color: theme === t ? 'var(--accent)' : undefined,
                borderColor: theme === t ? 'var(--border-accent)' : undefined,
              }}
            >{t}</button>
          ))}
        </div>
      </div>

      {/* Timezone */}
      <div className="card" style={{ padding: 20, marginBottom: 16 }}>
        <div style={{ fontWeight: 600, marginBottom: 14, display: 'flex', alignItems: 'center', gap: 6 }}>
          <Clock size={14} style={{ color: 'var(--accent)' }} />
          Vaqt zonasi
        </div>
        <select
          className="input"
          value={tz}
          onChange={e => setTz(e.target.value)}
          style={{ cursor: 'pointer' }}
        >
          {TIMEZONES.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>

      {/* Working hours */}
      <div className="card" style={{ padding: 20, marginBottom: 24 }}>
        <div style={{ fontWeight: 600, marginBottom: 14 }}>Ish vaqti</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.8125rem', color: 'var(--text-muted)', marginBottom: 6 }}>Boshlanish</label>
            <input className="input" type="time" value={workStart} onChange={e => setWorkStart(e.target.value)} />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.8125rem', color: 'var(--text-muted)', marginBottom: 6 }}>Tugash</label>
            <input className="input" type="time" value={workEnd} onChange={e => setWorkEnd(e.target.value)} />
          </div>
        </div>
        <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 8 }}>
          Ogohlantirishlar faqat ish vaqtida yuboriladi
        </p>
      </div>

      <button className="btn btn-primary" onClick={save} style={{ height: 40, paddingInline: 32 }}>
        {saved ? '✓ Saqlandi' : 'O\'zgarishlarni saqlash'}
      </button>
    </div>
  );
}
