"""Publica transações ao vivo no stream (`python -m sentinela.produtor --tps 10 --minutos 10`)."""
import argparse
import json
import time
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .db import Conta, SessionLocal, obter_redis
from .gerador import gerar_contas, gerar_transacoes


def gerar_ao_vivo(sessao: Session, total: int, seed_contas: int = 42) -> list[dict[str, Any]]:
    """`total` transações do gerador para as contas do banco (ts é redefinido ao publicar)."""
    criada_em = dict(sessao.execute(select(Conta.id, Conta.criada_em)).all())
    if not criada_em:
        raise SystemExit("Sem contas no banco: rode make seed")
    # dispositivos e contatos dependem só de (n, seed): reconstrói os mesmos do seed
    contas = gerar_contas(len(criada_em), seed=seed_contas)
    for c in contas:
        c["criada_em"] = criada_em.get(c["id"], c["criada_em"])
    normais = sum(c["tipo"] == "normal" for c in contas)
    dias = total // (normais * 3) + 2
    # seed pelo relógio: ids novos a cada execução (ids repetidos seriam ignorados pela idempotência)
    return gerar_transacoes(contas, datetime.now(), dias, seed=int(time.time()))[:total]


def publicar(r: Any, txs: list[dict[str, Any]], tps: float) -> int:
    """XADD de cada transação com ts = agora, no ritmo de `tps` (0 = sem pausa)."""
    for tx in txs:
        dados = json.dumps({**tx, "ts": datetime.now().isoformat()})
        r.xadd(settings.stream_name, {"dados": dados})
        if tps:
            time.sleep(1 / tps)
    return len(txs)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tps", type=float, default=10)
    ap.add_argument("--minutos", type=float, default=10)
    a = ap.parse_args()
    with SessionLocal() as s:
        txs = gerar_ao_vivo(s, int(a.tps * a.minutos * 60))
    print(f"publicando {len(txs)} transações a {a.tps} tps em {settings.stream_name}")
    publicar(obter_redis(), txs, a.tps)


if __name__ == "__main__":
    main()
