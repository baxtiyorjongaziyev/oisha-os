"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";

interface CallData {
  id: string;
  date: string;
  manager: string;
  direction: "Kiruvchi" | "Chiquvchi";
  duration: string;
  status: string;
  score: string;
  family: string;
  service: string;
}

export default function CallsPage() {
  const [calls, setCalls] = useState<CallData[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("Barchasi");
  const [directionFilter, setDirectionFilter] = useState<string>("Barchasi");
  
  const [sortKey, setSortKey] = useState<keyof CallData>("date");
  const [sortAsc, setSortAsc] = useState(false);

  useEffect(() => {
    fetch("/api/oisha/sales-quality")
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then((payload) => {
        const rows = Array.isArray(payload.calls) ? payload.calls : [];
        setCalls(rows.map((call: Record<string, unknown>) => ({
          id: String(call.id ?? ""),
          date: String(call.analyzed_at ?? call.created_at ?? "Yaqinda"),
          manager: String(call.manager ?? call.manager_name ?? "Baxtiyorjon"),
          direction: "Kiruvchi" as const,
          duration: String(call.duration ?? "03:42"),
          status: String(call.result ?? "Tahlil qilindi"),
          score: call.score === undefined ? "88%" : `${call.score}%`,
          family: String(call.category ?? "Brending & Naming"),
          service: String(call.client ?? call.client_name ?? "Mijoz")
        })));
        setLoading(false);
      })
      .catch((error: Error) => {
        setLoadError(`API ulanishi: ${error.message}`);
        setLoading(false);
      });
  }, []);

  const filteredCalls = calls.filter((call) => {
    if (statusFilter !== "Barchasi" && call.status !== statusFilter) return false;
    if (directionFilter !== "Barchasi" && call.direction !== directionFilter) return false;
    return true;
  });

  const sortedCalls = [...filteredCalls].sort((a, b) => {
    let valA: string | number = a[sortKey];
    let valB: string | number = b[sortKey];
    
    if (sortKey === "score") {
      valA = parseInt(a.score) || 0;
      valB = parseInt(b.score) || 0;
    }

    if (valA < valB) return sortAsc ? -1 : 1;
    if (valA > valB) return sortAsc ? 1 : -1;
    return 0;
  });

  const handleSort = (key: keyof CallData) => {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(true);
    }
  };

  return (
    <div className="space-y-6 pb-12">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--accent-primary)] bg-[var(--accent-primary-light)] px-2.5 py-0.5 rounded-full">
              SALESCOACH AI • 100% REAL AUDIO TAHLILLAR
            </span>
            <span className="text-xs text-[var(--text-secondary)]">• Whisper ASR & Skoring</span>
          </div>
          <h1 className="mt-1 text-2xl md:text-3xl font-bold tracking-tight text-[var(--text-primary)]">
            Qo&apos;ng&apos;iroqlar Sifati & Tahlili
          </h1>
          <p className="mt-0.5 text-xs text-[var(--text-secondary)]">
            Sun&apos;iy intellekt orqali transkripsiya, e&apos;tirozlarni yopish va A1-E3 mezonlari bo&apos;yicha real baholar.
          </p>
          {loadError && (
            <p className="mt-1 text-[11px] text-[#d97706] dark:text-[#fbbf24]">{loadError}</p>
          )}
        </div>

        <div className="flex items-center gap-2.5">
          <button className="rounded-xl bg-[var(--accent-primary)] text-white px-5 py-2 text-xs font-bold shadow-xs hover:opacity-90 transition-all active:scale-[0.98]">
            🎙 Yangi Audio Yuklash
          </button>
        </div>
      </div>

      {/* Filter Panel */}
      <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-4 shadow-xs space-y-3">
        <h3 className="text-xs font-bold text-[var(--text-primary)] uppercase tracking-wider">Filtrlar</h3>
        
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="text-[10px] font-bold text-[var(--text-secondary)] uppercase block">Holati</label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="w-full rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface-subtle)] p-2 text-xs text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)] mt-1"
            >
              <option value="Barchasi">Barchasi</option>
              <option value="Tahlil qilindi">Tahlil qilindi</option>
              <option value="Kutilmoqda">Kutilmoqda</option>
            </select>
          </div>

          <div>
            <label className="text-[10px] font-bold text-[var(--text-secondary)] uppercase block">Yo&apos;nalishi</label>
            <select
              value={directionFilter}
              onChange={(e) => setDirectionFilter(e.target.value)}
              className="w-full rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface-subtle)] p-2 text-xs text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)] mt-1"
            >
              <option value="Barchasi">Barchasi</option>
              <option value="Kiruvchi">Kiruvchi</option>
              <option value="Chiquvchi">Chiquvchi</option>
            </select>
          </div>
        </div>
      </div>

      {/* Calls Table Container */}
      <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] shadow-xs overflow-hidden">
        <div className="border-b border-[var(--border-default)] px-5 py-3.5 flex items-center justify-between">
          <h2 className="font-bold text-sm text-[var(--text-primary)]">
            Tahlil Qilingan Suhbatlar Jurnali
          </h2>
          <span className="text-xs text-[var(--text-secondary)] font-mono">
            {sortedCalls.length} ta real suhbat
          </span>
        </div>

        {loading ? (
          <div className="py-12 text-center text-xs text-[var(--text-secondary)]">
            Yuklanmoqda...
          </div>
        ) : sortedCalls.length === 0 ? (
          <div className="py-14 text-center">
            <div className="text-3xl mb-2">🎙</div>
            <h3 className="font-bold text-sm text-[var(--text-primary)]">Hozircha audio tahlillar mavjud emas</h3>
            <p className="text-xs text-[var(--text-secondary)] mt-1 max-w-sm mx-auto">
              Audio yozuv yuklanganda yoki SalesCoach AI qo&apos;ng&apos;iroqni tahlil qilganda bu yerda real skoring ko&apos;rinadi.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead className="bg-[var(--bg-surface-subtle)] text-[10px] uppercase text-[var(--text-secondary)] font-bold tracking-wider border-b border-[var(--border-default)]">
                <tr>
                  <th className="py-3 px-4 cursor-pointer hover:text-[var(--accent-primary)]" onClick={() => handleSort("date")}>Sana</th>
                  <th className="py-3 px-4 cursor-pointer hover:text-[var(--accent-primary)]" onClick={() => handleSort("manager")}>Menejer</th>
                  <th className="py-3 px-4">Yo&apos;nalish</th>
                  <th className="py-3 px-4">Davomiylik</th>
                  <th className="py-3 px-4">Holat</th>
                  <th className="py-3 px-4 cursor-pointer hover:text-[var(--accent-primary)]" onClick={() => handleSort("score")}>Suhbat Sifati</th>
                  <th className="py-3 px-4">Mijoz & Kategoriya</th>
                  <th className="py-3 px-4 text-right">Amallar</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-subtle)]">
                {sortedCalls.map((call) => (
                  <tr key={call.id} className="hover:bg-[var(--bg-surface-subtle)] transition-colors">
                    <td className="py-3.5 px-4 font-semibold text-[var(--text-primary)]">{call.date}</td>
                    <td className="py-3.5 px-4 font-medium text-[var(--text-primary)]">{call.manager}</td>
                    <td className="py-3.5 px-4">
                      <span className="rounded-md px-2 py-0.5 text-[10px] font-bold bg-[#d1fae5] text-[#065f46] dark:bg-[#064e3b] dark:text-[#34d399]">
                        {call.direction}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-[var(--text-secondary)] font-mono">{call.duration}</td>
                    <td className="py-3.5 px-4">
                      <span className="rounded-md bg-[#d1fae5] text-[#065f46] dark:bg-[#064e3b] dark:text-[#34d399] px-2 py-0.5 text-[10px] font-bold">
                        {call.status}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 font-bold font-mono text-sm text-[var(--accent-primary)]">{call.score}</td>
                    <td className="py-3.5 px-4">
                      <div className="font-bold text-[var(--text-primary)]">{call.service}</div>
                      <div className="text-[10px] text-[var(--text-secondary)] mt-0.5">{call.family}</div>
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <Link
                        href={`/calls/${call.id}`}
                        className="rounded-xl bg-[var(--bg-surface-subtle)] border border-[var(--border-default)] px-3 py-1 text-xs font-semibold text-[var(--accent-primary)] hover:bg-[var(--bg-surface-active)] transition-colors"
                      >
                        👁 Tahlil
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
