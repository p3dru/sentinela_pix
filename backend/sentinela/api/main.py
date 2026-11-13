"""API de decisão e console de analistas."""
from collections.abc import Iterator
from contextlib import asynccontextmanager
from datetime import datetime
from functools import lru_cache
from typing import Annotated, Any, Literal

import numpy as np
import redis
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import grafo, llm
from ..config import settings
from ..db import Conta, Decisao, Rotulo, SessionLocal, Transacao, init_db, obter_redis
from ..decisao import processar
from ..features import EstadoRedis
from ..modelo import Modelo
from .schemas import CasosSaida, DecisaoEntrada, DecisaoSaida, ResumoSaida, RotuloEntrada

REVISAVEIS = ("REVISAR", "BLOQUEAR")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    Modelo.carregar()
    yield


app = FastAPI(title="Sentinela Pix", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_sessao() -> Iterator[Session]:
    with SessionLocal() as s:
        yield s


@lru_cache
def get_redis() -> redis.Redis:
    return obter_redis()


Sessao = Annotated[Session, Depends(get_sessao)]
Redis = Annotated[redis.Redis, Depends(get_redis)]


def exigir_modelo() -> None:
    if not Modelo.carregado():
        raise HTTPException(503, "Modelo não carregado: rode make seed")


def _tx(t: Transacao) -> dict[str, Any]:
    return {
        "id": t.id, "ts": t.ts, "origem": t.origem, "destino": t.destino, "valor": t.valor,
        "dispositivo": t.dispositivo,
    }


def _caso(s: Session, id: str) -> tuple[Transacao, Decisao]:
    t, d = s.get(Transacao, id), s.get(Decisao, id)
    if t is None or d is None:
        raise HTTPException(404, "Caso não encontrado")
    return t, d


def _decisao(d: Decisao) -> dict[str, Any]:
    return {
        "score": d.score, "decisao": d.decisao, "motivos": d.motivos, "features": d.features,
        "modelo_versao": d.modelo_versao, "latencia_ms": d.latencia_ms, "criado_em": d.criado_em,
    }


def _grafo(s: Session, r: redis.Redis, conta: str) -> dict[str, list[dict[str, Any]]]:
    """Subgrafo de 2 saltos a partir das transações da conta e das de seus vizinhos."""

    def txs(ids: set[str], limite: int) -> list[dict[str, Any]]:
        # ponytail: só as mais recentes; pré-computar o grafo se contas muito conectadas ficarem truncadas
        q = (
            select(Transacao.origem, Transacao.destino, Transacao.valor)
            .where(or_(Transacao.origem.in_(ids), Transacao.destino.in_(ids)))
            .order_by(Transacao.ts.desc())
            .limit(limite)
        )
        return [dict(m) for m in s.execute(q).mappings()]

    vizinhos = {c for t in txs({conta}, 500) for c in (t["origem"], t["destino"])}
    G = grafo.construir(txs(vizinhos, 3000)) if vizinhos else grafo.construir([])
    sub = grafo.subgrafo_2_saltos(G, conta, contas_fraude=set(r.smembers("contas_fraude")))
    tipos = dict(s.execute(select(Conta.id, Conta.tipo).where(Conta.id.in_([n["id"] for n in sub["nodes"]]))).all())
    for n in sub["nodes"]:
        n["tipo"] = tipos.get(n["id"], "normal")
    return sub


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "modelo_versao": Modelo.versao()}


@app.post("/decisao", response_model=DecisaoSaida, dependencies=[Depends(exigir_modelo)])
def decisao(
    body: DecisaoEntrada, s: Sessao, r: Redis
) -> dict[str, Any]:
    return processar(body.model_dump(), EstadoRedis(r), s)


@app.get("/casos", response_model=CasosSaida)
def casos(
    s: Sessao,
    decisao: Literal["APROVAR", "REVISAR", "BLOQUEAR"] | None = None,
    pendentes: bool = False,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    q = (
        select(
            Transacao.id.label("transacao_id"), Transacao.ts, Transacao.origem, Transacao.destino,
            Transacao.valor, Decisao.score, Decisao.decisao, Rotulo.rotulo,
        )
        .join(Decisao, Decisao.transacao_id == Transacao.id)
        .outerjoin(Rotulo, Rotulo.transacao_id == Transacao.id)
    )
    if decisao:
        q = q.where(Decisao.decisao == decisao)
    if pendentes:
        q = q.where(Rotulo.transacao_id.is_(None))
    total = s.scalar(select(func.count()).select_from(q.subquery()))
    linhas = s.execute(q.order_by(Decisao.score.desc(), Transacao.id).limit(limit).offset(offset))
    return {"itens": [dict(m) for m in linhas.mappings()], "total": total}


@app.get("/casos/{id}")
def caso(id: str, s: Sessao, r: Redis) -> dict[str, Any]:
    t, d = _caso(s, id)
    rot = s.get(Rotulo, id)
    historico = s.scalars(
        select(Transacao).where(Transacao.origem == t.origem).order_by(Transacao.ts.desc()).limit(20)
    )
    return {
        "transacao": _tx(t),
        "decisao": _decisao(d),
        "rotulo": rot and {"rotulo": rot.rotulo, "analista": rot.analista, "criado_em": rot.criado_em},
        "historico_origem": [_tx(h) for h in historico],
        "grafo": _grafo(s, r, t.destino),
    }


@app.post("/casos/{id}/rotulo")
def rotular(
    id: str, body: RotuloEntrada, s: Sessao, r: Redis
) -> dict[str, Any]:
    t, _ = _caso(s, id)
    s.merge(Rotulo(transacao_id=id, rotulo=body.rotulo, analista=body.analista, criado_em=datetime.now()))
    s.commit()
    if body.rotulo == "fraude":
        r.sadd("contas_fraude", t.destino)
    return {"transacao_id": id, "rotulo": body.rotulo, "analista": body.analista}


@app.post("/casos/{id}/resumo", response_model=ResumoSaida)
def resumo(id: str, s: Sessao) -> dict[str, Any]:
    t, d = _caso(s, id)
    texto, fonte = llm.resumir({"transacao": _tx(t), "decisao": _decisao(d)})
    return {"resumo": texto, "fonte": fonte}


@app.get("/metricas")
def metricas(s: Sessao) -> dict[str, Any]:
    por_decisao = {"APROVAR": 0, "REVISAR": 0, "BLOQUEAR": 0}
    por_decisao.update(s.execute(select(Decisao.decisao, func.count()).group_by(Decisao.decisao)).all())
    bloqueado = s.scalar(
        select(func.coalesce(func.sum(Transacao.valor), 0.0))
        .join(Decisao, Decisao.transacao_id == Transacao.id)
        .where(Decisao.decisao == "BLOQUEAR")
    )
    # ponytail: carrega todas as latências; trocar por percentile_cont no Postgres se a tabela crescer
    lat = np.array(s.scalars(select(Decisao.latencia_ms)).all() or [0.0])
    rotulos = s.scalars(
        select(Rotulo.rotulo)
        .join(Decisao, Decisao.transacao_id == Rotulo.transacao_id)
        .where(Decisao.decisao.in_(REVISAVEIS))
    ).all()
    return {
        "total": sum(por_decisao.values()),
        "por_decisao": por_decisao,
        "valor_bloqueado": round(float(bloqueado), 2),
        "latencia_ms": {f"p{p}": round(float(np.percentile(lat, p)), 3) for p in (50, 95, 99)},
        "rotulados": s.scalar(select(func.count()).select_from(Rotulo)),
        "precisao_rotulos": round(rotulos.count("fraude") / len(rotulos), 4) if rotulos else None,
        "modelo": Modelo.meta,
    }
