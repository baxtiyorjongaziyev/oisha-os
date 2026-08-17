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
  
  const [sortKey, setSortKey] = useState<keyof CallData>("date");
  const [sortAsc, setSortAsc] = useState(false);
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
          date: String(call.analyzed_at ?? "Bugun"),
          manager: String(call.manager ?? "Baxtiyorjon Gaziyev"),
          direction: "Kiruvchi" as const,
          duration: String(call.duration ?? "03:42"),
          status: String(call.result ?? "Tahlil qilindi"),
          score: call.score === undefined ? "88%" : `${call.score}%`,
          family: String(call.category ?? "Brending & Naming"),
          service: String(call.client ?? "Apex Logistics")
        })));
        setLoadError(payload.real_data === false ? String(payload.message ?? "") : "");
      })
      .catch((error: Error) => setLoadError(`Demo rejim: ${error.message}`));
  }, []);

  const defaultCalls: CallData[] = [
    {
      id: "call-1",
      date: "Bugun, 14:20",
      manager: "Baxtiyorjon Gaziyev",
      direction: "Kiruvchi",
      duration: "04:18",
      status: "Bog'langan",
      score: "94%",
      family: "Brending & Identika",
      service: "Apex Logistics",
    },
    {
      id: "call-2",
      date: "Bugun, 11:05",
      manager: "Baxtiyorjon Gaziyev",
      direction: "Chiquvchi",
      duration: "02:45",
      status: "Bog'langan",
      score: "86%",
      family: "Naming & Patent",
      service: "Safir Klinika",
    },
    {
      id: "call-3",
      date: "Kecha, 17:30",
      manager: "Sardor",
      direction: "Kiruvchi",
      duration: "05:12",
      status: "Bog'langan",
      score: "91%",
      family: "Qadoq Dizayni",
      service: "Orzu Mebel",
    },
    {
      id: "call-4",
      date: "15-Avgust",
      manager: "Baxtiyorjon Gaziyev",
      direction: "Kiruvchi",
      duration: "03:55",
      status: "Bog'langan",
      score: "78%",
      family: "Rebrending",
      service: "Grand Tour",
    },
  ];

  const currentList = calls.length > 0 ? calls : defaultCalls;

  const filteredCalls = currentList.filter((call) => {
    if (statusFilter !== "Barchasi" && call.status !== statusFilter) return false;
    if (directionFilter !== "Barchasi" && call.direction !== directionFilter) return false;
    if (serviceFilter !== "Barchasi" && !call.service.includes(serviceFilter)) return false;
    if (managerFilter !== "Barchasi" && call.manager !== managerFilter) return false;
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
    <div className="space-y-7 pb-12">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold uppercase tracking-wider text-[#0b57d0] dark:text-[#a8c7fa] bg-[#d3e3fd] dark:bg-[#004a77] px-2.5 py-0.5 rounded-full">
              SALESCOACH AI • WHISPER ASR
            </span>
            <span className="text-xs text-[var(--md-sys-color-on-surface-variant)]">• Audio Tahlil & Skoring</span>
          </div>
          <h1 className="mt-1 text-2xl md:text-3xl font-bold tracking-tight text-[var(--md-sys-color-on-surface)]">
            Qo&apos;ng&apos;iroqlar Sifati & Tahlili
          </h1>
          <p className="mt-0.5 text-xs text-[var(--md-sys-color-on-surface-variant)]">
            Sun&apos;iy intellekt orqali transkripsiya, e&apos;tirozlarni yopish va A1-E3 mezonlari bo&apos;yicha baholash.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button className="rounded-full bg-[#0b57d0] dark:bg-[#a8c7fa] dark:text-[#041e49] text-white px-5 py-2.5 text-xs font-bold shadow-sm hover:opacity-90 transition-all active:scale-[0.98]">
            🎙 Yangi Audio Yuklash
          </button>
        </div>
      </div>

      {/* Filter Panel (Google Pill Selects) */}
      <div className="rounded-3xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface)] p-5 shadow-sm space-y-4">
        <h3 className="text-xs font-bold text-[var(--md-sys-color-on-surface)] uppercase tracking-wider">Filtrlar</h3>
        
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <label className="text-[10px] font-bold text-[var(--md-sys-color-on-surface-variant)] uppercase block">Holati</label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="w-full rounded-2xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface-container)] p-2.5 text-xs text-[var(--md-sys-color-on-surface)] focus:outline-none focus:border-[#0b57d0] mt-1"
            >
              <option value="Barchasi">Barchasi</option>
              <option value="Bog'langan">Bog&apos;langan</option>
              <option value="Javobsiz">Javobsiz</option>
              <option value="Xatolik">Xatolik</option>
            </select>
          </div>

          <div>
            <label className="text-[10px] font-bold text-[var(--md-sys-color-on-surface-variant)] uppercase block">Yo&apos;nalishi</label>
            <select
              value={directionFilter}
              onChange={(e) => setDirectionFilter(e.target.value)}
              className="w-full rounded-2xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface-container)] p-2.5 text-xs text-[var(--md-sys-color-on-surface)] focus:outline-none focus:border-[#0b57d0] mt-1"
            >
              <option value="Barchasi">Barchasi</option>
              <option value="Kiruvchi">Kiruvchi</option>
              <option value="Chiquvchi">Chiquvchi</option>
            </select>
          </div>

          <div>
            <label className="text-[10px] font-bold text-[var(--md-sys-color-on-surface-variant)] uppercase block">Xizmat turi</label>
            <select
              value={serviceFilter}
              onChange={(e) => setServiceFilter(e.target.value)}
              className="w-full rounded-2xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface-container)] p-2.5 text-xs text-[var(--md-sys-color-on-surface)] focus:outline-none focus:border-[#0b57d0] mt-1"
            >
              <option value="Barchasi">Barchasi</option>
              <option value="Apex">Apex Logistics</option>
              <option value="Safir">Safir Klinika</option>
              <option value="Orzu">Orzu Mebel</option>
              <option value="Grand">Grand Tour</option>
            </select>
          </div>

          <div>
            <label className="text-[10px] font-bold text-[var(--md-sys-color-on-surface-variant)] uppercase block">Menejer</label>
            <select
              value={managerFilter}
              onChange={(e) => setManagerFilter(e.target.value)}
              className="w-full rounded-2xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface-container)] p-2.5 text-xs text-[var(--md-sys-color-on-surface)] focus:outline-none focus:border-[#0b57d0] mt-1"
            >
              <option value="Barchasi">Barchasi</option>
              <option value="Baxtiyorjon Gaziyev">Baxtiyorjon Gaziyev</option>
              <option value="Sardor">Sardor</option>
            </select>
          </div>
        </div>
      </div>

      {/* Calls Table Container */}
      <div className="rounded-3xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface)] shadow-sm overflow-hidden">
        <div className="border-b border-[var(--md-sys-color-outline)] px-6 py-4 flex items-center justify-between">
          <h2 className="font-bold text-base text-[var(--md-sys-color-on-surface)]">
            Tahlil Qilingan Suhbatlar Jurnali
          </h2>
          <span className="text-xs text-[var(--md-sys-color-on-surface-variant)] font-mono">
            {sortedCalls.length} ta suhbat
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead className="bg-[var(--md-sys-color-surface-container-low)] text-[10px] uppercase text-[var(--md-sys-color-on-surface-variant)] font-bold tracking-wider border-b border-[var(--md-sys-color-outline)]">
              <tr>
                <th className="py-3.5 px-4 cursor-pointer hover:text-[#0b57d0]" onClick={() => handleSort("date")}>Sana</th>
                <th className="py-3.5 px-4 cursor-pointer hover:text-[#0b57d0]" onClick={() => handleSort("manager")}>Menejer</th>
                <th className="py-3.5 px-4">Yo&apos;nalish</th>
                <th className="py-3.5 px-4">Davomiylik</th>
                <th className="py-3.5 px-4">Holat</th>
                <th className="py-3.5 px-4 cursor-pointer hover:text-[#0b57d0]" onClick={() => handleSort("score")}>Suhbat Sifati</th>
                <th className="py-3.5 px-4">Mijoz & Kategoriya</th>
                <th className="py-3.5 px-4 text-right">Amallar</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--md-sys-color-outline-variant)]">
              {sortedCalls.map((call) => (
                <tr key={call.id} className="hover:bg-[var(--md-sys-color-surface-container-low)] transition-colors">
                  <td className="py-4 px-4 font-semibold text-[var(--md-sys-color-on-surface)]">{call.date}</td>
                  <td className="py-4 px-4 font-medium text-[var(--md-sys-color-on-surface)]">{call.manager}</td>
                  <td className="py-4 px-4">
                    <span className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold ${
                      call.direction === "Kiruvchi"
                        ? "bg-[#c4eed0] text-[#0f5223] dark:bg-[#0f5223] dark:text-[#6dd58c]"
                        : "bg-[#d3e3fd] text-[#041e49] dark:bg-[#004a77] dark:text-[#c2e7ff]"
                    }`}>
                      {call.direction}
                    </span>
                  </td>
                  <td className="py-4 px-4 text-[var(--md-sys-color-on-surface-variant)] font-mono">{call.duration}</td>
                  <td className="py-4 px-4">
                    <span className="rounded-full bg-[#c4eed0] text-[#0f5223] dark:bg-[#0f5223] dark:text-[#6dd58c] px-2.5 py-0.5 text-[10px] font-bold">
                      {call.status}
                    </span>
                  </td>
                  <td className="py-4 px-4 font-black text-sm text-[#0b57d0] dark:text-[#a8c7fa]">{call.score}</td>
                  <td className="py-4 px-4">
                    <div className="font-bold text-[var(--md-sys-color-on-surface)]">{call.service}</div>
                    <div className="text-[10px] text-[var(--md-sys-color-on-surface-variant)] mt-0.5">{call.family}</div>
                  </td>
                  <td className="py-4 px-4 text-right">
                    <Link
                      href={`/calls/${call.id}`}
                      className="rounded-full bg-[var(--md-sys-color-surface-container)] border border-[var(--md-sys-color-outline)] px-3.5 py-1.5 text-xs font-semibold text-[#0b57d0] dark:text-[#a8c7fa] hover:bg-[var(--md-sys-color-surface-container-high)] transition-colors"
                    >
                      👁 Tahlil
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
