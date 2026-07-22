"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

type Call = { id?: string; call_id?: string; client?: string; manager?: string; score?: number; duration?: string; outcome?: string };
type Payload = {
  real_data?: boolean;
  reason?: string;
  overview?: { total_calls?: number; average_score?: number };
  managers?: Array<{ name: string; total_calls: number; average_score: number }>;
  calls?: Call[];
};

export default function HomePage() {
  const [data, setData] = useState<Payload | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/api/oisha/sales-quality", { cache: "no-store" })
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.reason || payload.message || `HTTP ${response.status}`);
        return payload;
      })
      .then(setData)
      .catch((reason: Error) => setError(reason.message));
  }, []);

  const calls = data?.calls ?? [];
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-text">Bosh sahifa</h1>
        <p className="mt-1 text-xs text-text-muted">Faqat saqlangan real qo&apos;ng&apos;iroq tahlillari.</p>
      </div>

      {error ? <div className="border border-rose-300 bg-rose-50 p-4 text-sm text-rose-700">Real manba ishlamayapti: {error}</div> : null}
      {!error && !data ? <div className="p-6 text-sm text-text-muted">Yuklanmoqda...</div> : null}
      {data ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="border border-border bg-bg-card p-5">
              <div className="text-xs text-text-muted">Tahlil qilingan qo&apos;ng&apos;iroqlar</div>
              <div className="mt-2 text-3xl font-bold text-text">{data.overview?.total_calls ?? 0}</div>
            </div>
            <div className="border border-border bg-bg-card p-5">
              <div className="text-xs text-text-muted">O&apos;rtacha sifat</div>
              <div className="mt-2 text-3xl font-bold text-text">{data.overview?.average_score ?? 0}%</div>
            </div>
          </div>

          {data.real_data === false ? <div className="border border-amber-300 bg-amber-50 p-4 text-sm text-amber-800">Real yozuv topilmadi. {data.reason || "Call analysis jadvali bo'sh."}</div> : null}

          <section className="border border-border bg-bg-card p-5">
            <h2 className="text-sm font-bold text-text">So&apos;nggi tahlillar</h2>
            {calls.length === 0 ? <p className="mt-4 text-xs text-text-muted">Real tahlillar mavjud emas.</p> : (
              <div className="mt-4 divide-y divide-border">
                {calls.slice(0, 10).map((call) => {
                  const id = String(call.call_id || call.id || "");
                  return <Link key={id} href={`/calls/${id}`} className="flex items-center justify-between py-3 text-xs hover:text-brand">
                    <span>{call.client || "Noma'lum mijoz"} · {call.manager || "Noma'lum menejer"}</span>
                    <strong>{call.score ?? 0}%</strong>
                  </Link>;
                })}
              </div>
            )}
          </section>
        </>
      ) : null}
    </div>
  );
}
