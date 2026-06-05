'use client';
import { useState } from 'react';
import { Camera, User, Mail, Phone, Shield, Bell, LogOut } from 'lucide-react';

export default function ProfilePage() {
  const [name, setName] = useState('Baxtiyorjon Gaziyev');
  const [email] = useState('baxtiyorjongaziyev@gmail.com');
  const [phone, setPhone] = useState('+998917851546');
  const [telegramConnected] = useState(true);
  const [saved, setSaved] = useState(false);

  const save = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div style={{ padding: '32px', maxWidth: 600 }}>
      <h2 style={{ fontSize: '1.125rem', fontWeight: 700, marginBottom: 4 }}>Profil</h2>
      <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginBottom: 24 }}>Shaxsiy ma'lumotlar va sozlamalar</p>

      {/* Avatar */}
      <div className="card" style={{ padding: 24, marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
          <div style={{ position: 'relative' }}>
            <div style={{
              width: 72, height: 72, borderRadius: '50%',
              background: 'linear-gradient(135deg, var(--accent), var(--accent-violet))',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '1.75rem', fontWeight: 700,
            }}>B</div>
            <button style={{
              position: 'absolute', bottom: 0, right: 0,
              width: 24, height: 24, borderRadius: '50%',
              background: 'var(--accent)', border: '2px solid var(--bg-base)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              cursor: 'pointer',
            }}>
              <Camera size={11} color="white" />
            </button>
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: '1rem' }}>{name}</div>
            <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginBottom: 8 }}>{email}</div>
            <span className="badge badge-blue">Sotuv menejeri</span>
          </div>
        </div>
      </div>

      {/* Personal info */}
      <div className="card" style={{ padding: 20, marginBottom: 16 }}>
        <div style={{ fontWeight: 600, marginBottom: 16 }}>Shaxsiy ma'lumotlar</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.8125rem', color: 'var(--text-muted)', marginBottom: 6 }}>To'liq ism</label>
            <div style={{ position: 'relative' }}>
              <User size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              <input className="input" value={name} onChange={e => setName(e.target.value)} style={{ paddingLeft: 32 }} />
            </div>
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.8125rem', color: 'var(--text-muted)', marginBottom: 6 }}>Email</label>
            <div style={{ position: 'relative' }}>
              <Mail size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              <input className="input" value={email} readOnly style={{ paddingLeft: 32, opacity: 0.6, cursor: 'not-allowed' }} />
            </div>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 4 }}>Email o'zgartirib bo'lmaydi</p>
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.8125rem', color: 'var(--text-muted)', marginBottom: 6 }}>Telefon raqam</label>
            <div style={{ position: 'relative' }}>
              <Phone size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              <input className="input" value={phone} onChange={e => setPhone(e.target.value)} style={{ paddingLeft: 32 }} />
            </div>
          </div>
        </div>
        <button className="btn btn-primary" onClick={save} style={{ marginTop: 20, height: 38, paddingInline: 24 }}>
          {saved ? '✓ Saqlandi' : 'Saqlash'}
        </button>
      </div>

      {/* Telegram */}
      <div className="card" style={{ padding: 20, marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div style={{ fontWeight: 600, marginBottom: 2 }}>Telegram</div>
            <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
              {telegramConnected ? '@Metasell_uz bilan bog\'langan' : 'Ulangan emas'}
            </div>
          </div>
          {telegramConnected
            ? <span className="badge badge-green">Ulangan</span>
            : <button className="btn btn-primary" style={{ height: 34, fontSize: '0.8125rem' }}>Ulash</button>
          }
        </div>
      </div>

      {/* Security */}
      <div className="card" style={{ padding: 20, marginBottom: 16 }}>
        <div style={{ fontWeight: 600, marginBottom: 14, display: 'flex', alignItems: 'center', gap: 6 }}>
          <Shield size={14} style={{ color: 'var(--accent)' }} />
          Xavfsizlik
        </div>
        <button className="btn btn-ghost" style={{ width: '100%', justifyContent: 'flex-start', height: 38 }}>
          Parolni o'zgartirish
        </button>
      </div>

      {/* Notifications */}
      <div className="card" style={{ padding: 20, marginBottom: 16 }}>
        <div style={{ fontWeight: 600, marginBottom: 14, display: 'flex', alignItems: 'center', gap: 6 }}>
          <Bell size={14} style={{ color: 'var(--accent)' }} />
          Bildirishnomalar
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {[
            { label: 'Kunlik hisobot (Telegram)', defaultOn: true },
            { label: 'Yangi ogohlantirishlar', defaultOn: true },
            { label: 'Email xabarlar', defaultOn: false },
          ].map(({ label, defaultOn }) => (
            <NotifToggle key={label} label={label} defaultOn={defaultOn} />
          ))}
        </div>
      </div>

      {/* Logout */}
      <button className="btn btn-ghost" style={{ color: 'var(--accent-red)', borderColor: 'rgba(239,68,68,0.2)', gap: 6, height: 38 }}>
        <LogOut size={14} />
        Chiqish
      </button>
    </div>
  );
}

function NotifToggle({ label, defaultOn }: { label: string; defaultOn: boolean }) {
  const [on, setOn] = useState(defaultOn);
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
      <span style={{ fontSize: '0.8125rem' }}>{label}</span>
      <button
        onClick={() => setOn(v => !v)}
        style={{
          width: 36, height: 20, borderRadius: 10, padding: '2px 3px',
          background: on ? 'var(--accent)' : 'var(--border)',
          border: 'none', cursor: 'pointer', transition: 'background 0.2s',
          display: 'flex', alignItems: 'center',
          justifyContent: on ? 'flex-end' : 'flex-start',
        }}
      >
        <div style={{ width: 14, height: 14, borderRadius: '50%', background: 'white' }} />
      </button>
    </div>
  );
}
