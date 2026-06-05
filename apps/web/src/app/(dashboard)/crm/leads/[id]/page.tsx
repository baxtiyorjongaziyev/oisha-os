"use client";

import React, { useState } from "react";
import { useParams, useRouter } from "next/navigation";

interface HistoryCall {
  time: string;
  type: "attempt" | "call";
  desc: string;
  manager: string;
  duration: string;
  status: "Javobsiz" | "Yakunlangan";
}

interface DateGroup {
  date: string;
  items: HistoryCall[];
}

export default function CRMLeadPage() {
  const params = useParams();
  const router = useRouter();
  const leadId = params.id as string;

  // Local state for inline player
  const [activePlayId, setActivePlayId] = useState<string | null>(null);

  const historyGroups: DateGroup[] = [
    {
      date: "2026-06-03",
      items: [
        { time: "14:22", type: "call", desc: "Mijoz bilan birinchi naming kelishuvi", manager: "Baxtiyorjon Gaziyev", duration: "2:40", status: "Yakunlangan" },
        { time: "10:15", type: "attempt", desc: "Qo'ng'iroq urinishi (Javob berilmadi)", manager: "Baxtiyorjon Gaziyev", duration: "0:00", status: "Javobsiz" }
      ]
    },
    {
      date: "2026-06-02",
      items: [
        { time: "11:05", type: "call", desc: "Brend yo'nalishi va logotip loyihasi boshlanishi", manager: "Baxtiyorjon Gaziyev", duration: "1:15", status: "Yakunlangan" }
      ]
    },
    {
      date: "2026-05-28",
      items: [
        { time: "10:15", type: "call", desc: "Brendbuk shartlari bo'yicha kiruvchi muzokara", manager: "Baxtiyorjon Gaziyev", duration: "5:12", status: "Yakunlangan" }
      ]
    }
  ];

  return (
    <div className="space-y-6">
      {/* Top navbar */}
      <div>
        <button
          onClick={() => router.back()}
          className="flex items-center gap-2 text-xs font-semibold text-text-muted hover:text-brand"
        >
          &larr; Orqaga
        </button>
      </div>

      {/* Title block */}
      <div className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <span className="text-[10px] font-bold text-text-muted uppercase tracking-wider">CRM Integratsiya</span>
          <h1 className="text-lg font-bold text-text mt-1">Zvonok na +998973355900 (Ne dozovilsya)</h1>
          <p className="text-xs text-text-muted mt-0.5">Sdelka ID: {leadId}</p>
        </div>

        <span className="rounded-full bg-emerald-100 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-400 px-3.5 py-1 text-xs font-bold uppercase tracking-wider">
          Faol
        </span>
      </div>

      {/* Details layout grids */}
      <div className="grid md:grid-cols-3 gap-6">
        {/* Left pane: values & managers */}
        <div className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm space-y-4 md:col-span-2">
          <h3 className="text-xs font-bold text-brand uppercase tracking-wider">Sdelka tafsilotlari</h3>
          
          <div className="grid sm:grid-cols-2 gap-4 text-xs">
            <div className="space-y-1">
              <span className="text-text-muted">Qiymati:</span>
              <div className="font-bold text-text">Hammasi bo&apos;lib: — UZS</div>
            </div>
            <div className="space-y-1">
              <span className="text-text-muted">Menejer:</span>
              <div className="font-bold text-text">Baxtiyorjon Gaziyev</div>
            </div>
            <div className="space-y-1">
              <span className="text-text-muted">Kontakt:</span>
              <div className="font-bold text-text">Hasanboy Gaziyev (Avtokontakt)</div>
            </div>
            <div className="space-y-1">
              <span className="text-text-muted">Telefon:</span>
              <div className="font-bold text-text">+998 97 335 59 00</div>
            </div>
          </div>

          <div className="pt-4 border-t border-border/50">
            <span className="text-[10px] font-bold text-text-muted uppercase block">Sotuv voronkasi bosqichi</span>
            <div className="flex items-center gap-2 mt-2">
              <span className="rounded bg-brand text-white px-3 py-1.5 text-xs font-semibold">Hunter (Setter)</span>
              <span className="text-text-muted">&rarr;</span>
              <span className="rounded bg-brand-light text-brand px-3 py-1.5 text-xs font-semibold">Yangi so&apos;rov</span>
            </div>
          </div>
        </div>

        {/* Right pane: signals & updates */}
        <div className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm space-y-4">
          <h3 className="text-xs font-bold text-brand uppercase tracking-wider">Operatsion signallar</h3>
          
          <div className="space-y-3 text-xs">
            <div className="flex justify-between border-b border-border/40 pb-1.5">
              <span className="text-text-muted">Qo&apos;ng&apos;iroq urinishlari:</span>
              <span className="font-bold text-text">15 ta</span>
            </div>
            <div className="flex justify-between border-b border-border/40 pb-1.5">
              <span className="text-text-muted">Tahlil qilingan:</span>
              <span className="font-bold text-text">6 ta</span>
            </div>
            <div className="flex justify-between border-b border-border/40 pb-1.5">
              <span className="text-text-muted">CRM izohlar:</span>
              <span className="font-bold text-text">0 ta</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">Bosqich o&apos;zgarishi:</span>
              <span className="font-bold text-text">1 marta</span>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom timeline history */}
      <div className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm space-y-6">
        <h3 className="text-xs font-bold text-brand uppercase tracking-wider">Qo&apos;ng&apos;iroqlar tarixi</h3>
        
        <div className="space-y-6 relative border-l border-border pl-6 ml-3">
          {historyGroups.map((group, groupIdx) => (
            <div key={groupIdx} className="space-y-3 relative">
              {/* Date node indicator */}
              <div className="absolute -left-[31px] top-0.5 bg-brand text-white text-[9px] font-bold rounded px-1.5 py-0.5 border border-white">
                {group.date}
              </div>

              <div className="space-y-3 pt-6">
                {group.items.map((item, itemIdx) => {
                  const playId = `${groupIdx}-${itemIdx}`;
                  return (
                    <div key={itemIdx} className="rounded-2xl border border-border bg-bg p-4 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs font-bold text-text-muted">{item.time}</span>
                          <span className={`rounded-full px-2 py-0.5 text-[9px] font-bold ${
                            item.status === "Yakunlangan"
                              ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40"
                              : "bg-rose-100 text-rose-800 dark:bg-rose-950/40"
                          }`}>
                            {item.status}
                          </span>
                        </div>
                        <h4 className="text-xs font-semibold text-text mt-1">{item.desc}</h4>
                        <div className="text-[10px] text-text-muted mt-0.5">Menejer: {item.manager}</div>
                      </div>

                      {/* Inline audio player for finished calls */}
                      {item.status === "Yakunlangan" && (
                        <div className="flex items-center gap-3 self-end sm:self-center bg-bg-card border border-border p-1.5 rounded-xl">
                          <button
                            onClick={() => setActivePlayId(activePlayId === playId ? null : playId)}
                            className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand text-white hover:bg-brand-hover text-[10px] transition-transform active:scale-95"
                          >
                            {activePlayId === playId ? "||" : "▶"}
                          </button>
                          
                          <div className="w-20 h-1 bg-bg rounded-full overflow-hidden">
                            <div
                              className="h-full bg-brand rounded-full transition-all"
                              style={{ width: activePlayId === playId ? "60%" : "0%" }}
                            ></div>
                          </div>
                          <span className="text-[9px] text-text-muted font-mono">{item.duration}</span>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
