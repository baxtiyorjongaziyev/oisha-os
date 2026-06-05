import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Metasell — AI Sotuv Platforma',
  description: 'AI-asosidagi sotuv qo\'ng\'iroqlari tahlil platformasi',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="uz">
      <body>{children}</body>
    </html>
  );
}
