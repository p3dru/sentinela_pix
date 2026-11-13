"""Grafo de contas: métricas para as features e subgrafo para o console."""
from collections.abc import Iterable
from typing import Any

import networkx as nx


def construir(transacoes: Iterable[dict[str, Any]]) -> nx.Graph:
    """Grafo não-direcionado; aresta origem–destino com qtd e valor_total."""
    G = nx.Graph()
    for t in transacoes:
        o, d = t["origem"], t["destino"]
        if G.has_edge(o, d):
            G[o][d]["qtd"] += 1
            G[o][d]["valor_total"] += t["valor"]
        else:
            G.add_edge(o, d, qtd=1, valor_total=t["valor"])
    return G


def calcular_metricas(G: nx.Graph, contas_fraude: set[str]) -> dict[str, dict[str, int]]:
    """Por conta: grau e menor distância (até 3; 4 se nenhuma) a uma conta de fraude conhecida."""
    fontes = {c for c in contas_fraude if c in G}
    # weight=None: cada aresta vale 1 salto
    dist = nx.multi_source_dijkstra_path_length(G, fontes, cutoff=3, weight=None) if fontes else {}
    return {
        n: {"grau_destino": G.degree(n), "dist_fraude_conhecida": int(dist.get(n, 4))} for n in G.nodes
    }


def atualizar_redis(metricas: dict[str, dict[str, int]], redis: Any) -> None:
    """Grava os hashes `grafo:{id}`."""
    p = redis.pipeline()
    for i, (conta, m) in enumerate(metricas.items(), 1):
        p.hset(f"grafo:{conta}", mapping=m)
        if i % 5000 == 0:
            p.execute()
    p.execute()


def subgrafo_2_saltos(
    G: nx.Graph,
    conta: str,
    max_nos: int = 40,
    tipos: dict[str, str] | None = None,
    contas_fraude: set[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Vizinhança de até 2 saltos da conta, limitada a max_nos (os mais próximos primeiro)."""
    tipos, contas_fraude = tipos or {}, contas_fraude or set()
    saltos = nx.single_source_shortest_path_length(G, conta, cutoff=2) if conta in G else {conta: 0}
    escolhidos = dict(sorted(saltos.items(), key=lambda kv: kv[1])[:max_nos])
    nodes = [
        {"id": n, "tipo": tipos.get(n, "normal"), "fraude_conhecida": n in contas_fraude, "salto": s}
        for n, s in escolhidos.items()
    ]
    edges = [
        {"source": a, "target": b, "qtd": d["qtd"], "valor_total": round(d["valor_total"], 2)}
        for a, b, d in G.subgraph(escolhidos).edges(data=True)
    ]
    return {"nodes": nodes, "edges": edges}
