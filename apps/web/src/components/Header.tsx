"use client";

import React, { useState } from "react";
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
    setAlerts,
    alertsCount
  } = useTheme();

  // Local state for search query and bug report
  const [searchQuery, setSearchQuery] = useState("");
  const [bugCategory, setBugCategory] = useState("idea");
  const [bugText, setBugText] = useState("");
  const [bugSuccess, setBugSuccess] = useState(false);
  const [bugError, setBugError] = useState("");
  const [businessDropdownOpen, setBusinessDropdownOpen] = useState(false);
  const [avatarDropdownOpen, setAvatarDropdownOpen] = useState(false);
  const [newBusinessModalOpen, setNewBusinessModalOpen] = useState(false);
  const [newBusinessName, setNewBusinessName] = useState("");

  const businesses = [
    { name: "Jon Branding agency", status: "Muzlatilgan" },
    { name: "Jon Academy", status: "Faol" }
  ];

  const searchResults: {
    contacts: Array<{ name: string; role: string; phone: string }>;
    leads: Array<{ name: string; stage: string; id: string }>;
  } | null = searchQuery.trim() ? { contacts: [], leads: [] } : null;
  const searchError = searchQuery.trim() ? "Real CRM qidiruv endpointi sozlanmagan." : "";

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

  const handleAddBusiness = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newBusinessName.trim()) return;
    setCurrentBusiness(newBusinessName);
    setNewBusinessName("");
    setNewBusinessModalOpen(false);
    setBusinessDropdownOpen(false);
  };

  return (
    <>
      <header className="sticky top-0 z-40 flex h-16 w-full items-center justify-between border-b border-border bg-bg-card/85 px-6 backdrop-blur transition-all duration-300">
        {/* Left Section: Menu Toggle & Title */}
        <div className="flex items-center gap-4">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            aria-label="Sidebar menyusini almashtirish"
            className="rounded-xl p-2 text-text-muted hover:bg-brand-light hover:text-brand active:scale-[0.98] transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1"
          >
            <svg aria-hidden="true" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>

          <div className="hidden sm:block">
            <span className="text-xs font-semibold uppercase tracking-[0.2em] text-brand">
              METASELL
            </span>
            <h2 className="text-sm font-semibold text-text mt-[-2px]">Sotuv Tahlil Tizimi</h2>
          </div>
        </div>

        {/* Center/Right Section: Interactive controls */}
        <div className="flex items-center gap-2 md:gap-4">
          {/* Quick Search Trigger */}
          <button
            onClick={() => setSearchOpen(true)}
            aria-label="Qidirish"
            className="flex items-center gap-2 rounded-2xl border border-border bg-bg px-3 py-2 text-xs text-text-muted hover:border-brand-hover hover:bg-brand-light/30 active:scale-[0.98] transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1 w-36 md:w-56"
          >
            <svg aria-hidden="true" className="h-4 w-4 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <span className="flex-1 text-left hidden md:inline">Qidirish...</span>
            <kbd className="hidden md:inline-flex h-5 items-center gap-1 rounded border border-border bg-bg-card px-1.5 font-mono text-[10px] font-medium text-text-muted">
              /
            </kbd>
          </button>

          {/* Business Switcher Dropdown */}
          <div className="relative">
            <button
              onClick={() => setBusinessDropdownOpen(!businessDropdownOpen)}
              aria-expanded={businessDropdownOpen}
              aria-label="Biznesni o'zgartirish menyusi"
              className="flex items-center gap-1.5 rounded-2xl bg-brand-light px-3 py-1.5 text-xs font-medium text-brand hover:bg-brand-light/80 active:scale-[0.98] transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1"
            >
              <svg aria-hidden="true" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
              </svg>
              <span className="max-w-[120px] truncate">{currentBusiness}</span>
              <svg aria-hidden="true" className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {businessDropdownOpen && (
              <div className="absolute right-0 mt-2 w-56 rounded-2xl border border-border bg-bg-popover p-2 shadow-xl animate-fade-in z-50">
                <div
                  id="businesses-heading"
                  className="px-3 py-1.5 text-[10px] font-semibold text-text-muted uppercase tracking-wider"
                >
                  Mavjud Bizneslar
                </div>
                <ul aria-labelledby="businesses-heading" className="space-y-0.5">
                  {businesses.map((b) => (
                    <li key={b.name}>
                      <button
                        onClick={() => {
                          setCurrentBusiness(b.name);
                          setBusinessDropdownOpen(false);
                        }}
                        aria-current={currentBusiness === b.name ? "true" : undefined}
                        className={`flex w-full items-center justify-between rounded-xl px-3 py-2 text-left text-xs transition-colors hover:bg-bg focus:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1 ${
                          currentBusiness === b.name
                            ? "bg-brand-light font-semibold text-brand"
                            : "text-text"
                        }`}
                      >
                        <span className="flex items-center gap-2">
                          {currentBusiness === b.name && (
                            <svg aria-hidden="true" className="h-3.5 w-3.5 text-brand shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="3">
                              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                            </svg>
                          )}
                          <span className={currentBusiness !== b.name ? "pl-5.5" : ""}>
                            {b.name}
                          </span>
                        </span>
                        <span
                          className={`rounded px-1.5 py-0.5 text-[9px] font-bold shrink-0 ${
                            b.status === "Muzlatilgan"
                              ? "bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:text-rose-400"
                              : "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400"
                          }`}
                        >
                          {b.status}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
                <div className="border-t border-border my-1"></div>
                <button
                  onClick={() => {
                    setNewBusinessModalOpen(true);
                    setBusinessDropdownOpen(false);
                  }}
                  className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-xs text-brand font-medium hover:bg-brand-light transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1"
                >
                  <svg aria-hidden="true" className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
                  </svg>
                  Yangi biznes qo&apos;shish
                </button>
              </div>
            )}
          </div>

          {/* Theme Toggle */}
          <button
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            aria-label="Tungi rejimni yoqish/o'chirish"
            className="rounded-xl p-2 text-text-muted hover:bg-brand-light hover:text-brand active:scale-[0.98] transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1"
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

          {/* Notification Bell */}
          <div className="relative">
            <button
              onClick={() => setNotificationsOpen(!notificationsOpen)}
              aria-label="Bildirishnomalar"
              className="relative rounded-xl p-2 text-text-muted hover:bg-brand-light hover:text-brand active:scale-[0.98] transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1"
            >
              <svg aria-hidden="true" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
              </svg>
              {alertsCount > 0 && (
                <span className="absolute right-1.5 top-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-rose-500 text-[9px] font-bold text-white ring-2 ring-bg-card">
                  {alertsCount}
                </span>
              )}
            </button>

            {notificationsOpen && (
              <div className="absolute right-0 mt-2 w-80 rounded-2xl border border-border bg-bg-popover p-2 shadow-xl animate-fade-in z-50">
                <div className="flex items-center justify-between border-b border-border px-3 py-2">
                  <span className="text-xs font-semibold text-text">Ogohlantirishlar</span>
                  <Link
                    href="/alerts"
                    onClick={() => setNotificationsOpen(false)}
                    className="text-[10px] font-semibold text-brand hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1 rounded-sm"
                  >
                    Hammasini ko&apos;rish
                  </Link>
                </div>
                <div className="max-h-60 overflow-y-auto p-1">
                  {alerts.map((a) => (
                    <div
                      key={a.id}
                      className="group flex gap-2.5 rounded-xl p-2.5 hover:bg-bg transition-colors duration-200"
                    >
                      <div
                        className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                          a.type === "error"
                            ? "bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:text-rose-400"
                            : "bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-400"
                        }`}
                      >
                        {a.managerAvatar}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] font-bold text-text-muted">
                            {a.typeLabel}
                          </span>
                          <span className="text-[9px] text-text-muted">{a.time}</span>
                        </div>
                        <h4 className="text-xs font-semibold text-text truncate mt-0.5">
                          {a.title}
                        </h4>
                        <p className="text-[10px] text-text-muted line-clamp-2 mt-0.5">
                          {a.description}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Bug Report button */}
          <button
            onClick={() => setBugReportOpen(true)}
            aria-label="Bug yoki taklif yuborish"
            className="rounded-xl p-2 text-text-muted hover:bg-brand-light hover:text-brand active:scale-[0.98] transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1"
          >
            <svg aria-hidden="true" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </button>

          {/* User Profile Avatar Dropdown */}
          <div className="relative">
            <button
              onClick={() => setAvatarDropdownOpen(!avatarDropdownOpen)}
              aria-expanded={avatarDropdownOpen}
              aria-label="Foydalanuvchi profili menyusi"
              className="flex h-8 w-8 items-center justify-center rounded-full bg-brand text-xs font-bold text-white ring-2 ring-brand/10 hover:scale-105 transition-transform focus:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1"
            >
              B
              <span className="absolute bottom-0 right-0 h-2.5 w-2.5 rounded-full bg-emerald-500 ring-2 ring-bg-card"></span>
            </button>

            {avatarDropdownOpen && (
              <div className="absolute right-0 mt-2 w-56 rounded-2xl border border-border bg-bg-popover p-2 shadow-xl animate-fade-in z-50">
                <div className="px-3 py-2 border-b border-border">
                  <div className="text-xs font-bold text-text">Baxtiyorjon</div>
                  <div className="text-[10px] text-text-muted mt-0.5">Rahbar</div>
                  <div className="text-[9px] bg-brand-light text-brand px-1.5 py-0.5 rounded font-medium inline-block mt-1">
                    Jon Branding agency
                  </div>
                </div>
                <div className="p-1">
                  <Link
                    href="/settings?tab=profil"
                    onClick={() => setAvatarDropdownOpen(false)}
                    className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-xs text-text hover:bg-bg transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1"
                  >
                    Profil
                  </Link>
                  <Link
                    href="/settings"
                    onClick={() => setAvatarDropdownOpen(false)}
                    className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-xs text-text hover:bg-bg transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1"
                  >
                    Sozlamalar
                  </Link>
                  <div className="border-t border-border my-1"></div>
                  <button
                    onClick={() => {
                      alert("Tizimdan chiqildi!");
                      setAvatarDropdownOpen(false);
                    }}
                    className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-xs text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-950/20 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-500 focus-visible:ring-offset-1"
                  >
                    Chiqish
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Global Interactive Search Modal */}
      {searchOpen && (
        <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 backdrop-blur-sm p-4 pt-20">
          <div className="w-full max-w-xl rounded-3xl border border-border bg-bg-popover p-4 shadow-2xl animate-fade-in">
            <div className="flex items-center gap-3 border-b border-border pb-3">
              <svg aria-hidden="true" className="h-5 w-5 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                id="search-input"
                type="text"
                autoFocus
                aria-label="Qidiruv so'rovi"
                placeholder="Ism, telefon raqami yoki kalit so'zni yozing... (masalan: 'Baxtiyorjon')"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="flex-1 bg-transparent text-sm text-text focus:outline-none"
              />
              {searchQuery && (
                <button
                  type="button"
                  aria-label="Qidiruvni tozalash"
                  onClick={() => {
                    setSearchQuery("");
                    document.getElementById("search-input")?.focus();
                  }}
                  className="rounded-full p-1 text-text-muted hover:bg-bg transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1"
                >
                  <svg aria-hidden="true" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              )}
              <button
                onClick={() => setSearchOpen(false)}
                aria-label="Qidiruvni yopish"
                className="rounded-lg p-1.5 text-text-muted hover:bg-bg transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1"
              >
                ESC
              </button>
            </div>

            {/* Results output */}
            <div className="mt-4 max-h-80 overflow-y-auto">
              {searchQuery.trim() === "" ? (
                <div className="py-6 text-center text-xs text-text-muted">
                  Qidiruv natijalarini ko&apos;rish uchun biror narsa kiriting...
                </div>
              ) : searchError ? (
                <div className="py-6 text-center text-xs text-amber-700">{searchError}</div>
              ) : searchResults ? (
                <div className="space-y-4">
                  <div>
                    <h4 className="text-[10px] font-bold text-text-muted uppercase tracking-wider px-2">
                      Kontaktlar ({searchResults.contacts.length} ta topildi)
                    </h4>
                    <div className="mt-1 space-y-1">
                      {searchResults.contacts.map((c, i) => (
                        <div
                          key={i}
                          className="flex items-center justify-between rounded-xl p-2 hover:bg-bg transition-colors cursor-pointer"
                        >
                          <div>
                            <div className="text-xs font-semibold text-text">{c.name}</div>
                            <div className="text-[10px] text-text-muted">{c.role}</div>
                          </div>
                          <div className="text-xs text-brand font-medium">{c.phone}</div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div>
                    <h4 className="text-[10px] font-bold text-text-muted uppercase tracking-wider px-2">
                      Lidlar ({searchResults.leads.length} ta topildi)
                    </h4>
                    <div className="mt-1 space-y-1">
                      {searchResults.leads.map((l) => (
                        <Link
                          href={`/crm/leads/${l.id}`}
                          key={l.id}
                          onClick={() => setSearchOpen(false)}
                          className="flex items-center justify-between rounded-xl p-2 hover:bg-bg transition-colors cursor-pointer block"
                        >
                          <div>
                            <div className="text-xs font-semibold text-text">{l.name}</div>
                            <div className="text-[10px] text-text-muted">Bosqich: {l.stage}</div>
                          </div>
                          <span className="rounded bg-brand-light px-2 py-0.5 text-[10px] font-bold text-brand">
                            Ko&apos;rish
                          </span>
                        </Link>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="py-6 text-center text-xs text-text-muted">
                  Hech narsa topilmadi. &quot;Baxtiyorjon&quot; deb yozib ko&apos;ring.
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Global Interactive Bug Report Modal */}
      {bugReportOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-3xl border border-border bg-bg-popover p-6 shadow-2xl animate-fade-in">
            <h3 className="text-lg font-bold text-text">
              Tizim bo&apos;yicha taklif yoki xatolik yuborish
            </h3>
            <p className="text-xs text-text-muted mt-1">
              Metasell platformasini yanada yaxshilash uchun bizga yordam bering.
            </p>

            <form onSubmit={handleBugSubmit} className="mt-4 space-y-4">
              <div>
                <label
                  id="bug-category-label"
                  className="text-[10px] font-bold text-text-muted uppercase block"
                >
                  Turi
                </label>
                <div
                  role="group"
                  aria-labelledby="bug-category-label"
                  className="grid grid-cols-3 gap-2 mt-1"
                >
                  {["idea", "request", "bug"].map((cat) => (
                    <button
                      key={cat}
                      type="button"
                      onClick={() => setBugCategory(cat)}
                      aria-pressed={bugCategory === cat}
                      className={`rounded-xl py-2 text-xs font-medium border transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1 ${
                        bugCategory === cat
                          ? "bg-brand text-white border-brand shadow-md"
                          : "bg-bg text-text border-border hover:bg-brand-light"
                      }`}
                    >
                      {cat === "idea" ? "G'oya" : cat === "request" ? "Talab" : "Xatolik"}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label
                  htmlFor="bug-description"
                  className="text-[10px] font-bold text-text-muted uppercase block"
                >
                  Tavsif
                </label>
                <textarea
                  id="bug-description"
                  required
                  rows={4}
                  value={bugText}
                  onChange={(e) => setBugText(e.target.value)}
                  placeholder="G'oyangiz yoki yuzaga kelgan texnik muammoni batafsil tasvirlab bering..."
                  className="w-full rounded-2xl border border-border bg-bg p-3 text-xs text-text focus:border-brand-hover focus:outline-none mt-1"
                ></textarea>
              </div>

              <div className="rounded-2xl bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900/40 p-3 flex gap-2.5">
                <svg aria-hidden="true" className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span className="text-[10px] text-amber-800 dark:text-amber-400">
                  <strong>Eslatma:</strong> Muammoni tezroq hal qilishimiz uchun joriy biznes
                  konteksti (Jon Branding agency ma&apos;lumotlari) xabarga qo&apos;shib yuboriladi.
                </span>
              </div>

              {bugSuccess && (
                <div className="text-center text-xs font-bold text-emerald-600 bg-emerald-50 dark:bg-emerald-950/20 py-2 rounded-xl border border-emerald-200">
                  Xabar jo&apos;natildi! Rahmat!
                </div>
              )}
              {bugError && (
                <div className="text-center text-xs font-bold text-rose-600 bg-rose-50 py-2 border border-rose-200">
                  Xabar yuborilmadi: {bugError}
                </div>
              )}

              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setBugReportOpen(false)}
                  className="rounded-xl px-4 py-2 text-xs font-medium text-text-muted hover:bg-bg focus:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1"
                >
                  Bekor qilish
                </button>
                <button
                  type="submit"
                  className="rounded-xl bg-brand px-4 py-2 text-xs font-medium text-white hover:bg-brand-hover shadow-md transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1"
                >
                  Yuborish
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* New Business Modal */}
      {newBusinessModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="w-full max-w-sm rounded-3xl border border-border bg-bg-popover p-6 shadow-2xl animate-fade-in">
            <h3 className="text-base font-bold text-text">Yangi biznes qo&apos;shish</h3>
            <p className="text-xs text-text-muted mt-1">
              Platformaga yangi sotuv voronkasi qo&apos;shish uchun nom tanlang.
            </p>

            <form onSubmit={handleAddBusiness} className="mt-4 space-y-4">
              <input
                required
                type="text"
                aria-label="Yangi biznes nomi"
                value={newBusinessName}
                onChange={(e) => setNewBusinessName(e.target.value)}
                placeholder="Masalan: Jon Marketing, Jon Academy..."
                className="w-full rounded-2xl border border-border bg-bg p-3 text-xs text-text focus:border-brand-hover focus:outline-none"
              />
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setNewBusinessModalOpen(false)}
                  className="rounded-xl px-4 py-2 text-xs font-medium text-text-muted hover:bg-bg focus:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1"
                >
                  Bekor qilish
                </button>
                <button
                  type="submit"
                  className="rounded-xl bg-brand px-4 py-2 text-xs font-medium text-white hover:bg-brand-hover shadow-md focus:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1"
                >
                  Qo&apos;shish
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
