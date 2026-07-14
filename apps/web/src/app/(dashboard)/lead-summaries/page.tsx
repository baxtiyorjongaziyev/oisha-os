"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

type Summary = { id?: string; call_id?: string; client?: string; manager?: string; summary?: string; score?: number; analyzed_at?: string };

export default function LeadSummariesPage() {
  const [rows, setRows] = useState<Summary[]>([]);
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    fetch("/api/oisha/sales-quality", { cache: "no-store" })
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.reason || payload.message || `HTTP ${response.status}`);
        return Array.isArray(payload.calls) ? payload.calls : [];
      })
      .then((calls) => setRows(calls.filter((call: Summary) => Boolean(call.summary))))
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoaded(true));
  }, []);

  return <div className="space-y-6">
    <div><h1 className="text-2xl font-bold text-text">Lid xulosalari</h1><p className="mt-1 text-xs text-text-muted">Real qo&apos;ng&apos;iroq tahlillaridan olingan xulosalar.</p></div>
    {error ? <div className="border border-rose-300 bg-rose-50 p-4 text-sm text-rose-700">Real manba ishlamayapti: {error}</div> : null}
    {loaded && !error && rows.length === 0 ? <div className="border border-border bg-bg-card p-8 text-center text-sm text-text-muted">Xulosa saqlangan real tahlil topilmadi.</div> : null}
    <div className="space-y-3">{rows.map((row) => {
      const id = String(row.call_id || row.id || "");
      return <Link href={`/calls/${id}`} key={id} className="block border border-border bg-bg-card p-5 hover:border-brand">
        <div className="flex justify-between gap-4"><strong>{row.client || "Noma'lum mijoz"}</strong><span className="text-sm text-brand">{row.score ?? 0}%</span></div>
        <p className="mt-2 text-sm text-text-muted">{row.summary}</p>
        <div className="mt-2 text-xs text-text-muted">{row.manager || "Noma'lum menejer"} · {row.analyzed_at || "Sana yo'q"}</div>
      </Link>;
    })}</div>
  </div>;
}
