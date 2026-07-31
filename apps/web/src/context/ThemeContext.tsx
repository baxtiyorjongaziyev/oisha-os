"use client";

import React, { createContext, useContext, useState, useEffect } from "react";

export type Theme = "light" | "dark";
export type Palette = "sage" | "indigo" | "rose" | "amber" | "teal" | "violet" | "emerald";
export type Language = "uz" | "en" | "ru";

export interface Alert {
  id: string;
  type: "warning" | "error";
  typeLabel: string;
  status: "new" | "read" | "dismissed";
  time: string;
  title: string;
  description: string;
  manager: string;
  managerAvatar: string;
}

interface ThemeContextType {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  palette: Palette;
  setPalette: (palette: Palette) => void;
  language: Language;
  setLanguage: (lang: Language) => void;
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
  currentBusiness: string;
  setCurrentBusiness: (business: string) => void;
  searchOpen: boolean;
  setSearchOpen: (open: boolean) => void;
  bugReportOpen: boolean;
  setBugReportOpen: (open: boolean) => void;
  notificationsOpen: boolean;
  setNotificationsOpen: (open: boolean) => void;
  alerts: Alert[];
  setAlerts: React.Dispatch<React.SetStateAction<Alert[]>>;
  alertsCount: number;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

const initialAlerts: Alert[] = [];

// localStorage'ni useState lazy initializer'da o'qiymiz: effect ichida setState
// qilish kaskadli render keltirib chiqaradi (react-hooks/set-state-in-effect).
// SSR paytida `window` yo'q — fallback qiymat qaytadi, klientda esa birinchi
// render'dayoq saqlangan qiymat ishlatiladi.
function readStored<T extends string>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  return (localStorage.getItem(key) as T | null) ?? fallback;
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(() =>
    readStored<Theme>("metasell-theme", "light")
  );
  const [palette, setPaletteState] = useState<Palette>(() =>
    readStored<Palette>("metasell-palette", "sage")
  );
  const [language, setLanguageState] = useState<Language>(() =>
    readStored<Language>("metasell-lang", "uz")
  );
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [currentBusiness, setCurrentBusiness] = useState("Jon Branding agency");
  const [searchOpen, setSearchOpen] = useState(false);
  const [bugReportOpen, setBugReportOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [alerts, setAlerts] = useState<Alert[]>(initialAlerts);

  // DOM klasslarini va localStorage'ni state bilan sinxronlaymiz.
  useEffect(() => {
    const root = document.documentElement;
    
    // Theme logic
    if (theme === "dark") {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
    localStorage.setItem("metasell-theme", theme);
    
    // Palette logic
    // Clear old palette classes
    const paletteClasses = [
      "palette-sage", "palette-indigo", "palette-rose", 
      "palette-amber", "palette-teal", "palette-violet", "palette-emerald"
    ];
    root.classList.remove(...paletteClasses);
    root.classList.add(`palette-${palette}`);
    localStorage.setItem("metasell-palette", palette);
  }, [theme, palette]);

  const setTheme = (t: Theme) => setThemeState(t);
  const setPalette = (p: Palette) => setPaletteState(p);
  const setLanguage = (l: Language) => {
    setLanguageState(l);
    localStorage.setItem("metasell-lang", l);
  };

  // Keyboard shortcut for search "/"
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      const isInput = target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.tagName === "SELECT" || target.isContentEditable;

      if (e.key === "/" && !isInput) {
        e.preventDefault();
        setSearchOpen(true);
      }
      if (e.key === "Escape") {
        setSearchOpen(false);
        setBugReportOpen(false);
        setNotificationsOpen(false);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const alertsCount = alerts.filter(a => a.status === "new").length;

  return (
    <ThemeContext.Provider
      value={{
        theme,
        setTheme,
        palette,
        setPalette,
        language,
        setLanguage,
        sidebarOpen,
        setSidebarOpen,
        currentBusiness,
        setCurrentBusiness,
        searchOpen,
        setSearchOpen,
        bugReportOpen,
        setBugReportOpen,
        notificationsOpen,
        setNotificationsOpen,
        alerts,
        setAlerts,
        alertsCount
      }}
    >
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return context;
}
