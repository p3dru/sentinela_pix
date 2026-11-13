"""Popula banco e Redis, treina o modelo e pré-processa casos (`python -m sentinela.seed`)."""
import json
from collections import Counter
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, insert
from sqlalchemy.orm import Session

from . import grafo
from .db import Conta, Decisao, Rotulo, SessionLocal, Transacao, init_db, obter_redis
from .decisao import processar
from .features import EstadoRedis
from .gerador import gerar_contas, gerar_transacoes
from .modelo import Modelo
from .treino import FRACAO_TREINO, metricas_grafo_treino, treinar

LOTE = 5000


def inserir(sessao: Session, contas: list[dict[str, Any]], txs: list[dict[str, Any]]) -> None:
    """Insere contas e transações em lotes."""
    linhas = [{k: c[k] for k in ("id", "criada_em", "tipo")} for c in contas]
    for tabela, dados in ((Conta, linhas), (Transacao, txs)):
        for i in range(0, len(dados), LOTE):
            sessao.execute(insert(tabela), dados[i : i + LOTE])
    sessao.commit()


def main(
    n_contas: int = 2000, dias: int = 30, n_processar: int = 3000, n_estimators: int = 300
) -> dict[str, Any]:
    init_db()
    r = obter_redis()
    agora = datetime.now()
    inicio = agora - timedelta(days=dias)
    with SessionLocal() as s:
        for tabela in (Rotulo, Decisao, Transacao, Conta):
            s.execute(delete(tabela))
        s.commit()
        r.flushdb()

        contas = gerar_contas(n_contas, inicio=inicio)
        txs = gerar_transacoes(contas, inicio, dias)
        inserir(s, contas, txs)
        print(f"{len(contas)} contas e {len(txs)} transações inseridas")

        meta = treinar(s, n_estimators=n_estimators)
        Modelo.carregar()

        # estado online: últimos 2 dias, exceto as tx que serão processadas a seguir
        estado = EstadoRedis(r)
        ultimas = txs[-n_processar:]
        fim_estado = len(txs) - len(ultimas)
        for tx in txs[:fim_estado]:
            if tx["ts"] >= agora - timedelta(days=2):
                estado.registrar(tx)
        grafo.atualizar_redis(metricas_grafo_treino(txs[: int(len(txs) * FRACAO_TREINO)]), r)

        decisoes = Counter(processar(tx, estado, s)["decisao"] for tx in ultimas)
    print(f"{len(ultimas)} transações processadas: {dict(decisoes)}")
    print(json.dumps(meta["metricas"], indent=2))
    return meta


if __name__ == "__main__":
    main()
