"""Consome o stream e decide cada transação (`python -m sentinela.consumer`)."""
import json
import time
from datetime import datetime, timedelta
from typing import Any

import redis as redis_lib
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import grafo
from .config import settings
from .db import Rotulo, SessionLocal, Transacao, init_db, obter_redis
from .decisao import processar
from .features import EstadoRedis
from .modelo import Modelo
from .treino import FRACAO_TREINO

CAMPOS = ("origem", "destino", "valor", "dispositivo")


def fraudes_treino(s: Session) -> set[str]:
    """Destinos de fraude da janela de treino (primeiros 80% do que existia ao treinar)."""
    ate = Modelo.meta.get("treinado_em")
    if not ate:
        return set()
    historico = Transacao.ts <= datetime.fromisoformat(ate)
    n = s.scalar(select(func.count()).select_from(Transacao).where(historico))
    corte = s.scalar(
        select(Transacao.ts).where(historico).order_by(Transacao.ts, Transacao.id)
        .offset(int(n * FRACAO_TREINO)).limit(1)
    )
    if corte is None:
        return set()
    return set(s.scalars(select(Transacao.destino).where(Transacao.is_fraude, Transacao.ts < corte).distinct()))


def recalcular_grafo(s: Session, r: Any, base: set[str]) -> None:
    """Grafo das últimas 24h; fraudes conhecidas = treino + contas rotuladas no console."""
    q = select(Transacao.origem, Transacao.destino, Transacao.valor).where(
        Transacao.ts >= datetime.now() - timedelta(hours=24)
    )
    rotuladas = s.scalars(
        select(Transacao.destino).join(Rotulo, Rotulo.transacao_id == Transacao.id).where(Rotulo.rotulo == "fraude")
    )
    fraude = base | set(rotuladas) | set(r.smembers("contas_fraude"))
    G = grafo.construir(dict(m) for m in s.execute(q).mappings())
    grafo.atualizar_redis(grafo.calcular_metricas(G, fraude), r)


def consumir(
    r: Any, nome: str = "consumer-1", max_msgs: int | None = None, block: int = 2000,
    recalcular_cada: int = 500,
) -> int:
    """Laço de consumo; com `max_msgs` (testes) para ao atingir o total ou esvaziar o stream."""
    stream, grupo = settings.stream_name, settings.consumer_group

    def criar_grupo() -> None:
        try:
            r.xgroup_create(stream, grupo, id="0", mkstream=True)
        except redis_lib.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    criar_grupo()
    estado = EstadoRedis(r)
    n, soma_lat, t0 = 0, 0.0, time.perf_counter()
    cursor = "0"  # primeiro as pendentes de uma execução anterior, depois as novas
    with SessionLocal() as s:
        base = fraudes_treino(s)
        while max_msgs is None or n < max_msgs:
            try:
                resp = r.xreadgroup(grupo, nome, {stream: cursor}, count=100, block=block)
            except redis_lib.ResponseError as e:  # seed fez FLUSHDB: stream e grupo sumiram
                if "NOGROUP" not in str(e) and "UNBLOCKED" not in str(e):
                    raise
                criar_grupo()
                cursor = "0"
                continue
            Modelo.atualizar()
            msgs = resp[0][1] if resp else []
            if not msgs:
                if cursor == "0":
                    cursor = ">"
                elif max_msgs is not None:
                    break
                continue
            for msg_id, campos in msgs:
                try:
                    tx = json.loads(campos["dados"])
                    tx["ts"] = datetime.fromisoformat(tx["ts"])
                    faltam = [c for c in CAMPOS if c not in tx]
                    if faltam:
                        raise KeyError(*faltam)
                except (KeyError, ValueError, TypeError) as e:
                    print(f"mensagem inválida {msg_id} descartada: {e!r}")
                else:
                    soma_lat += processar(tx, estado, s)["latencia_ms"]  # faz commit
                r.xack(stream, grupo, msg_id)
                n += 1
                if n % 100 == 0:
                    dt = time.perf_counter() - t0
                    print(f"{n} msgs | {100 / dt:.1f} tps | latência média {soma_lat / 100:.2f} ms")
                    soma_lat, t0 = 0.0, time.perf_counter()
                if n % recalcular_cada == 0:
                    recalcular_grafo(s, r, base)
    return n


def main() -> None:
    init_db()
    if not Modelo.atualizar():
        print("Modelo não encontrado: aguardando make seed", flush=True)
        while not Modelo.atualizar():
            time.sleep(5)
    consumir(obter_redis())


if __name__ == "__main__":
    main()
