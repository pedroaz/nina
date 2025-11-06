import type { Metadata } from "next";
import { Inter, Syne } from 'next/font/google';
import "./globals.css";
import { LandingHeader } from '@/components/landing';

const displayFont = Syne({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-space-display',
});

const baseFont = Inter({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-space-default',
});

export const metadata: Metadata = {
  title: "Nina",
  description: "Nina AI German Learning App",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${baseFont.variable} ${displayFont.variable} scroll-smooth`}>
        <LandingHeader />
        {children}
      </body>
    </html>
  );
}
