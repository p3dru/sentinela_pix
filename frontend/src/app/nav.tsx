"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", texto: "Painel" },
  { href: "/casos", texto: "Fila de casos" },
];

export default function Nav() {
  const caminho = usePathname();
  return (
    <nav className="flex gap-1 md:flex-col">
      {NAV.map((n) => {
        const atual = n.href === "/" ? caminho === "/" : caminho.startsWith(n.href);
        return (
          <Link
            key={n.href}
            href={n.href}
            aria-current={atual ? "page" : undefined}
            className={`rounded px-3 py-2 text-sm hover:bg-slate-800 hover:text-white ${
              atual ? "bg-slate-800 text-white" : "text-slate-300"
            }`}
          >
            {n.texto}
          </Link>
        );
      })}
    </nav>
  );
}
