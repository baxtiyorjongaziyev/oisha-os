"use client";

import React, { useState, useRef } from "react";
import Link from "next/link";
import { useTheme } from "@/context/ThemeContext";

export default function Header() {
  const {
    theme,
    setTheme,
    currentBusiness,
    setCurrentBusiness,
    sidebarOpen,
    setSidebarOpen,
    searchOpen,
    setSearchOpen,
    bugReportOpen,
    setBugReportOpen,
    notificationsOpen,
    setNotificationsOpen,
    alerts,
    alertsCount,
  } = useTheme();

  const [searchQuery, setSearchQuery] = useState("");
  const [bugCategory, setBugCategory] = useState("idea");
  const [bugText, setBugText] = useState("");
  const [bugSuccess, setBugSuccess] = useState(false);
  const [bugError, setBugError] = useState("");
  const [businessDropdownOpen, setBusinessDropdownOpen] = useState(false);
  const [avatarDropdownOpen, setAvatarDropdownOpen] = useState(false);

  const searchInputRef = useRef<HTMLInputElement>(null);

  const businesses = [
    { name: "Jon Branding agency", status: "Faol", deals: "487 bitim" },
    { name: "Jon Academy", status: "Faol", deals: "128 o'quvchi" },
  ];

  const handleBugSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!bugText.trim()) return;
    setBugSuccess(false);
    setBugError("");
    try {
      const response = await fetch("/api/oisha/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category: bugCategory, text: bugText, business: currentBusiness }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
      setBugSuccess(true);
      setBugText("");
    } catch (error) {
      setBugError(error instanceof Error ? error.message : "Xabar yuborilmadi");
    }
  };

  return (
    <>
      <header className="sticky top-0 z-40 flex h-16 w-full items-center justify-between border-b border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface)]/90 px-6 backdrop-blur-md transition-all duration-200">
        {/* Left Section: Menu Toggle & Title */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            aria-label="Menyuni almashtirish"
            className="flex h-10 w-10 items-center justify-center rounded-full text-[var(--md-sys-color-on-surface-variant)] hover:bg-[var(--md-sys-color-surface-container)] hover:text-[var(--md-sys-color-on-surface)] active:scale-95 transition-all focus:outline-none"
          >
            <svg aria-hidden="true" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>

          {/* Business Switcher Pill (Google Cloud project selector style) */}
          <div className="relative">
            <button
              onClick={() => setBusinessDropdownOpen(!businessDropdownOpen)}
              className="flex items-center gap-2 rounded-full border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface-container-low)] px-3.5 py-1.5 text-xs font-semibold text-[var(--md-sys-color-on-surface)] hover:bg-[var(--md-sys-color-surface-container)] transition-all active:scale-[0.98]"
            >
              <span className="flex h-2 w-2 rounded-full bg-[#0b57d0] dark:bg-[#a8c7fa]"></span>
              <span className="max-w-[140px] truncate">{currentBusiness}</span>
              <svg aria-hidden="true" className="h-3.5 w-3.5 text-[var(--md-sys-color-on-surface-variant)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {businessDropdownOpen && (
              <div className="absolute left-0 mt-2 w-64 rounded-3xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface)] p-2 shadow-xl animate-fade-in z-50">
                <div className="px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider text-[var(--md-sys-color-on-surface-variant)]">
                  Mavjud Loyihalar
                </div>
                <div className="space-y-1">
                  {businesses.map((b) => (
                    <button
                      key={b.name}
                      onClick={() => {
                        setCurrentBusiness(b.name);
                        setBusinessDropdownOpen(false);
                      }}
                      className={`flex w-full items-center justify-between rounded-2xl px-3 py-2 text-left text-xs transition-colors ${
                        currentBusiness === b.name
                          ? "bg-[#d3e3fd] text-[#041e49] font-bold dark:bg-[#004a77] dark:text-[#c2e7ff]"
                          : "text-[var(--md-sys-color-on-surface)] hover:bg-[var(--md-sys-color-surface-container)]"
                      }`}
                    >
                      <span>{b.name}</span>
                      <span className="text-[10px] text-[var(--md-sys-color-on-surface-variant)] font-mono">{b.deals}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Center: Google Search Omnibar */}
        <div className="flex-1 max-w-xl mx-4 hidden md:block">
          <button
            onClick={() => setSearchOpen(true)}
            className="flex w-full items-center justify-between rounded-full bg-[var(--md-sys-color-surface-container)] px-4 py-2 text-xs text-[var(--md-sys-color-on-surface-variant)] hover:bg-[var(--md-sys-color-surface-container-high)] border border-[var(--md-sys-color-outline-variant)] transition-all shadow-inner"
          >
            <div className="flex items-center gap-2.5">
              <svg aria-hidden="true" className="h-4 w-4 text-[var(--md-sys-color-on-surface-variant)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <span>Lidlar, tranzaksiyalar yoki buyruqlarni qidirish...</span>
            </div>
            <kbd className="flex h-5 items-center rounded-full bg-[var(--md-sys-color-surface)] px-2 font-mono text-[10px] font-bold text-[var(--md-sys-color-on-surface-variant)] border border-[var(--md-sys-color-outline-variant)]">
              /
            </kbd>
          </button>
        </div>

        {/* Right Section: Actions & Google Profile */}
        <div className="flex items-center gap-2">
          {/* AI Trigger (Gemini Sparkle Button) */}
          <button
            onClick={() => setBugReportOpen(true)}
            className="flex items-center gap-1.5 rounded-full bg-[#ede9fe] dark:bg-[#4a287a] px-3.5 py-1.5 text-xs font-bold text-[#7c3aed] dark:text-[#d0bcff] hover:opacity-90 active:scale-95 transition-all"
          >
            <span>✨</span>
            <span className="hidden sm:inline">AI Buyruq</span>
          </button>

          {/* Theme Toggle */}
          <button
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            className="flex h-10 w-10 items-center justify-center rounded-full text-[var(--md-sys-color-on-surface-variant)] hover:bg-[var(--md-sys-color-surface-container)] hover:text-[var(--md-sys-color-on-surface)] active:scale-95 transition-all"
            aria-label="Rejimni almashtirish"
          >
            {theme === "dark" ? (
              <svg aria-hidden="true" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707m0-12.728l.707.707m12.728 12.728l.707-.707M12 8a4 4 0 100 8 4 4 0 000-8z" />
              </svg>
            ) : (
              <svg aria-hidden="true" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
              </svg>
            )}
          </button>

          {/* Notifications */}
          <div className="relative">
            <button
              onClick={() => setNotificationsOpen(!notificationsOpen)}
              className="relative flex h-10 w-10 items-center justify-center rounded-full text-[var(--md-sys-color-on-surface-variant)] hover:bg-[var(--md-sys-color-surface-container)] hover:text-[var(--md-sys-color-on-surface)] active:scale-95 transition-all"
              aria-label="Bildirishnomalar"
            >
              <svg aria-hidden="true" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
              </svg>
              {alertsCount > 0 && (
                <span className="absolute right-2 top-2 flex h-2 w-2 rounded-full bg-[#b3261e]"></span>
              )}
            </button>

            {notificationsOpen && (
              <div className="absolute right-0 mt-2 w-80 rounded-3xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface)] p-3 shadow-xl animate-fade-in z-50">
                <div className="flex items-center justify-between border-b border-[var(--md-sys-color-outline)] pb-2 px-2">
                  <span className="text-xs font-bold text-[var(--md-sys-color-on-surface)]">Bildirishnomalar</span>
                  <span className="text-[10px] font-mono text-[var(--md-sys-color-on-surface-variant)]">Barchasi o&apos;qilgan</span>
                </div>
                <div className="py-6 text-center text-xs text-[var(--md-sys-color-on-surface-variant)]">
                  Yangi shoshilinch bildirishnomalar yo&apos;q.
                </div>
              </div>
            )}
          </div>

          {/* Google Account Avatar */}
          <div className="relative">
            <button
              onClick={() => setAvatarDropdownOpen(!avatarDropdownOpen)}
              className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-tr from-[#0b57d0] to-[#7c3aed] text-xs font-bold text-white shadow-sm ring-2 ring-[var(--md-sys-color-surface-container)] hover:scale-105 transition-transform"
            >
              B
            </button>

            {avatarDropdownOpen && (
              <div className="absolute right-0 mt-2 w-60 rounded-3xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface)] p-3 shadow-2xl animate-fade-in z-50">
                <div className="border-b border-[var(--md-sys-color-outline)] pb-3 px-2">
                  <div className="text-xs font-bold text-[var(--md-sys-color-on-surface)]">Baxtiyorjon Gaziyev</div>
                  <div className="text-[10px] text-[var(--md-sys-color-on-surface-variant)]">Agency Owner & Strategist</div>
                  <div className="mt-1 inline-block rounded-full bg-[#d3e3fd] px-2 py-0.5 text-[9px] font-bold text-[#041e49] dark:bg-[#004a77] dark:text-[#c2e7ff]">
                    Jon Branding agency
                  </div>
                </div>
                <div className="mt-2 space-y-1">
                  <Link
                    href="/settings"
                    onClick={() => setAvatarDropdownOpen(false)}
                    className="flex w-full items-center rounded-2xl px-3 py-2 text-xs font-semibold text-[var(--md-sys-color-on-surface)] hover:bg-[var(--md-sys-color-surface-container)] transition-colors"
                  >
                    ⚙️ Tizim Sozlamalari
                  </Link>
                  <button
                    onClick={() => {
                      alert("Tizimdan chiqildi!");
                      setAvatarDropdownOpen(false);
                    }}
                    className="flex w-full items-center rounded-2xl px-3 py-2 text-xs font-semibold text-[#b3261e] hover:bg-[#ffdad6] dark:hover:bg-[#601410] transition-colors"
                  >
                    🚪 Chiqish
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Global Material 3 Search Modal */}
      {searchOpen && (
        <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 backdrop-blur-sm p-4 pt-20">
          <div className="w-full max-w-xl rounded-3xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface)] p-4 shadow-2xl animate-fade-in">
            <div className="flex items-center gap-3 border-b border-[var(--md-sys-color-outline)] pb-3 px-2">
              <svg aria-hidden="true" className="h-5 w-5 text-[var(--md-sys-color-on-surface-variant)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                ref={searchInputRef}
                type="text"
                autoFocus
                placeholder="Lid, mijoz, tranzaksiya yoki buyruq..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="flex-1 bg-transparent text-sm text-[var(--md-sys-color-on-surface)] focus:outline-none"
              />
              <button
                onClick={() => setSearchOpen(false)}
                className="rounded-full bg-[var(--md-sys-color-surface-container)] px-2 py-1 text-[10px] font-bold text-[var(--md-sys-color-on-surface-variant)]"
              >
                ESC
              </button>
            </div>
            <div className="py-8 text-center text-xs text-[var(--md-sys-color-on-surface-variant)]">
              Qidirish uchun kalit so&apos;z kiriting... (masalan: &quot;Apex Logistics&quot; yoki &quot;Kirim&quot;)
            </div>
          </div>
        </div>
      )}

      {/* AI Command / Bug Modal */}
      {bugReportOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-3xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface)] p-6 shadow-2xl animate-fade-in">
            <div className="flex items-center gap-2">
              <span className="text-xl">✨</span>
              <h3 className="text-base font-bold text-[var(--md-sys-color-on-surface)]">
                Oisha AI Command Console
              </h3>
            </div>
            <p className="text-xs text-[var(--md-sys-color-on-surface-variant)] mt-1">
              Oisha-OS agentlariga to&apos;g&apos;ridan-to&apos;g&apos;ri buyruq yoki taklif yuboring.
            </p>

            <form onSubmit={handleBugSubmit} className="mt-4 space-y-4">
              <div className="grid grid-cols-3 gap-2">
                {["idea", "request", "bug"].map((cat) => (
                  <button
                    key={cat}
                    type="button"
                    onClick={() => setBugCategory(cat)}
                    className={`rounded-2xl py-2 text-xs font-semibold border transition-all ${
                      bugCategory === cat
                        ? "bg-[#0b57d0] text-white border-[#0b57d0] shadow-sm dark:bg-[#a8c7fa] dark:text-[#041e49]"
                        : "bg-[var(--md-sys-color-surface-container)] text-[var(--md-sys-color-on-surface)] border-transparent hover:bg-[var(--md-sys-color-surface-container-high)]"
                    }`}
                  >
                    {cat === "idea" ? "G'oya" : cat === "request" ? "Buyruq" : "Xatolik"}
                  </button>
                ))}
              </div>

              <textarea
                required
                rows={4}
                value={bugText}
                onChange={(e) => setBugText(e.target.value)}
                placeholder="Buyruq yoki fikringizni yozing..."
                className="w-full rounded-2xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface-container-low)] p-3 text-xs text-[var(--md-sys-color-on-surface)] focus:outline-none focus:border-[#0b57d0]"
              ></textarea>

              {bugSuccess && (
                <div className="rounded-2xl bg-[#c4eed0] p-2.5 text-center text-xs font-bold text-[#0f5223]">
                  ✓ Buyruq Oisha-OS agentlariga yuborildi!
                </div>
              )}

              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setBugReportOpen(false)}
                  className="rounded-full px-4 py-2 text-xs font-semibold text-[var(--md-sys-color-on-surface-variant)] hover:bg-[var(--md-sys-color-surface-container)]"
                >
                  Yopish
                </button>
                <button
                  type="submit"
                  className="rounded-full bg-[#0b57d0] dark:bg-[#a8c7fa] dark:text-[#041e49] text-white px-5 py-2 text-xs font-bold shadow-md hover:opacity-90"
                >
                  Yuborish
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
