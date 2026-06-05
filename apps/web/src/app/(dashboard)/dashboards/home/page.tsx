"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useTheme } from "@/context/ThemeContext";

interface Widget {
  id: string;
  name: string;
  enabled: boolean;
}

export default function HomePage() {
  const { currentBusiness } = useTheme();
  
  // Time filters: "today" | "week" | "month"
  const [timeFilter, setTimeFilter] = useState<"today" | "week" | "month">("today");
  
  // Dynamic business pulse category tabs
  const [pulseFocus, setPulseFocus] = useState<"sales" | "quality" | "tasks">("sales");

  // Widget customizer state
  const [customizerOpen, setCustomizerOpen] = useState(false);
  const [widgets, setWidgets] = useState<Widget[]>([
    { id: "pulse", name: "Biznes pulsi (AI)", enabled: true },
    { id: "quality", name: "Sifat ko'rinishi (grafik)", enabled: true },
    { id: "trends", name: "Sifat trendi (Playbook)", enabled: true },
    { id: "alerts", name: "Ogohlantirishlar", enabled: true },
    { id: "latest_calls", name: "So'nggi tahlillar", enabled: true },
    { id: "crm_activity", name: "CRM faolligi va natijalar", enabled: false },
    { id: "route_kpi", name: "Route-first KPI lar", enabled: false },
    { id: "route_exceptions", name: "Natijalar va route istisnolari", enabled: false },
    { id: "manager_rating", name: "Menejerlar reytingi", enabled: false },
    { id: "lost_reasons", name: "Nima uchun mijozlarni yo'qotyapmiz", enabled: false },
    { id: "funnel_response", name: "Voronka va javob tezligi", enabled: false },
    { id: "activity_volume", name: "Faoliyat (qo'ng'iroq + vazifalar)", enabled: false }
  ]);

  // Move widgets up / down
  const moveWidget = (index: number, direction: "up" | "down") => {
    const newIndex = direction === "up" ? index - 1 : index + 1;
    if (newIndex < 0 || newIndex >= widgets.length) return;
    
    const updated = [...widgets];
    const temp = updated[index];
    updated[index] = updated[newIndex];
    updated[newIndex] = temp;
    setWidgets(updated);
  };

  const toggleWidget = (id: string) => {
    setWidgets(
      widgets.map((w) => (w.id === id ? { ...w, enabled: !w.enabled } : w))
    );
  };

  // Mock data depending on timeFilter
  const data = {
    today: {
      sales: 0,
      deals: 0,
      avgQuality: "—",
      conversion: "0.00%",
      callsScored: 0,
      leadsQuality: "—",
      unreached: 0,
      avgDuration: "—",
      tasks: 0,
      pulseText: "Bugun faoliyat to'xtagan ko'rinadi. Obunangiz muzlatilganligi sababli yangi qo'ng'iroqlar tahlilga kirishi kechikmoqda yoki menejer faolligi aniqlanmadi.",
      pulseStatus: "Muzlatilgan",
      pulseColor: "bg-rose-500",
      svgPoints: "0,150 120,150 240,150 360,150 480,150 600,150",
      calls: []
    },
    week: {
      sales: "12,400,000 UZS",
      deals: "15,000,000 UZS",
      avgQuality: "68%",
      conversion: "4.20%",
      callsScored: 45,
      leadsQuality: "Yaxshi (65%)",
      unreached: 8,
      avgDuration: "2:14",
      tasks: 12,
      pulseText: "Haftalik natijalar o'rtacha. Salomlashish va ehtiyoj aniqlash yaxshi, biroq 'Yopish va kelishuvlar' bosqichida zaifliklar mavjud.",
      pulseStatus: "Barqaror",
      pulseColor: "bg-emerald-500",
      svgPoints: "0,140 120,90 240,110 360,60 480,85 600,30",
      calls: [
        { id: "1", date: "Bugun 14:22", manager: "Baxtiyorjon G.", duration: "2:40", direction: "Kiruvchi", category: "Naming", score: "78%", status: "Bog'langan" },
        { id: "2", date: "Kecha 11:05", manager: "Baxtiyorjon G.", duration: "1:15", direction: "Chiquvchi", category: "Logotip", score: "45%", status: "Bog'langan" },
        { id: "3", date: "01.06 17:50", manager: "Baxtiyorjon G.", duration: "0:30", direction: "Chiquvchi", category: "Patentlash", score: "—", status: "Xatolik" }
      ]
    },
    month: {
      sales: "58,600,000 UZS",
      deals: "72,000,000 UZS",
      avgQuality: "72%",
      conversion: "6.80%",
      callsScored: 257,
      leadsQuality: "Yaxshi (74%)",
      unreached: 32,
      avgDuration: "1:47",
      tasks: 84,
      pulseText: "Oylik umumiy ko'rsatkichlar ijobiy. 257 ta qo'ng'iroq tahlil qilindi. Top menejeringiz samaradorligi 75% KPI darajasiga yaqinlashmoqda.",
      pulseStatus: "Faol",
      pulseColor: "bg-blue-500",
      svgPoints: "0,130 100,110 200,80 300,95 400,50 500,40 600,20",
      calls: [
        { id: "1", date: "Bugun 14:22", manager: "Baxtiyorjon G.", duration: "2:40", direction: "Kiruvchi", category: "Naming", score: "78%", status: "Bog'langan" },
        { id: "2", date: "Kecha 11:05", manager: "Baxtiyorjon G.", duration: "1:15", direction: "Chiquvchi", category: "Logotip", score: "45%", status: "Bog'langan" },
        { id: "3", date: "01.06 17:50", manager: "Baxtiyorjon G.", duration: "0:30", direction: "Chiquvchi", category: "Patentlash", score: "—", status: "Xatolik" },
        { id: "4", date: "28.05 10:15", manager: "Baxtiyorjon G.", duration: "5:12", direction: "Kiruvchi", category: "Brendbuk", score: "89%", status: "Bog'langan" },
        { id: "5", date: "25.05 16:30", manager: "Baxtiyorjon G.", duration: "1:45", direction: "Chiquvchi", category: "Qadoq dizayni", score: "62%", status: "Bog'langan" }
      ]
    }
  };

  const activeData = data[timeFilter];

  return (
    <div className="space-y-6">
      {/* Top action bar: Subscription Alert and Page Title */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text">Bosh sahifa</h1>
          <p className="text-xs text-text-muted mt-1">
            Biznesingizning savdo tahlillari va sotuv ko&apos;rsatkichlari.
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Time Filters */}
          <div className="flex rounded-2xl bg-bg-card p-1 border border-border">
            {(["today", "week", "month"] as const).map((filter) => (
              <button
                key={filter}
                onClick={() => setTimeFilter(filter)}
                className={`rounded-xl px-4 py-2 text-xs font-semibold uppercase tracking-wider transition-all ${
                  timeFilter === filter
                    ? "bg-brand text-white shadow-md shadow-brand/10"
                    : "text-text-muted hover:text-brand"
                }`}
              >
                {filter === "today" ? "Bugun" : filter === "week" ? "Hafta" : "Oy"}
              </button>
            ))}
          </div>

          {/* Section Customize Button */}
          <button
            onClick={() => setCustomizerOpen(true)}
            className="flex items-center gap-2 rounded-2xl border border-border bg-bg-card px-4 py-2.5 text-xs font-semibold text-text-muted hover:border-brand hover:text-brand transition-colors focus:outline-none"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
            </svg>
            Bo&apos;limlarni sozlash
          </button>
        </div>
      </div>

      {/* Subscription Warnings block */}
      <div className="rounded-3xl border border-rose-200 dark:border-rose-950/40 bg-rose-50/50 dark:bg-rose-950/10 p-5 flex flex-col md:flex-row gap-4 items-start md:items-center justify-between">
        <div className="flex gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-rose-100 dark:bg-rose-900/30 text-rose-600 dark:text-rose-400 font-bold text-lg">
            !
          </span>
          <div>
            <h4 className="text-sm font-bold text-rose-800 dark:text-rose-400">Obuna holati: Muzlatilgan</h4>
            <p className="text-xs text-rose-700/80 dark:text-rose-400/70 mt-0.5">
              To&apos;lov amalga oshirilmaganligi sababli qo&apos;ng&apos;iroqlar tahlili vaqtinchalik to&apos;xtatilgan. Oylik narx: 640,000 UZS.
            </p>
          </div>
        </div>
        <Link
          href="/settings?tab=subscription"
          className="rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold px-4 py-2 transition-colors inline-block whitespace-nowrap shadow-lg shadow-rose-600/15"
        >
          To&apos;lov sahifasiga o&apos;tish
        </Link>
      </div>

      {/* Render Dynamic Widgets */}
      <div className="space-y-6">
        {widgets
          .filter((w) => w.enabled)
          .map((widget) => {
            switch (widget.id) {
              case "pulse":
                return (
                  <div key={widget.id} className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className={`h-2.5 w-2.5 rounded-full ${activeData.pulseColor} animate-pulse`}></span>
                        <h3 className="text-base font-bold text-text">Biznes Pulsi (AI Xulosa)</h3>
                      </div>
                      <span className="rounded-full bg-brand-light px-2.5 py-0.5 text-[10px] font-bold text-brand uppercase tracking-wider">
                        {timeFilter === "today" ? "Bugun" : timeFilter === "week" ? "Shu hafta" : "Shu oy"}
                      </span>
                    </div>

                    <p className="mt-4 text-xs text-text-muted leading-relaxed">
                      {activeData.pulseText}
                    </p>

                    {/* Selector Buttons */}
                    <div className="flex flex-wrap gap-2 mt-4 border-b border-border pb-4">
                      <button
                        onClick={() => setPulseFocus("sales")}
                        className={`rounded-xl px-4 py-2 text-xs font-semibold transition-all ${
                          pulseFocus === "sales" ? "bg-brand text-white" : "bg-bg text-text hover:bg-brand-light"
                        }`}
                      >
                        Sotuvlar: {activeData.sales}
                      </button>
                      <button
                        onClick={() => setPulseFocus("quality")}
                        className={`rounded-xl px-4 py-2 text-xs font-semibold transition-all ${
                          pulseFocus === "quality" ? "bg-brand text-white" : "bg-bg text-text hover:bg-brand-light"
                        }`}
                      >
                        Suhbat sifati: {activeData.avgQuality}
                      </button>
                      <button
                        onClick={() => setPulseFocus("tasks")}
                        className={`rounded-xl px-4 py-2 text-xs font-semibold transition-all ${
                          pulseFocus === "tasks" ? "bg-brand text-white" : "bg-bg text-text hover:bg-brand-light"
                        }`}
                      >
                        Bajarilishi: {activeData.deals ? "Muammo bor" : "—"}
                      </button>
                    </div>

                    {/* Explanatory Content for Focus Selection */}
                    <div className="mt-4">
                      {pulseFocus === "sales" && (
                        <div className="space-y-1">
                          <h4 className="text-xs font-bold text-text">Sotuv faoliyati bo&apos;yicha tavsiya:</h4>
                          <p className="text-[11px] text-text-muted">
                            {timeFilter === "today"
                              ? "Bugun hech qanday bitim yoki sotuv qayd etilmagan. Menejerlarning faolligini CRM orqali tekshiring."
                              : `Ushbu davrda jami sotuvlar summasi ${activeData.sales} ni tashkil etdi. Obuna qayta faollashgach, tushum konversiyalarini batafsil diagrammalarda ko'rishingiz mumkin.`}
                          </p>
                        </div>
                      )}
                      {pulseFocus === "quality" && (
                        <div className="space-y-1">
                          <h4 className="text-xs font-bold text-text">Ovozli tahlillar tahlili:</h4>
                          <p className="text-[11px] text-text-muted">
                            {timeFilter === "today"
                              ? "Tahlillar kutilmoqda. Avvalroq amalga oshirilgan suhbatlarning umumiy ko'rsatkichlarini ko'rish uchun filtrlarni 'Hafta' yoki 'Oy' ga o'tkazing."
                              : `Suhbatlarning o'rtacha sifati ${activeData.avgQuality} ballni tashkil qilmoqda. Salomlashish standartlari yaxshi, lekin e'tirozlar bilan ishlash zaif.`}
                          </p>
                        </div>
                      )}
                      {pulseFocus === "tasks" && (
                        <div className="space-y-1">
                          <h4 className="text-xs font-bold text-text">Topshiriqlar bajarilish holati:</h4>
                          <p className="text-[11px] text-text-muted">
                            {timeFilter === "today"
                              ? "Menejerlarga biriktirilgan vazifalar va topshiriqlar bugun yakunlanmagan."
                              : `Muddati o'tib ketgan ${activeData.tasks} ta CRM topshiriqlar mavjud. Menejer topshiriqlari ijrosini qat'iy nazorat ostiga olishingiz kerak.`}
                          </p>
                        </div>
                      )}
                    </div>

                    {/* Secondary Cards Summary */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-6">
                      {[
                        { title: "Lid konversiyasi", value: activeData.conversion },
                        { title: "Suhbat sifati", value: activeData.avgQuality },
                        { title: "Topshiriqlar", value: activeData.tasks },
                        { title: "Bajarilishi", value: timeFilter === "today" ? "—" : "65%" }
                      ].map((item, idx) => (
                        <div key={idx} className="rounded-2xl bg-bg p-3.5 border border-border">
                          <div className="text-[10px] font-bold text-text-muted uppercase">{item.title}</div>
                          <div className="text-base font-bold text-brand mt-1">{item.value}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                );

              case "quality":
                return (
                  <div key={widget.id} className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm">
                    <h3 className="text-base font-bold text-text">Sifat ko&apos;rinishi</h3>
                    
                    {/* Primary stats */}
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-4">
                      {[
                        { label: "Tahlil qilingan", value: activeData.callsScored },
                        { label: "O'rt. suhbat sifati", value: activeData.avgQuality },
                        { label: "Lid sifati", value: activeData.leadsQuality },
                        { label: "Bog'lana olmagan", value: activeData.unreached },
                        { label: "O'rtacha davomiylik", value: activeData.avgDuration }
                      ].map((item, i) => (
                        <div key={i} className="rounded-2xl border border-border p-3 text-center">
                          <div className="text-[9px] font-bold text-text-muted uppercase tracking-wider">{item.label}</div>
                          <div className="text-sm font-bold text-text mt-1">{item.value}</div>
                        </div>
                      ))}
                    </div>

                    {/* SVG Quality Trend Line Chart */}
                    <div className="mt-6">
                      <div className="text-xs font-bold text-text mb-3 px-1">Suhbat sifati tendentsiyasi (%)</div>
                      <div className="relative h-48 w-full bg-bg rounded-2xl border border-border overflow-hidden p-4">
                        {timeFilter === "today" ? (
                          <div className="absolute inset-0 flex items-center justify-center text-xs text-text-muted font-medium">
                            Bugun tahlil qilingan qo&apos;ng&apos;iroqlar mavjud emas
                          </div>
                        ) : (
                          <>
                            {/* Grid Y lines */}
                            <div className="absolute inset-x-0 top-1/4 border-b border-border/40"></div>
                            <div className="absolute inset-x-0 top-2/4 border-b border-border/40"></div>
                            <div className="absolute inset-x-0 top-3/4 border-b border-border/40"></div>
                            
                            {/* Graphic Line */}
                            <svg className="h-full w-full" viewBox="0 0 600 200" preserveAspectRatio="none">
                              <defs>
                                <linearGradient id="chart-grad" x1="0" y1="0" x2="0" y2="1">
                                  <stop offset="0%" stopColor="var(--brand)" stopOpacity="0.2" />
                                  <stop offset="100%" stopColor="var(--brand)" stopOpacity="0" />
                                </linearGradient>
                              </defs>
                              <path
                                d={`M ${activeData.svgPoints}`}
                                fill="none"
                                stroke="var(--brand)"
                                strokeWidth="3"
                                strokeLinecap="round"
                              />
                              <path
                                d={`M ${activeData.svgPoints} L 600,200 L 0,200 Z`}
                                fill="url(#chart-grad)"
                              />
                            </svg>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                );

              case "trends":
                return (
                  <div key={widget.id} className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm">
                    <h3 className="text-base font-bold text-text">Sifat trendi (Playbook)</h3>
                    <p className="text-xs text-text-muted mt-0.5">Savdo mezonlari va qoidalarining jami 16 ta ko&apos;rsatkichi.</p>

                    <div className="grid md:grid-cols-2 gap-4 mt-6">
                      {[
                        { category: "Salomlashish", items: [
                          { code: "A1", name: "Kompaniya va menejer tanishtirish", val: timeFilter === "today" ? 0 : 85, weak: 0 },
                          { code: "A2", name: "Murojaat manbasini aniqlash", val: timeFilter === "today" ? 0 : 16, weak: 4 },
                          { code: "A3", name: "Suhbat maqsadini belgilash", val: timeFilter === "today" ? 0 : 23, weak: 3 }
                        ]},
                        { category: "Ehtiyoj aniqlash", items: [
                          { code: "B1", name: "Mijoz vaziyati ochilishi", val: timeFilter === "today" ? 0 : 64, weak: 1 },
                          { code: "B2", name: "Xizmat yo'nalishi aniqlanishi", val: timeFilter === "today" ? 0 : 75, weak: 0 },
                          { code: "B3", name: "Qaror va resurs holati", val: timeFilter === "today" ? 0 : 38, weak: 2 }
                        ]}
                      ].map((cat, idx) => (
                        <div key={idx} className="space-y-4">
                          <h4 className="text-xs font-bold text-brand uppercase tracking-wider">{cat.category}</h4>
                          <div className="space-y-3">
                            {cat.items.map((item) => (
                              <div key={item.code} className="space-y-1">
                                <div className="flex items-center justify-between text-xs">
                                  <span className="font-semibold text-text truncate max-w-[80%]">
                                    <span className="inline-block bg-brand-light text-brand px-1.5 py-0.5 rounded font-mono font-bold mr-1.5">{item.code}</span>
                                    {item.name}
                                  </span>
                                  <span className="font-bold text-text">{item.val}%</span>
                                </div>
                                <div className="flex items-center gap-3">
                                  <div className="flex-1 h-2 bg-bg rounded-full overflow-hidden">
                                    <div
                                      className="h-full bg-brand rounded-full transition-all duration-500"
                                      style={{ width: `${item.val}%` }}
                                    ></div>
                                  </div>
                                  {item.weak > 0 && (
                                    <span className="text-[10px] text-rose-500 font-bold bg-rose-50 dark:bg-rose-950/20 px-1.5 py-0.5 rounded border border-rose-100 dark:border-rose-900/30">
                                      {item.weak} zaif
                                    </span>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                );

              case "alerts":
                return (
                  <div key={widget.id} className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm">
                    <div className="flex items-center justify-between">
                      <h3 className="text-base font-bold text-text">Ogohlantirishlar (Mini-panel)</h3>
                      <Link href="/alerts" className="text-xs font-semibold text-brand hover:underline">
                        Hammasini ko&apos;rish
                      </Link>
                    </div>

                    <div className="mt-4 space-y-3">
                      {[
                        { type: "error", title: "Menejer faolligi yo'q", text: "Baxtiyorjon Gaziyev bugun birorta ham qo'ng'iroqni amalga oshirmadi.", time: "17 soat oldin" },
                        { type: "warning", title: "Suhbat sifati past", text: "Oxirgi 5 ta qo'ng'iroq bo'yicha o'rtacha sifat 24% (KPI: 75%+).", time: "1 kun oldin" }
                      ].map((al, idx) => (
                        <div key={idx} className="flex gap-3 rounded-2xl bg-bg p-3 border border-border">
                          <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-xl text-sm font-bold ${
                            al.type === "error" ? "bg-rose-100 text-rose-700 dark:bg-rose-950/40" : "bg-amber-100 text-amber-700 dark:bg-amber-950/40"
                          }`}>
                            !
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between">
                              <h4 className="text-xs font-bold text-text truncate">{al.title}</h4>
                              <span className="text-[9px] text-text-muted">{al.time}</span>
                            </div>
                            <p className="text-[10px] text-text-muted mt-0.5">{al.text}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                );

              case "latest_calls":
                return (
                  <div key={widget.id} className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm overflow-hidden">
                    <h3 className="text-base font-bold text-text">So&apos;nggi tahlillar</h3>
                    
                    {timeFilter === "today" || activeData.calls.length === 0 ? (
                      <div className="py-8 text-center text-xs text-text-muted">
                        Bu davr uchun scored (baholangan) qo&apos;ng&apos;iroqlar ro&yxati yo&apos;q.
                      </div>
                    ) : (
                      <div className="mt-4 overflow-x-auto">
                        <table className="w-full text-left text-xs border-collapse">
                          <thead>
                            <tr className="border-b border-border text-text-muted font-bold">
                              <th className="py-2.5 px-3">Sana</th>
                              <th className="py-2.5 px-3">Menejer</th>
                              <th className="py-2.5 px-3">Yo&apos;nalish</th>
                              <th className="py-2.5 px-3">Kategoriya</th>
                              <th className="py-2.5 px-3">Sifat</th>
                              <th className="py-2.5 px-3">Amallar</th>
                            </tr>
                          </thead>
                          <tbody>
                            {activeData.calls.map((call) => (
                              <tr key={call.id} className="border-b border-border/50 hover:bg-bg/40 transition-colors">
                                <td className="py-3 px-3 font-medium text-text">{call.date}</td>
                                <td className="py-3 px-3 text-text">{call.manager}</td>
                                <td className="py-3 px-3">
                                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                                    call.direction === "Kiruvchi"
                                      ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-400"
                                      : "bg-blue-100 text-blue-800 dark:bg-blue-950/40 dark:text-blue-400"
                                  }`}>
                                    {call.direction}
                                  </span>
                                </td>
                                <td className="py-3 px-3 font-semibold text-text">{call.category}</td>
                                <td className="py-3 px-3 font-bold text-brand">{call.score}</td>
                                <td className="py-3 px-3">
                                  <Link
                                    href={`/calls/${call.id}`}
                                    className="rounded-lg bg-brand-light text-brand hover:bg-brand text-xs font-semibold px-2.5 py-1 transition-colors hover:text-white"
                                  >
                                    Ko&apos;rish
                                  </Link>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                );

              default:
                // Fallback rendering for optional blocks to show visual placement
                return (
                  <div key={widget.id} className="rounded-3xl border border-border border-dashed bg-bg-card p-6 shadow-sm flex flex-col items-center justify-center text-center">
                    <h4 className="text-xs font-bold text-text-muted">{widget.name}</h4>
                    <p className="text-[10px] text-text-muted mt-1 max-w-sm">
                      Ushbu qo&apos;shimcha tahliliy blok Next-bosqichda real ma&apos;lumotlar oqimiga bog&apos;lanadi. Hozircha sozlamalar bo&apos;limi orqali interfeys ko&apos;rinishini sinashingiz mumkin.
                    </p>
                  </div>
                );
            }
          })}
      </div>

      {/* Widget Customizer Modal Panel */}
      {customizerOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-end bg-black/40 backdrop-blur-sm">
          <div className="w-full max-w-md h-full bg-bg-popover border-l border-border p-6 shadow-2xl overflow-y-auto animate-fade-in flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between border-b border-border pb-4">
                <h3 className="text-base font-bold text-text">Dashboard bo&apos;limlarini sozlash</h3>
                <button
                  onClick={() => setCustomizerOpen(false)}
                  className="rounded-lg p-1.5 text-text-muted hover:bg-bg"
                >
                  Yopish
                </button>
              </div>
              <p className="text-xs text-text-muted mt-2">
                Asosiy sahifadagi bloklarni yoqish/o&apos;chirish yoki ularning joylashuv tartibini o&apos;zgartirish.
              </p>

              <div className="mt-6 space-y-3">
                {widgets.map((widget, index) => (
                  <div
                    key={widget.id}
                    className="flex items-center justify-between rounded-2xl border border-border bg-bg p-3 transition-all"
                  >
                    <div className="flex items-center gap-2">
                      {/* Checkbox trigger toggle */}
                      <button
                        onClick={() => toggleWidget(widget.id)}
                        className={`flex h-5 w-5 shrink-0 items-center justify-center rounded border transition-colors ${
                          widget.enabled ? "bg-brand border-brand text-white" : "border-border bg-bg-card"
                        }`}
                      >
                        {widget.enabled && (
                          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="3">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                          </svg>
                        )}
                      </button>
                      <span className="text-xs font-semibold text-text">{widget.name}</span>
                    </div>

                    {/* Up/Down ordering controls */}
                    <div className="flex items-center gap-1">
                      <button
                        disabled={index === 0}
                        onClick={() => moveWidget(index, "up")}
                        className="rounded p-1 text-text-muted hover:bg-brand-light hover:text-brand disabled:opacity-30 disabled:pointer-events-none"
                      >
                        ▲
                      </button>
                      <button
                        disabled={index === widgets.length - 1}
                        onClick={() => moveWidget(index, "down")}
                        className="rounded p-1 text-text-muted hover:bg-brand-light hover:text-brand disabled:opacity-30 disabled:pointer-events-none"
                      >
                        ▼
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="mt-8 pt-4 border-t border-border flex justify-end">
              <button
                onClick={() => setCustomizerOpen(false)}
                className="w-full rounded-xl bg-brand py-3 text-xs font-semibold text-white hover:bg-brand-hover shadow-lg shadow-brand/10 transition-colors"
              >
                O&apos;zgarishlarni saqlash
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
