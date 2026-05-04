'use client';
import { useState, useRef, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { api } from '@/lib/api';

interface Assessment {
  stage: string;
  intent: string;
  objection: string;
  urgency: string;
  sentiment: string;
  closeProbability: number;
  nextAction: string;
  approvalNeeded: boolean;
  riskFlags: string[];
  painPoints: string[];
  buyingSignals: string[];
}

interface Suggestion {
  assessment: Assessment;
  suggestedReply: string;
  alternativeReplies: string[];
  talkingPoints: string[];
  surgicalMission: string;
  warningFlags: string[];
}

interface Message {
  role: 'manager' | 'customer';
  content: string;
  ts: number;
  suggestion?: Suggestion;
}

export default function NegotiatePage() {
  return (
    <Suspense>
      <NegotiateInner />
    </Suspense>
  );
}

function NegotiateInner() {
  const searchParams = useSearchParams();
  const customerName = searchParams.get('customerName') ?? '';
  const linkedCallId = searchParams.get('callId') ?? '';

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [crmStatus, setCrmStatus] = useState(customerName ? `Customer: ${customerName}` : '');
  const [serviceType, setServiceType] = useState('branding');
  const [loading, setLoading] = useState(false);
  const [activeSuggestion, setActiveSuggestion] = useState<Suggestion | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;
    const customerMsg: Message = { role: 'customer', content: input.trim(), ts: Date.now() };
    setMessages((prev) => [...prev, customerMsg]);
    const msgText = input.trim();
    setInput('');
    setLoading(true);

    try {
      const history = messages.map((m) => ({ role: m.role, content: m.content }));
      const result = await api.post<Suggestion>('/negotiations/suggest', {
        message: msgText,
        history,
        crmStatus,
        serviceType,
        ...(customerName && { customerName }),
        ...(linkedCallId && { callId: linkedCallId }),
      });
      setActiveSuggestion(result);
      const aiMsg: Message = {
        role: 'manager',
        content: result.suggestedReply,
        ts: Date.now(),
        suggestion: result,
      };
      setMessages((prev) => [...prev, aiMsg]);
    } catch (e: any) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const prob = activeSuggestion?.assessment.closeProbability ?? 0;
  const probColor = prob >= 0.6 ? 'var(--accent-green)' : prob >= 0.35 ? 'var(--accent-amber)' : 'var(--accent-red)';

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Left — Conversation */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Topbar */}
        <div className="flex items-center gap-4 px-6 py-4 border-b border-[var(--border)] shrink-0">
          <Link href="/dashboard" className="text-sm hover:text-[var(--accent-cyan)] transition-colors"
            style={{ color: 'var(--text-secondary)' }}>
            ← Dashboard
          </Link>
          <div className="flex-1" />
          <select
            value={serviceType}
            onChange={(e) => setServiceType(e.target.value)}
            className="text-xs px-3 py-1.5 rounded-lg border border-[var(--border)] bg-transparent focus:outline-none focus:border-[var(--accent-cyan)]"
            style={{ color: 'var(--text-secondary)' }}
          >
            <option value="branding">Branding</option>
            <option value="web">Web</option>
            <option value="marketing">Marketing</option>
            <option value="consulting">Consulting</option>
          </select>
          <input
            value={crmStatus}
            onChange={(e) => setCrmStatus(e.target.value)}
            placeholder="CRM status (optional)"
            className="text-xs px-3 py-1.5 rounded-lg border border-[var(--border)] bg-transparent focus:outline-none focus:border-[var(--accent-cyan)] w-40"
            style={{ color: 'var(--text-secondary)' }}
          />
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full gap-4 text-center"
              style={{ color: 'var(--text-secondary)' }}>
              <div className="text-5xl">🤝</div>
              <div>
                <p className="font-semibold text-lg" style={{ color: 'var(--text-primary)' }}>
                  {customerName ? `Negotiating with ${customerName}` : 'Autonomous Negotiation Assistant'}
                </p>
                <p className="text-sm mt-1">Paste a customer message and get an AI-powered reply suggestion</p>
                {linkedCallId && (
                  <Link href={`/calls/${linkedCallId}`}
                    className="text-xs mt-2 inline-block hover:text-[var(--accent-cyan)] transition-colors"
                    style={{ color: 'var(--text-muted)' }}>
                    ← Back to call analysis
                  </Link>
                )}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === 'manager' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[68%] ${msg.role === 'manager' ? 'items-end' : 'items-start'} flex flex-col gap-1`}>
                <div className={`text-xs font-medium px-1 ${
                  msg.role === 'manager' ? 'text-right' : 'text-left'
                }`} style={{ color: 'var(--text-muted)' }}>
                  {msg.role === 'manager' ? '🤖 AI Suggestion' : '👤 Customer'}
                </div>
                <div
                  className={`px-4 py-3 rounded-2xl text-sm leading-relaxed cursor-pointer transition-all hover:opacity-90 ${
                    msg.role === 'manager'
                      ? 'glass-accent text-[var(--text-primary)] rounded-br-sm'
                      : 'glass text-[var(--text-primary)] rounded-bl-sm'
                  }`}
                  onClick={() => msg.suggestion && setActiveSuggestion(msg.suggestion)}
                >
                  {msg.content}
                </div>
                {msg.suggestion?.assessment && (
                  <div className="flex gap-2 px-1 flex-wrap">
                    <ProbBadge prob={msg.suggestion.assessment.closeProbability} />
                    {msg.suggestion.assessment.objection !== 'none' && (
                      <span className="text-xs px-2 py-0.5 rounded-full badge-red">
                        ⚠ {msg.suggestion.assessment.objection}
                      </span>
                    )}
                    {msg.suggestion.assessment.buyingSignals.length > 0 && (
                      <span className="text-xs px-2 py-0.5 rounded-full badge-green">
                        🎯 {msg.suggestion.assessment.buyingSignals[0]}
                      </span>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex justify-end">
              <div className="glass-accent px-4 py-3 rounded-2xl rounded-br-sm text-sm"
                style={{ color: 'var(--text-secondary)' }}>
                <span className="pulse-live inline-block">Analyzing...</span>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="p-4 border-t border-[var(--border)] shrink-0">
          <div className="flex gap-3 items-end">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } }}
              placeholder="Paste customer message... (Enter to send)"
              rows={3}
              className="flex-1 px-4 py-3 rounded-xl border border-[var(--border)] bg-[var(--bg-card)] text-sm resize-none focus:outline-none focus:border-[var(--accent-cyan)] transition-colors"
              style={{ color: 'var(--text-primary)' }}
            />
            <button
              onClick={sendMessage}
              disabled={!input.trim() || loading}
              className="px-5 py-3 rounded-xl font-medium text-sm disabled:opacity-40 transition-all hover:opacity-90 shrink-0"
              style={{ background: 'linear-gradient(135deg,var(--accent-violet),var(--accent-cyan))', color:'#fff' }}
            >
              Analyze →
            </button>
          </div>
        </div>
      </div>

      {/* Right — Live Panel */}
      <aside className="w-80 border-l border-[var(--border)] flex flex-col overflow-y-auto p-5 gap-5 shrink-0">
        <div>
          <h3 className="font-semibold text-sm mb-1">Negotiation Intel</h3>
          <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Updates on each message</p>
        </div>

        {activeSuggestion ? (
          <>
            {/* Probability */}
            <div className="glass p-4">
              <p className="text-xs uppercase tracking-widest mb-3" style={{ color: 'var(--text-muted)' }}>
                Close Probability
              </p>
              <div className="flex items-center gap-3">
                <span className="text-3xl font-bold" style={{ color: probColor }}>
                  {Math.round(prob * 100)}%
                </span>
                <div className="flex-1">
                  <div className="progress-bar">
                    <div className="progress-fill" style={{ width: `${prob * 100}%` }} />
                  </div>
                  <p className="text-xs mt-1.5" style={{ color: 'var(--text-secondary)' }}>
                    Stage: <span className="font-medium" style={{ color: 'var(--accent-cyan)' }}>
                      {activeSuggestion.assessment.stage.replace(/_/g, ' ')}
                    </span>
                  </p>
                </div>
              </div>
            </div>

            {/* Surgical Mission */}
            {activeSuggestion.surgicalMission && (
              <div className="glass-accent p-4 tip-card">
                <p className="text-xs uppercase tracking-widest mb-3" style={{ color: 'var(--accent-cyan)' }}>
                  Surgical Mission
                </p>
                <p className="text-sm whitespace-pre-line leading-relaxed" style={{ color: 'var(--text-primary)' }}>
                  {activeSuggestion.surgicalMission}
                </p>
              </div>
            )}

            {/* Talking Points */}
            {activeSuggestion.talkingPoints.length > 0 && (
              <div className="glass p-4">
                <p className="text-xs uppercase tracking-widest mb-3" style={{ color: 'var(--text-muted)' }}>
                  Talking Points
                </p>
                <ul className="space-y-2">
                  {activeSuggestion.talkingPoints.map((tp, i) => (
                    <li key={i} className="flex gap-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
                      <span style={{ color: 'var(--accent-green)' }}>•</span>{tp}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Alt replies */}
            {activeSuggestion.alternativeReplies.length > 0 && (
              <div className="glass p-4">
                <p className="text-xs uppercase tracking-widest mb-3" style={{ color: 'var(--text-muted)' }}>
                  Alternative Replies
                </p>
                <div className="space-y-2">
                  {activeSuggestion.alternativeReplies.map((r, i) => (
                    <div key={i} className="text-xs p-3 rounded-xl cursor-pointer transition-all hover:opacity-90"
                      style={{ background: 'rgba(255,255,255,.04)', color: 'var(--text-secondary)', border: '1px solid var(--border)' }}
                      onClick={() => setInput(r)}>
                      {r}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Risk flags */}
            {(activeSuggestion.assessment.riskFlags.length > 0 || activeSuggestion.warningFlags.length > 0) && (
              <div className="glass p-4 border-[var(--accent-red)] opacity-90"
                style={{ borderColor: 'rgba(255,75,110,.25)' }}>
                <p className="text-xs uppercase tracking-widest mb-3" style={{ color: 'var(--accent-red)' }}>
                  ⚠ Risks
                </p>
                {[...activeSuggestion.assessment.riskFlags, ...activeSuggestion.warningFlags].map((f, i) => (
                  <div key={i} className="text-xs py-1" style={{ color: 'var(--text-secondary)' }}>
                    → {f.replace(/_/g, ' ')}
                  </div>
                ))}
              </div>
            )}

            {/* Pain points */}
            {activeSuggestion.assessment.painPoints.length > 0 && (
              <div className="glass p-4">
                <p className="text-xs uppercase tracking-widest mb-2" style={{ color: 'var(--text-muted)' }}>
                  Pain Points
                </p>
                {activeSuggestion.assessment.painPoints.map((p, i) => (
                  <div key={i} className="text-xs py-1" style={{ color: 'var(--text-secondary)' }}>
                    🎯 {p}
                  </div>
                ))}
              </div>
            )}
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-center p-6"
            style={{ color: 'var(--text-muted)', fontSize: '.8125rem' }}>
            Send a customer message to see the negotiation analysis
          </div>
        )}
      </aside>
    </div>
  );
}

function ProbBadge({ prob }: { prob: number }) {
  const cls = prob >= 0.6 ? 'badge-green' : prob >= 0.35 ? 'badge-amber' : 'badge-red';
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${cls}`}>
      {Math.round(prob * 100)}% close
    </span>
  );
}
