"use client";

import React, { useState } from "react";
import { useTheme, Alert } from "@/context/ThemeContext";

export default function AlertsPage() {
  const { alerts, setAlerts } = useTheme();
  const [activeTab, setActiveTab] = useState<"all" | "new" | "read" | "dismissed">("all");
  const [typeFilter, setTypeFilter] = useState("Barchasi");

  const handleMarkAsRead = (id: string) => {
    setAlerts(
      alerts.map((al) => (al.id === id ? { ...al, status: "read" as const } : al))
    );
  };

  const handleDismiss = (id: string) => {
    setAlerts(
      alerts.map((al) => (al.id === id ? { ...al, status: "dismissed" as const } : al))
    );
  };

  const filteredAlerts = alerts.filter((al) => {
    // Tab filter
    if (activeTab === "new" && al.status !== "new") return false;
    if (activeTab === "read" && al.status !== "read") return false;
    if (activeTab === "dismissed" && al.status !== "dismissed") return false;

    // Type filter
    if (typeFilter !== "Barchasi" && al.typeLabel !== typeFilter) return false;
    
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Title */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-text">Ogohlantirishlar</h1>
        <p className="text-xs text-text-muted mt-1">
          Tizimdagi muhim bildirishnomalar, menejerlar faolligi va savdo mezonlari ogohlantirishlari ro&apos;yxati.
        </p>
      </div>

      {/* Tabs and filters header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-border pb-2">
        {/* Category Tabs */}
        <div className="flex gap-2 overflow-x-auto no-scrollbar">
          {[
            { id: "all", label: "Barchasi" },
            { id: "new", label: "Yangi" },
            { id: "read", label: "O'qilgan" },
            { id: "dismissed", label: "Bekor qilingan" }
          ].map((tab) => {
            const count = tab.id === "all" 
              ? alerts.length + 22 
              : tab.id === "new" 
              ? alerts.filter(a => a.status === "new").length + 22 
              : alerts.filter(a => a.status === tab.id).length;
            
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`rounded-xl px-4 py-2 text-xs font-bold transition-all whitespace-nowrap ${
                  activeTab === tab.id
                    ? "bg-brand text-white"
                    : "text-text-muted hover:bg-brand-light hover:text-brand"
                }`}
              >
                {tab.label} ({count})
              </button>
            );
          })}
        </div>

        {/* Dropdown type filter */}
        <div className="flex items-center gap-2">
          <label className="text-[10px] font-bold text-text-muted uppercase whitespace-nowrap">Ogohlantirish turi:</label>
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="rounded-xl border border-border bg-bg-card p-2 text-xs text-text focus:border-brand focus:outline-none"
          >
            <option value="Barchasi">Barchasi</option>
            <option value="Faoliyatsiz menejer">Faoliyatsiz menejer</option>
            <option value="Past samaradorlik">Past samaradorlik</option>
          </select>
        </div>
      </div>

      {/* Alerts list layout */}
      <div className="space-y-4">
        {filteredAlerts.length === 0 ? (
          <div className="rounded-3xl border border-border bg-bg-card p-12 text-center text-xs text-text-muted">
            Hech qanday ogohlantirishlar topilmadi.
          </div>
        ) : (
          filteredAlerts.map((al) => (
            <div
              key={al.id}
              className={`rounded-3xl border border-border bg-bg-card p-5 shadow-sm transition-all duration-300 flex flex-col md:flex-row justify-between gap-4 items-start ${
                al.status === "new" ? "ring-1 ring-brand/10 border-brand-light" : "opacity-80"
              }`}
            >
              {/* Left description */}
              <div className="flex gap-4 min-w-0">
                <div
                  className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl text-xs font-bold ${
                    al.type === "error"
                      ? "bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:text-rose-400"
                      : "bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-400"
                  }`}
                >
                  {al.managerAvatar}
                </div>
                <div className="space-y-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={`rounded px-1.5 py-0.5 text-[9px] font-bold ${
                      al.type === "error"
                        ? "bg-rose-100 text-rose-700 dark:bg-rose-950/40"
                        : "bg-amber-100 text-amber-700 dark:bg-amber-950/40"
                    }`}>
                      {al.typeLabel}
                    </span>
                    {al.status === "new" && (
                      <span className="rounded bg-brand-light text-brand px-1.5 py-0.5 text-[9px] font-bold uppercase">
                        Yangi
                      </span>
                    )}
                    <span className="text-[10px] text-text-muted">{al.time}</span>
                  </div>
                  <h3 className="text-xs font-bold text-text truncate">{al.title}</h3>
                  <p className="text-xs text-text-muted leading-relaxed">{al.description}</p>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex gap-2 self-end md:self-center shrink-0">
                {al.status === "new" && (
                  <button
                    onClick={() => handleMarkAsRead(al.id)}
                    className="rounded-xl border border-border bg-bg hover:bg-brand-light hover:text-brand px-3.5 py-2 text-xs font-semibold text-text-muted transition-colors focus:outline-none"
                  >
                    O&apos;qilgan deb belgilash
                  </button>
                )}
                
                {al.status !== "dismissed" && (
                  <button
                    onClick={() => handleDismiss(al.id)}
                    className="rounded-xl bg-rose-50 dark:bg-rose-950/20 text-rose-600 dark:text-rose-400 hover:bg-rose-100 px-3.5 py-2 text-xs font-semibold transition-colors focus:outline-none"
                  >
                    Bekor qilish
                  </button>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
