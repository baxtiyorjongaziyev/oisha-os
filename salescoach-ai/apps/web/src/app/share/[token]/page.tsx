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
      // Read token from fragment first, fall back to path segment
      const fragment = typeof window !== 'undefined'
        ? new URLSearchParams(window.location.hash.slice(1)).get('k')
        : null;
      const token = fragment ?? pathToken;

      const params = new URLSearchParams({ token });
      if (pwd) params.set('password', pwd);

      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:4000/v1'}/public/share?${params}`,
      );

      if (res.status === 401) {
        setNeedsPassword(true);
        setError('Password required');
        return;
      }
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

  if (loading) return <div className="p-8 text-center">Loading...</div>;

  if (needsPassword) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="bg-white rounded-2xl shadow-lg p-8 w-80">
          <h2 className="text-lg font-semibold mb-4">Password required</h2>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Enter password"
            className="w-full border rounded-lg px-3 py-2 mb-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          {error && <p className="text-red-500 text-sm mb-3">{error}</p>}
          <button
            onClick={() => resolve(password)}
            className="w-full bg-blue-600 text-white rounded-lg py-2 hover:bg-blue-700"
          >
            Access Call
          </button>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-xl font-semibold text-gray-800 mb-2">Link unavailable</h2>
          <p className="text-gray-500">{error ?? 'This link may have expired or been revoked.'}</p>
        </div>
      </div>
    );
  }

  const { call } = data;
  return (
    <div className="max-w-4xl mx-auto p-8">
      <div className="mb-6">
        <p className="text-xs text-gray-400 mb-1">Shared via SalesCoach AI</p>
        <h1 className="text-2xl font-bold">{call.customerName ?? 'Sales Call'}</h1>
        <p className="text-gray-500 text-sm">
          {call.direction} · {call.language} · {call.durationSec ? `${Math.floor(call.durationSec / 60)} min` : ''} ·{' '}
          {new Date(call.createdAt).toLocaleDateString()}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border shadow-sm p-4 h-[60vh] overflow-y-auto">
          <h2 className="font-semibold mb-4">Transcript</h2>
          <div className="space-y-3">
            {call.transcript.map((seg) => (
              <div key={seg.seq} className="flex gap-3">
                <span className={`text-xs font-medium mt-1 w-16 shrink-0 ${
                  seg.speaker === 'manager' ? 'text-blue-600' : 'text-green-600'
                }`}>{seg.speaker.toUpperCase()}</span>
                <p className="text-sm text-gray-800">{seg.text}</p>
              </div>
            ))}
          </div>
        </div>

        {call.scorecard && (
          <div className="space-y-4">
            <div className="bg-white rounded-xl border shadow-sm p-6">
              <div className="flex items-center justify-between mb-3">
                <h2 className="font-semibold">Score</h2>
                <span className="text-4xl font-bold text-blue-600">
                  {Math.round(call.scorecard.overallScore)}
                </span>
              </div>
              <p className="text-sm text-gray-600">{call.scorecard.summary}</p>
            </div>
            <div className="bg-white rounded-xl border shadow-sm p-6">
              <h3 className="font-semibold mb-3">Good Points</h3>
              {call.scorecard.goodPoints.map((p, i) => (
                <p key={i} className="text-sm text-gray-600">✓ {p}</p>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
