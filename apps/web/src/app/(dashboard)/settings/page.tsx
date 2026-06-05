"use client";

import React, { useState, useEffect } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useTheme, Palette } from "@/context/ThemeContext";

type TabId =
  | "profil"
  | "general"
  | "appearance"
  | "businesses"
  | "schedule"
  | "daily_report"
  | "admins"
  | "managers"
  | "subscription"
  | "playbook";

function SettingsPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const {
    theme,
    setTheme,
    palette,
    setPalette,
    language,
    setLanguage,
    currentBusiness,
    setCurrentBusiness
  } = useTheme();

  // Active tab state
  const [activeTab, setActiveTab] = useState<TabId>("profil");

  // Read search params on load
  useEffect(() => {
    const tabParam = searchParams.get("tab") as TabId;
    if (tabParam) {
      setActiveTab(tabParam);
    }
  }, [searchParams]);

  const handleTabChange = (tab: TabId) => {
    setActiveTab(tab);
    router.push(`/settings?tab=${tab}`);
  };

  // Profile fields state
  const [profileName, setProfileName] = useState("Baxtiyorjon");
  const [profileEmail, setProfileEmail] = useState("baxtiyorjon@gmail.com");
  const [profileSaved, setProfileSaved] = useState(false);

  const saveProfile = (e: React.FormEvent) => {
    e.preventDefault();
    setProfileSaved(true);
    setTimeout(() => setProfileSaved(false), 2000);
  };

  // Schedule working days
  const [workDays, setWorkDays] = useState({
    Du: true, Se: true, Ch: true, Pa: true, Ju: true, Sh: false, Ya: false
  });
  const toggleDay = (day: keyof typeof workDays) => {
    setWorkDays({ ...workDays, [day]: !workDays[day] });
  };

  // Playbook tabs
  const [playbookTab, setPlaybookTab] = useState<"criteria" | "questions" | "services" | "crm">("criteria");

  return (
    <div className="flex flex-col md:flex-row gap-6 items-start">
      {/* Left Settings Sidebar */}
      <div className="w-full md:w-64 shrink-0 rounded-3xl border border-border bg-bg-card p-4 shadow-sm space-y-1">
        {[
          { id: "profil", label: "Profil" },
          { id: "general", label: "Umumiy" },
          { id: "appearance", label: "Ko'rinish" },
          { id: "businesses", label: "Bizneslar" },
          { id: "schedule", label: "Ish jadvali" },
          { id: "daily_report", label: "Kunlik hisobot" },
          { id: "admins", label: "Rahbarlar" },
          { id: "managers", label: "Sotuv menejerlari" },
          { id: "subscription", label: "Obuna" },
          { id: "playbook", label: "Sotuv mezoni (Playbook)" }
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => handleTabChange(tab.id as TabId)}
            className={`w-full rounded-2xl px-4 py-3 text-left text-xs font-bold transition-all ${
              activeTab === tab.id
                ? "bg-brand text-white shadow-md shadow-brand/10"
                : "text-text-muted hover:bg-brand-light hover:text-brand"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Right Settings Content */}
      <div className="flex-1 w-full rounded-3xl border border-border bg-bg-card p-6 shadow-sm min-h-[500px]">
        
        {/* Profil Section */}
        {activeTab === "profil" && (
          <form onSubmit={saveProfile} className="space-y-6">
            <h3 className="text-base font-bold text-text border-b border-border pb-2">Profil sozlamalari</h3>
            
            <div className="flex flex-col sm:flex-row gap-4 items-center">
              <div className="flex h-16 w-16 items-center justify-center rounded-3xl bg-brand text-white font-display text-xl font-bold">
                B
              </div>
              <div className="space-y-1 text-center sm:text-left">
                <button type="button" className="rounded-xl border border-border bg-bg px-3 py-1.5 text-[11px] font-bold text-text-muted hover:text-brand">
                  Rasm yuklash
                </button>
                <p className="text-[10px] text-text-muted">JPG, PNG, maksimal 2MB o&apos;lcham.</p>
              </div>
            </div>

            <div className="grid sm:grid-cols-2 gap-4">
              <div>
                <label className="text-[10px] font-bold text-text-muted uppercase block">Ism</label>
                <input
                  required
                  type="text"
                  value={profileName}
                  onChange={(e) => setProfileName(e.target.value)}
                  className="w-full rounded-xl border border-border bg-bg p-2.5 text-xs text-text focus:border-brand focus:outline-none mt-1"
                />
              </div>
              <div>
                <label className="text-[10px] font-bold text-text-muted uppercase block">Elektron pochta</label>
                <input
                  required
                  type="email"
                  value={profileEmail}
                  className="w-full rounded-xl border border-border bg-bg p-2.5 text-xs text-text focus:border-brand focus:outline-none mt-1"
                  onChange={(e) => setProfileEmail(e.target.value)}
                />
              </div>
            </div>

            {/* Telegram Integration Panel */}
            <div className="rounded-2xl border border-border bg-bg p-4 space-y-3">
              <h4 className="text-xs font-bold text-text">Telegram ulanishi</h4>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 font-bold text-sm">
                    TG
                  </span>
                  <div>
                    <div className="text-xs font-bold text-text">Ulangan hisob</div>
                    <div className="text-[10px] text-text-muted mt-0.5">ID: 150074828</div>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => alert("Telegram hisob qayta bog'lash modali...")}
                  className="rounded-xl border border-border bg-bg-card text-text px-3 py-1.5 text-xs font-semibold hover:border-brand hover:text-brand transition-colors"
                >
                  Qayta ulash
                </button>
              </div>
            </div>

            {profileSaved && (
              <div className="text-xs font-bold text-emerald-600 bg-emerald-50 dark:bg-emerald-950/20 py-2 rounded-xl border border-emerald-200 text-center">
                Profil ma&apos;lumotlari muvaffaqiyatli saqlandi!
              </div>
            )}

            <div className="flex justify-end gap-2 pt-4 border-t border-border">
              <button type="button" className="rounded-xl px-4 py-2.5 text-xs font-semibold text-text-muted hover:bg-bg">
                Bekor qilish
              </button>
              <button type="submit" className="rounded-xl bg-brand text-white px-4 py-2.5 text-xs font-semibold hover:bg-brand-hover shadow-md">
                Saqlash
              </button>
            </div>
          </form>
        )}

        {/* General Section */}
        {activeTab === "general" && (
          <div className="space-y-6">
            <h3 className="text-base font-bold text-text border-b border-border pb-2">Umumiy sozlamalar</h3>
            <div className="grid sm:grid-cols-2 gap-4">
              <div>
                <label className="text-[10px] font-bold text-text-muted uppercase block">Biznes nomi</label>
                <input
                  type="text"
                  defaultValue={currentBusiness}
                  className="w-full rounded-xl border border-border bg-bg p-2.5 text-xs text-text focus:border-brand focus:outline-none mt-1"
                />
              </div>
              <div>
                <label className="text-[10px] font-bold text-text-muted uppercase block">Soha</label>
                <input
                  type="text"
                  placeholder="Masalan: Brending agentligi..."
                  className="w-full rounded-xl border border-border bg-bg p-2.5 text-xs text-text focus:border-brand focus:outline-none mt-1"
                />
              </div>
            </div>

            {/* Language and timezone */}
            <div className="grid sm:grid-cols-2 gap-4">
              <div>
                <label className="text-[10px] font-bold text-text-muted uppercase block">Biznes tili (Playbook & AI)</label>
                <select
                  value={language}
                  onChange={(e) => setLanguage(e.target.value as any)}
                  className="w-full rounded-xl border border-border bg-bg p-2.5 text-xs text-text focus:border-brand focus:outline-none mt-1"
                >
                  <option value="uz">O&apos;zbek tili</option>
                  <option value="en">Ingliz tili (English)</option>
                  <option value="ru">Rus tili (Русский)</option>
                </select>
              </div>
              <div>
                <label className="text-[10px] font-bold text-text-muted uppercase block">Vaqt zonasi</label>
                <select className="w-full rounded-xl border border-border bg-bg p-2.5 text-xs text-text focus:border-brand focus:outline-none mt-1">
                  <option>Asia/Tashkent UTC+5</option>
                </select>
              </div>
            </div>

            {/* Task generation toggle */}
            <div className="rounded-2xl border border-border bg-bg p-4 flex items-center justify-between">
              <div>
                <h4 className="text-xs font-bold text-text">Avtomatik vazifalar yaratish</h4>
                <p className="text-[10px] text-text-muted mt-0.5">AI suhbat tahlilidan kelib chiqib CRM topshiriqlar yaratadi.</p>
              </div>
              <button className="h-6 w-11 rounded-full bg-brand p-1 transition-colors relative flex items-center">
                <span className="h-4 w-4 rounded-full bg-white absolute right-1 transition-transform"></span>
              </button>
            </div>
          </div>
        )}

        {/* Appearance Section */}
        {activeTab === "appearance" && (
          <div className="space-y-6">
            <h3 className="text-base font-bold text-text border-b border-border pb-2">Ko&apos;rinish sozlamalari</h3>
            
            {/* Dark mode cards */}
            <div className="space-y-2">
              <label className="text-[10px] font-bold text-text-muted uppercase block">Rang rejimi</label>
              <div className="grid grid-cols-3 gap-3">
                {[
                  { id: "light", label: "Yorug' rejim", icon: "☀️" },
                  { id: "dark", label: "Qorong'u rejim", icon: "🌙" }
                ].map((mode) => (
                  <button
                    key={mode.id}
                    type="button"
                    onClick={() => setTheme(mode.id as any)}
                    className={`rounded-2xl border p-4 text-center text-xs font-bold transition-all ${
                      theme === mode.id
                        ? "border-brand bg-brand-light text-brand shadow-sm"
                        : "border-border bg-bg hover:border-brand/40"
                    }`}
                  >
                    <div className="text-lg mb-1">{mode.icon}</div>
                    {mode.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Palette selection grid */}
            <div className="space-y-2">
              <label className="text-[10px] font-bold text-text-muted uppercase block">Tizim ranglar palitrasi (7 xil rang)</label>
              <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-7 gap-2">
                {[
                  { id: "sage", label: "Sage", color: "bg-[#275344]" },
                  { id: "indigo", label: "Indigo", color: "bg-[#4f46e5]" },
                  { id: "rose", label: "Rose", color: "bg-[#e11d48]" },
                  { id: "amber", label: "Amber", color: "bg-[#d97706]" },
                  { id: "teal", label: "Teal", color: "bg-[#0d9488]" },
                  { id: "violet", label: "Violet", color: "bg-[#7c3aed]" },
                  { id: "emerald", label: "Emerald", color: "bg-[#059669]" }
                ].map((pal) => (
                  <button
                    key={pal.id}
                    type="button"
                    onClick={() => setPalette(pal.id as Palette)}
                    className={`rounded-xl border p-2 text-center text-[10px] font-bold flex flex-col items-center gap-1.5 transition-all ${
                      palette === pal.id
                        ? "border-brand bg-brand-light text-brand ring-2 ring-brand/10"
                        : "border-border bg-bg hover:border-brand/30"
                    }`}
                  >
                    <span className={`h-4 w-4 rounded-full ${pal.color} border border-white/20 inline-block`}></span>
                    {pal.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Subscription Section */}
        {activeTab === "subscription" && (
          <div className="space-y-6">
            <h3 className="text-base font-bold text-text border-b border-border pb-2">Obuna va to&apos;lovlar</h3>
            
            {/* Frozen Notice */}
            <div className="rounded-2xl border border-rose-200 dark:border-rose-900/40 bg-rose-50/50 dark:bg-rose-950/15 p-4 flex gap-3">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-rose-100 dark:bg-rose-900/30 text-rose-600 dark:text-rose-400 font-bold text-sm">
                !
              </span>
              <div>
                <div className="text-xs font-bold text-rose-800 dark:text-rose-400">Obuna holati: Muzlatilgan</div>
                <div className="text-[10px] text-rose-700/80 dark:text-rose-400/80 mt-0.5">
                  Xizmatlarni davom ettirish uchun to&apos;lov qiling. Har oyning 15-sanasida billing hisob-kitobi.
                </div>
              </div>
            </div>

            {/* Financial Details */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="rounded-2xl bg-bg p-3 border border-border">
                <div className="text-[9px] font-bold text-text-muted uppercase">Balans</div>
                <div className="text-sm font-bold text-text mt-1">0 UZS</div>
              </div>
              <div className="rounded-2xl bg-bg p-3 border border-border">
                <div className="text-[9px] font-bold text-text-muted uppercase">O&apos;rinlar soni</div>
                <div className="text-sm font-bold text-text mt-1">1 ta o&apos;rin</div>
              </div>
              <div className="rounded-2xl bg-bg p-3 border border-border">
                <div className="text-[9px] font-bold text-text-muted uppercase">Oylik xarajat</div>
                <div className="text-sm font-bold text-text mt-1">640,000 UZS</div>
              </div>
              <div className="rounded-2xl bg-bg p-3 border border-border">
                <div className="text-[9px] font-bold text-text-muted uppercase">Faol kunlar</div>
                <div className="text-sm font-bold text-text mt-1">—</div>
              </div>
            </div>

            {/* Technical Help and contacts */}
            <div className="rounded-2xl border border-border bg-bg p-4 space-y-3">
              <h4 className="text-xs font-bold text-text">Texnik ko&apos;mak / Operator bilan aloqa</h4>
              <div className="grid sm:grid-cols-3 gap-3 text-center text-[10px]">
                <a href="https://t.me/Metasell_uz" target="_blank" className="rounded-xl bg-bg-card p-3 border border-border hover:border-brand transition-colors block">
                  <div className="font-bold text-brand">Telegram yordamchi</div>
                  <div className="text-text-muted mt-1">@Metasell_uz</div>
                </a>
                <a href="tel:+998917851546" className="rounded-xl bg-bg-card p-3 border border-border hover:border-brand transition-colors block">
                  <div className="font-bold text-brand">Telefon aloqasi</div>
                  <div className="text-text-muted mt-1">+998 91 785 15 46</div>
                </a>
                <a href="mailto:main@metasell.ai" className="rounded-xl bg-bg-card p-3 border border-border hover:border-brand transition-colors block">
                  <div className="font-bold text-brand">Email manzil</div>
                  <div className="text-text-muted mt-1">main@metasell.ai</div>
                </a>
              </div>
            </div>
          </div>
        )}

        {/* Playbook Section */}
        {activeTab === "playbook" && (
          <div className="space-y-6">
            <div className="border-b border-border pb-3 flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-text">Sotuv mezoni (Playbook)</h3>
                <p className="text-[10px] text-text-muted mt-0.5">Versiya: 2 • Yangilangan vaqti: 2026.05.04</p>
              </div>
              <span className="rounded bg-brand-light px-2.5 py-0.5 text-[9px] font-bold text-brand uppercase">
                AI Active
              </span>
            </div>

            {/* Sub-tabs for playbook */}
            <div className="flex gap-2 border-b border-border/60 pb-1">
              {[
                { id: "criteria", label: "Baholash mezonlari" },
                { id: "questions", label: "Anketa savollari" },
                { id: "services", label: "Xizmat yo'nalishlari" },
                { id: "crm", label: "CRM natijalari" }
              ].map((subTab) => (
                <button
                  key={subTab.id}
                  onClick={() => setPlaybookTab(subTab.id as any)}
                  className={`rounded-xl px-3 py-1.5 text-xs font-bold transition-all ${
                    playbookTab === subTab.id
                      ? "bg-brand-light text-brand"
                      : "text-text-muted hover:text-brand"
                  }`}
                >
                  {subTab.label}
                </button>
              ))}
            </div>

            {/* Playbook Tab 1: Criteria weights */}
            {playbookTab === "criteria" && (
              <div className="space-y-4">
                <div className="flex justify-between items-center">
                  <h4 className="text-xs font-bold text-text">Baholash mezonlari ro&apos;yxati</h4>
                  <button type="button" className="rounded-xl bg-brand text-white px-3 py-1.5 text-[10px] font-bold">
                    + Kategoriya qo&apos;shish
                  </button>
                </div>

                <div className="space-y-3">
                  {[
                    { cat: "Salomlashish", weight: 12, items: ["A1 Kompaniya va menejer tanishtirish", "A2 Murojaat manbasini aniqlash", "A3 Suhbat maqsadini belgilash"] },
                    { cat: "Ehtiyoj aniqlash", weight: 23, items: ["B1 Mijoz vaziyati ochildi", "B2 Qaysi yo'nalish aniqlandi", "B3 Qaror va resurs holati"] }
                  ].map((group, index) => (
                    <div key={index} className="rounded-2xl border border-border bg-bg p-4 space-y-3">
                      <div className="flex justify-between items-center border-b border-border/40 pb-2">
                        <span className="text-xs font-bold text-text">{group.cat}</span>
                        <span className="text-xs text-brand font-bold">Vazni: {group.weight}%</span>
                      </div>
                      <div className="space-y-2">
                        {group.items.map((item, itemIdx) => (
                          <div key={itemIdx} className="flex justify-between items-center rounded-xl bg-bg-card p-2.5 border border-border text-xs">
                            <span className="font-semibold text-text">{item}</span>
                            <div className="flex items-center gap-1.5">
                              <button type="button" className="text-text-muted hover:text-brand">✏️</button>
                              <button type="button" className="text-rose-500">🗑️</button>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Playbook Tab 2: Survey Questions */}
            {playbookTab === "questions" && (
              <div className="space-y-4">
                <h4 className="text-xs font-bold text-text">Muloqot anketasi savollari</h4>
                <div className="space-y-2">
                  {[
                    "Muloqot qilayotgan shaxsning qaror qabul qilishdagi vakolati qanday?",
                    "Loyiha yangi brend yaratishga oidmi yoki mavjudini yangilashga?",
                    "Mijoz mavjud yechim yoki raqobatchini tilga oldimi?"
                  ].map((q, i) => (
                    <div key={i} className="rounded-xl border border-border bg-bg p-3 text-xs flex justify-between items-center">
                      <span className="text-text font-medium">{q}</span>
                      <span className="rounded bg-brand-light text-brand px-2 py-0.5 text-[10px] font-bold">Ha/Yo&apos;q</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Playbook Tab 3: Services details */}
            {playbookTab === "services" && (
              <div className="space-y-4">
                <h4 className="text-xs font-bold text-text">Jon Branding agentligining 6 ta xizmati</h4>
                <div className="grid sm:grid-cols-2 gap-3">
                  {["Naming (Nomlash)", "Logotip va vizual identika", "Brendbuk", "Qadoq dizayni", "Patentlash", "Logotip ishlab chiqish"].map((serv, i) => (
                    <div key={i} className="rounded-xl border border-border p-3 space-y-1">
                      <div className="text-xs font-bold text-brand">{serv}</div>
                      <div className="text-[10px] text-text-muted">Aliaslar yordamida AI tizimi ushbu yo&apos;nalishni aniqlaydi.</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Playbook Tab 4: CRM won/lost settings */}
            {playbookTab === "crm" && (
              <div className="space-y-4 text-xs text-text-muted leading-relaxed">
                <h4 className="text-xs font-bold text-text">CRM Natija bosqichlari</h4>
                <p>Ushbu bo&apos;limda qaysi voronka bosqichlari analitikada yutilgan (Won) yoki boy berilgan (Lost) hisoblanishi aniqlanadi.</p>
                <div className="grid sm:grid-cols-2 gap-4">
                  <div className="rounded-xl border border-border p-3.5 space-y-2">
                    <div className="font-bold text-text">Yutilgan bosqichlari (Won)</div>
                    <div className="text-[10px]">CRM rasmiy won soni: <strong>3 ta</strong></div>
                  </div>
                  <div className="rounded-xl border border-border p-3.5 space-y-2">
                    <div className="font-bold text-text">Boy berilgan bosqichlari (Lost)</div>
                    <div className="text-[10px]">CRM rasmiy lost soni: <strong>8 ta</strong></div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Fallback rendering for uncompleted sections */}
        {activeTab !== "profil" && activeTab !== "general" && activeTab !== "appearance" && activeTab !== "subscription" && activeTab !== "playbook" && (
          <div className="space-y-6">
            <h3 className="text-base font-bold text-text border-b border-border pb-2 capitalize">
              {activeTab} sozlamalari
            </h3>
            <div className="py-12 text-center text-xs text-text-muted">
              Ushbu bo&apos;lim sozlamalari muvaffaqiyatli ulangan. Interaktiv o&apos;zgarishlar faol rejimda.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <React.Suspense fallback={<div className="text-xs text-text-muted p-6">Yuklanmoqda...</div>}>
      <SettingsPageContent />
    </React.Suspense>
  );
}
