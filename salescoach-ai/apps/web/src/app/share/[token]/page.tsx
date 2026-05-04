'use client';
import { useEffect, useState } from 'react';
import { use } from 'react';

// Token lives in URL fragment (#k=...) — never sent to server in HTTP logs.
// This page reads the fragment client-side and sends it to the API.

interface SharedCall {
  id: string; customerName: string | null; direction: string;
  language: string | null; durationSec: number | null; createdAt: string;
  transcript: Array<{ speaker: string; start: number; end: number; text: string; seq: number }>;
  scorecard: { overallScore: number; summary: string; goodPoints: string[]; improvementPoints: string[] } | null;
}

export default function SharePage({ params }: { params: Promise<{ token: string }> }) {
  const { token: pathToken } = use(params);
  const [data, setData] = useState<{ call: SharedCall } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [needsPassword, setNeedsPassword] = useState(false);
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(true);

  const resolve = async (pwd?: string) => {
    setLoading(true);
    try {
      const fragment = typeof window !== 'undefined'
        ? new URLSearchParams(window.location.hash.slice(1)).get('k')
        : null;
      const token = fragment ?? pathToken;

      const qs = new URLSearchParams({ token });
      if (pwd) qs.set('password', pwd);

      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:4000/v1'}/public/share?${qs}`,
      );

      if (res.status === 401) { setNeedsPassword(true); setError('Password required'); return; }
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body.message ?? 'Link not found or expired');
        return;
      }
      setData(await res.json());
      setNeedsPassword(false);
      setError(null);
    } catch {
      setError('Failed to load');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { resolve(); }, []);

  if (loading) return (
    <div className="flex items-center justify-center h-screen" style={{ color: 'var(--text-secondary)' }}>
      <span className="pulse-live text-2xl">⚡</span>
    </div>
  );

  if (needsPassword) return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="glass w-80 p-8">
        <div className="text-center mb-6">
          <div className="text-3xl mb-2">🔐</div>
          <h2 className="font-semibold" style={{ color: 'var(--text-primary)' }}>Password required</h2>
          <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>This call is password-protected</p>
        </div>
        <input
          type="password" value={password}
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && resolve(password)}
          placeholder="Enter password"
          className="w-full px-4 py-3 rounded-xl border border-[var(--border)] bg-[var(--bg-card)] text-sm focus:outline-none focus:border-[var(--accent-cyan)] transition-colors mb-3"
          style={{ color: 'var(--text-primary)' }}
        />
        {error && <p className="text-xs badge-red px-3 py-2 rounded-lg mb-3">{error}</p>}
        <button onClick={() => resolve(password)}
          className="w-full py-3 rounded-xl font-medium text-sm hover:opacity-90 transition-all"
          style={{ background: 'linear-gradient(135deg,var(--accent-violet),var(--accent-cyan))', color: '#fff' }}>
          Unlock
        </button>
      </div>
    </div>
  );

  if (error || !data) return (
    <div className="min-h-screen flex items-center justify-center text-center p-8">
      <div>
        <div className="text-4xl mb-4">🔗</div>
        <h2 className="text-xl font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>
          Link unavailable
        </h2>
        <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
          {error ?? 'This link may have expired or been revoked.'}
        </p>
      </div>
    </div>
  );

  const { call } = data;
  const sc = call.scorecard;
  const scoreColor = sc
    ? sc.overallScore >= 80 ? 'var(--accent-green)'
      : sc.overallScore >= 60 ? 'var(--accent-amber)'
      : 'var(--accent-red)'
    : 'var(--text-muted)';

  return (
    <div className="min-h-screen p-6">
      {/* Header */}
      <div className="max-w-5xl mx-auto mb-6">
        <div className="glass-accent p-4 flex items-center gap-4">
          <div className="text-2xl">🤝</div>
          <div className="flex-1">
            <p className="text-[10px] uppercase tracking-widest mb-0.5" style={{ color: 'var(--accent-cyan)' }}>
              Shared via SalesCoach AI
            </p>
            <h1 className="font-bold text-lg" style={{ color: 'var(--text-primary)' }}>
              {call.customerName ?? 'Sales Call'}
            </h1>
            <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
              {call.direction} · {call.language?.toUpperCase()} ·{' '}
              {call.durationSec ? `${Math.floor(call.durationSec / 60)}m ${call.durationSec % 60}s` : ''}  ·{' '}
              {new Date(call.createdAt).toLocaleDateString()}
            </p>
          </div>
          {sc && (
            <div className="text-right shrink-0">
              <p className="text-xs uppercase tracking-widest mb-1" style={{ color: 'var(--text-muted)' }}>Score</p>
              <span className="text-3xl font-bold" style={{ color: scoreColor }}>
                {Math.round(sc.overallScore)}
              </span>
            </div>
          )}
        </div>
      </div>

      <div className="max-w-5xl mx-auto grid grid-cols-[1fr_340px] gap-5">
        {/* Transcript */}
        <div className="glass p-4 h-[70vh] overflow-y-auto">
          <p className="text-xs uppercase tracking-widest mb-4" style={{ color: 'var(--text-muted)' }}>
            Transcript
          </p>
          <div className="space-y-2">
            {call.transcript.map((seg) => (
              <div key={seg.seq} className="flex gap-3 px-2 py-1.5 rounded-lg hover:bg-[var(--bg-card-hover)]">
                <span className="text-[10px] font-bold mt-1 w-14 shrink-0 uppercase" style={{
                  color: seg.speaker === 'manager' ? 'var(--accent-cyan)' : 'var(--accent-violet)'
                }}>
                  {seg.speaker === 'manager' ? '🤖 MGR' : '👤 CLI'}
                </span>
                <p className="text-sm leading-relaxed" style={{ color: 'var(--text-primary)' }}>{seg.text}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Scorecard panel */}
        {sc ? (
          <div className="space-y-4">
            <div className="glass p-5">
              <p className="text-xs uppercase tracking-widest mb-3" style={{ color: 'var(--text-muted)' }}>
                Summary
              </p>
              <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{sc.summary}</p>
            </div>

            {sc.goodPoints.length > 0 && (
              <div className="glass p-4">
                <p className="text-xs uppercase tracking-widest mb-3" style={{ color: 'var(--accent-green)' }}>
                  ✓ Good Points
                </p>
                {sc.goodPoints.map((p, i) => (
                  <p key={i} className="text-xs py-1" style={{ color: 'var(--text-secondary)' }}>
                    <span style={{ color: 'var(--accent-green)' }}>•</span> {p}
                  </p>
                ))}
              </div>
            )}

            {sc.improvementPoints.length > 0 && (
              <div className="glass p-4">
                <p className="text-xs uppercase tracking-widest mb-3" style={{ color: 'var(--accent-amber)' }}>
                  → Improvements
                </p>
                {sc.improvementPoints.map((p, i) => (
                  <p key={i} className="text-xs py-1" style={{ color: 'var(--text-secondary)' }}>
                    <span style={{ color: 'var(--accent-amber)' }}>→</span> {p}
                  </p>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="glass p-8 text-center" style={{ color: 'var(--text-muted)', fontSize: '.8125rem' }}>
            No scorecard available
          </div>
        )}
      </div>
    </div>
  );
}
