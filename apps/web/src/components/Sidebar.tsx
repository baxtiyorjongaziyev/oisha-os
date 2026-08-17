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
}

export default function Sidebar() {
  const pathname = usePathname();
  const { sidebarOpen, setSidebarOpen, setBugReportOpen } = useTheme();

  const navItems: NavItem[] = [
    {
      name: "Boshqaruv markazi",
      href: "/dashboards/home",
      icon: (
        <svg aria-hidden="true" className="h-5 w-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
        </svg>
      ),
    },
    {
      name: "CRM Voronkasi",
      href: "/crm",
      badge: "487",
      icon: (
        <svg aria-hidden="true" className="h-5 w-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
        </svg>
      ),
    },
    {
      name: "Moliya (Hisobchi)",
      href: "/finance",
      badge: "Live",
      icon: (
        <svg aria-hidden="true" className="h-5 w-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
    },
    {
      name: "Qo'ng'iroqlar (AI)",
      href: "/calls",
      icon: (
        <svg aria-hidden="true" className="h-5 w-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.94.725l.548 2.2a1 1 0 01-.321.988l-1.305.98a10.582 10.582 0 004.872 4.872l.98-1.305a1 1 0 01.988-.321l2.2.548a1 1 0 01.725.94V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
        </svg>
      ),
    },
    {
      name: "Vazifalar (Frog)",
      href: "/tasks",
      badge: "🐸 Top",
      icon: (
        <svg aria-hidden="true" className="h-5 w-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
        </svg>
      ),
    },
    {
      name: "Analitika & LTV",
      href: "/analytics",
      icon: (
        <svg aria-hidden="true" className="h-5 w-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
      ),
    },
    {
      name: "Sozlamalar",
      href: "/settings",
      icon: (
        <svg aria-hidden="true" className="h-5 w-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      ),
    },
  ];

  return (
    <motion.aside
      initial={{ width: sidebarOpen ? 264 : 80 }}
      animate={{ width: sidebarOpen ? 264 : 80 }}
      transition={{ type: "spring", stiffness: 350, damping: 35 }}
      className="relative z-30 flex h-full flex-col border-r border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface)] select-none"
    >
      {/* Brand Header */}
      <div className="flex h-16 items-center px-5">
        <Link href="/dashboards/home" className="flex items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-tr from-[#0b57d0] via-[#7c3aed] to-[#00875a] text-xl shadow-md shadow-blue-500/20">
            👸
          </div>
          <AnimatePresence>
            {sidebarOpen && (
              <motion.div
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -8 }}
                transition={{ duration: 0.15 }}
                className="flex flex-col"
              >
                <div className="flex items-center gap-1.5 font-bold tracking-tight text-[var(--md-sys-color-on-surface)] text-[15px]">
                  <span>Oisha OS</span>
                  <span className="flex h-2 w-2 rounded-full bg-[#137333] dark:bg-[#6dd58c]"></span>
                </div>
                <span className="text-[10px] font-semibold text-[var(--md-sys-color-on-surface-variant)] uppercase tracking-wider">
                  Agency Command
                </span>
              </motion.div>
            )}
          </AnimatePresence>
        </Link>
      </div>

      {/* Google FAB Action Button */}
      <div className="px-4 py-3">
        <button
          onClick={() => setBugReportOpen(true)}
          className={`flex w-full items-center justify-center gap-2.5 rounded-2xl bg-[var(--md-sys-color-surface-container)] text-[var(--md-sys-color-on-surface)] font-semibold text-xs py-3 px-4 hover:bg-[var(--md-sys-color-surface-container-high)] shadow-sm transition-all active:scale-[0.98] border border-[var(--md-sys-color-outline-variant)]`}
        >
          <span className="text-base">✨</span>
          {sidebarOpen && <span>AI Buyruq / Vazifa</span>}
        </button>
      </div>

      {/* Navigation Links (Google MD3 Pill Shape) */}
      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-2">
        {navItems.map((item) => {
          const isActive = pathname === item.href || (item.href !== "/dashboards/home" && pathname.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`group flex items-center justify-between rounded-full px-4 py-3 text-xs font-semibold transition-all duration-150 ${
                isActive
                  ? "bg-[#d3e3fd] text-[#041e49] shadow-sm dark:bg-[#004a77] dark:text-[#c2e7ff]"
                  : "text-[var(--md-sys-color-on-surface-variant)] hover:bg-[var(--md-sys-color-surface-container)] hover:text-[var(--md-sys-color-on-surface)]"
              }`}
            >
              <div className="flex items-center gap-3">
                <span className={isActive ? "text-[#0b57d0] dark:text-[#a8c7fa]" : "text-[var(--md-sys-color-on-surface-variant)] group-hover:text-[var(--md-sys-color-on-surface)]"}>
                  {item.icon}
                </span>
                {sidebarOpen && <span>{item.name}</span>}
              </div>

              {sidebarOpen && item.badge && (
                <span
                  className={`rounded-full px-2 py-0.5 text-[9px] font-bold ${
                    isActive
                      ? "bg-[#0b57d0] text-white dark:bg-[#a8c7fa] dark:text-[#041e49]"
                      : "bg-[var(--md-sys-color-surface-container-high)] text-[var(--md-sys-color-on-surface-variant)]"
                  }`}
                >
                  {item.badge}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Quota & Telemetry Box (Google Cloud style) */}
      {sidebarOpen && (
        <div className="m-3 rounded-2xl bg-[var(--md-sys-color-surface-container-low)] p-3.5 border border-[var(--md-sys-color-outline-variant)]">
          <div className="flex items-center justify-between text-[11px] font-bold text-[var(--md-sys-color-on-surface)]">
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-[#137333] dark:bg-[#6dd58c]"></span>
              Oracle VM (Telethon)
            </span>
            <span className="text-[10px] font-mono text-[var(--md-sys-color-on-surface-variant)]">24/7 Live</span>
          </div>
          <div className="mt-2.5">
            <div className="flex justify-between text-[10px] text-[var(--md-sys-color-on-surface-variant)]">
              <span>AmoCRM Bitimlar:</span>
              <strong className="text-[var(--md-sys-color-on-surface)]">487 / 500</strong>
            </div>
            <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-[var(--md-sys-color-surface-container-highest)]">
              <div className="h-full bg-[#0b57d0] dark:bg-[#a8c7fa]" style={{ width: "97.4%" }}></div>
            </div>
          </div>
        </div>
      )}

      {/* Collapse Toggle Footer */}
      <div className="border-t border-[var(--md-sys-color-outline)] p-3">
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="flex w-full items-center justify-center rounded-full p-2 text-[var(--md-sys-color-on-surface-variant)] hover:bg-[var(--md-sys-color-surface-container)] transition-colors"
          aria-label={sidebarOpen ? "Menyuni ixchamlashtirish" : "Menyuni kengaytirish"}
        >
          <svg aria-hidden="true" className={`h-5 w-5 transition-transform ${sidebarOpen ? "" : "rotate-180"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
          </svg>
        </button>
      </div>
    </motion.aside>
  );
}
