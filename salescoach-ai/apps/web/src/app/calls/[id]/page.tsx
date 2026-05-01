'use client';
import { useEffect, useState, useRef } from 'react';
import { use } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api';

interface Segment { id: string; speaker: string; start: number; end: number; text: string; seq: number; }
interface Scorecard {
  overallScore: number; summary: string; goodPoints: string[];
  improvementPoints: string[]; recommendedPhrase: string; riskFlags: string[];
  leadQualityScore: number;
  voiceAnalytics: { managerTalkRatio: number; customerTalkRatio: number; wpm: number; tone: string; energy: string };
}
interface CallDetail {
  id: string; customerName: string | null; direction: string; status: string;
  language: string | null; durationSec: number | null; audioUrl: string | null;
  createdAt: string; scorecard: Scorecard | null;
}

export default function CallDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [call, setCall] = useState<CallDetail | null>(null);
  const [transcript, setTranscript] = useState<Segment[]>([]);
  const [activeSegment, setActiveSegment] = useState<number | null>(null);
  const audioRef = useRef<HTMLAudioElement>(null);

  useEffect(() => {
    Promise.all([
      api.get<CallDetail>(`/calls/${id}`),
      api.get<Segment[]>(`/calls/${id}/transcript`),
    ]).then(([c, t]) => { setCall(c); setTranscript(t); });
  }, [id]);

  const seekTo = (start: number) => {
    if (audioRef.current) { audioRef.current.currentTime = start; audioRef.current.play(); }
  };

  if (!call) return <div className="p-8 text-center">Loading...</div>;

  return (
    <div className="max-w-6xl mx-auto p-8">
      <div className="flex items-center gap-3 mb-6">
        <Link href="/dashboard" className="text-gray-500 hover:text-gray-700">← Dashboard</Link>
        <h1 className="text-xl font-bold">{call.customerName ?? 'Unknown Customer'}</h1>
        <span className="text-sm text-gray-400">{call.direction} · {call.language}</span>
      </div>

      {call.audioUrl && (
        <div className="mb-6 bg-gray-900 rounded-xl p-4">
          <audio ref={audioRef} src={call.audioUrl} controls className="w-full" />
        </div>
      )}

      <div className="grid grid-cols-2 gap-6">
        {/* Transcript */}
        <div className="bg-white rounded-xl border shadow-sm p-4 h-[60vh] overflow-y-auto">
          <h2 className="font-semibold text-gray-800 mb-4">Transcript</h2>
          <div className="space-y-3">
            {transcript.map((seg, i) => (
              <div
                key={seg.id}
                onClick={() => { seekTo(seg.start); setActiveSegment(i); }}
                className={`flex gap-3 cursor-pointer rounded-lg p-2 transition-colors ${
                  activeSegment === i ? 'bg-blue-50' : 'hover:bg-gray-50'
                }`}
              >
                <div className={`text-xs font-medium mt-1 w-16 shrink-0 ${
                  seg.speaker === 'manager' ? 'text-blue-600' : 'text-green-600'
                }`}>
                  {seg.speaker.toUpperCase()}
                </div>
                <div>
                  <p className="text-sm text-gray-800">{seg.text}</p>
                  <p className="text-xs text-gray-400 mt-0.5">{formatTime(seg.start)}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Scorecard */}
        <div className="space-y-4">
          {call.scorecard ? (
            <>
              <div className="bg-white rounded-xl border shadow-sm p-6">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="font-semibold text-gray-800">Overall Score</h2>
                  <span className={`text-4xl font-bold ${
                    call.scorecard.overallScore >= 80 ? 'text-green-600' :
                    call.scorecard.overallScore >= 60 ? 'text-yellow-600' : 'text-red-600'
                  }`}>{Math.round(call.scorecard.overallScore)}</span>
                </div>
                <p className="text-sm text-gray-600">{call.scorecard.summary}</p>
              </div>

              <div className="bg-white rounded-xl border shadow-sm p-6">
                <h3 className="font-semibold text-gray-800 mb-3">Good Points</h3>
                <ul className="space-y-1">
                  {call.scorecard.goodPoints.map((p, i) => (
                    <li key={i} className="text-sm text-gray-600 flex gap-2">
                      <span className="text-green-500">✓</span>{p}
                    </li>
                  ))}
                </ul>
              </div>

              <div className="bg-white rounded-xl border shadow-sm p-6">
                <h3 className="font-semibold text-gray-800 mb-3">Improvements</h3>
                <ul className="space-y-1">
                  {call.scorecard.improvementPoints.map((p, i) => (
                    <li key={i} className="text-sm text-gray-600 flex gap-2">
                      <span className="text-amber-500">→</span>{p}
                    </li>
                  ))}
                </ul>
              </div>

              {call.scorecard.riskFlags.length > 0 && (
                <div className="bg-red-50 rounded-xl border border-red-200 p-6">
                  <h3 className="font-semibold text-red-700 mb-3">Risk Flags</h3>
                  <ul className="space-y-1">
                    {call.scorecard.riskFlags.map((f, i) => (
                      <li key={i} className="text-sm text-red-600">{f}</li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          ) : (
            <div className="bg-white rounded-xl border shadow-sm p-12 text-center text-gray-500">
              {call.status === 'DONE' ? 'No scorecard' : `Processing: ${call.status}`}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function formatTime(sec: number) {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}
