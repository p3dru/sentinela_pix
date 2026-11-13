export type Decisao = "APROVAR" | "REVISAR" | "BLOQUEAR";
export type RotuloValor = "fraude" | "legitima";

export type Motivo = {
  feature: string;
  rotulo: string;
  valor: number | null;
  impacto: number | null;
};

export type CasoItem = {
  transacao_id: string;
  ts: string;
  origem: string;
  destino: string;
  valor: number;
  score: number;
  decisao: Decisao;
  rotulo: RotuloValor | null;
};

export type Casos = { itens: CasoItem[]; total: number };

export type Transacao = {
  id: string;
  ts: string;
  origem: string;
  destino: string;
  valor: number;
  dispositivo: string;
};

export type NoGrafo = {
  id: string;
  tipo: string;
  fraude_conhecida: boolean;
  salto: number;
};

export type ArestaGrafo = {
  source: string;
  target: string;
  qtd: number;
  valor_total: number;
};

export type Grafo = { nodes: NoGrafo[]; edges: ArestaGrafo[] };

export type CasoDetalhe = {
  transacao: Transacao;
  decisao: {
    score: number;
    decisao: Decisao;
    motivos: Motivo[];
    modelo_versao: string;
    latencia_ms: number;
  };
  rotulo: { rotulo: RotuloValor; analista: string; criado_em: string } | null;
  historico_origem: Transacao[];
  grafo: Grafo;
};

export type Resumo = { resumo: string; fonte: "llm" | "template" };

export type Metricas = {
  total: number;
  por_decisao: Record<Decisao, number>;
  valor_bloqueado: number;
  latencia_ms: { p50: number; p95: number; p99: number };
  rotulados: number;
  precisao_rotulos: number | null;
  modelo: {
    versao?: string;
    treinado_em?: string;
    metricas?: {
      pr_auc: number;
      limiares: Record<string, { precisao: number; recall: number }>;
    };
  } | null;
};
