import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SalesCoach AI",
  description: "AI-powered sales call quality and coaching platform"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="uz">
      <body>
        <a
          href="#main-content"
          className="absolute left-0 top-0 z-50 -translate-y-full bg-white px-4 py-2 text-sm font-semibold text-amberline transition-transform focus:translate-y-0 focus:outline-none focus-visible:ring-2 focus-visible:ring-amberline"
        >
          Asosiy tarkibga o&apos;tish
        </a>
        {children}
      </body>
    </html>
  );
}
