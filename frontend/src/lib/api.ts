import type { CasoDetalhe, Casos, Decisao, Metricas, Resumo, RotuloValor } from "./tipos";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function req<T>(caminho: string, corpo?: unknown, metodo = corpo ? "POST" : "GET"): Promise<T> {
  const r = await fetch(`${API_URL}${caminho}`, {
    method: metodo,
    headers: corpo ? { "Content-Type": "application/json" } : undefined,
    body: corpo ? JSON.stringify(corpo) : undefined,
  });
  if (!r.ok) throw new Error(`Erro ${r.status} em ${caminho}`);
  return r.json();
}

export const obterMetricas = () => req<Metricas>("/metricas");

export const listarCasos = (decisao: Decisao, pendentes: boolean, limit = 50, offset = 0) =>
  req<Casos>(`/casos?decisao=${decisao}&pendentes=${pendentes}&limit=${limit}&offset=${offset}`);

export const obterCaso = (id: string) => req<CasoDetalhe>(`/casos/${encodeURIComponent(id)}`);

export const rotular = (id: string, rotulo: RotuloValor, analista: string) =>
  req<{ transacao_id: string }>(`/casos/${encodeURIComponent(id)}/rotulo`, { rotulo, analista });

export const gerarResumo = (id: string) =>
  req<Resumo>(`/casos/${encodeURIComponent(id)}/resumo`, undefined, "POST");
