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
  const [loadError, setLoadError] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("Barchasi");
  const [directionFilter, setDirectionFilter] = useState<string>("Barchasi");
  const [serviceFilter, setServiceFilter] = useState<string>("Barchasi");
  const [managerFilter, setManagerFilter] = useState<string>("Barchasi");
  
  // Sorting state
  const [sortKey, setSortKey] = useState<keyof CallData>("date");
  const [sortAsc, setSortAsc] = useState(false);

  // Active dropdown index for actions menu
  const [activeActionsMenu, setActiveActionsMenu] = useState<string | null>(null);

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
          date: String(call.analyzed_at ?? ""),
          manager: String(call.manager ?? "Noma'lum manager"),
          direction: "Kiruvchi" as const,
          duration: String(call.duration ?? "00:00"),
          status: String(call.result ?? "Tahlil qilindi"),
          score: call.score === undefined ? "-" : `${call.score}%`,
          family: String(call.category ?? "Noma'lum"),
          service: String(call.client ?? "Noma'lum mijoz")
        })));
        setLoadError(payload.real_data === false ? String(payload.message ?? "Real tahlillar topilmadi") : "");
      })
      .catch((error: Error) => setLoadError(`Real API ulanmagan: ${error.message}`));
  }, []);

  // Filter application
  const filteredCalls = calls.filter((call) => {
    if (statusFilter !== "Barchasi" && call.status !== statusFilter) return false;
    if (directionFilter !== "Barchasi" && call.direction !== directionFilter) return false;
    if (serviceFilter !== "Barchasi" && !call.service.includes(serviceFilter)) return false;
    if (managerFilter !== "Barchasi" && call.manager !== managerFilter) return false;
    return true;
  });

  // Sort application
  const sortedCalls = [...filteredCalls].sort((a, b) => {
    let valA: string | number = a[sortKey];
    let valB: string | number = b[sortKey];
    
    // Custom logic for score parsing or empty values
    if (sortKey === "score") {
      valA = a.score === "—" ? -1 : parseInt(a.score);
      valB = b.score === "—" ? -1 : parseInt(b.score);
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

  const handleDeleteCall = (id: string) => {
    if (confirm("Ushbu qo'ng'iroq tahlilini ro'yxatdan o'chirishni xohlaysizmi?")) {
      setCalls(calls.filter(c => c.id !== id));
      setActiveActionsMenu(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Title */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-text">Qo&apos;ng&apos;iroqlar</h1>
        <p className="text-xs text-text-muted mt-1">
          Barcha yozib olingan va AI tomonidan tahlil qilingan qo&apos;ng&apos;iroqlar ro&apos;yxati.
        </p>
        {loadError ? <p className="mt-2 text-xs text-amber-600">{loadError}</p> : null}
      </div>

      {/* Filter panel */}
      <div className="rounded-3xl border border-border bg-bg-card p-5 shadow-sm space-y-4">
        <h3 className="text-xs font-bold text-text uppercase tracking-wider">Filtrlar</h3>
        
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
          {/* Status Filter */}
          <div>
            <label className="text-[10px] font-bold text-text-muted uppercase block">Holati</label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="w-full rounded-xl border border-border bg-bg p-2.5 text-xs text-text focus:border-brand focus:outline-none mt-1"
            >
              <option value="Barchasi">Barchasi</option>
              <option value="Bog'langan">Bog&apos;langan</option>
              <option value="Xatolik">Xatolik</option>
              <option value="Javobsiz">Javobsiz</option>
              <option value="Kutilmoqda">Kutilmoqda</option>
              <option value="Tahlil qilinmoqda">Tahlil qilinmoqda</option>
            </select>
          </div>

          {/* Direction Filter */}
          <div>
            <label className="text-[10px] font-bold text-text-muted uppercase block">Yo&apos;nalishi</label>
            <select
              value={directionFilter}
              onChange={(e) => setDirectionFilter(e.target.value)}
              className="w-full rounded-xl border border-border bg-bg p-2.5 text-xs text-text focus:border-brand focus:outline-none mt-1"
            >
              <option value="Barchasi">Barchasi</option>
              <option value="Kiruvchi">Kiruvchi</option>
              <option value="Chiquvchi">Chiquvchi</option>
            </select>
          </div>

          {/* Service Filter */}
          <div>
            <label className="text-[10px] font-bold text-text-muted uppercase block">Xizmat turi</label>
            <select
              value={serviceFilter}
              onChange={(e) => setServiceFilter(e.target.value)}
              className="w-full rounded-xl border border-border bg-bg p-2.5 text-xs text-text focus:border-brand focus:outline-none mt-1"
            >
              <option value="Barchasi">Barchasi</option>
              <option value="Naming">Naming</option>
              <option value="Logotip">Logotip</option>
              <option value="Brendbuk">Brendbuk</option>
              <option value="Qadoq dizayni">Qadoq dizayni</option>
              <option value="Patentlash">Patentlash</option>
            </select>
          </div>

          {/* Manager Filter */}
          <div>
            <label className="text-[10px] font-bold text-text-muted uppercase block">Menejer</label>
            <select
              value={managerFilter}
              onChange={(e) => setManagerFilter(e.target.value)}
              className="w-full rounded-xl border border-border bg-bg p-2.5 text-xs text-text focus:border-brand focus:outline-none mt-1"
            >
              <option value="Barchasi">Barchasi</option>
              <option value="Baxtiyorjon Gaziyev">Baxtiyorjon Gaziyev</option>
            </select>
          </div>
        </div>
      </div>

      {/* Calls list container */}
      <div className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm overflow-hidden">
        {sortedCalls.length === 0 ? (
          <div className="py-12 text-center text-xs text-text-muted">
            Filtrga mos keladigan qo&apos;ng&apos;iroqlar topilmadi.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-border text-text-muted font-bold select-none">
                  <th className="py-3 px-3">
                    <button
                      type="button"
                      onClick={() => handleSort("date")}
                      className="flex items-center gap-1.5 w-full hover:text-brand focus:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1 rounded transition-colors"
                      aria-label="Sana bo'yicha tartiblash"
                    >
                      Sana
                      {sortKey === "date" && (
                        <svg aria-hidden="true" className={`h-3 w-3 transition-transform ${sortAsc ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M19 14l-7 7m0 0l-7-7m7 7V3" />
                        </svg>
                      )}
                    </button>
                  </th>
                  <th className="py-3 px-3">
                    <button
                      type="button"
                      onClick={() => handleSort("manager")}
                      className="flex items-center gap-1.5 w-full hover:text-brand focus:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1 rounded transition-colors"
                      aria-label="Menejer bo'yicha tartiblash"
                    >
                      Menejer
                      {sortKey === "manager" && (
                        <svg aria-hidden="true" className={`h-3 w-3 transition-transform ${sortAsc ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M19 14l-7 7m0 0l-7-7m7 7V3" />
                        </svg>
                      )}
                    </button>
                  </th>
                  <th className="py-3 px-3">
                    <button
                      type="button"
                      onClick={() => handleSort("direction")}
                      className="flex items-center gap-1.5 w-full hover:text-brand focus:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1 rounded transition-colors"
                      aria-label="Yo'nalish bo'yicha tartiblash"
                    >
                      Yo&apos;nalish
                      {sortKey === "direction" && (
                        <svg aria-hidden="true" className={`h-3 w-3 transition-transform ${sortAsc ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M19 14l-7 7m0 0l-7-7m7 7V3" />
                        </svg>
                      )}
                    </button>
                  </th>
                  <th className="py-3 px-3">
                    <button
                      type="button"
                      onClick={() => handleSort("duration")}
                      className="flex items-center gap-1.5 w-full hover:text-brand focus:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1 rounded transition-colors"
                      aria-label="Davomiylik bo'yicha tartiblash"
                    >
                      Davomiylik
                      {sortKey === "duration" && (
                        <svg aria-hidden="true" className={`h-3 w-3 transition-transform ${sortAsc ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M19 14l-7 7m0 0l-7-7m7 7V3" />
                        </svg>
                      )}
                    </button>
                  </th>
                  <th className="py-3 px-3">
                    <button
                      type="button"
                      onClick={() => handleSort("status")}
                      className="flex items-center gap-1.5 w-full hover:text-brand focus:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1 rounded transition-colors"
                      aria-label="Holat bo'yicha tartiblash"
                    >
                      Holat
                      {sortKey === "status" && (
                        <svg aria-hidden="true" className={`h-3 w-3 transition-transform ${sortAsc ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M19 14l-7 7m0 0l-7-7m7 7V3" />
                        </svg>
                      )}
                    </button>
                  </th>
                  <th className="py-3 px-3">
                    <button
                      type="button"
                      onClick={() => handleSort("score")}
                      className="flex items-center gap-1.5 w-full hover:text-brand focus:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1 rounded transition-colors"
                      aria-label="Suhbat sifati bo'yicha tartiblash"
                    >
                      Suhbat sifati
                      {sortKey === "score" && (
                        <svg aria-hidden="true" className={`h-3 w-3 transition-transform ${sortAsc ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M19 14l-7 7m0 0l-7-7m7 7V3" />
                        </svg>
                      )}
                    </button>
                  </th>
                  <th className="py-3 px-3">Kategoriya</th>
                  <th className="py-3 px-3 text-right">Amallar</th>
                </tr>
              </thead>
              <tbody>
                {sortedCalls.map((call) => (
                  <tr key={call.id} className="border-b border-border/50 hover:bg-bg/40 transition-colors">
                    <td className="py-3.5 px-3 font-medium text-text">{call.date}</td>
                    <td className="py-3.5 px-3 text-text">{call.manager}</td>
                    <td className="py-3.5 px-3">
                      <span className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold ${
                        call.direction === "Kiruvchi"
                          ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-400"
                          : "bg-blue-100 text-blue-800 dark:bg-blue-950/40 dark:text-blue-400"
                      }`}>
                        {call.direction}
                      </span>
                    </td>
                    <td className="py-3.5 px-3 text-text-muted font-mono">{call.duration}</td>
                    <td className="py-3.5 px-3">
                      <span className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold ${
                        call.status === "Bog'langan"
                          ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-400"
                          : call.status === "Xatolik"
                          ? "bg-rose-100 text-rose-800 dark:bg-rose-950/40 dark:text-rose-400"
                          : "bg-amber-100 text-amber-800 dark:bg-amber-950/40 dark:text-amber-400"
                      }`}>
                        {call.status}
                      </span>
                    </td>
                    <td className="py-3.5 px-3 font-bold text-brand">{call.score}</td>
                    <td className="py-3.5 px-3">
                      <div className="font-semibold text-text">{call.service}</div>
                      <div className="text-[10px] text-text-muted mt-0.5">{call.family}</div>
                    </td>
                    <td className="py-3.5 px-3 text-right relative">
                      <div className="flex items-center justify-end gap-1.5">
                        <Link
                          href={`/calls/${call.id}`}
                          className="rounded-xl bg-brand/10 hover:bg-brand text-brand hover:text-white px-3 py-1.5 text-xs font-semibold transition-colors"
                        >
                          👁 Tahlil
                        </Link>
                        
                        {/* 3 dots action menu */}
                        <div className="relative">
                          <button
                            onClick={() => setActiveActionsMenu(activeActionsMenu === call.id ? null : call.id)}
                            aria-label="Qo'shimcha amallar"
                            aria-expanded={activeActionsMenu === call.id}
                            aria-haspopup="true"
                            className="rounded-xl p-1.5 text-text-muted hover:bg-bg transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1"
                          >
                            <svg aria-hidden="true" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                              <path strokeLinecap="round" strokeLinejoin="round" d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z" />
                            </svg>
                          </button>
                          
                          {activeActionsMenu === call.id && (
                            <div className="absolute right-0 mt-1 w-28 rounded-xl border border-border bg-bg-popover p-1 shadow-lg z-10 animate-fade-in text-left">
                              <Link
                                href={`/calls/${call.id}`}
                                className="block rounded-lg px-3 py-1.5 text-xs text-text hover:bg-bg transition-colors"
                                onClick={() => setActiveActionsMenu(null)}
                              >
                                Ko&apos;rish
                              </Link>
                              <button
                                onClick={() => handleDeleteCall(call.id)}
                                className="w-full block rounded-lg px-3 py-1.5 text-xs text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-950/20 text-left transition-colors"
                              >
                                O&apos;chirish
                              </button>
                            </div>
                          )}
                        </div>
                      </div>
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
