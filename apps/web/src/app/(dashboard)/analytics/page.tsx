"use client";

import React, { useState } from "react";
import Link from "next/link";

export default function AnalyticsPage() {
  const [activeTab, setActiveTab] = useState<"overview" | "quality" | "training" | "customer" | "activity" | "leads">("overview");
  const [timeFilter, setTimeFilter] = useState<"today" | "3days" | "week" | "month" | "custom">("month");
  
  // Dynamic AI advice state for training tab
  const [aiRefreshing, setAiRefreshing] = useState(false);
  const [aiAdviceText, setAiAdviceText] = useState(
    "Menejer Baxtiyorjon Gaziyevning mijoz ehtiyojlarini aniqlash (B1-B3) bosqichidagi ko'rsatkichlari 38% ga tushib ketgan. Naming (Nomlash) va Logotip yo'nalishlarida narx e'tirozlarini boshqarish bo'yicha maxsus trening o'tash tavsiya etiladi."
  );

  const handleRefreshAi = () => {
    setAiRefreshing(true);
    setTimeout(() => {
      setAiRefreshing(false);
      setAiAdviceText(
        "Yangi baholangan 12 ta qo'ng'iroq tahlilidan so'ng: Baxtiyorjon Gaziyev Salomlashish (A1) va Kirish bosqichini mustahkamlagan. Biroq, Taklif yopilishidan oldin brifing yuborish (E1) bo'yicha topshiriqlar hali ham 17% darajasida qolmoqda. E'tiborni E1 mezonini to'g'irlashga qaratish lozim."
      );
    }, 1500);
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text">Analitika</h1>
          <p className="text-xs text-text-muted mt-1">
            Sotuv va qo&apos;ng&apos;iroqlar tahlili bo&apos;yicha chuqur sun&apos;iy intellekt hisobotlari.
          </p>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap gap-2 rounded-2xl bg-bg-card p-1 border border-border">
          {(["today", "3days", "week", "month"] as const).map((filter) => (
            <button
              key={filter}
              onClick={() => setTimeFilter(filter)}
              className={`rounded-xl px-3 py-1.5 text-xs font-semibold uppercase tracking-wider transition-all ${
                timeFilter === filter
                  ? "bg-brand text-white"
                  : "text-text-muted hover:text-brand"
              }`}
            >
              {filter === "today" ? "Bugun" : filter === "3days" ? "3 Kun" : filter === "week" ? "Hafta" : "Oy"}
            </button>
          ))}
        </div>
      </div>

      {/* Tabs navigation */}
      <div className="flex border-b border-border overflow-x-auto no-scrollbar scroll-smooth">
        {[
          { id: "overview", label: "Umumiy ko'rinish" },
          { id: "quality", label: "Sifat nazorati" },
          { id: "training", label: "Jamoa malakasi" },
          { id: "customer", label: "Mijoz tahlili" },
          { id: "activity", label: "Faoliyat tahlili" },
          { id: "leads", label: "Lid analitikasi" }
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={`border-b-2 px-4 py-3 text-xs font-bold uppercase tracking-wider whitespace-nowrap transition-colors ${
              activeTab === tab.id
                ? "border-brand text-brand"
                : "border-transparent text-text-muted hover:text-brand hover:border-brand/40"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Contents */}
      <div className="mt-4">
        {/* Tab 1: Overview */}
        {activeTab === "overview" && (
          <div className="space-y-6">
            {/* AI Summary card */}
            <div className="rounded-3xl border border-border bg-bg-card p-5 shadow-sm">
              <h3 className="text-sm font-bold text-text">Biznes Pulsi (Analitika)</h3>
              <p className="text-xs text-text-muted mt-2">
                Oxirgi 30 kun ichida Jon Branding agentligi voronkasida konversiya darajasi 0.00% da qolgan. Bunga asosiy sabab faol lidlar soni 487 taga yetgan bo&apos;lsa-da, ularni yopish (Closing) jarayonlari sustligi va obuna muzlatilganligidir.
              </p>
            </div>

            {/* KPI Cards Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { title: "Sotuvlar", value: "0 UZS", trend: "0%" },
                { title: "Bitim tushumi", value: "0 UZS", trend: "0%" },
                { title: "Lid konversiyasi", value: "0.00%", trend: "-100%" },
                { title: "O'rtacha bitim", value: "—", trend: "0%" },
                { title: "Suhbat sifati", value: "72%", trend: "+2.5%" },
                { title: "Yopilishga yaqin leadlar", value: "12 ta", trend: "+4 ta" },
                { title: "Topshiriqlar", value: "84 ta", trend: "+12 ta" },
                { title: "Bajarilishi", value: "65%", trend: "-8%" }
              ].map((kpi, i) => (
                <div key={i} className="rounded-3xl border border-border bg-bg-card p-4 shadow-sm">
                  <div className="text-[10px] font-bold text-text-muted uppercase">{kpi.title}</div>
                  <div className="text-base font-bold text-text mt-1.5">{kpi.value}</div>
                  <div className="flex items-center gap-1 mt-1 text-[9px] font-bold text-text-muted">
                    <span>{kpi.trend}</span>
                    <span>davrga nisbatan</span>
                  </div>
                </div>
              ))}
            </div>

            {/* SVG Double-Axis Chart */}
            <div className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm">
              <h3 className="text-sm font-bold text-text">Konversiya va suhbat sifati trendi</h3>
              <div className="relative h-56 w-full bg-bg rounded-2xl border border-border overflow-hidden p-4 mt-4">
                <div className="absolute inset-0 flex items-center justify-center text-xs text-text-muted font-medium">
                  {/* SVG background grid lines */}
                  <svg className="h-full w-full opacity-10" viewBox="0 0 600 200" preserveAspectRatio="none">
                    <line x1="0" y1="50" x2="600" y2="50" stroke="currentColor" strokeWidth="1" />
                    <line x1="0" y1="100" x2="600" y2="100" stroke="currentColor" strokeWidth="1" />
                    <line x1="0" y1="150" x2="600" y2="150" stroke="currentColor" strokeWidth="1" />
                  </svg>
                </div>
                
                {/* SVG trend lines rendering */}
                <svg className="h-full w-full" viewBox="0 0 600 200" preserveAspectRatio="none">
                  {/* Conversion line (Blue) */}
                  <path d="M 0,180 L 120,175 L 240,180 L 360,180 L 480,180 L 600,180" fill="none" stroke="#3b82f6" strokeWidth="3" />
                  {/* Quality line (Sage / Brand) */}
                  <path d="M 0,120 L 120,130 L 240,110 L 360,95 L 480,90 L 600,80" fill="none" stroke="var(--brand)" strokeWidth="3" />
                </svg>

                {/* Legend overlay */}
                <div className="absolute bottom-3 left-4 flex gap-4 text-[9px] font-bold">
                  <div className="flex items-center gap-1.5 text-blue-600">
                    <span className="h-2 w-2 rounded-full bg-blue-500"></span> Lid konversiyasi (%)
                  </div>
                  <div className="flex items-center gap-1.5 text-brand">
                    <span className="h-2 w-2 rounded-full bg-brand"></span> Suhbat sifati (%)
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Quality Control */}
        {activeTab === "quality" && (
          <div className="space-y-6">
            <div className="border-b border-border pb-2">
              <h3 className="text-base font-bold text-text">Avval eng zaif mezonlardan boshlang</h3>
              <p className="text-xs text-text-muted mt-1">Playbook bo&apos;yicha aniqlangan muammolar va zaif o&apos;rinlar.</p>
            </div>

            <div className="grid md:grid-cols-2 gap-4">
              {[
                { code: "A2", name: "Murojaat manbasini aniqlash", rate: 16, count: 24, weakDesc: "Menejer mijoz bizni qayerdan topganini so'ramaydi.", hint: "Mijozdan o'z so'rovi manbasini aniqlashni odat qiling." },
                { code: "E1", name: "Brif yuborish/kelishish", rate: 17, count: 18, weakDesc: "Menejer brif yuborishni unutilgan qoldiradi.", hint: "Har suhbat oxirida brifing havolasini taqdim eting." },
                { code: "A3", name: "Suhbat maqsadini belgilash", rate: 23, count: 12, weakDesc: "Menejer suhbat maqsadi va algoritmini aytmaydi.", hint: "Kirish qismida suhbat tartibini bayon qiling." },
                { code: "E3", name: "Moliyaviy kelishuvni yakunlash", rate: 32, count: 9, weakDesc: "Avans to'lovlari bo'yicha kelishuv qilinmagan.", hint: "Avans to'lovi foizlari va muddatlarini aniqlashtiring." }
              ].map((item) => (
                <div key={item.code} className="rounded-3xl border border-border bg-bg-card p-5 shadow-sm flex flex-col justify-between space-y-3">
                  <div className="flex items-start justify-between">
                    <div>
                      <span className="rounded bg-brand-light text-brand px-2 py-0.5 text-xs font-mono font-bold">
                        {item.code}
                      </span>
                      <h4 className="text-xs font-bold text-text mt-1.5">{item.name}</h4>
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-bold text-rose-500">{item.rate}%</div>
                      <div className="text-[9px] font-bold text-text-muted uppercase">Bajarilishi</div>
                    </div>
                  </div>

                  {/* Progress and weak stats */}
                  <div className="space-y-1">
                    <div className="h-1.5 w-full bg-bg rounded-full overflow-hidden">
                      <div className="h-full bg-rose-500" style={{ width: `${item.rate}%` }}></div>
                    </div>
                    <div className="text-[9px] text-text-muted font-semibold">
                      Jami scored qo&apos;ng&apos;iroqlardan {item.count} ta zaif holat aniqlandi.
                    </div>
                  </div>

                  {/* Recommendations */}
                  <div className="text-[10px] space-y-1 pt-2 border-t border-border/40">
                    <div className="text-rose-600 dark:text-rose-400">
                      <strong>Xato:</strong> {item.weakDesc}
                    </div>
                    <div className="text-emerald-700 dark:text-emerald-400">
                      <strong>Maslahat:</strong> {item.hint}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Tab 3: Training */}
        {activeTab === "training" && (
          <div className="space-y-6">
            {/* AI Advisor Panel */}
            <div className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-text">AI Malaka oshirish tavsiyalari</h3>
                <button
                  disabled={aiRefreshing}
                  onClick={handleRefreshAi}
                  className="rounded-xl border border-border bg-bg px-3 py-1.5 text-[10px] font-bold text-brand hover:bg-brand-light transition-colors disabled:opacity-50"
                >
                  {aiRefreshing ? "Yangilanmoqda..." : "AI tavsiyasini yangilash"}
                </button>
              </div>

              <div className="rounded-2xl bg-brand-light/50 border border-brand/5 p-4 flex gap-3">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brand text-white font-bold text-sm">
                  💡
                </span>
                <p className="text-xs text-text leading-relaxed">
                  {aiAdviceText}
                </p>
              </div>
            </div>

            {/* Manager training list */}
            <div className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm space-y-4">
              <h3 className="text-sm font-bold text-text">Hozir kimning malakasini oshirish kerak?</h3>
              
              <div className="rounded-2xl border border-border bg-bg p-4 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-brand text-white font-bold text-sm">
                    BG
                  </div>
                  <div>
                    <div className="text-xs font-bold text-text">Baxtiyorjon Gaziyev (Sotuvchi)</div>
                    <div className="text-[10px] text-text-muted mt-0.5">Focus: Ehtiyojni aniqlash va qiymat tushuntirish</div>
                  </div>
                </div>

                <div className="flex gap-2">
                  <span className="rounded bg-rose-100 dark:bg-rose-950/40 text-rose-800 dark:text-rose-400 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider">
                    1-Prioritet
                  </span>
                  <Link
                    href="/calls/1"
                    className="rounded-xl bg-brand text-white text-xs font-semibold px-4 py-2 hover:bg-brand-hover shadow-md transition-colors"
                  >
                    Ko&apos;rib chiqish qo&apos;ng&apos;iroqini ochish
                  </Link>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 4: Customer Analysis */}
        {activeTab === "customer" && (
          <div className="space-y-6">
            <div className="grid md:grid-cols-3 gap-4">
              {[
                { label: "Jami bitim summasi", value: "0 UZS" },
                { label: "Bitimlar soni", value: "0 ta" },
                { label: "O'rtacha bitim qiymati", value: "—" }
              ].map((c, i) => (
                <div key={i} className="rounded-3xl border border-border bg-bg-card p-4 text-center">
                  <div className="text-[10px] font-bold text-text-muted uppercase tracking-wider">{c.label}</div>
                  <div className="text-base font-bold text-text mt-1.5">{c.value}</div>
                </div>
              ))}
            </div>

            {/* Objections chart */}
            <div className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm">
              <h3 className="text-sm font-bold text-text">Top e&apos;tirozlar tahlili</h3>
              
              <div className="mt-4 space-y-3.5">
                {[
                  { name: "Narx qimmat", count: 4, pct: 100 },
                  { name: "Boshqa yechim bor", count: 3, pct: 75 },
                  { name: "Ishonch yo'q", count: 2, pct: 50 },
                  { name: "Kerak emas", count: 2, pct: 50 },
                  { name: "Maslahatlashaman", count: 1, pct: 25 },
                  { name: "O'ylab ko'raman", count: 1, pct: 25 }
                ].map((obj, i) => (
                  <div key={i} className="space-y-1">
                    <div className="flex justify-between text-xs font-semibold">
                      <span className="text-text">{obj.name}</span>
                      <span className="text-text-muted">{obj.count} ta suhbatda</span>
                    </div>
                    <div className="h-3 w-full bg-bg rounded-full overflow-hidden flex">
                      <div className="h-full bg-brand rounded-full" style={{ width: `${obj.pct}%` }}></div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Tab 5: Activity Analysis */}
        {activeTab === "activity" && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
              {[
                { label: "Jami qo'ng'iroqlar", value: "278" },
                { label: "Ulangan", value: "172" },
                { label: "Bog'lana olmagan", value: "106" },
                { label: "Tahlil qilingan", value: "257" },
                { label: "Baholangan suhbat", value: "17" },
                { label: "O'rtacha davomiylik", value: "1:47" }
              ].map((item, i) => (
                <div key={i} className="rounded-3xl border border-border bg-bg-card p-3 text-center">
                  <div className="text-[9px] font-bold text-text-muted uppercase tracking-wider">{item.label}</div>
                  <div className="text-sm font-bold text-text mt-1">{item.value}</div>
                </div>
              ))}
            </div>

            {/* Unreached Call Activity Chart */}
            <div className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm">
              <h3 className="text-sm font-bold text-text">Bog&apos;lana olmagan — Faollik tendentsiyasi (Daily)</h3>
              <div className="relative h-48 w-full bg-bg rounded-2xl border border-border overflow-hidden p-4 mt-4">
                <svg className="h-full w-full" viewBox="0 0 600 200" preserveAspectRatio="none">
                  {/* Grid Lines */}
                  <line x1="0" y1="100" x2="600" y2="100" stroke="rgba(0,0,0,0.05)" strokeWidth="1" />
                  {/* Red trend line */}
                  <path d="M 0,150 L 100,120 L 200,160 L 300,90 L 400,130 L 500,70 L 600,110" fill="none" stroke="#ef4444" strokeWidth="2.5" />
                </svg>
              </div>
            </div>
          </div>
        )}

        {/* Tab 6: Leads Analysis */}
        {activeTab === "leads" && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { label: "Jami yangi lidlar", value: "89 ta", change: "-65%" },
                { label: "Yutganlar (Won)", value: "0 ta", change: "-100%" },
                { label: "Boy berilganlar (Lost)", value: "8 ta", change: "+12%" },
                { label: "Faol lidlar soni", value: "85 ta", change: "+5%" }
              ].map((l, i) => (
                <div key={i} className="rounded-3xl border border-border bg-bg-card p-4 shadow-sm">
                  <div className="text-[10px] font-bold text-text-muted uppercase">{l.label}</div>
                  <div className="text-base font-bold text-text mt-1">{l.value}</div>
                  <div className="text-[9px] font-bold text-rose-500 mt-0.5">{l.change} o&apos;tgan oydan</div>
                </div>
              ))}
            </div>

            {/* Lead quality gradient bar */}
            <div className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm space-y-4">
              <h3 className="text-sm font-bold text-text">Lid sifati taqsimoti</h3>
              
              <div className="flex h-5 w-full rounded-full overflow-hidden bg-bg border border-border">
                <div className="bg-rose-500 h-full flex items-center justify-center text-[9px] font-bold text-white" style={{ width: "67%" }}>Past (67%)</div>
                <div className="bg-amber-500 h-full flex items-center justify-center text-[9px] font-bold text-white" style={{ width: "6%" }}>O&apos;rtacha (6%)</div>
                <div className="bg-emerald-500 h-full flex items-center justify-center text-[9px] font-bold text-white" style={{ width: "28%" }}>Yaxshi (28%)</div>
              </div>

              <div className="grid grid-cols-3 text-center text-[10px] text-text-muted mt-2">
                <div>Past: 12 ta</div>
                <div>O&apos;rtacha: 1 ta</div>
                <div>Yaxshi: 5 ta</div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
