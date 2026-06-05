'use client';
import { CreditCard, MessageCircle, Phone, Mail, AlertCircle, Clock } from 'lucide-react';

export default function SubscriptionPage() {
  return (
    <div style={{ padding: '32px', maxWidth: 640 }}>
      <h2 style={{ fontSize: '1.125rem', fontWeight: 700, marginBottom: 4 }}>Obuna</h2>
      <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginBottom: 24 }}>Obuna holati va to'lov ma'lumotlari</p>

      {/* Status warning */}
      <div style={{
        padding: 16, marginBottom: 24, borderRadius: 10,
        background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)',
        display: 'flex', alignItems: 'flex-start', gap: 10,
      }}>
        <AlertCircle size={18} style={{ color: 'var(--accent-red)', flexShrink: 0, marginTop: 1 }} />
        <div>
          <div style={{ fontWeight: 600, color: 'var(--accent-red)', marginBottom: 2 }}>Obuna muzlatilgan</div>
          <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
            Xizmatlarni davom ettirish uchun to'lov qiling.
          </div>
        </div>
      </div>

      {/* Plan info */}
      <div className="card" style={{ padding: 24, marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: 4 }}>Joriy plan</div>
            <div style={{ fontWeight: 700, fontSize: '1.125rem' }}>Asosiy</div>
          </div>
          <span className="badge badge-red">Muzlatilgan</span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
          {[
            { label: 'Balans', value: '0 UZS' },
            { label: 'O\'rinlar', value: '1 ta' },
            { label: 'Oylik xarajat', value: '640,000 UZS' },
            { label: 'Qolgan kunlar', value: '—' },
          ].map(({ label, value }) => (
            <div key={label} style={{ background: 'var(--bg-surface)', borderRadius: 8, padding: '12px 14px' }}>
              <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', marginBottom: 3 }}>{label}</div>
              <div style={{ fontWeight: 700, fontSize: '1rem' }}>{value}</div>
            </div>
          ))}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '10px 12px', background: 'rgba(255,255,255,0.03)', borderRadius: 8, marginBottom: 16 }}>
          <Clock size={14} style={{ color: 'var(--text-muted)' }} />
          <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
            Davr: 25 aprel 2026 — 15 may 2026 · Har oyning 15-sanasida to'lov
          </span>
        </div>

        <button className="btn btn-primary" style={{ width: '100%', justifyContent: 'center', height: 40 }}>
          <CreditCard size={15} />
          To'lov qilish — 640,000 UZS
        </button>
      </div>

      {/* Pricing breakdown */}
      <div className="card" style={{ padding: 20, marginBottom: 16 }}>
        <div style={{ fontWeight: 600, marginBottom: 12 }}>Narx tarkibi</div>
        <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
          <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>1 × 640,000 UZS (1 o'rin)</span>
          <span style={{ fontWeight: 600 }}>640,000 UZS</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0' }}>
          <span style={{ fontWeight: 600 }}>Jami</span>
          <span style={{ fontWeight: 700, color: 'var(--accent)' }}>640,000 UZS / oy</span>
        </div>
      </div>

      {/* Support */}
      <div className="card" style={{ padding: 20, marginBottom: 16 }}>
        <div style={{ fontWeight: 600, marginBottom: 12 }}>Qo'llab-quvvatlash</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {[
            { icon: MessageCircle, label: 'Telegram', value: '@Metasell_uz', href: 'https://t.me/Metasell_uz' },
            { icon: Phone, label: 'Telefon', value: '+998917851546', href: 'tel:+998917851546' },
            { icon: Mail, label: 'Email', value: 'main@metasell.ai', href: 'mailto:main@metasell.ai' },
          ].map(({ icon: Icon, label, value, href }) => (
            <a key={label} href={href} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0', textDecoration: 'none' }}>
              <Icon size={15} style={{ color: 'var(--accent)', flexShrink: 0 }} />
              <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', width: 70 }}>{label}:</span>
              <span style={{ fontSize: '0.8125rem', color: 'var(--accent)' }}>{value}</span>
            </a>
          ))}
        </div>
      </div>

      {/* Transaction history */}
      <div className="card" style={{ padding: 20 }}>
        <div style={{ fontWeight: 600, marginBottom: 12 }}>So'nggi tranzaksiyalar</div>
        <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--text-muted)', fontSize: '0.8125rem' }}>
          Tranzaksiyalar topilmadi
        </div>
      </div>
    </div>
  );
}
