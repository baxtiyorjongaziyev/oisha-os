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
          className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:p-4 focus:bg-white focus:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amberline focus-visible:ring-offset-2 rounded-br-lg font-medium"
        >
          Asosiy tarkibga o&apos;tish
        </a>
        {children}
      </body>
    </html>
  );
}
