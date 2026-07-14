"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

type CallDetail = {
  call_id: string;
  lead_name: string;
  summary: string;
  sentiment: string;
  metrics: Array<{ label: string; score: number; status: string }>;
  transcript: Array<{ speaker?: string; text?: string; timestamp?: string }>;
  next_steps: string[];
};

export default function CallDetailsPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [call, setCall] = useState<CallDetail | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`/api/oisha/sales-quality/${encodeURIComponent(id)}`, { cache: "no-store" })
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
        return payload;
      })
      .then(setCall)
      .catch((reason: Error) => setError(reason.message));
  }, [id]);

  return <div className="space-y-6">
    <button onClick={() => router.back()} className="text-xs font-semibold text-text-muted hover:text-brand">&larr; Orqaga</button>
    {error ? <div className="border border-rose-300 bg-rose-50 p-4 text-sm text-rose-700">Real tahlil olinmadi: {error}</div> : null}
    {!error && !call ? <div className="p-6 text-sm text-text-muted">Yuklanmoqda...</div> : null}
    {call ? <>
      <header className="border border-border bg-bg-card p-6">
        <div className="text-xs text-text-muted">Call ID: {call.call_id}</div>
        <h1 className="mt-1 text-xl font-bold text-text">{call.lead_name}</h1>
        <p className="mt-3 text-sm text-text-muted">{call.summary || "Xulosa mavjud emas."}</p>
        <div className="mt-3 text-xs font-semibold text-brand">Kayfiyat: {call.sentiment}</div>
      </header>
      <section className="border border-border bg-bg-card p-6">
        <h2 className="text-sm font-bold">Baholash mezonlari</h2>
        {call.metrics.length === 0 ? <p className="mt-3 text-xs text-text-muted">Mezonlar saqlanmagan.</p> : call.metrics.map((metric) => <div key={metric.label} className="mt-3 flex justify-between border-b border-border pb-2 text-sm"><span>{metric.label}</span><strong>{metric.score}%</strong></div>)}
      </section>
      <section className="border border-border bg-bg-card p-6">
        <h2 className="text-sm font-bold">Transcript</h2>
        {call.transcript.length === 0 ? <p className="mt-3 text-xs text-text-muted">Transcript saqlanmagan.</p> : call.transcript.map((line, index) => <div key={index} className="mt-3 text-sm"><strong>{line.speaker || "Suhbat"}:</strong> {line.text || ""} <span className="text-xs text-text-muted">{line.timestamp || ""}</span></div>)}
      </section>
      <section className="border border-border bg-bg-card p-6">
        <h2 className="text-sm font-bold">Keyingi qadamlar</h2>
        {call.next_steps.length === 0 ? <p className="mt-3 text-xs text-text-muted">Keyingi qadam saqlanmagan.</p> : <ul className="mt-3 list-disc pl-5 text-sm">{call.next_steps.map((step) => <li key={step}>{step}</li>)}</ul>}
      </section>
    </> : null}
  </div>;
}
