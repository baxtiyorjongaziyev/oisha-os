import type { Metadata } from "next";
import { Plus_Jakarta_Sans } from "next/font/google";
import { ThemeProvider } from "@/context/ThemeContext";
import { Providers } from "./providers";
import "./globals.css";

const plusJakartaSans = Plus_Jakarta_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
  display: "swap",
  variable: "--font-sans",
});

export const metadata: Metadata = {
  title: "Oisha OS — Google-Grade Agentic Business Intelligence",
  description: "Autonomous Multi-Agent Operating System for Modern Agency Operations, CRM & Financial Intelligence",
  icons: {
    icon: "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>👸</text></svg>",
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="uz" className={plusJakartaSans.variable} suppressHydrationWarning>
      <body className="min-h-screen bg-[var(--md-sys-color-background)] text-[var(--md-sys-color-on-surface)] antialiased font-sans transition-colors duration-200">
        <ThemeProvider>
          <Providers>
            <a
              href="#main-content"
              className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus:rounded-full focus:bg-[#0b57d0] focus:px-4 focus:py-2 focus:text-white focus:shadow-lg focus:outline-none"
            >
              Asosiy tarkibga o&apos;tish
            </a>
            {children}
          </Providers>
        </ThemeProvider>
      </body>
    </html>
  );
}
