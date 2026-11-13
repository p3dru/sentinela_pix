import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Suspense } from "react";
import "./globals.css";
import Nav from "./nav";
import Providers from "./providers";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Sentinela Pix",
  description: "Console de análise de fraude em Pix",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full bg-slate-950 text-slate-200">
        <aside className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-slate-800 bg-slate-900 p-4 md:fixed md:inset-y-0 md:left-0 md:block md:w-52 md:border-r md:border-b-0">
          <p className="text-lg font-semibold text-emerald-400 md:mb-6">Sentinela Pix</p>
          <Suspense fallback={null}>
            <Nav />
          </Suspense>
        </aside>
        <main className="p-4 md:ml-52 md:p-6">
          <Providers>
            <Suspense fallback={<p className="text-slate-400">Carregando…</p>}>{children}</Suspense>
          </Providers>
        </main>
      </body>
    </html>
  );
}
