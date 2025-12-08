import type { Metadata } from "next";
import { Nunito, Geist_Mono } from "next/font/google";
import "@uiw/react-markdown-preview/markdown.css";
import "./globals.css";
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/app-sidebar";
import { Providers } from "./providers";
import { getSession } from "@/lib/auth";

const nunito = Nunito({
  variable: "--font-nunito",
  subsets: ["latin"],
  weight: ["400", "600", "700", "800"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Nina - AI Language Learning",
  description: "Learn languages with AI-powered lessons, flashcards, and exercises",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const session = await getSession();
  return (
    <html lang="en">
      <body
        className={`${nunito.variable} ${geistMono.variable} antialiased`}
      >
        <Providers initialSession={session}>
          <SidebarProvider>
            <AppSidebar />
            <SidebarInset>
              <header className="flex h-16 shrink-0 items-center gap-4 border-b border-neutral-200 bg-white px-4">
                <SidebarTrigger className="-ml-1" />
              </header>
              <main className="flex-1">{children}</main>
            </SidebarInset>
          </SidebarProvider>
        </Providers>
      </body>
    </html>
  );
}
