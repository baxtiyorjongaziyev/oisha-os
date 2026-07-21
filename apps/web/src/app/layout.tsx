import type { Metadata } from "next";
import { ThemeProvider } from "@/context/ThemeContext";
import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "Metasell — AI Sotuv Analitikasi",
  description: "O'zbek tilidagi AI-asosidagi savdo qo'ng'iroqlarini tahlil qilish va boshqarish platformasi"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="uz">
      <body className="bg-gradient-mesh min-h-screen">
        <ThemeProvider>
          <Providers>
            <a
              href="#main-content"
              className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:p-4 focus:bg-white focus:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amberline focus-visible:ring-offset-2 rounded-br-lg font-medium"
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
