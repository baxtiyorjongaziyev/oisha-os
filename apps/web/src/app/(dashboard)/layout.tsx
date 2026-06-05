"use client";

import React from "react";
import Sidebar from "@/components/Sidebar";
import Header from "@/components/Header";
import { useTheme } from "@/context/ThemeContext";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { sidebarOpen } = useTheme();

  return (
    <div className="flex h-screen w-screen overflow-hidden">
      {/* Sidebar - left */}
      <Sidebar />

      {/* Main Container - right */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Sticky Header */}
        <Header />

        {/* Content Area */}
        <main
          id="main-content"
          className="flex-1 overflow-x-hidden overflow-y-auto px-6 py-8 focus:outline-none"
          tabIndex={-1}
        >
          <div className="mx-auto max-w-7xl animate-fade-in">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
