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

const initialAlerts: Alert[] = [
  {
    id: "1",
    type: "warning",
    typeLabel: "Faoliyatsiz menejer",
    status: "new",
    time: "17 soat oldin",
    title: "Menejer faoliyatsizligi aniqlandi",
    description: "Baxtiyorjon Gaziyev bugun birorta ham qo'ng'iroqni amalga oshirmadi. Kunlik reja 15 ta qo'ng'iroq edi.",
    manager: "Baxtiyorjon Gaziyev",
    managerAvatar: "B"
  },
  {
    id: "2",
    type: "error",
    typeLabel: "Past samaradorlik",
    status: "new",
    time: "1 kun oldin",
    title: "Suhbat sifati past ko'rsatkichda",
    description: "Oxirgi 5 ta qo'ng'iroq bo'yicha o'rtacha suhbat sifati 24% ni tashkil etdi (maqsadli KPI: 75%+).",
    manager: "Baxtiyorjon Gaziyev",
    managerAvatar: "B"
  },
  {
    id: "3",
    type: "warning",
    typeLabel: "Faoliyatsiz menejer",
    status: "new",
    time: "2 kun oldin",
    title: "CRM topshiriqlar muddati o'tdi",
    description: "Jami 8 ta faol bitim bo'yicha muddati o'tgan yoki bajarilmagan vazifalar mavjud.",
    manager: "Baxtiyorjon Gaziyev",
    managerAvatar: "B"
  }
];

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>("light");
  const [palette, setPaletteState] = useState<Palette>("sage");
  const [language, setLanguageState] = useState<Language>("uz");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [currentBusiness, setCurrentBusiness] = useState("Jon Branding agency");
  const [searchOpen, setSearchOpen] = useState(false);
  const [bugReportOpen, setBugReportOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [alerts, setAlerts] = useState<Alert[]>(initialAlerts);

  // Sync with localStorage & DOM classes on mount/change
  useEffect(() => {
    const savedTheme = localStorage.getItem("metasell-theme") as Theme;
    const savedPalette = localStorage.getItem("metasell-palette") as Palette;
    const savedLang = localStorage.getItem("metasell-lang") as Language;
    
    if (savedTheme) setThemeState(savedTheme);
    if (savedPalette) setPaletteState(savedPalette);
    if (savedLang) setLanguageState(savedLang);
  }, []);

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
      if (e.key === "/" && document.activeElement?.tagName !== "INPUT" && document.activeElement?.tagName !== "TEXTAREA") {
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

  const alertsCount = alerts.filter(a => a.status === "new").length + 22; // Hardcoded default offset of 22 to make 25 unread alerts in total

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
