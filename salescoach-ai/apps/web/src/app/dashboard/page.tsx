'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api';

interface CallSummary {
  id: string;
  customerName: string | null;
  direction: string;
  status: string;
  createdAt: string;
  durationSec: number | null;
  scorecard: { overallScore: number } | null;
}

export default function DashboardPage() {
  const [calls, setCalls] = useState<CallSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<CallSummary[]>('/calls').then(setCalls).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-8 text-center">Loading...</div>;

  return (
    <div className="max-w-5xl mx-auto p-8">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-bold">SalesCoach AI</h1>
        <Link
          href="/calls/upload"
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          Upload Call
        </Link>
      </div>

      <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Customer</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Direction</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Score</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Date</th>
            </tr>
          </thead>
          <tbody>
            {calls.map((call) => (
              <tr key={call.id} className="border-b hover:bg-gray-50 cursor-pointer">
                <td className="px-4 py-3">
                  <Link href={`/calls/${call.id}`} className="font-medium text-blue-600 hover:underline">
                    {call.customerName ?? 'Unknown'}
                  </Link>
                </td>
                <td className="px-4 py-3 text-gray-600">{call.direction}</td>
                <td className="px-4 py-3">
                  <StatusBadge status={call.status} />
                </td>
                <td className="px-4 py-3">
                  {call.scorecard ? (
                    <ScoreBadge score={call.scorecard.overallScore} />
                  ) : (
                    <span className="text-gray-400">—</span>
                  )}
                </td>
                <td className="px-4 py-3 text-gray-500">
                  {new Date(call.createdAt).toLocaleDateString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {calls.length === 0 && (
          <div className="text-center py-16 text-gray-500">
            No calls yet. Upload your first recording.
          </div>
        )}
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    UPLOADED: 'bg-gray-100 text-gray-700',
    TRANSCRIBING: 'bg-yellow-100 text-yellow-700',
    SCORING: 'bg-blue-100 text-blue-700',
    DONE: 'bg-green-100 text-green-700',
    FAILED: 'bg-red-100 text-red-700',
  };
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${colors[status] ?? 'bg-gray-100'}`}>
      {status}
    </span>
  );
}

function ScoreBadge({ score }: { score: number }) {
  const color = score >= 80 ? 'text-green-600' : score >= 60 ? 'text-yellow-600' : 'text-red-600';
  return <span className={`font-bold ${color}`}>{Math.round(score)}</span>;
}
