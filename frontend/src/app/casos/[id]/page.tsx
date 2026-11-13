"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { ErroApi, gerarResumo, obterCaso, rotular } from "../../../lib/api";
import { BADGE, brl, dataHora, valorMotivo } from "../../../lib/formato";
import type { Grafo, Motivo, RotuloValor } from "../../../lib/tipos";

const CARD = "rounded-lg border border-slate-800 bg-slate-900 p-4";

function Motivos({ motivos }: { motivos: Motivo[] }) {
  const regras = motivos.filter((m) => m.feature === "regra");
  const shap = motivos.filter((m) => m.feature !== "regra");
  const max = Math.max(...shap.map((m) => Math.abs(m.impacto ?? 0)), 1e-9);
  return (
    <ul className="space-y-2 text-sm">
      {regras.map((m, i) => (
        <li key={`r${i}`} className="rounded border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-amber-300">
          Regra: {m.rotulo}
        </li>
      ))}
      {shap.map((m) => {
        const imp = m.impacto ?? 0;
        return (
          <li key={m.feature}>
            <div className="flex justify-between gap-4">
              <span className="text-slate-200">
                {m.rotulo} <span className="text-slate-500">= {valorMotivo(m.feature, m.valor)}</span>
              </span>
              <span className={`tabular-nums ${imp > 0 ? "text-rose-400" : "text-emerald-400"}`}>
                {imp > 0 ? "+" : ""}
                {imp.toFixed(4)}
              </span>
            </div>
            <div className="mt-1 h-1.5 rounded bg-slate-800">
              <div
                className={`h-full rounded ${imp > 0 ? "bg-rose-500" : "bg-emerald-500"}`}
                style={{ width: `${(Math.abs(imp) / max) * 100}%` }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

// Layout radial: destino no centro, 1º salto no anel interno, 2º no externo.
function GrafoRadial({ grafo }: { grafo: Grafo }) {
  const RAIO = [0, 80, 160];
  const pos = new Map<string, { x: number; y: number }>();
  for (const salto of [0, 1, 2]) {
    const nos = grafo.nodes.filter((n) => n.salto === salto);
    nos.forEach((n, i) => {
      const ang = (2 * Math.PI * i) / nos.length;
      pos.set(n.id, { x: RAIO[salto] * Math.cos(ang), y: RAIO[salto] * Math.sin(ang) });
    });
  }
  return (
    <svg viewBox="-180 -180 360 360" className="mx-auto w-full max-w-md" role="img" aria-label="Grafo de 2 saltos do destino">
      {[80, 160].map((r) => (
        <circle key={r} r={r} fill="none" className="stroke-slate-800" strokeDasharray="2 4" />
      ))}
      {grafo.edges.map((e) => {
        const a = pos.get(e.source);
        const b = pos.get(e.target);
        return a && b ? (
          <line key={`${e.source}-${e.target}`} x1={a.x} y1={a.y} x2={b.x} y2={b.y} className="stroke-slate-600" strokeWidth={Math.min(1 + Math.log2(e.qtd), 4)}>
            <title>{`${e.qtd} tx · ${brl(e.valor_total)}`}</title>
          </line>
        ) : null;
      })}
      {grafo.nodes.map((n) => {
        const p = pos.get(n.id)!;
        const risco = n.tipo === "laranja" || n.fraude_conhecida;
        return (
          <circle
            key={n.id}
            cx={p.x}
            cy={p.y}
            r={n.salto === 0 ? 9 : 5}
            className={`${risco ? "fill-rose-500" : "fill-slate-400"} ${n.salto === 0 ? "stroke-white" : "stroke-slate-950"}`}
            strokeWidth={n.salto === 0 ? 2 : 1}
          >
            <title>{`${n.id} · ${n.tipo}${n.fraude_conhecida ? " · fraude conhecida" : ""}`}</title>
          </circle>
        );
      })}
    </svg>
  );
}

export default function Detalhe() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const [analista, setAnalista] = useState("analista.demo");
  const naoExiste = (e: unknown) => e instanceof ErroApi && e.status === 404;
  const { data: c, error } = useQuery({
    queryKey: ["caso", id],
    queryFn: () => obterCaso(id),
    retry: (n, e) => !naoExiste(e) && n < 2,
  });
  const resumo = useMutation({ mutationFn: () => gerarResumo(id) });
  const rotulo = useMutation({
    mutationFn: (r: RotuloValor) => rotular(id, r, analista),
    onSuccess: () => qc.invalidateQueries(),
  });

  if (!c)
    return error ? (
      <p className="text-rose-400">{naoExiste(error) ? "Caso não encontrado." : "Não foi possível carregar o caso."}</p>
    ) : (
      <p className="text-slate-400">Carregando…</p>
    );

  const { transacao: t, decisao: d } = c;

  return (
    <div className="space-y-4">
      <title>{`Caso ${brl(c.transacao.valor)} · Sentinela Pix`}</title>
      <Link href="/casos" className="text-sm text-slate-400 hover:text-white">
        ← Fila de casos
      </Link>

      <header className={`${CARD} flex flex-wrap items-center gap-4`}>
        <div>
          <p className="text-3xl font-semibold text-white">{brl(t.valor)}</p>
          <p className="mt-1 font-mono text-xs text-slate-400">
            {t.origem} → {t.destino} · {dataHora(t.ts)} · {t.dispositivo}
          </p>
        </div>
        <span className={`ml-auto rounded border px-3 py-1 text-sm ${BADGE[d.decisao]}`}>{d.decisao}</span>
        <div className="text-right">
          <p className="text-xs uppercase text-slate-400">Score</p>
          <p className="text-2xl font-semibold tabular-nums text-white">{d.score.toFixed(3)}</p>
        </div>
      </header>

      <div className="grid gap-4 xl:grid-cols-2">
        <section className={CARD}>
          <h2 className="mb-3 text-sm font-medium text-slate-300">Motivos</h2>
          <Motivos motivos={d.motivos} />
        </section>

        <section className={CARD}>
          <h2 className="mb-3 text-sm font-medium text-slate-300">Rede do destino (2 saltos)</h2>
          <GrafoRadial grafo={c.grafo} />
          <p className="mt-2 text-xs text-slate-400">
            <span className="mr-1 inline-block h-2 w-2 rounded-full bg-rose-500" />
            conta laranja ou fraude conhecida
          </p>
        </section>
      </div>

      <section className={CARD}>
        <h2 className="mb-3 text-sm font-medium text-slate-300">Análise</h2>
        <div className="flex flex-wrap items-center gap-2">
          <label className="text-sm text-slate-400">
            Analista{" "}
            <input
              value={analista}
              onChange={(e) => setAnalista(e.target.value)}
              className="ml-1 rounded border border-slate-700 bg-slate-950 px-2 py-1 text-slate-200"
            />
          </label>
          <button
            onClick={() => rotulo.mutate("fraude")}
            disabled={rotulo.isPending || !analista.trim()}
            className="rounded bg-rose-600 px-3 py-1.5 text-sm text-white hover:bg-rose-500 disabled:opacity-50"
          >
            Confirmar fraude
          </button>
          <button
            onClick={() => rotulo.mutate("legitima")}
            disabled={rotulo.isPending || !analista.trim()}
            className="rounded bg-emerald-600 px-3 py-1.5 text-sm text-white hover:bg-emerald-500 disabled:opacity-50"
          >
            Marcar legítima
          </button>
          <button
            onClick={() => resumo.mutate()}
            disabled={resumo.isPending}
            className="rounded border border-slate-700 px-3 py-1.5 text-sm text-slate-200 hover:bg-slate-800 disabled:opacity-50"
          >
            {resumo.isPending ? "Gerando…" : "Gerar resumo"}
          </button>
        </div>
        {c.rotulo && (
          <p className="mt-3 text-sm text-slate-300">
            Rotulado como <strong className="text-white">{c.rotulo.rotulo}</strong> por {c.rotulo.analista} em{" "}
            {dataHora(c.rotulo.criado_em)}.
          </p>
        )}
        {(rotulo.isError || resumo.isError) && <p className="mt-3 text-sm text-rose-400">A operação falhou. Tente de novo.</p>}
        {resumo.data && (
          <div className="mt-3 rounded border border-slate-800 bg-slate-950 p-3 text-sm">
            <p className="whitespace-pre-line text-slate-200">{resumo.data.resumo}</p>
            <p className="mt-2 text-xs text-slate-500">Fonte: {resumo.data.fonte}</p>
          </div>
        )}
      </section>

      <section className={CARD}>
        <h2 className="mb-3 text-sm font-medium text-slate-300">Histórico da origem</h2>
        <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-xs uppercase text-slate-400">
            <tr>
              {["Hora", "Destino", "Valor", "Dispositivo"].map((h) => (
                <th key={h} className="py-1 font-medium">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {c.historico_origem.map((h) => (
              <tr key={h.id} className={`border-t border-slate-800/60 ${h.id === t.id ? "text-white" : "text-slate-300"}`}>
                <td className="py-1">{dataHora(h.ts)}</td>
                <td className="py-1 font-mono text-xs">{h.destino}</td>
                <td className="py-1">{brl(h.valor)}</td>
                <td className="py-1 font-mono text-xs">{h.dispositivo}</td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </section>
    </div>
  );
}
