"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "@/context/ThemeContext";
import { motion, AnimatePresence } from "framer-motion";

interface NavItem {
  name: string;
  href: string;
  icon: React.ReactNode;
  badge?: string;
  badgeType?: "live" | "count" | "accent";
}

export default function Sidebar() {
  const pathname = usePathname();
  const { sidebarOpen, setSidebarOpen, setBugReportOpen } = useTheme();

  const navItems: NavItem[] = [
    {
      name: "Boshqaruv markazi",
      href: "/dashboards/home",
      icon: (
        <svg aria-hidden="true" className="h-4.5 w-4.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
        </svg>
      ),
    },
    {
      name: "CRM & Lidlar",
      href: "/crm",
      badge: "487",
      badgeType: "count",
      icon: (
        <svg aria-hidden="true" className="h-4.5 w-4.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
        </svg>
      ),
    },
    {
      name: "Moliya & Kassa",
      href: "/finance",
      badge: "Live",
      badgeType: "live",
      icon: (
        <svg aria-hidden="true" className="h-4.5 w-4.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
    },
    {
      name: "Qo'ng'iroqlar (AI)",
      href: "/calls",
      icon: (
        <svg aria-hidden="true" className="h-4.5 w-4.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.94.725l.548 2.2a1 1 0 01-.321.988l-1.305.98a10.582 10.582 0 004.872 4.872l.98-1.305a1 1 0 01.988-.321l2.2.548a1 1 0 01.725.94V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
        </svg>
      ),
    },
    {
      name: "Vazifalar (Frog)",
      href: "/tasks",
      badge: "🐸 Top",
      badgeType: "accent",
      icon: (
        <svg aria-hidden="true" className="h-4.5 w-4.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
        </svg>
      ),
    },
    {
      name: "Analitika & LTV",
      href: "/analytics",
      icon: (
        <svg aria-hidden="true" className="h-4.5 w-4.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
      ),
    },
    {
      name: "Sozlamalar",
      href: "/settings",
      icon: (
        <svg aria-hidden="true" className="h-4.5 w-4.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      ),
    },
  ];

  return (
    <motion.aside
      initial={{ width: sidebarOpen ? 256 : 76 }}
      animate={{ width: sidebarOpen ? 256 : 76 }}
      transition={{ type: "spring", stiffness: 380, damping: 36 }}
      className="relative z-30 flex h-full flex-col border-r border-[var(--border-default)] bg-[var(--bg-glass)] backdrop-blur-xl select-none"
    >
      {/* Brand Header */}
      <div className="flex h-16 items-center px-5">
        <Link href="/dashboards/home" className="flex items-center gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-tr from-[#0284c7] via-[#7c3aed] to-[#059669] text-lg shadow-sm">
            👸
          </div>
          <AnimatePresence>
            {sidebarOpen && (
              <motion.div
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -6 }}
                transition={{ duration: 0.15 }}
                className="flex flex-col"
              >
                <div className="flex items-center gap-1.5 font-bold tracking-tight text-[var(--text-primary)] text-sm">
                  <span>Oisha OS</span>
                  <span className="flex h-2 w-2 rounded-full bg-[#059669] animate-pulse"></span>
                </div>
                <span className="text-[10px] font-semibold text-[var(--text-tertiary)] uppercase tracking-wider">
                  Agency Command
                </span>
              </motion.div>
            )}
          </AnimatePresence>
        </Link>
      </div>

      {/* Linear Quick Action Button */}
      <div className="px-3 py-2">
        <button
          onClick={() => setBugReportOpen(true)}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-[var(--bg-surface-subtle)] text-[var(--text-primary)] font-semibold text-xs py-2.5 px-3 hover:bg-[var(--bg-surface-active)] border border-[var(--border-default)] shadow-xs transition-all active:scale-[0.98]"
        >
          <span className="text-sm">✨</span>
          {sidebarOpen && (
            <div className="flex flex-1 items-center justify-between">
              <span>AI Buyruq berish</span>
              <kbd className="rounded border border-[var(--border-default)] bg-[var(--bg-surface)] px-1.5 py-0.5 font-mono text-[9px] text-[var(--text-tertiary)]">
                ⌘K
              </kbd>
            </div>
          )}
        </button>
      </div>

      {/* Navigation List */}
      <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-2">
        {navItems.map((item) => {
          const isActive = pathname === item.href || (item.href !== "/dashboards/home" && pathname.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`group flex items-center justify-between rounded-xl px-3.5 py-2.5 text-xs font-semibold transition-all duration-150 ${
                isActive
                  ? "bg-[var(--accent-primary-light)] text-[var(--accent-primary-on-light)] border border-[var(--accent-primary)]/20 shadow-xs"
                  : "text-[var(--text-secondary)] hover:bg-[var(--bg-surface-subtle)] hover:text-[var(--text-primary)]"
              }`}
            >
              <div className="flex items-center gap-3">
                <span className={isActive ? "text-[var(--accent-primary)]" : "text-[var(--text-tertiary)] group-hover:text-[var(--text-primary)]"}>
                  {item.icon}
                </span>
                {sidebarOpen && <span>{item.name}</span>}
              </div>

              {sidebarOpen && item.badge && (
                <span
                  className={`rounded-full px-2 py-0.5 text-[9px] font-bold ${
                    item.badgeType === "live"
                      ? "bg-[#d1fae5] text-[#065f46] dark:bg-[#064e3b] dark:text-[#34d399]"
                      : item.badgeType === "accent"
                      ? "bg-[#ede9fe] text-[#5b21b6] dark:bg-[#4c1d95] dark:text-[#c084fc]"
                      : "bg-[var(--bg-surface-subtle)] text-[var(--text-secondary)]"
                  }`}
                >
                  {item.badge}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Shopify/Polaris Quota & Telemetry Box */}
      {sidebarOpen && (
        <div className="m-3 rounded-2xl bg-[var(--bg-surface-subtle)] p-3 border border-[var(--border-subtle)]">
          <div className="flex items-center justify-between text-[11px] font-bold text-[var(--text-primary)]">
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-[#059669]"></span>
              Oracle VM (Telethon)
            </span>
            <span className="text-[10px] font-mono text-[var(--text-tertiary)]">24/7 Live</span>
          </div>
          <div className="mt-2.5">
            <div className="flex justify-between text-[10px] text-[var(--text-secondary)]">
              <span>AmoCRM Bitimlar:</span>
              <strong className="text-[var(--text-primary)]">487 / 500</strong>
            </div>
            <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-[var(--bg-surface-active)]">
              <div className="h-full bg-[var(--accent-primary)]" style={{ width: "97.4%" }}></div>
            </div>
          </div>
        </div>
      )}

      {/* Collapse Toggle Footer */}
      <div className="border-t border-[var(--border-default)] p-3">
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="flex w-full items-center justify-center rounded-xl p-2 text-[var(--text-tertiary)] hover:bg-[var(--bg-surface-subtle)] hover:text-[var(--text-primary)] transition-colors"
          aria-label={sidebarOpen ? "Menyuni ixchamlashtirish" : "Menyuni kengaytirish"}
        >
          <svg aria-hidden="true" className={`h-4.5 w-4.5 transition-transform ${sidebarOpen ? "" : "rotate-180"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
          </svg>
        </button>
      </div>
    </motion.aside>
  );
}
