"use client";

import { useQuery } from "@tanstack/react-query";
import { obterMetricas } from "../lib/api";
import { brl, FUNDO } from "../lib/formato";
import type { Decisao } from "../lib/tipos";

const DECISOES: Decisao[] = ["APROVAR", "REVISAR", "BLOQUEAR"];
const pct = (v: number | undefined) => (v == null ? "—" : `${(v * 100).toFixed(1)}%`);

function Card({ titulo, valor }: { titulo: string; valor: string }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <p className="text-xs uppercase tracking-wide text-slate-400">{titulo}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{valor}</p>
    </div>
  );
}

export default function Painel() {
  const { data: m, isError } = useQuery({
    queryKey: ["metricas"],
    queryFn: obterMetricas,
    refetchInterval: 5000,
  });

  if (!m)
    return isError ? (
      <p className="text-rose-400">Não foi possível carregar as métricas da API.</p>
    ) : (
      <p className="text-slate-400">Carregando…</p>
    );

  const total = m.total || 1;
  const mm = m.modelo?.metricas;
  const lim = mm?.limiares?.["0.4"];

  return (
    <div className="space-y-6">
      <title>Painel · Sentinela Pix</title>
      <h1 className="text-xl font-semibold text-white">Painel</h1>
      {isError && (
        <p role="status" className="rounded border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm text-amber-300">
          Sem conexão com a API; exibindo os últimos dados.
        </p>
      )}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Card titulo="Total analisado" valor={m.total.toLocaleString("pt-BR")} />
        <Card titulo="Em revisão" valor={pct(m.por_decisao.REVISAR / total)} />
        <Card titulo="Valor bloqueado" valor={brl(m.valor_bloqueado)} />
        <Card titulo="Latência p99" valor={`${m.latencia_ms.p99.toFixed(1)} ms`} />
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
          <h2 className="mb-3 text-sm font-medium text-slate-300">Distribuição por decisão</h2>
          <div className="flex h-4 overflow-hidden rounded bg-slate-800">
            {DECISOES.map((d) => (
              <div key={d} className={FUNDO[d]} style={{ width: `${(m.por_decisao[d] / total) * 100}%` }} />
            ))}
          </div>
          <ul className="mt-3 space-y-1 text-sm">
            {DECISOES.map((d) => (
              <li key={d} className="flex items-center gap-2">
                <span className={`h-2 w-2 rounded-full ${FUNDO[d]}`} />
                <span className="text-slate-300">{d}</span>
                <span className="ml-auto text-slate-400">
                  {m.por_decisao[d].toLocaleString("pt-BR")} ({pct(m.por_decisao[d] / total)})
                </span>
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
          <h2 className="mb-3 text-sm font-medium text-slate-300">Modelo</h2>
          <dl className="grid grid-cols-2 gap-y-2 text-sm">
            <dt className="text-slate-400">Versão</dt>
            <dd className="font-mono text-white">{m.modelo?.versao ?? "—"}</dd>
            <dt className="text-slate-400">PR-AUC</dt>
            <dd className="text-white">{mm ? mm.pr_auc.toFixed(4) : "—"}</dd>
            <dt className="text-slate-400">Precisão @0.4</dt>
            <dd className="text-white">{pct(lim?.precisao)}</dd>
            <dt className="text-slate-400">Recall @0.4</dt>
            <dd className="text-white">{pct(lim?.recall)}</dd>
            <dt className="text-slate-400">Casos rotulados</dt>
            <dd className="text-white">{m.rotulados}</dd>
            <dt className="text-slate-400">Precisão dos rótulos</dt>
            <dd className="text-white">{pct(m.precisao_rotulos ?? undefined)}</dd>
          </dl>
        </div>
      </div>
    </div>
  );
}
