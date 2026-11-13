"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { listarCasos } from "../../lib/api";
import { BADGE, brl, corScore, dataHora } from "../../lib/formato";
import type { Decisao } from "../../lib/tipos";

const ABAS: Decisao[] = ["REVISAR", "BLOQUEAR"];
const LIMITE = 50;

export default function Fila() {
  const router = useRouter();
  const [aba, setAba] = useState<Decisao>("REVISAR");
  const [pendentes, setPendentes] = useState(true);
  const [pagina, setPagina] = useState(0);
  const { data, isError } = useQuery({
    queryKey: ["casos", aba, pendentes, pagina],
    queryFn: () => listarCasos(aba, pendentes, LIMITE, pagina * LIMITE),
    refetchInterval: 5000,
    placeholderData: keepPreviousData,
  });
  const total = data?.total ?? 0;
  const inicio = pagina * LIMITE;

  return (
    <div className="space-y-4">
      <title>Fila de casos · Sentinela Pix</title>
      <h1 className="text-xl font-semibold text-white">Fila de casos</h1>

      <div className="flex flex-wrap items-center gap-2">
        {ABAS.map((a) => (
          <button
            key={a}
            onClick={() => {
              setAba(a);
              setPagina(0);
            }}
            aria-pressed={aba === a}
            className={`rounded border px-3 py-1.5 text-sm ${
              aba === a ? BADGE[a] : "border-slate-800 text-slate-400 hover:text-white"
            }`}
          >
            {a}
          </button>
        ))}
        <label className="ml-4 flex items-center gap-2 text-sm text-slate-300">
          <input type="checkbox" checked={pendentes} onChange={(e) => {
              setPendentes(e.target.checked);
              setPagina(0);
            }}
          />
          só pendentes
        </label>
        <span className="ml-auto text-sm text-slate-400">
          {!data ? "" : total ? `${Math.min(inicio + 1, total)}–${Math.min(inicio + LIMITE, total)} de ${total}` : "0 casos"}
        </span>
      </div>

      {isError && <p className="text-rose-400">Não foi possível carregar os casos.</p>}

      <div className="overflow-x-auto rounded-lg border border-slate-800 bg-slate-900">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-800 text-xs uppercase text-slate-400">
            <tr>
              {["Hora", "Origem", "Destino", "Valor", "Score", "Decisão", "Rótulo"].map((c) => (
                <th key={c} className="px-3 py-2 font-medium">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data?.itens.map((c) => (
              <tr
                key={c.transacao_id}
                onClick={() => router.push(`/casos/${c.transacao_id}`)}
                className="cursor-pointer border-b border-slate-800/60 hover:bg-slate-800/50"
              >
                <td className="px-3 py-2 text-slate-300">
                  <Link href={`/casos/${c.transacao_id}`} onClick={(e) => e.stopPropagation()} className="hover:underline">
                    {dataHora(c.ts)}
                  </Link>
                </td>
                <td className="px-3 py-2 font-mono text-xs">{c.origem}</td>
                <td className="px-3 py-2 font-mono text-xs">{c.destino}</td>
                <td className="px-3 py-2 text-white">{brl(c.valor)}</td>
                <td className="px-3 py-2">
                  <div className="flex items-center gap-2">
                    <div className="h-1.5 w-20 rounded bg-slate-800">
                      <div className={`h-full rounded ${corScore(c.score)}`} style={{ width: `${c.score * 100}%` }} />
                    </div>
                    <span className="tabular-nums text-slate-300">{c.score.toFixed(2)}</span>
                  </div>
                </td>
                <td className="px-3 py-2">
                  <span className={`rounded border px-2 py-0.5 text-xs ${BADGE[c.decisao]}`}>{c.decisao}</span>
                </td>
                <td className="px-3 py-2 text-slate-300">{c.rotulo ?? "—"}</td>
              </tr>
            ))}
            {!data && !isError && (
              <tr>
                <td colSpan={7} className="px-3 py-6 text-center text-slate-400">
                  Carregando…
                </td>
              </tr>
            )}
            {data?.itens.length === 0 && (
              <tr>
                <td colSpan={7} className="px-3 py-6 text-center text-slate-400">
                  Nenhum caso nesta fila.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="flex justify-end gap-2">
        {(
          [
            ["Anterior", -1, pagina === 0],
            ["Próxima", 1, inicio + LIMITE >= total],
          ] as const
        ).map(([texto, passo, desabilitado]) => (
          <button
            key={texto}
            onClick={() => setPagina(pagina + passo)}
            disabled={desabilitado}
            className="rounded border border-slate-800 px-3 py-1.5 text-sm text-slate-300 hover:text-white disabled:opacity-40"
          >
            {texto}
          </button>
        ))}
      </div>
    </div>
  );
}
