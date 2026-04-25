import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'SalesCoach AI',
  description: 'AI-powered sales call analysis for CIS market',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="uz">
      <body>{children}</body>
    </html>
  );
}
