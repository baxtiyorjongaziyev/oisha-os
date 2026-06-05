"use client";

import React, { useState } from "react";
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

const mockCalls: CallData[] = [
  { id: "1", date: "2026-06-03 14:22", manager: "Baxtiyorjon Gaziyev", direction: "Kiruvchi", duration: "2:40", status: "Bog'langan", score: "78%", family: "Lidni aniqlash", service: "Naming (Nomlash)" },
  { id: "2", date: "2026-06-02 11:05", manager: "Baxtiyorjon Gaziyev", direction: "Chiquvchi", duration: "1:15", status: "Bog'langan", score: "45%", family: "Mijoz bilan koordinatsiya", service: "Logotip ishlab chiqish" },
  { id: "3", date: "2026-06-01 17:50", manager: "Baxtiyorjon Gaziyev", direction: "Chiquvchi", duration: "0:30", status: "Xatolik", score: "—", family: "Moliya/admin", service: "Patentlash" },
  { id: "4", date: "2026-05-28 10:15", manager: "Baxtiyorjon Gaziyev", direction: "Kiruvchi", duration: "5:12", status: "Bog'langan", score: "89%", family: "Yopish/muzokara", service: "Brendbuk" },
  { id: "5", date: "2026-05-25 16:30", manager: "Baxtiyorjon Gaziyev", direction: "Chiquvchi", duration: "1:45", status: "Bog'langan", score: "62%", family: "Yechim taqdimoti", service: "Qadoq dizayni" },
  { id: "6", date: "2026-05-24 14:02", manager: "Baxtiyorjon Gaziyev", direction: "Kiruvchi", duration: "0:12", status: "Javobsiz", score: "—", family: "Biznesga oid emas", service: "Noma'lum" },
  { id: "7", date: "2026-05-22 09:15", manager: "Baxtiyorjon Gaziyev", direction: "Chiquvchi", duration: "3:22", status: "Bog'langan", score: "71%", family: "Lidni aniqlash", service: "Logotip ishlab chiqish" }
];

export default function CallsPage() {
  const [calls, setCalls] = useState<CallData[]>(mockCalls);
  const [statusFilter, setStatusFilter] = useState<string>("Barchasi");
  const [directionFilter, setDirectionFilter] = useState<string>("Barchasi");
  const [serviceFilter, setServiceFilter] = useState<string>("Barchasi");
  const [managerFilter, setManagerFilter] = useState<string>("Barchasi");
  
  // Sorting state
  const [sortKey, setSortKey] = useState<keyof CallData>("date");
  const [sortAsc, setSortAsc] = useState(false);

  // Active dropdown index for actions menu
  const [activeActionsMenu, setActiveActionsMenu] = useState<string | null>(null);

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
                  <th onClick={() => handleSort("date")} className="py-3 px-3 cursor-pointer hover:text-brand">
                    Sana {sortKey === "date" && (sortAsc ? "▲" : "▼")}
                  </th>
                  <th onClick={() => handleSort("manager")} className="py-3 px-3 cursor-pointer hover:text-brand">
                    Menejer {sortKey === "manager" && (sortAsc ? "▲" : "▼")}
                  </th>
                  <th onClick={() => handleSort("direction")} className="py-3 px-3 cursor-pointer hover:text-brand">
                    Yo&apos;nalish {sortKey === "direction" && (sortAsc ? "▲" : "▼")}
                  </th>
                  <th onClick={() => handleSort("duration")} className="py-3 px-3 cursor-pointer hover:text-brand">
                    Davomiylik {sortKey === "duration" && (sortAsc ? "▲" : "▼")}
                  </th>
                  <th onClick={() => handleSort("status")} className="py-3 px-3 cursor-pointer hover:text-brand">
                    Holat {sortKey === "status" && (sortAsc ? "▲" : "▼")}
                  </th>
                  <th onClick={() => handleSort("score")} className="py-3 px-3 cursor-pointer hover:text-brand">
                    Suhbat sifati {sortKey === "score" && (sortAsc ? "▲" : "▼")}
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
                            className="rounded-xl p-1.5 text-text-muted hover:bg-bg transition-colors focus:outline-none"
                          >
                            ⋯
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
