"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { listarCasos } from "../../lib/api";
import { BADGE, brl, corScore, dataHora } from "../../lib/formato";
import type { Decisao } from "../../lib/tipos";

const ABAS: Decisao[] = ["REVISAR", "BLOQUEAR"];

export default function Fila() {
  const router = useRouter();
  const [aba, setAba] = useState<Decisao>("REVISAR");
  const [pendentes, setPendentes] = useState(true);
  const { data, isError } = useQuery({
    queryKey: ["casos", aba, pendentes],
    queryFn: () => listarCasos(aba, pendentes),
    refetchInterval: 5000,
  });

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-white">Fila de casos</h1>

      <div className="flex items-center gap-2">
        {ABAS.map((a) => (
          <button
            key={a}
            onClick={() => setAba(a)}
            aria-pressed={aba === a}
            className={`rounded border px-3 py-1.5 text-sm ${
              aba === a ? BADGE[a] : "border-slate-800 text-slate-400 hover:text-white"
            }`}
          >
            {a}
          </button>
        ))}
        <label className="ml-4 flex items-center gap-2 text-sm text-slate-300">
          <input type="checkbox" checked={pendentes} onChange={(e) => setPendentes(e.target.checked)} />
          só pendentes
        </label>
        <span className="ml-auto text-sm text-slate-400">{data ? `${data.total} casos` : ""}</span>
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
                <td className="px-3 py-2 text-slate-300">{dataHora(c.ts)}</td>
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
    </div>
  );
}
