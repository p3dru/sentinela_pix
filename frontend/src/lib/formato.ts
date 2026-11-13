import type { Decisao } from "./tipos";

const moeda = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
export const brl = (v: number) => moeda.format(v);

export const dataHora = (ts: string) =>
  new Date(ts).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "medium" });

export const BADGE: Record<Decisao, string> = {
  APROVAR: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  REVISAR: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  BLOQUEAR: "bg-rose-500/15 text-rose-400 border-rose-500/30",
};

export const FUNDO: Record<Decisao, string> = {
  APROVAR: "bg-emerald-500",
  REVISAR: "bg-amber-500",
  BLOQUEAR: "bg-rose-500",
};

export const corScore = (s: number) =>
  s >= 0.85 ? "bg-rose-500" : s >= 0.4 ? "bg-amber-500" : "bg-emerald-500";

const BINARIAS = new Set(["madrugada", "destinatario_novo", "dispositivo_novo"]);
export const valorMotivo = (feature: string, v: number | null) =>
  v == null
    ? "—"
    : BINARIAS.has(feature)
      ? v ? "Sim" : "Não"
      : v.toLocaleString("pt-BR", { maximumFractionDigits: 2 });
