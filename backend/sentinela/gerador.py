"""Gerador de contas e transações Pix sintéticas (determinístico por seed)."""
import uuid
from datetime import datetime, timedelta
from itertools import pairwise

import numpy as np

PADROES = ("falso_parente", "conta_laranja", "account_takeover")
_PESOS_HORA = np.array([5.0 if 8 <= h <= 22 else 1.0 for h in range(24)])
_PESOS_HORA /= _PESOS_HORA.sum()


def _uuid(rng: np.random.Generator) -> str:
    return str(uuid.UUID(bytes=rng.bytes(16), version=4))


def _dev(rng: np.random.Generator) -> str:
    return f"dev-{rng.bytes(4).hex()}"


def gerar_contas(n: int = 2000, seed: int = 42, inicio: datetime | None = None) -> list[dict]:
    """Contas com id, criada_em, tipo, dispositivos e contatos.

    Ids, dispositivos e contatos dependem só de (n, seed); `inicio` afeta apenas criada_em.
    """
    rng = np.random.default_rng(seed)
    inicio = inicio or datetime.now()
    laranjas = {int(i) for i in rng.choice(n, max(3, round(n * 0.05)), replace=False)}
    contas = []
    for i in range(n):
        laranja = i in laranjas
        idade = int(rng.integers(1, 31 if laranja else 1501))
        contas.append(
            {
                "id": f"conta-{i:05d}",
                "criada_em": inicio - timedelta(days=idade),
                "tipo": "laranja" if laranja else "normal",
                "dispositivos": [_dev(rng) for _ in range(int(rng.integers(1, 3)))],
                "contatos": [],
            }
        )
    normais = [c["id"] for c in contas if c["tipo"] == "normal"]
    for c in contas:
        if c["tipo"] != "normal":
            continue
        k = int(rng.integers(5, 16))
        cand = rng.choice(len(normais), min(k + 1, len(normais)), replace=False)
        c["contatos"] = [normais[j] for j in cand if normais[j] != c["id"]][:k]
    return contas


def gerar_transacoes(contas: list[dict], inicio: datetime, dias: int, seed: int = 42) -> list[dict]:
    """Transações normais + ~2% de fraudes em [inicio, inicio + dias), ordenadas por ts."""
    rng = np.random.default_rng(seed)
    fim = inicio + timedelta(days=dias)
    base = inicio.replace(hour=0, minute=0, second=0, microsecond=0)
    normais = [c for c in contas if c["tipo"] == "normal"]
    laranjas = [c for c in contas if c["tipo"] == "laranja"]
    txs: list[dict] = []

    def tx(ts: datetime, origem: str, destino: str, valor: float, dispositivo: str,
           padrao: str | None = None) -> None:
        txs.append(
            {
                "id": _uuid(rng),
                "ts": ts,
                "origem": origem,
                "destino": destino,
                "valor": round(float(valor), 2),
                "dispositivo": dispositivo,
                "is_fraude": padrao is not None,
                "padrao": padrao,
            }
        )

    def sortear(lista: list[dict]) -> dict:
        return lista[int(rng.integers(0, len(lista)))]

    # comportamento normal
    for c in normais:
        por_dia = rng.poisson(3, dias + 1)
        total = int(por_dia.sum())
        segundos = (
            np.repeat(np.arange(dias + 1), por_dia) * 86400
            + rng.choice(24, total, p=_PESOS_HORA) * 3600
            + rng.uniform(0, 3600, total)
        )
        valores = np.clip(rng.lognormal(4.5, 1.0, total), 1, 20000)
        dests = rng.integers(0, len(c["contatos"]), total)
        for s, v, d in zip(segundos, valores, dests):
            ts = base + timedelta(seconds=float(s))
            if inicio <= ts < fim:
                tx(ts, c["id"], c["contatos"][int(d)], v, c["dispositivos"][0])

    # fraudes: alterna os padrões até atingir ~2% do total
    alvo = round(len(txs) * 0.02 / 0.98)
    janela = dias * 86400
    n_fraude = i = 0
    while n_fraude < alvo:
        padrao = PADROES[i % 3]
        i += 1
        antes = len(txs)
        if padrao == "falso_parente":
            vitima, laranja = sortear(normais), sortear(laranjas)
            t0 = inicio + timedelta(seconds=float(rng.uniform(0, janela - 1800)))
            for _ in range(int(rng.integers(1, 4))):
                ts = t0 + timedelta(seconds=float(rng.uniform(0, 1800)))
                tx(ts, vitima["id"], laranja["id"], rng.uniform(500, 3000), vitima["dispositivos"][0], padrao)
        elif padrao == "conta_laranja":
            saltos = min(int(rng.integers(2, 4)), len(laranjas))
            cadeia = [laranjas[int(j)] for j in rng.choice(len(laranjas), saltos, replace=False)]
            n_vit = min(int(rng.integers(5, 21)), len(normais))
            vitimas = [normais[int(j)] for j in rng.choice(len(normais), n_vit, replace=False)]
            t0 = inicio + timedelta(seconds=float(rng.uniform(0, janela - 3 * 3600)))
            offsets = rng.uniform(0, 3600, n_vit)
            total = 0.0
            for vitima, off in zip(vitimas, offsets):
                valor = round(float(rng.uniform(200, 2000)), 2)
                total += valor
                ts = t0 + timedelta(seconds=float(off))
                tx(ts, vitima["id"], cadeia[0]["id"], valor, vitima["dispositivos"][0], padrao)
            t = t0 + timedelta(seconds=float(offsets.max()))
            for a, b in pairwise(cadeia):
                t += timedelta(seconds=float(rng.uniform(600, 2400)))
                total *= 0.9
                tx(t, a["id"], b["id"], total, a["dispositivos"][0], padrao)
        else:  # account_takeover
            vitima, novo = sortear(normais), _dev(rng)
            k = int(rng.integers(3, 9))
            while True:  # início entre 0h e 4h40 de algum dia dentro da janela
                t0 = base + timedelta(
                    days=int(rng.integers(0, dias + 1)), seconds=float(rng.uniform(0, 5 * 3600 - 1200))
                )
                if inicio <= t0 and t0 + timedelta(minutes=20) < fim:
                    break
            offsets = np.sort(rng.uniform(0, 1200, k))
            valores = np.sort(np.linspace(300, 5000, k) * rng.uniform(0.9, 1.1, k))
            for off, v in zip(offsets, valores):
                tx(t0 + timedelta(seconds=float(off)), vitima["id"], sortear(laranjas)["id"], v, novo, padrao)
        n_fraude += len(txs) - antes

    txs.sort(key=lambda t: (t["ts"], t["id"]))
    return txs
