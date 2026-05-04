'use client';
import { useEffect, useState, useRef, useCallback } from 'react';
import { use } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api';

/* ── Types ────────────────────────────────────────────────────── */
interface Segment {
  id: string; speaker: string; start: number; end: number; text: string; seq: number;
}

interface StageScores {
  opening: number;
  need_discovery: number;
  value_presentation: number;
  objection_handling: number;
  closing: number;
  rapport_building: number;
}

interface Scorecard {
  overallScore: number;
  summary: string;
  goodPoints: string[];
  improvementPoints: string[];
  recommendedPhrase: string;
  riskFlags: string[];
  leadQualityScore: number;
  stageScores?: StageScores;
  predictedOutcome?: string;
  voiceAnalytics: {
    managerTalkRatio: number;
    customerTalkRatio: number;
    wpm: number;
    tone: string;
    energy: string;
  };
}

interface CallDetail {
  id: string;
  customerName: string | null;
  direction: string;
  status: string;
  language: string | null;
  durationSec: number | null;
  audioUrl: string | null;
  createdAt: string;
  scorecard: Scorecard | null;
}

interface CoachingTip {
  type: 'tip' | 'alert';
  message: string;
  ts: number;
}

/* ── Helpers ──────────────────────────────────────────────────── */
function formatTime(sec: number) {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function formatDuration(sec: number | null) {
  if (!sec) return '—';
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}m ${s}s`;
}

const STAGE_LABELS: Record<string, string> = {
  opening: 'Opening',
  need_discovery: 'Need Discovery',
  value_presentation: 'Value Pitch',
  objection_handling: 'Objection Handling',
  closing: 'Closing',
  rapport_building: 'Rapport',
};

/* ── Main Page ────────────────────────────────────────────────── */
export default function CallDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [call, setCall] = useState<CallDetail | null>(null);
  const [transcript, setTranscript] = useState<Segment[]>([]);
  const [activeSegment, setActiveSegment] = useState<number | null>(null);
  const [liveMode, setLiveMode] = useState(false);
  const [tips, setTips] = useState<CoachingTip[]>([]);
  const [wsStatus, setWsStatus] = useState<'idle' | 'connecting' | 'connected' | 'error'>('idle');
  const audioRef = useRef<HTMLAudioElement>(null);
  const wsRef = useRef<any>(null);
  const tipsBottomRef = useRef<HTMLDivElement>(null);

  /* Fetch call + transcript */
  useEffect(() => {
    Promise.all([
      api.get<CallDetail>(`/calls/${id}`),
      api.get<Segment[]>(`/calls/${id}/transcript`),
    ]).then(([c, t]) => {
      setCall(c);
      setTranscript(t);
    });
  }, [id]);

  /* Auto-refresh while processing */
  useEffect(() => {
    if (!call) return;
    if (['UPLOADED', 'TRANSCRIBING', 'SCORING'].includes(call.status)) {
      const t = setTimeout(() => {
        api.get<CallDetail>(`/calls/${id}`).then(setCall);
      }, 4000);
      return () => clearTimeout(t);
    }
  }, [call, id]);

  /* WebSocket coaching */
  const connectLive = useCallback(async () => {
    if (wsRef.current) return;
    setWsStatus('connecting');
    try {
      const { io } = await import('socket.io-client');
      const token = localStorage.getItem('accessToken');
      const socket = io(
        (process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:4000').replace('/v1', '') + '/coaching',
        { auth: { token }, transports: ['websocket'] }
      );
      wsRef.current = socket;

      socket.on('connect', () => {
        setWsStatus('connected');
        socket.emit('call:join', { callId: id });
      });
      socket.on('coaching:tip', (data: { message: string }) => {
        setTips(p => [...p, { type: 'tip', message: data.message, ts: Date.now() }]);
        tipsBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
      });
      socket.on('coaching:alert', (data: { message: string }) => {
        setTips(p => [...p, { type: 'alert', message: data.message, ts: Date.now() }]);
        tipsBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
      });
      socket.on('disconnect', () => setWsStatus('idle'));
      socket.on('connect_error', () => setWsStatus('error'));
    } catch {
      setWsStatus('error');
    }
  }, [id]);

  const disconnectLive = useCallback(() => {
    wsRef.current?.disconnect();
    wsRef.current = null;
    setWsStatus('idle');
    setLiveMode(false);
  }, []);

  const seekTo = (start: number) => {
    if (audioRef.current) { audioRef.current.currentTime = start; audioRef.current.play(); }
  };

  if (!call) return (
    <div className="flex items-center justify-center h-screen" style={{ color: 'var(--text-secondary)' }}>
      <div className="flex flex-col items-center gap-3">
        <span className="pulse-live inline-block text-3xl">⚡</span>
        <p>Loading call data...</p>
      </div>
    </div>
  );

  const sc = call.scorecard;
  const scoreColor = sc
    ? sc.overallScore >= 80 ? 'var(--accent-green)'
      : sc.overallScore >= 60 ? 'var(--accent-amber)'
      : 'var(--accent-red)'
    : 'var(--text-muted)';

  return (
    <div className="flex h-screen overflow-hidden">

      {/* ── Left: Transcript ──────────────────────────────────── */}
      <div className="flex flex-col w-[38%] min-w-0 border-r border-[var(--border)]">

        {/* Header */}
        <div className="flex items-center gap-3 px-5 py-4 border-b border-[var(--border)] shrink-0">
          <Link href="/dashboard"
            className="text-sm hover:text-[var(--accent-cyan)] transition-colors"
            style={{ color: 'var(--text-muted)' }}>
            ← Back
          </Link>
          <div className="flex-1 min-w-0">
            <p className="font-semibold truncate" style={{ color: 'var(--text-primary)' }}>
              {call.customerName ?? 'Unknown Customer'}
            </p>
            <p className="text-xs mt-0.5 flex items-center gap-2" style={{ color: 'var(--text-muted)' }}>
              <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                call.direction === 'OUTBOUND' ? 'badge-cyan' : 'badge-violet'
              }`}>{call.direction}</span>
              <StatusChip status={call.status} />
              <span>{formatDuration(call.durationSec)}</span>
              <span>{call.language?.toUpperCase() ?? ''}</span>
            </p>
          </div>
          <Link href={`/negotiate?customerName=${encodeURIComponent(call.customerName ?? '')}&callId=${call.id}`}>
            <button className="px-3 py-1.5 text-xs rounded-lg font-medium transition-all hover:opacity-90 shrink-0"
              style={{ background: 'linear-gradient(135deg,var(--accent-violet),var(--accent-cyan))', color: '#fff' }}>
              🤝 Negotiate
            </button>
          </Link>
        </div>

        {/* Audio */}
        {call.audioUrl && (
          <div className="px-4 py-3 border-b border-[var(--border)] shrink-0">
            <audio ref={audioRef} src={call.audioUrl} controls
              className="w-full h-8 rounded-lg" style={{ accentColor: 'var(--accent-cyan)' }} />
          </div>
        )}

        {/* Transcript scroll area */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {transcript.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center"
              style={{ color: 'var(--text-muted)', fontSize: '.8125rem' }}>
              {['UPLOADED', 'TRANSCRIBING'].includes(call.status)
                ? <><span className="pulse-live text-2xl mb-2">🎙️</span><p>Transcribing...</p></>
                : <p>No transcript available</p>
              }
            </div>
          )}
          {transcript.map((seg, i) => (
            <div
              key={seg.id}
              onClick={() => { seekTo(seg.start); setActiveSegment(i); }}
              className={`flex gap-3 cursor-pointer rounded-xl px-3 py-2.5 transition-all ${
                activeSegment === i
                  ? 'glass-accent'
                  : 'hover:bg-[var(--bg-card-hover)]'
              }`}
            >
              <div className={`text-[10px] font-bold mt-1 w-14 shrink-0 uppercase tracking-wider ${
                seg.speaker === 'manager' ? '' : ''
              }`} style={{
                color: seg.speaker === 'manager' ? 'var(--accent-cyan)' : 'var(--accent-violet)'
              }}>
                {seg.speaker === 'manager' ? '🤖 MGR' : '👤 CLI'}
              </div>
              <div className="min-w-0">
                <p className="text-sm leading-relaxed" style={{ color: 'var(--text-primary)' }}>{seg.text}</p>
                <p className="text-[10px] mt-1" style={{ color: 'var(--text-muted)' }}>
                  {formatTime(seg.start)}
                </p>
              </div>
            </div>
          ))}
        </div>

        {/* Live coaching toggle */}
        <div className="px-4 py-3 border-t border-[var(--border)] shrink-0">
          {!liveMode ? (
            <button
              onClick={() => { setLiveMode(true); connectLive(); }}
              className="w-full py-2.5 rounded-xl text-sm font-medium transition-all hover:opacity-90"
              style={{ background: 'rgba(0,242,255,.08)', color: 'var(--accent-cyan)', border: '1px solid rgba(0,242,255,.2)' }}>
              ⚡ Connect Live Coaching
            </button>
          ) : (
            <button onClick={disconnectLive}
              className="w-full py-2.5 rounded-xl text-sm font-medium transition-all hover:opacity-90"
              style={{ background: 'rgba(255,75,110,.08)', color: 'var(--accent-red)', border: '1px solid rgba(255,75,110,.2)' }}>
              ✕ Disconnect
            </button>
          )}
        </div>
      </div>

      {/* ── Right: Score + Intel ───────────────────────────────── */}
      <div className="flex-1 overflow-y-auto p-6 space-y-5">

        {/* Processing banner */}
        {['UPLOADED', 'TRANSCRIBING', 'SCORING'].includes(call.status) && (
          <div className="glass-accent p-4 flex items-center gap-3">
            <span className="pulse-live text-xl">⚙️</span>
            <div>
              <p className="text-sm font-medium" style={{ color: 'var(--accent-cyan)' }}>Processing call...</p>
              <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
                Status: {call.status} · Auto-refreshing
              </p>
            </div>
          </div>
        )}

        {sc ? (
          <>
            {/* Score hero */}
            <div className="glass p-6 flex items-center gap-6">
              <ScoreRing score={sc.overallScore} />
              <div className="flex-1">
                <p className="text-xs uppercase tracking-widest mb-1" style={{ color: 'var(--text-muted)' }}>
                  Overall Performance
                </p>
                <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                  {sc.summary}
                </p>
                {sc.predictedOutcome && (
                  <p className="text-xs mt-2 font-medium" style={{ color: 'var(--accent-amber)' }}>
                    Predicted: {sc.predictedOutcome.replace(/_/g, ' ')}
                  </p>
                )}
              </div>
              {sc.leadQualityScore !== undefined && (
                <div className="text-center shrink-0">
                  <p className="text-xs uppercase tracking-widest mb-1" style={{ color: 'var(--text-muted)' }}>
                    Lead Quality
                  </p>
                  <span className="text-2xl font-bold" style={{ color: 'var(--accent-violet)' }}>
                    {Math.round(sc.leadQualityScore)}
                  </span>
                  <span className="text-xs ml-1" style={{ color: 'var(--text-muted)' }}>/100</span>
                </div>
              )}
            </div>

            {/* Stage breakdown */}
            {sc.stageScores && (
              <div className="glass p-5">
                <p className="text-xs uppercase tracking-widest mb-4" style={{ color: 'var(--text-muted)' }}>
                  Stage Breakdown
                </p>
                <div className="space-y-3">
                  {(Object.entries(sc.stageScores) as [string, number][]).map(([key, val]) => (
                    <div key={key}>
                      <div className="flex justify-between text-xs mb-1.5">
                        <span style={{ color: 'var(--text-secondary)' }}>{STAGE_LABELS[key] ?? key}</span>
                        <span className="font-medium" style={{
                          color: val >= 80 ? 'var(--accent-green)' : val >= 60 ? 'var(--accent-amber)' : 'var(--accent-red)'
                        }}>{Math.round(val)}</span>
                      </div>
                      <div className="progress-bar">
                        <div className="progress-fill" style={{ width: `${val}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Voice analytics */}
            {sc.voiceAnalytics && (
              <div className="glass p-5">
                <p className="text-xs uppercase tracking-widest mb-4" style={{ color: 'var(--text-muted)' }}>
                  Voice Analytics
                </p>
                <div className="grid grid-cols-2 gap-3">
                  <VoiceStat label="Manager Talk" value={`${Math.round(sc.voiceAnalytics.managerTalkRatio * 100)}%`} color="var(--accent-cyan)" />
                  <VoiceStat label="Customer Talk" value={`${Math.round(sc.voiceAnalytics.customerTalkRatio * 100)}%`} color="var(--accent-violet)" />
                  <VoiceStat label="WPM" value={`${sc.voiceAnalytics.wpm ?? '—'}`} color="var(--accent-amber)" />
                  <VoiceStat label="Tone" value={sc.voiceAnalytics.tone ?? '—'} color="var(--accent-green)" />
                </div>
                <div className="mt-3 flex gap-2 items-center">
                  <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Energy:</span>
                  <span className="text-xs px-2 py-0.5 rounded-full badge-amber">
                    {sc.voiceAnalytics.energy ?? '—'}
                  </span>
                </div>
                {/* Talk ratio bar */}
                <div className="mt-3">
                  <div className="h-2 rounded-full overflow-hidden flex" style={{ background: 'rgba(255,255,255,.06)' }}>
                    <div style={{ width: `${sc.voiceAnalytics.managerTalkRatio * 100}%`, background: 'var(--accent-cyan)', transition: 'width .4s' }} />
                    <div style={{ flex: 1, background: 'var(--accent-violet)' }} />
                  </div>
                  <div className="flex justify-between text-[10px] mt-1" style={{ color: 'var(--text-muted)' }}>
                    <span>Manager</span><span>Customer</span>
                  </div>
                </div>
              </div>
            )}

            {/* Good points + improvements */}
            <div className="grid grid-cols-2 gap-4">
              {sc.goodPoints.length > 0 && (
                <div className="glass p-4">
                  <p className="text-xs uppercase tracking-widest mb-3" style={{ color: 'var(--accent-green)' }}>
                    ✓ Good Points
                  </p>
                  <ul className="space-y-2">
                    {sc.goodPoints.map((p, i) => (
                      <li key={i} className="flex gap-2 text-xs" style={{ color: 'var(--text-secondary)' }}>
                        <span style={{ color: 'var(--accent-green)' }}>•</span>{p}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {sc.improvementPoints.length > 0 && (
                <div className="glass p-4">
                  <p className="text-xs uppercase tracking-widest mb-3" style={{ color: 'var(--accent-amber)' }}>
                    → Improvements
                  </p>
                  <ul className="space-y-2">
                    {sc.improvementPoints.map((p, i) => (
                      <li key={i} className="flex gap-2 text-xs" style={{ color: 'var(--text-secondary)' }}>
                        <span style={{ color: 'var(--accent-amber)' }}>→</span>{p}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            {/* Recommended phrase */}
            {sc.recommendedPhrase && (
              <div className="glass-accent p-4 tip-card">
                <p className="text-xs uppercase tracking-widest mb-2" style={{ color: 'var(--accent-cyan)' }}>
                  💬 Recommended Phrase
                </p>
                <p className="text-sm italic leading-relaxed" style={{ color: 'var(--text-primary)' }}>
                  "{sc.recommendedPhrase}"
                </p>
              </div>
            )}

            {/* Risk flags */}
            {sc.riskFlags.length > 0 && (
              <div className="glass p-4" style={{ borderColor: 'rgba(255,75,110,.25)', borderWidth: 1 }}>
                <p className="text-xs uppercase tracking-widest mb-3" style={{ color: 'var(--accent-red)' }}>
                  ⚠ Risk Flags
                </p>
                <div className="flex flex-wrap gap-2">
                  {sc.riskFlags.map((f, i) => (
                    <span key={i} className="text-xs px-2 py-1 rounded-full badge-red">{f}</span>
                  ))}
                </div>
              </div>
            )}
          </>
        ) : call.status === 'DONE' ? (
          <div className="glass p-12 text-center" style={{ color: 'var(--text-muted)' }}>
            No scorecard available for this call.
          </div>
        ) : null}

        {/* Live coaching feed */}
        {liveMode && (
          <div className="glass p-4 slide-up">
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs uppercase tracking-widest" style={{ color: 'var(--accent-cyan)' }}>
                ⚡ Live Coaching Feed
              </p>
              <WsStatusDot status={wsStatus} />
            </div>
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {tips.length === 0 && (
                <p className="text-xs text-center py-4" style={{ color: 'var(--text-muted)' }}>
                  Waiting for coaching events...
                </p>
              )}
              {tips.map((tip, i) => (
                <div key={i} className={`text-xs px-3 py-2 rounded-lg tip-card ${
                  tip.type === 'alert' ? 'badge-red' : ''
                }`} style={tip.type === 'tip' ? {
                  background: 'rgba(0,242,255,.06)',
                  color: 'var(--text-secondary)',
                  border: '1px solid rgba(0,242,255,.15)'
                } : undefined}>
                  <span style={{ color: tip.type === 'alert' ? 'var(--accent-red)' : 'var(--accent-cyan)' }}>
                    {tip.type === 'alert' ? '⚠ ' : '💡 '}
                  </span>
                  {tip.message}
                </div>
              ))}
              <div ref={tipsBottomRef} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Sub-components ───────────────────────────────────────────── */

function ScoreRing({ score }: { score: number }) {
  const color = score >= 80 ? 'var(--accent-green)' : score >= 60 ? 'var(--accent-amber)' : 'var(--accent-red)';
  return (
    <div className="score-ring shrink-0" style={{ ['--pct' as any]: score }}>
      <span style={{ color }}>{Math.round(score)}</span>
    </div>
  );
}

function StatusChip({ status }: { status: string }) {
  const cls: Record<string, string> = {
    UPLOADED: 'badge-amber', TRANSCRIBING: 'badge-amber',
    SCORING: 'badge-cyan', DONE: 'badge-green', FAILED: 'badge-red',
  };
  return (
    <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${cls[status] ?? 'badge-amber'}`}>
      {status}
    </span>
  );
}

function VoiceStat({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="px-3 py-2 rounded-lg" style={{ background: 'rgba(255,255,255,.03)', border: '1px solid var(--border)' }}>
      <p className="text-[10px] uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>{label}</p>
      <p className="text-sm font-semibold" style={{ color }}>{value}</p>
    </div>
  );
}

function WsStatusDot({ status }: { status: 'idle' | 'connecting' | 'connected' | 'error' }) {
  const colors = {
    idle: 'var(--text-muted)',
    connecting: 'var(--accent-amber)',
    connected: 'var(--accent-green)',
    error: 'var(--accent-red)',
  };
  const labels = { idle: 'Idle', connecting: 'Connecting…', connected: 'Live', error: 'Error' };
  return (
    <div className="flex items-center gap-1.5">
      <span className={`w-2 h-2 rounded-full ${status === 'connected' ? 'pulse-live' : ''}`}
        style={{ background: colors[status], display: 'inline-block' }} />
      <span className="text-[10px]" style={{ color: colors[status] }}>{labels[status]}</span>
    </div>
  );
}
