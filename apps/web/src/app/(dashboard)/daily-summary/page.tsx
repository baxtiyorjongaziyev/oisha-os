"use client";

import React, { useState } from "react";

interface DayData {
  dayName: string;
  dateStr: string;
  hasAnalysis: boolean;
  isCurrent: boolean;
}

export default function DailySummaryPage() {
  const [selectedDate, setSelectedDate] = useState("2026-06-03");
  const [managerExpanded, setManagerExpanded] = useState(true);

  const days: DayData[] = [
    { dayName: "Du", dateStr: "2026-06-01", hasAnalysis: true, isCurrent: false },
    { dayName: "Se", dateStr: "2026-06-02", hasAnalysis: true, isCurrent: false },
    { dayName: "Ch", dateStr: "2026-06-03", hasAnalysis: true, isCurrent: true },
    { dayName: "Pa", dateStr: "2026-06-04", hasAnalysis: false, isCurrent: false },
    { dayName: "Ju", dateStr: "2026-06-05", hasAnalysis: false, isCurrent: false },
    { dayName: "Sh", dateStr: "2026-06-06", hasAnalysis: false, isCurrent: false },
    { dayName: "Ya", dateStr: "2026-06-07", hasAnalysis: false, isCurrent: false }
  ];

  return (
    <div className="space-y-6">
      {/* Title */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-text">Kunlik hisobot</h1>
        <p className="text-xs text-text-muted mt-1">
          Har bir savdo kuni bo&apos;yicha sun&apos;iy intellekt tomonidan tayyorlangan qisqacha kunlik hisobotlar.
        </p>
      </div>

      {/* Weekly calendar selector header */}
      <div className="rounded-3xl border border-border bg-bg-card p-4 shadow-sm flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <button className="rounded-xl border border-border bg-bg p-2 text-text-muted hover:text-brand" aria-label="Oldingi hafta">
            &larr;
          </button>
          <span className="text-xs font-bold text-text">Iyun 2026</span>
          <button className="rounded-xl border border-border bg-bg p-2 text-text-muted hover:text-brand" aria-label="Keyingi hafta">
            &rarr;
          </button>
        </div>

        {/* Days grid */}
        <div className="flex gap-2">
          {days.map((day) => (
            <button
              key={day.dateStr}
              onClick={() => setSelectedDate(day.dateStr)}
              className={`flex flex-col items-center rounded-2xl p-2.5 w-12 border transition-all ${
                selectedDate === day.dateStr
                  ? "bg-brand border-brand text-white shadow-md shadow-brand/15"
                  : "border-border bg-bg hover:border-brand/40"
              }`}
            >
              <span className={`text-[10px] uppercase font-bold ${selectedDate === day.dateStr ? "text-white" : "text-text-muted"}`}>
                {day.dayName}
              </span>
              <span className="text-xs font-bold mt-1">{day.dateStr.split("-")[2]}</span>
              
              {/* Day analysis badges */}
              <span className={`h-1.5 w-1.5 rounded-full mt-1.5 ${
                day.hasAnalysis 
                  ? (selectedDate === day.dateStr ? "bg-white" : "bg-emerald-500") 
                  : "bg-amber-400"
              }`}></span>
            </button>
          ))}
        </div>

        <button
          onClick={() => setSelectedDate("2026-06-03")}
          className="rounded-xl bg-brand-light text-brand px-3.5 py-2 text-xs font-semibold hover:bg-brand hover:text-white transition-colors"
        >
          BUGUN
        </button>
      </div>

      {/* Selected day summary details */}
      <div className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm space-y-6">
        {/* Day label */}
        <div className="border-b border-border pb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-base font-bold text-text">
            Jon Branding agency: {selectedDate} kunlik hisoboti
          </h2>
          <span className="rounded bg-brand-light px-2.5 py-0.5 text-[10px] font-bold text-brand uppercase">
            Tahlil yakunlangan
          </span>
        </div>

        {/* Section: CRM & Call statistics */}
        <div className="grid md:grid-cols-2 gap-6 pb-6 border-b border-border/50">
          <div className="space-y-4">
            <h3 className="text-xs font-bold text-brand uppercase tracking-wider">1. CRM faolligi va qo&apos;ng&apos;iroqlar</h3>
            
            <div className="space-y-2 text-xs text-text-muted">
              <div className="flex justify-between"><span>Jami qo&apos;ng&apos;iroqlar:</span> <span className="font-bold text-text">12 ta</span></div>
              <div className="flex justify-between"><span>Mijoz bilan bog&apos;langan:</span> <span className="font-bold text-text">8 ta</span></div>
              <div className="flex justify-between"><span>Javobsiz/bog&apos;lanilmagan:</span> <span className="font-bold text-text">4 ta</span></div>
              <div className="flex justify-between"><span>Bog&apos;lanish darajasi (Connect rate):</span> <span className="font-bold text-text">66.7%</span></div>
              <div className="flex justify-between"><span>Umumiy suhbat davomiyligi:</span> <span className="font-bold text-text">24 daq 15 soniya</span></div>
            </div>
          </div>

          {/* Activity compare chart (SVG side-by-side bars) */}
          <div className="rounded-2xl bg-bg p-4 border border-border space-y-2">
            <h4 className="text-[10px] font-bold text-text-muted uppercase">Qo&apos;ng&apos;iroqlar taqqoslami (Kecha vs Bugun)</h4>
            <div className="h-28 w-full flex items-end justify-around pb-2">
              {/* Bar 1 (Calls) */}
              <div className="flex flex-col items-center gap-1.5">
                <div className="flex gap-1 items-end h-16">
                  <div className="w-4 bg-brand-hover/40 rounded-t h-12" title="Kecha: 10"></div>
                  <div className="w-4 bg-brand rounded-t h-16" title="Bugun: 12"></div>
                </div>
                <span className="text-[9px] text-text-muted">Qo&apos;ng&apos;iroqlar</span>
              </div>

              {/* Bar 2 (Connects) */}
              <div className="flex flex-col items-center gap-1.5">
                <div className="flex gap-1 items-end h-16">
                  <div className="w-4 bg-emerald-500/40 rounded-t h-8" title="Kecha: 6"></div>
                  <div className="w-4 bg-emerald-500 rounded-t h-12" title="Bugun: 8"></div>
                </div>
                <span className="text-[9px] text-text-muted">Bog&apos;langan</span>
              </div>
            </div>
          </div>
        </div>

        {/* Section: Sifat, Lidlar harakati, AI summary */}
        <div className="grid md:grid-cols-3 gap-6 pt-2">
          {/* Sifat */}
          <div className="space-y-3">
            <h3 className="text-xs font-bold text-brand uppercase tracking-wider">Qo&apos;ng&apos;iroqlar sifati</h3>
            <div className="space-y-2 text-xs text-text-muted">
              <div className="flex justify-between"><span>Scored (Tahlil qilingan):</span> <span className="font-bold text-text">3 ta</span></div>
              <div className="flex justify-between"><span>Mezon bajarilishi (Avg score):</span> <span className="font-bold text-text">68.5%</span></div>
              <div className="flex justify-between"><span>Zaif mezon holati:</span> <span className="font-bold text-rose-500">2 ta mezon</span></div>
            </div>
          </div>

          {/* Lidlar */}
          <div className="space-y-3">
            <h3 className="text-xs font-bold text-brand uppercase tracking-wider">Lidlar harakati</h3>
            <div className="space-y-2 text-xs text-text-muted">
              <div className="flex justify-between"><span>Yangi lidlar:</span> <span className="font-bold text-text">2 ta</span></div>
              <div className="flex justify-between"><span>Yutilganlar (Won):</span> <span className="font-bold text-text">0 ta</span></div>
              <div className="flex justify-between"><span>Yo&apos;qotilganlar (Lost):</span> <span className="font-bold text-text">1 ta</span></div>
            </div>
          </div>

          {/* AI Advice for tomorrow */}
          <div className="space-y-3">
            <h3 className="text-xs font-bold text-brand uppercase tracking-wider">Ertangi kun uchun tavsiyalar</h3>
            <div className="rounded-2xl bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900/40 p-3.5">
              <p className="text-[10px] text-amber-800 dark:text-amber-400 leading-relaxed font-semibold">
                Menejer Baxtiyorjon Gaziyev kirish qismida salomlashish ko&apos;rsatkichini oshirishi va har bir yangi lidda keyingi qadamni belgilashda ko&apos;proq faollik ko&apos;rsatishi lozim. Ertaga rejalashtirilgan 5 ta brif uchrashuvi bor.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Section: Accordion for individual managers */}
      <div className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm space-y-4">
        <h3 className="text-sm font-bold text-text">Menejerlar faoliyati tahlili</h3>

        <div className="rounded-2xl border border-border bg-bg overflow-hidden">
          {/* Accordion Trigger */}
          <button
            onClick={() => setManagerExpanded(!managerExpanded)}
            className="w-full flex items-center justify-between px-5 py-4 text-xs font-bold text-text hover:bg-brand-light/35 transition-colors focus:outline-none"
          >
            <div className="flex items-center gap-2">
              <span className="flex h-6 w-6 items-center justify-center rounded bg-brand text-white text-[10px] font-bold">
                BG
              </span>
              <span>Baxtiyorjon Gaziyev (Sotuvchi)</span>
            </div>
            <span>{managerExpanded ? "Yopish ▴" : "Ochiq ▾"}</span>
          </button>

          {/* Accordion Content */}
          {managerExpanded && (
            <div className="px-5 pb-5 pt-2 border-t border-border/40 text-xs space-y-4 animate-fade-in bg-bg-card">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-center">
                <div className="rounded-xl border border-border p-2">
                  <div className="text-[9px] text-text-muted font-bold uppercase">Qo&apos;ng&apos;iroqlar</div>
                  <div className="text-sm font-bold text-text mt-1">12 ta</div>
                </div>
                <div className="rounded-xl border border-border p-2">
                  <div className="text-[9px] text-text-muted font-bold uppercase">Ulangan</div>
                  <div className="text-sm font-bold text-text mt-1">8 ta</div>
                </div>
                <div className="rounded-xl border border-border p-2">
                  <div className="text-[9px] text-text-muted font-bold uppercase">Average Score</div>
                  <div className="text-sm font-bold text-text mt-1">68%</div>
                </div>
                <div className="rounded-xl border border-border p-2">
                  <div className="text-[9px] text-text-muted font-bold uppercase">Vazifalar ijrosi</div>
                  <div className="text-sm font-bold text-text mt-1">100%</div>
                </div>
              </div>

              <div>
                <h4 className="text-[10px] font-bold text-text-muted uppercase">Menejer bo&apos;yicha AI xulosasi:</h4>
                <p className="text-xs text-text-muted leading-relaxed mt-1">
                  Baxtiyorjon Gaziyevning bugungi faoliyati barqaror. Naming loyihalari bo&apos;yicha brifing jarayonini to&apos;g&apos;ri boshqarmoqda, biroq moliyaviy masalalarni muhokama qilishda (E3) mijoz bilan uzoq muddatli shartnoma bo&apos;yicha qayta aloqani aniqlashtirmadi.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
