import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SalesCoach AI",
  description: "AI-powered sales call quality and coaching platform"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="uz">
      <body>{children}</body>
    </html>
  );
}
