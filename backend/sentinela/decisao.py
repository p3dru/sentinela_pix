"""Decisão de uma transação: features → score → explicação → regras → persistência."""
import time
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from .db import Conta, Decisao, Transacao
from .features import Estado, calcular_features
from .modelo import Modelo
from .regras import decidir


def _payload(d: Decisao) -> dict[str, Any]:
    return {
        "transacao_id": d.transacao_id,
        "score": d.score,
        "decisao": d.decisao,
        "motivos": d.motivos,
        "latencia_ms": d.latencia_ms,
        "modelo_versao": d.modelo_versao,
    }


def processar(tx: dict[str, Any], estado: Estado, sessao: Session) -> dict[str, Any]:
    """Idempotente por id: se já há decisão, retorna a existente sem reprocessar."""
    t0 = time.perf_counter()
    tx = dict(tx)
    tx["id"] = tx.get("id") or str(uuid.uuid4())
    ts = tx.get("ts") or datetime.now()
    if ts.tzinfo is not None:  # o resto do sistema usa hora local ingênua
        ts = ts.astimezone().replace(tzinfo=None)
    tx["ts"] = ts

    existente = sessao.get(Decisao, tx["id"])
    if existente is not None:
        return _payload(existente)

    conta = sessao.get(Conta, tx["destino"])
    f = calcular_features(tx, estado, {conta.id: conta.criada_em} if conta else {})
    score = Modelo.pontuar(f)
    decisao, regras = decidir(score, f)
    motivos = [{"feature": "regra", "rotulo": r, "valor": None, "impacto": None} for r in regras]
    motivos += Modelo.explicar(f)
    estado.registrar(tx)

    if sessao.get(Transacao, tx["id"]) is None:
        sessao.add(
            Transacao(
                id=tx["id"], ts=ts, origem=tx["origem"], destino=tx["destino"], valor=float(tx["valor"]),
                dispositivo=tx["dispositivo"], is_fraude=bool(tx.get("is_fraude", False)),
                padrao=tx.get("padrao"),
            )
        )
        sessao.flush()  # a decisão referencia a transação
    registro = Decisao(
        transacao_id=tx["id"], score=score, decisao=decisao, motivos=motivos, features=f,
        modelo_versao=Modelo.versao() or "", latencia_ms=round((time.perf_counter() - t0) * 1000, 3),
    )
    sessao.add(registro)
    sessao.commit()
    return _payload(registro)
