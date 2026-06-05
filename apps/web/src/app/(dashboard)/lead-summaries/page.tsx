"use client";

import React, { useState } from "react";

interface LeadSummary {
  id: string;
  leadName: string;
  stage: string;
  manager: string;
  date: string;
  summary: string;
  interestLevel: "High" | "Medium" | "Low";
}

export default function LeadSummariesPage() {
  const [showMockData, setShowMockData] = useState(false);
  const [managerFilter, setManagerFilter] = useState("Barchasi");
  const [stageFilter, setStageFilter] = useState("Barchasi");

  const mockSummaries: LeadSummary[] = [
    {
      id: "1",
      leadName: "Avtokontakt MCHJ (Hasanboy G.)",
      stage: "Yangi so'rov",
      manager: "Baxtiyorjon Gaziyev",
      date: "2026-06-03",
      interestLevel: "High",
      summary: "Naming (Nomlash) loyihasi uchun murojaat. Brend nomi o'zbekcha va xalqaro miqyosga mos bo'lishini xohlaydi. Brif yuborilgan, to'ldirilishi kutilmoqda. Quruq mevalar sohasi."
    },
    {
      id: "2",
      leadName: "Jon Branding test klienti",
      stage: "Brifing",
      manager: "Baxtiyorjon Gaziyev",
      date: "2026-06-01",
      interestLevel: "Medium",
      summary: "Logotip va vizual identika bo'yicha brif to'ldirilgan. Narx masalasida o'ylanmoqda. Keyingi uchrashuv dushanbaga rejalashtirilgan."
    }
  ];

  return (
    <div className="space-y-6">
      {/* Title */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text">Lid xulosalari</h1>
          <p className="text-xs text-text-muted mt-1">
            Har bir kelib tushgan lid bo&apos;yicha AI tomonidan tayyorlangan muloqot xulosalari va qisqacha tavsiflar.
          </p>
        </div>

        <button
          onClick={() => setShowMockData(!showMockData)}
          className="rounded-xl bg-brand-light text-brand px-4 py-2 text-xs font-semibold hover:bg-brand hover:text-white transition-colors"
        >
          {showMockData ? "Xaritalarni yopish (Bo'sh holat)" : "Simulyatsiyani yoqish (Mock ma'lumotlar)"}
        </button>
      </div>

      {/* Filter panel */}
      <div className="rounded-3xl border border-border bg-bg-card p-5 shadow-sm space-y-4">
        <h3 className="text-xs font-bold text-text uppercase tracking-wider">Filtrlar</h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
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

          <div>
            <label className="text-[10px] font-bold text-text-muted uppercase block">Lid holati</label>
            <select
              value={stageFilter}
              onChange={(e) => setStageFilter(e.target.value)}
              className="w-full rounded-xl border border-border bg-bg p-2.5 text-xs text-text focus:border-brand focus:outline-none mt-1"
            >
              <option value="Barchasi">Barchasi</option>
              <option value="Yangi so'rov">Yangi so&apos;rov</option>
              <option value="Brifing">Brifing</option>
            </select>
          </div>

          <div>
            <label className="text-[10px] font-bold text-text-muted uppercase block">Sana oralig&apos;i</label>
            <div className="rounded-xl border border-border bg-bg p-2.5 text-xs text-text mt-1 text-text-muted select-none">
              29.05.2026 — 04.06.2026
            </div>
          </div>
        </div>
      </div>

      {/* Main content grid */}
      <div className="rounded-3xl border border-border bg-bg-card p-6 shadow-sm min-h-[300px] flex items-center justify-center">
        {!showMockData ? (
          <div className="text-center max-w-sm space-y-3">
            <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-bg text-text-muted text-lg mx-auto">
              ⭐
            </span>
            <h3 className="text-sm font-bold text-text">Xulosalar topilmadi</h3>
            <p className="text-xs text-text-muted">
              Tanlangan sana oralig&apos;ida va filtrlar bo&apos;yicha hech qanday lid xulosalari aniqlanmadi. Yuqoridagi &quot;Simulyatsiyani yoqish&quot; tugmasini bosib mock xulosalarni ko&apos;rishingiz mumkin.
            </p>
          </div>
        ) : (
          <div className="w-full space-y-4">
            {mockSummaries
              .filter(s => managerFilter === "Barchasi" || s.manager === managerFilter)
              .filter(s => stageFilter === "Barchasi" || s.stage === stageFilter)
              .map((summary) => (
                <div key={summary.id} className="rounded-2xl border border-border p-5 hover:bg-bg/40 transition-colors flex flex-col md:flex-row gap-4 justify-between items-start">
                  <div className="space-y-2 flex-1">
                    <div className="flex items-center gap-2">
                      <h4 className="text-sm font-bold text-text">{summary.leadName}</h4>
                      <span className={`rounded-full px-2 py-0.5 text-[9px] font-bold ${
                        summary.interestLevel === "High" 
                          ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-400" 
                          : "bg-amber-100 text-amber-800 dark:bg-amber-950/40 dark:text-amber-400"
                      }`}>
                        Qiziqish: {summary.interestLevel}
                      </span>
                    </div>

                    <p className="text-xs text-text-muted leading-relaxed">
                      {summary.summary}
                    </p>

                    <div className="flex flex-wrap gap-2 text-[10px] text-text-muted pt-1">
                      <span>Menejer: <strong>{summary.manager}</strong></span>
                      <span>•</span>
                      <span>Sana: <strong>{summary.date}</strong></span>
                    </div>
                  </div>

                  <span className="rounded-full bg-brand-light px-3 py-1 text-xs font-bold text-brand uppercase tracking-wider whitespace-nowrap self-end md:self-start">
                    {summary.stage}
                  </span>
                </div>
              ))}
          </div>
        )}
      </div>
    </div>
  );
}
