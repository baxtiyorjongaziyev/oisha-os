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
      <header className="sticky top-0 z-40 flex h-16 w-full items-center justify-between border-b border-[var(--border-default)] bg-[var(--bg-glass)] px-6 backdrop-blur-xl transition-all duration-200">
        {/* Left Section: Menu Toggle & Business Selector */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            aria-label="Menyuni almashtirish"
            className="flex h-9 w-9 items-center justify-center rounded-xl text-[var(--text-secondary)] hover:bg-[var(--bg-surface-subtle)] hover:text-[var(--text-primary)] active:scale-95 transition-all focus:outline-none"
          >
            <svg aria-hidden="true" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>

          {/* Business Switcher Pill */}
          <div className="relative">
            <button
              onClick={() => setBusinessDropdownOpen(!businessDropdownOpen)}
              className="flex items-center gap-2 rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface-subtle)] px-3 py-1.5 text-xs font-semibold text-[var(--text-primary)] hover:bg-[var(--bg-surface-active)] transition-all active:scale-[0.98]"
            >
              <span className="flex h-2 w-2 rounded-full bg-[var(--accent-primary)]"></span>
              <span className="max-w-[140px] truncate">{currentBusiness}</span>
              <svg aria-hidden="true" className="h-3.5 w-3.5 text-[var(--text-tertiary)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {businessDropdownOpen && (
              <div className="absolute left-0 mt-2 w-64 rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-1.5 shadow-xl animate-fade-in z-50">
                <div className="px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider text-[var(--text-tertiary)]">
                  Mavjud Loyihalar
                </div>
                <div className="space-y-0.5">
                  {businesses.map((b) => (
                    <button
                      key={b.name}
                      onClick={() => {
                        setCurrentBusiness(b.name);
                        setBusinessDropdownOpen(false);
                      }}
                      className={`flex w-full items-center justify-between rounded-xl px-3 py-2 text-left text-xs transition-colors ${
                        currentBusiness === b.name
                          ? "bg-[var(--accent-primary-light)] text-[var(--accent-primary-on-light)] font-bold"
                          : "text-[var(--text-primary)] hover:bg-[var(--bg-surface-subtle)]"
                      }`}
                    >
                      <span>{b.name}</span>
                      <span className="text-[10px] text-[var(--text-tertiary)] font-mono">{b.deals}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Center: Linear/Raycast Style Omnibar */}
        <div className="flex-1 max-w-xl mx-4 hidden md:block">
          <button
            onClick={() => setSearchOpen(true)}
            className="flex w-full items-center justify-between rounded-xl bg-[var(--bg-surface-subtle)] px-3.5 py-2 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-surface-active)] border border-[var(--border-default)] transition-all shadow-xs"
          >
            <div className="flex items-center gap-2.5">
              <svg aria-hidden="true" className="h-4 w-4 text-[var(--text-tertiary)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <span>Lidlar, hisobotlar yoki AI buyruqlarini qidirish...</span>
            </div>
            <kbd className="flex h-5 items-center rounded-md bg-[var(--bg-surface)] px-1.5 font-mono text-[9px] font-bold text-[var(--text-tertiary)] border border-[var(--border-default)]">
              ⌘K
            </kbd>
          </button>
        </div>

        {/* Right Section: Actions & Avatar */}
        <div className="flex items-center gap-2">
          {/* AI Trigger */}
          <button
            onClick={() => setBugReportOpen(true)}
            className="flex items-center gap-1.5 rounded-xl bg-[var(--accent-purple-light)] px-3 py-1.5 text-xs font-bold text-[#7c3aed] dark:text-[#c084fc] hover:opacity-90 active:scale-95 transition-all"
          >
            <span>✨</span>
            <span className="hidden sm:inline">AI Buyruq</span>
          </button>

          {/* Theme Toggle */}
          <button
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            className="flex h-9 w-9 items-center justify-center rounded-xl text-[var(--text-secondary)] hover:bg-[var(--bg-surface-subtle)] hover:text-[var(--text-primary)] active:scale-95 transition-all"
            aria-label="Rejimni almashtirish"
          >
            {theme === "dark" ? (
              <svg aria-hidden="true" className="h-4.5 w-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707m0-12.728l.707.707m12.728 12.728l.707-.707M12 8a4 4 0 100 8 4 4 0 000-8z" />
              </svg>
            ) : (
              <svg aria-hidden="true" className="h-4.5 w-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
              </svg>
            )}
          </button>

          {/* Notifications */}
          <div className="relative">
            <button
              onClick={() => setNotificationsOpen(!notificationsOpen)}
              className="relative flex h-9 w-9 items-center justify-center rounded-xl text-[var(--text-secondary)] hover:bg-[var(--bg-surface-subtle)] hover:text-[var(--text-primary)] active:scale-95 transition-all"
              aria-label="Bildirishnomalar"
            >
              <svg aria-hidden="true" className="h-4.5 w-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
              </svg>
              {alertsCount > 0 && (
                <span className="absolute right-2 top-2 flex h-2 w-2 rounded-full bg-[#dc2626]"></span>
              )}
            </button>

            {notificationsOpen && (
              <div className="absolute right-0 mt-2 w-80 rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-3 shadow-xl animate-fade-in z-50">
                <div className="flex items-center justify-between border-b border-[var(--border-default)] pb-2 px-2">
                  <span className="text-xs font-bold text-[var(--text-primary)]">Bildirishnomalar</span>
                  <span className="text-[10px] font-mono text-[var(--text-tertiary)]">Barchasi o&apos;qilgan</span>
                </div>
                <div className="py-6 text-center text-xs text-[var(--text-secondary)]">
                  Yangi shoshilinch bildirishnomalar yo&apos;q.
                </div>
              </div>
            )}
          </div>

          {/* User Profile Avatar */}
          <div className="relative">
            <button
              onClick={() => setAvatarDropdownOpen(!avatarDropdownOpen)}
              className="flex h-8.5 w-8.5 items-center justify-center rounded-xl bg-gradient-to-tr from-[#0284c7] to-[#7c3aed] text-xs font-bold text-white shadow-xs ring-2 ring-[var(--border-subtle)] hover:scale-105 transition-transform"
            >
              B
            </button>

            {avatarDropdownOpen && (
              <div className="absolute right-0 mt-2 w-60 rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-2 shadow-2xl animate-fade-in z-50">
                <div className="border-b border-[var(--border-default)] pb-2.5 px-2">
                  <div className="text-xs font-bold text-[var(--text-primary)]">Baxtiyorjon Gaziyev</div>
                  <div className="text-[10px] text-[var(--text-secondary)]">Agency Owner & Strategist</div>
                  <div className="mt-1 inline-block rounded-md bg-[var(--accent-primary-light)] px-2 py-0.5 text-[9px] font-bold text-[var(--accent-primary-on-light)]">
                    Jon Branding agency
                  </div>
                </div>
                <div className="mt-1.5 space-y-0.5">
                  <Link
                    href="/settings"
                    onClick={() => setAvatarDropdownOpen(false)}
                    className="flex w-full items-center rounded-xl px-2.5 py-1.5 text-xs font-semibold text-[var(--text-primary)] hover:bg-[var(--bg-surface-subtle)] transition-colors"
                  >
                    ⚙️ Tizim Sozlamalari
                  </Link>
                  <button
                    onClick={() => {
                      alert("Tizimdan chiqildi!");
                      setAvatarDropdownOpen(false);
                    }}
                    className="flex w-full items-center rounded-xl px-2.5 py-1.5 text-xs font-semibold text-[#dc2626] hover:bg-[#fee2e2] dark:hover:bg-[#7f1d1d]/30 transition-colors"
                  >
                    🚪 Chiqish
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Global Linear Search Command Modal */}
      {searchOpen && (
        <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 backdrop-blur-sm p-4 pt-20">
          <div className="w-full max-w-xl rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-4 shadow-2xl animate-fade-in">
            <div className="flex items-center gap-3 border-b border-[var(--border-default)] pb-3 px-2">
              <svg aria-hidden="true" className="h-5 w-5 text-[var(--text-tertiary)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                ref={searchInputRef}
                type="text"
                autoFocus
                placeholder="Lid, mijoz, tranzaksiya yoki buyruq..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="flex-1 bg-transparent text-sm text-[var(--text-primary)] focus:outline-none font-medium"
              />
              <kbd className="rounded bg-[var(--bg-surface-subtle)] px-2 py-0.5 text-[10px] font-bold text-[var(--text-tertiary)]">
                ESC
              </kbd>
            </div>
            <div className="py-8 text-center text-xs text-[var(--text-secondary)]">
              Qidirish uchun kalit so&apos;z kiriting... (masalan: &quot;Apex Logistics&quot; yoki &quot;Kirim&quot;)
            </div>
          </div>
        </div>
      )}

      {/* AI Command Console Modal */}
      {bugReportOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-6 shadow-2xl animate-fade-in">
            <div className="flex items-center gap-2">
              <span className="text-xl">✨</span>
              <h3 className="text-base font-bold text-[var(--text-primary)]">
                Oisha AI Command Console
              </h3>
            </div>
            <p className="text-xs text-[var(--text-secondary)] mt-1">
              Oisha-OS agentlariga to&apos;g&apos;ridan-to&apos;g&apos;ri buyruq yoki vazifa yuboring.
            </p>

            <form onSubmit={handleBugSubmit} className="mt-4 space-y-4">
              <div className="grid grid-cols-3 gap-2">
                {["idea", "request", "bug"].map((cat) => (
                  <button
                    key={cat}
                    type="button"
                    onClick={() => setBugCategory(cat)}
                    className={`rounded-xl py-2 text-xs font-semibold border transition-all ${
                      bugCategory === cat
                        ? "bg-[var(--accent-primary)] text-white border-[var(--accent-primary)] shadow-xs"
                        : "bg-[var(--bg-surface-subtle)] text-[var(--text-primary)] border-transparent hover:bg-[var(--bg-surface-active)]"
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
                className="w-full rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface-subtle)] p-3 text-xs text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]"
              ></textarea>

              {bugSuccess && (
                <div className="rounded-xl bg-[#d1fae5] p-2.5 text-center text-xs font-bold text-[#065f46] dark:bg-[#064e3b] dark:text-[#34d399]">
                  ✓ Buyruq Oisha-OS agentlariga yuborildi!
                </div>
              )}

              {bugError && (
                <div className="rounded-xl bg-[#fee2e2] p-2.5 text-center text-xs font-bold text-[#dc2626] dark:bg-[#7f1d1d]/30">
                  {bugError}
                </div>
              )}

              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setBugReportOpen(false)}
                  className="rounded-xl px-4 py-2 text-xs font-semibold text-[var(--text-secondary)] hover:bg-[var(--bg-surface-subtle)]"
                >
                  Yopish
                </button>
                <button
                  type="submit"
                  className="rounded-xl bg-[var(--accent-primary)] text-white px-5 py-2 text-xs font-bold shadow-xs hover:opacity-90"
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
