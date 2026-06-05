'use client';
import { useState } from 'react';
import { ChevronDown, ChevronRight, GripVertical, Plus, Trash2, Info } from 'lucide-react';

interface Criterion {
  code: string;
  name: string;
  weight: number;
  description: string;
}

interface Category {
  id: string;
  code: string;
  name: string;
  weight: number;
  expanded: boolean;
  criteria: Criterion[];
}

const INITIAL_CATEGORIES: Category[] = [
  {
    id: 'A', code: 'A', name: 'Salomlashish va Rapport', weight: 12, expanded: true,
    criteria: [
      { code: 'A1', name: 'Iliq salomlashish va o\'zini tanishtirish', weight: 4, description: 'Menejer o\'zini va kompaniyani aniq va iliq tanishtirdi' },
      { code: 'A2', name: 'Muammo/ehtiyojni aniqlash', weight: 4, description: 'Mijozning muammosini ertada aniqlashga harakat qilindi' },
      { code: 'A3', name: 'Qo\'ng\'iroq maqsadini belgilash', weight: 4, description: 'Qo\'ng\'iroq nima uchun kerakligi aniqlanganmi' },
    ],
  },
  {
    id: 'B', code: 'B', name: 'Ehtiyojlarni Aniqlash', weight: 23, expanded: false,
    criteria: [
      { code: 'B1', name: 'Ochiq savollar berish', weight: 8, description: 'Mijozni gapirtirish uchun ochiq savollar ishlatildi' },
      { code: 'B2', name: 'Faol tinglash', weight: 8, description: 'Mijozni to\'xtatmay, diqqat bilan tinglanganmi' },
      { code: 'B3', name: 'Muammoni chuqurlashtirishg', weight: 7, description: 'Og\'riq nuqtani aniqlashtirish uchun qazib borilganmi' },
    ],
  },
  {
    id: 'C', code: 'C', name: 'Qiymat Taqdimoti', weight: 18, expanded: false,
    criteria: [
      { code: 'C1', name: 'Mahsulotni taqdim etish', weight: 6, description: 'Xizmat/mahsulot aniq tushuntirilganmi' },
      { code: 'C2', name: 'Foyda urg\'ulash', weight: 7, description: 'Mijozga beriladigan qiymat ko\'rsatilganmi' },
      { code: 'C3', name: 'Raqobatchilardan farq', weight: 5, description: 'Nima uchun biz? Farqimiz aytildimi' },
    ],
  },
  {
    id: 'D', code: 'D', name: 'E\'tirozlarni Boshqarish', weight: 12, expanded: false,
    criteria: [
      { code: 'D1', name: 'E\'tirozni tinglash', weight: 4, description: 'E\'tirozni to\'liq eshitib olindi' },
      { code: 'D2', name: 'Qayta yo\'naltirish', weight: 4, description: 'E\'tiroz qiymatga yo\'naltirilganmi' },
      { code: 'D3', name: 'Tasdiqlovchi savol', weight: 4, description: 'E\'tiroz hal bo\'lganligini tekshirilganmi' },
    ],
  },
  {
    id: 'E', code: 'E', name: 'Yakunlash', weight: 20, expanded: false,
    criteria: [
      { code: 'E1', name: 'Yopish urinishi', weight: 8, description: 'Aniq yopish qadami qo\'yilganmi' },
      { code: 'E2', name: 'Shartnoma/To\'lov muhokaması', weight: 6, description: 'Shartnoma yoki to\'lov haqida gapirilganmi' },
      { code: 'E3', name: 'Keyingi qadam belgilash', weight: 6, description: 'Keyingi aniq sana/qadam belgilandi' },
    ],
  },
  {
    id: 'F', code: 'F', name: 'Muloqot Sifati', weight: 15, expanded: false,
    criteria: [
      { code: 'F1', name: 'Nutq tezligi va aniqlik', weight: 5, description: 'Tez yoki sekin gapirmadi, aniq so\'zladi' },
      { code: 'F2', name: 'Professionallik', weight: 5, description: 'Slang, so\'kinish yo\'q; professional uslub' },
      { code: 'F3', name: 'Ijobiy atmosfera', weight: 5, description: 'Qo\'ng\'iroq paytida ijobiy ruh saqlandi' },
    ],
  },
];

const RUBRIC_TYPES = ['Umumiy', 'Hunter', 'Closer'];

export default function PlaybookPage() {
  const [rubricType, setRubricType] = useState('Umumiy');
  const [categories, setCategories] = useState<Category[]>(INITIAL_CATEGORIES);
  const [saved, setSaved] = useState(false);
  const [tooltip, setTooltip] = useState<string | null>(null);

  const totalWeight = categories.reduce((s, c) => s + c.weight, 0);

  const toggleExpand = (id: string) => {
    setCategories(prev => prev.map(c => c.id === id ? { ...c, expanded: !c.expanded } : c));
  };

  const save = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div style={{ padding: '32px', maxWidth: 720 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
        <h2 style={{ fontSize: '1.125rem', fontWeight: 700 }}>Sotuv Mezoni</h2>
        <span style={{
          fontSize: '0.8125rem', fontWeight: 600, padding: '4px 10px', borderRadius: 6,
          background: totalWeight === 100 ? 'rgba(16,185,129,0.12)' : 'rgba(239,68,68,0.12)',
          color: totalWeight === 100 ? 'var(--accent-green)' : 'var(--accent-red)',
        }}>
          Jami: {totalWeight}% {totalWeight !== 100 && '⚠ 100% bo\'lishi kerak'}
        </span>
      </div>
      <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginBottom: 20 }}>
        Qo'ng'iroq sifatini baholash mezonlari va og'irliklari
      </p>

      {/* Rubric type selector */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
        {RUBRIC_TYPES.map(t => (
          <button
            key={t}
            onClick={() => setRubricType(t)}
            className="btn btn-ghost"
            style={{
              height: 36, fontSize: '0.8125rem',
              background: rubricType === t ? 'var(--accent-muted)' : undefined,
              color: rubricType === t ? 'var(--accent)' : undefined,
              borderColor: rubricType === t ? 'var(--border-accent)' : undefined,
            }}
          >{t}</button>
        ))}
      </div>

      {/* Category list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {categories.map(cat => (
          <div key={cat.id} className="card" style={{ overflow: 'hidden' }}>
            {/* Category header */}
            <div
              onClick={() => toggleExpand(cat.id)}
              style={{
                padding: '14px 16px', display: 'flex', alignItems: 'center', gap: 10,
                cursor: 'pointer', userSelect: 'none',
              }}
            >
              <GripVertical size={14} style={{ color: 'var(--text-muted)', cursor: 'grab' }} />
              {cat.expanded
                ? <ChevronDown size={14} style={{ color: 'var(--accent)', flexShrink: 0 }} />
                : <ChevronRight size={14} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
              }
              <span style={{ width: 28, height: 28, borderRadius: 8, background: 'var(--accent-muted)', color: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: '0.8125rem', flexShrink: 0 }}>{cat.code}</span>
              <span style={{ flex: 1, fontWeight: 600, fontSize: '0.875rem' }}>{cat.name}</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{ height: 4, width: 80, background: 'rgba(255,255,255,0.06)', borderRadius: 2 }}>
                  <div style={{ height: '100%', width: `${cat.weight}%`, background: 'var(--accent)', borderRadius: 2 }} />
                </div>
                <WeightInput value={cat.weight} onChange={v => setCategories(prev => prev.map(c => c.id === cat.id ? { ...c, weight: v } : c))} />
              </div>
            </div>

            {/* Criteria list */}
            {cat.expanded && (
              <div style={{ borderTop: '1px solid var(--border)' }}>
                {cat.criteria.map((cr, ci) => (
                  <div key={cr.code} style={{ padding: '10px 16px 10px 56px', display: 'flex', alignItems: 'center', gap: 10, borderBottom: ci < cat.criteria.length - 1 ? '1px solid rgba(255,255,255,0.03)' : 'none' }}>
                    <span style={{ width: 32, fontSize: '0.75rem', fontWeight: 700, color: 'var(--accent)', flexShrink: 0 }}>{cr.code}</span>
                    <span style={{ flex: 1, fontSize: '0.8125rem' }}>{cr.name}</span>
                    <button
                      onMouseEnter={() => setTooltip(cr.code)}
                      onMouseLeave={() => setTooltip(null)}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', position: 'relative', padding: 2 }}
                    >
                      <Info size={12} style={{ color: 'var(--text-muted)' }} />
                      {tooltip === cr.code && (
                        <div style={{
                          position: 'absolute', right: 20, bottom: '50%', transform: 'translateY(50%)',
                          background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8,
                          padding: '8px 10px', width: 200, fontSize: '0.75rem', color: 'var(--text-secondary)',
                          zIndex: 10, boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
                        }}>
                          {cr.description}
                        </div>
                      )}
                    </button>
                    <WeightInput value={cr.weight} onChange={v => setCategories(prev => prev.map(c => c.id === cat.id ? { ...c, criteria: c.criteria.map((cr2, j) => j === ci ? { ...cr2, weight: v } : cr2) } : c))} />
                  </div>
                ))}
                <div style={{ padding: '8px 16px 8px 56px' }}>
                  <button className="btn btn-ghost" style={{ fontSize: '0.75rem', height: 28, gap: 4, color: 'var(--text-muted)' }}>
                    <Plus size={11} />Mezon qo'shish
                  </button>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', gap: 10, marginTop: 24 }}>
        <button className="btn btn-primary" onClick={save} style={{ height: 40, paddingInline: 28 }}>
          {saved ? '✓ Saqlandi' : 'Saqlash'}
        </button>
        <button className="btn btn-ghost" style={{ height: 40 }}>
          Standartga qaytarish
        </button>
      </div>
    </div>
  );
}

function WeightInput({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
      <input
        type="number"
        min={0}
        max={100}
        value={value}
        onChange={e => onChange(parseInt(e.target.value) || 0)}
        onClick={e => e.stopPropagation()}
        style={{
          width: 44, height: 28, borderRadius: 6,
          background: 'var(--bg-surface)', border: '1px solid var(--border)',
          color: 'var(--text-primary)', fontSize: '0.8125rem', fontWeight: 600,
          textAlign: 'center', padding: 0,
        }}
      />
      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>%</span>
    </div>
  );
}
