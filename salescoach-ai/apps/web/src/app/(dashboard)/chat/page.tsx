'use client';
import { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Loader2, TrendingUp, Users, Phone, BarChart2 } from 'lucide-react';

const SUGGESTIONS = [
  { icon: TrendingUp, label: 'Sotuv ko\'rsatkichlari', prompt: 'Bugungi sotuv ko\'rsatkichlarini ko\'rsating. Qancha qo\'ng\'iroq amalga oshirildi?' },
  { icon: Users, label: 'Eng yaxshi menejer', prompt: 'Shu hafta eng yaxshi natija ko\'rsatgan menejer kim? Uning qaysi ko\'rsatkichlari ajralib turadi?' },
  { icon: Phone, label: 'Qo\'ng\'iroq tahlili', prompt: 'Oxirgi qo\'ng\'iroqlarni tahlil qiling. Qaysi qo\'ng\'iroqlarda yopish bosqichi zaif bo\'ldi?' },
  { icon: BarChart2, label: 'Pipeline holati', prompt: 'Hozirgi pipeline holati qanday? Qaysi bosqichda qancha bitim bor?' },
];

interface Message {
  role: 'user' | 'ai';
  text: string;
  time: string;
}

const now = () => new Date().toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' });

const AI_RESPONSES = {
  default: "Ma'lumotlarni tahlil qilyapman... Hozircha real API ulanmagan. Tez orada to'liq AI javoblari ishlaydi.",
  sotuv: "📊 **Bugungi sotuv ko'rsatkichlari:**\n\n• Jami qo'ng'iroqlar: 47 ta\n• Ulangan: 31 ta (66%)\n• Tahlil qilingan: 28 ta\n• O'rtacha sifat: 72%\n\n⚠️ E'tibor: A2 va E1 mezonlari hali ham zaif — 16% va 17%. Menejerlar bilan individual mashg'ulot o'tkazish tavsiya etiladi.",
  menejer: "👤 **Hafta bo'yicha eng yaxshi menejer:**\n\n🏆 **Baxtiyorjon Gaziyev**\n• Qo'ng'iroqlar: 47 ta\n• O'rtacha ball: 72%\n• Eng kuchli: Mijoz bilan rapport (A1 — 90%)\n• Zaif tomoni: Yopish texnikasi (E1 — 17%)\n\nTavsiya: Yopish bosqichi bo'yicha 2 soatlik trening.",
  pipeline: "🔄 **Pipeline holati:**\n\n| Bosqich | Lidlar | Summa |\n|---|---|---|\n| Yangi so'rov | 89 | — |\n| Aloqa o'rnatildi | 52 | — |\n| Taklif yuborildi | 18 | ~25M UZS |\n| Muzokara | 7 | ~40M UZS |\n| Yopildi ✅ | 3 | 15M UZS |\n\n⚡ Konversiya: 0% (maqsad: 15%). Urgentlik zarur!",
};

function getAIResponse(text: string): string {
  if (text.toLowerCase().includes('sotuv') || text.toLowerCase().includes('ko\'rsatkich')) return AI_RESPONSES.sotuv;
  if (text.toLowerCase().includes('menejer') || text.toLowerCase().includes('eng yaxshi')) return AI_RESPONSES.menejer;
  if (text.toLowerCase().includes('pipeline') || text.toLowerCase().includes('bitim')) return AI_RESPONSES.pipeline;
  return AI_RESPONSES.default;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  async function send(text: string) {
    if (!text.trim() || loading) return;
    const userMsg: Message = { role: 'user', text, time: now() };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    await new Promise(r => setTimeout(r, 1200 + Math.random() * 800));

    const aiMsg: Message = { role: 'ai', text: getAIResponse(text), time: now() };
    setMessages(prev => [...prev, aiMsg]);
    setLoading(false);
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {messages.length === 0 ? (
        /* Welcome state */
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 32 }}>
          <div style={{ width: 56, height: 56, borderRadius: 16, background: 'linear-gradient(135deg, var(--accent), var(--accent-violet))', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 20 }}>
            <Bot size={28} color="white" />
          </div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: 6, letterSpacing: '-0.02em' }}>
            Salom, <span style={{ background: 'linear-gradient(90deg, #f472b6, var(--text-secondary))', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>Baxtiyorjon.</span>
          </h2>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: 32 }}>Bugun sizga qanday yordam bera olaman?</p>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, width: '100%', maxWidth: 600 }}>
            {SUGGESTIONS.map(s => (
              <button
                key={s.label}
                onClick={() => send(s.prompt)}
                className="card card-hover"
                style={{ padding: '16px 18px', textAlign: 'left', cursor: 'pointer', border: 'none', transition: 'all 0.15s' }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                  <s.icon size={15} style={{ color: 'var(--accent)' }} />
                  <span style={{ fontWeight: 600, fontSize: '0.8125rem' }}>{s.label}</span>
                </div>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', lineHeight: 1.4 }}>
                  {s.prompt.substring(0, 60)}...
                </p>
                <div style={{ marginTop: 8, display: 'flex', justifyContent: 'flex-end' }}>
                  <span style={{ color: 'var(--accent)', fontSize: '0.75rem' }}>→</span>
                </div>
              </button>
            ))}
          </div>
        </div>
      ) : (
        /* Chat messages */
        <div style={{ flex: 1, overflow: 'auto', padding: '24px', display: 'flex', flexDirection: 'column', gap: 16 }}>
          {messages.map((msg, i) => (
            <div key={i} style={{ display: 'flex', gap: 12, justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start' }}>
              {msg.role === 'ai' && (
                <div style={{ width: 32, height: 32, borderRadius: 10, background: 'linear-gradient(135deg, var(--accent), var(--accent-violet))', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                  <Bot size={16} color="white" />
                </div>
              )}
              <div style={{ maxWidth: '70%' }}>
                <div style={{
                  padding: '12px 16px',
                  borderRadius: msg.role === 'user' ? '16px 4px 16px 16px' : '4px 16px 16px 16px',
                  background: msg.role === 'user' ? 'var(--accent)' : 'var(--bg-card)',
                  border: msg.role === 'user' ? 'none' : '1px solid var(--border)',
                  fontSize: '0.875rem',
                  lineHeight: 1.6,
                  whiteSpace: 'pre-line',
                }}>
                  {msg.text}
                </div>
                <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', marginTop: 4, textAlign: msg.role === 'user' ? 'right' : 'left' }}>
                  {msg.time}
                </div>
              </div>
              {msg.role === 'user' && (
                <div style={{ width: 32, height: 32, borderRadius: '50%', background: 'linear-gradient(135deg, var(--accent), var(--accent-violet))', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: '0.875rem', flexShrink: 0 }}>
                  B
                </div>
              )}
            </div>
          ))}
          {loading && (
            <div style={{ display: 'flex', gap: 12 }}>
              <div style={{ width: 32, height: 32, borderRadius: 10, background: 'linear-gradient(135deg, var(--accent), var(--accent-violet))', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                <Bot size={16} color="white" />
              </div>
              <div style={{ padding: '12px 16px', background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '4px 16px 16px 16px', display: 'flex', alignItems: 'center', gap: 6 }}>
                <Loader2 size={14} style={{ color: 'var(--accent)', animation: 'spin 1s linear infinite' }} />
                <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>Tahlil qilinmoqda...</span>
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>
      )}

      {/* Input */}
      <div style={{ padding: '16px 24px', borderTop: '1px solid var(--border)', background: 'var(--bg-surface)' }}>
        <div style={{ display: 'flex', gap: 10, maxWidth: 800, margin: '0 auto' }}>
          <input
            className="input"
            placeholder="Xabar yozing..."
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), send(input))}
            style={{ flex: 1, height: 44 }}
            disabled={loading}
          />
          <button
            className="btn btn-primary"
            onClick={() => send(input)}
            disabled={loading || !input.trim()}
            style={{ height: 44, width: 44, padding: 0, justifyContent: 'center' }}
          >
            {loading ? <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /> : <Send size={16} />}
          </button>
        </div>
      </div>

      <style>{`@keyframes spin { from { transform: rotate(0deg) } to { transform: rotate(360deg) } }`}</style>
    </div>
  );
}
