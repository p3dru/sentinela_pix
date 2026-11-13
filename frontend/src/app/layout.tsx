import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import { Suspense } from "react";
import "./globals.css";
import Providers from "./providers";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Sentinela Pix",
  description: "Console de análise de fraude em Pix",
};

const NAV = [
  { href: "/", texto: "Painel" },
  { href: "/casos", texto: "Fila de casos" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full bg-slate-950 text-slate-200">
        <aside className="fixed inset-y-0 left-0 w-52 border-r border-slate-800 bg-slate-900 p-4">
          <p className="mb-6 text-lg font-semibold text-emerald-400">Sentinela Pix</p>
          <nav className="flex flex-col gap-1">
            {NAV.map((n) => (
              <Link
                key={n.href}
                href={n.href}
                className="rounded px-3 py-2 text-sm text-slate-300 hover:bg-slate-800 hover:text-white"
              >
                {n.texto}
              </Link>
            ))}
          </nav>
        </aside>
        <main className="ml-52 p-6">
          <Providers>
            <Suspense fallback={<p className="text-slate-400">Carregando…</p>}>{children}</Suspense>
          </Providers>
        </main>
      </body>
    </html>
  );
}
