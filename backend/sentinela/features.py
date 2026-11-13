"""Features de risco — a mesma função serve o batch (treino) e o online (decisão)."""
import math
from collections import defaultdict, deque
from datetime import datetime
from typing import Any, Protocol

FEATURES = [
    "valor",
    "log_valor",
    "hora",
    "madrugada",
    "qtd_origem_5m",
    "qtd_origem_1h",
    "soma_origem_1h",
    "destinatario_novo",
    "dispositivo_novo",
    "idade_conta_destino_dias",
    "origens_distintas_destino_1h",
    "razao_valor_media",
    "grau_destino",
    "dist_fraude_conhecida",
]

ROTULOS_PT = {
    "valor": "Valor da transação",
    "log_valor": "Valor (escala log)",
    "hora": "Hora do dia",
    "madrugada": "Transação de madrugada",
    "qtd_origem_5m": "Transações da origem em 5 min",
    "qtd_origem_1h": "Transações da origem em 1 h",
    "soma_origem_1h": "Total enviado pela origem em 1 h",
    "destinatario_novo": "Destinatário novo",
    "dispositivo_novo": "Dispositivo novo",
    "idade_conta_destino_dias": "Idade da conta de destino (dias)",
    "origens_distintas_destino_1h": "Origens distintas enviando ao destino em 1 h",
    "razao_valor_media": "Valor em relação à média da origem",
    "grau_destino": "Contrapartes do destino",
    "dist_fraude_conhecida": "Distância a fraude conhecida",
}

JANELA_5M = 300.0
JANELA_1H = 3600.0
ULTIMOS_VALORES = 30
GRAFO_PADRAO = (0, 4)  # (grau_destino, dist_fraude_conhecida) para conta fora do grafo


class Estado(Protocol):
    """Histórico consultado pelas features. Janelas são fechadas: [desde, ate]."""

    def janela_origem(self, origem: str, desde: float, ate: float) -> list[tuple[float, float]]:
        """(epoch, valor) das tx da origem na janela."""

    def conhece_destino(self, origem: str, destino: str) -> bool: ...

    def conhece_dispositivo(self, origem: str, dispositivo: str) -> bool: ...

    def origens_distintas(self, destino: str, desde: float, ate: float) -> int: ...

    def ultimos_valores(self, origem: str) -> list[float]: ...

    def grafo(self, conta: str) -> tuple[int, int]: ...

    def registrar(self, tx: dict[str, Any]) -> None: ...


class EstadoMemoria:
    """Estado em dicts/deques, para o batch."""

    def __init__(self) -> None:
        self._tx: dict[str, deque[tuple[float, float]]] = defaultdict(deque)
        self._dests: dict[str, set[str]] = defaultdict(set)
        self._devs: dict[str, set[str]] = defaultdict(set)
        self._origs: dict[str, dict[str, float]] = defaultdict(dict)
        self._vals: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=ULTIMOS_VALORES))
        self.grafo_metricas: dict[str, dict[str, int]] = {}

    def janela_origem(self, origem: str, desde: float, ate: float) -> list[tuple[float, float]]:
        return [(t, v) for t, v in self._tx.get(origem, ()) if desde <= t <= ate]

    def conhece_destino(self, origem: str, destino: str) -> bool:
        return destino in self._dests.get(origem, ())

    def conhece_dispositivo(self, origem: str, dispositivo: str) -> bool:
        return dispositivo in self._devs.get(origem, ())

    def origens_distintas(self, destino: str, desde: float, ate: float) -> int:
        return sum(desde <= t <= ate for t in self._origs.get(destino, {}).values())

    def ultimos_valores(self, origem: str) -> list[float]:
        return list(self._vals.get(origem, ()))

    def grafo(self, conta: str) -> tuple[int, int]:
        m = self.grafo_metricas.get(conta)
        return (m["grau_destino"], m["dist_fraude_conhecida"]) if m else GRAFO_PADRAO

    def registrar(self, tx: dict[str, Any]) -> None:
        origem, destino, valor = tx["origem"], tx["destino"], float(tx["valor"])
        e = tx["ts"].timestamp()
        corte = e - JANELA_1H
        fila = self._tx[origem]
        fila.append((e, valor))
        while fila and fila[0][0] < corte:
            fila.popleft()
        origs = self._origs[destino]
        origs[origem] = e
        for o in [o for o, t in origs.items() if t < corte]:
            del origs[o]
        self._dests[origem].add(destino)
        self._devs[origem].add(tx["dispositivo"])
        self._vals[origem].append(valor)


def _s(x: Any) -> str:
    return x.decode() if isinstance(x, bytes) else x


class EstadoRedis:
    """Estado no Redis, para o online. Mesma semântica do EstadoMemoria."""

    def __init__(self, redis: Any) -> None:
        self.r = redis

    def janela_origem(self, origem: str, desde: float, ate: float) -> list[tuple[float, float]]:
        itens = self.r.zrangebyscore(f"orig:{origem}:ts", desde, ate, withscores=True)
        return [(float(score), float(_s(membro).rsplit("|", 1)[1])) for membro, score in itens]

    def conhece_destino(self, origem: str, destino: str) -> bool:
        return bool(self.r.sismember(f"orig:{origem}:dests", destino))

    def conhece_dispositivo(self, origem: str, dispositivo: str) -> bool:
        return bool(self.r.sismember(f"orig:{origem}:devs", dispositivo))

    def origens_distintas(self, destino: str, desde: float, ate: float) -> int:
        return int(self.r.zcount(f"dest:{destino}:origs", desde, ate))

    def ultimos_valores(self, origem: str) -> list[float]:
        return [float(v) for v in self.r.lrange(f"orig:{origem}:vals", 0, -1)]

    def grafo(self, conta: str) -> tuple[int, int]:
        grau, dist = self.r.hmget(f"grafo:{conta}", "grau_destino", "dist_fraude_conhecida")
        if grau is None or dist is None:
            return GRAFO_PADRAO
        return int(grau), int(dist)

    def registrar(self, tx: dict[str, Any]) -> None:
        origem, destino, valor = tx["origem"], tx["destino"], float(tx["valor"])
        e = tx["ts"].timestamp()
        corte = f"({e - JANELA_1H!r}"  # exclusivo: expira só o que é mais antigo que 1h
        p = self.r.pipeline()
        p.zadd(f"orig:{origem}:ts", {f"{tx['id']}|{valor!r}": e})
        p.zremrangebyscore(f"orig:{origem}:ts", "-inf", corte)
        p.zadd(f"dest:{destino}:origs", {origem: e})
        p.zremrangebyscore(f"dest:{destino}:origs", "-inf", corte)
        p.sadd(f"orig:{origem}:dests", destino)
        p.sadd(f"orig:{origem}:devs", tx["dispositivo"])
        p.lpush(f"orig:{origem}:vals", repr(valor))
        p.ltrim(f"orig:{origem}:vals", 0, ULTIMOS_VALORES - 1)
        p.execute()


def calcular_features(
    tx: dict[str, Any], estado: Estado, contas_criada_em: dict[str, datetime]
) -> dict[str, float]:
    """Calcula as features lendo o estado ANTES de `estado.registrar(tx)`."""
    ts: datetime = tx["ts"]
    origem, destino, valor = tx["origem"], tx["destino"], float(tx["valor"])
    e = ts.timestamp()
    janela = estado.janela_origem(origem, e - JANELA_1H, e)
    ultimos = estado.ultimos_valores(origem)
    # fsum: soma independe da ordem, então memória e Redis dão o mesmo float
    media = math.fsum(ultimos) / len(ultimos) if ultimos else 0.0
    criada = contas_criada_em.get(destino)
    grau, dist = estado.grafo(destino)
    return {
        "valor": valor,
        "log_valor": math.log1p(valor),
        "hora": ts.hour,
        "madrugada": int(ts.hour < 6),
        "qtd_origem_5m": sum(t >= e - JANELA_5M for t, _ in janela),
        "qtd_origem_1h": len(janela),
        "soma_origem_1h": math.fsum(v for _, v in janela),
        "destinatario_novo": int(not estado.conhece_destino(origem, destino)),
        "dispositivo_novo": int(not estado.conhece_dispositivo(origem, tx["dispositivo"])),
        "idade_conta_destino_dias": (ts - criada).total_seconds() / 86400 if criada else 0.0,
        "origens_distintas_destino_1h": estado.origens_distintas(destino, e - JANELA_1H, e),
        "razao_valor_media": valor / media if media > 0 else 1.0,
        "grau_destino": grau,
        "dist_fraude_conhecida": dist,
    }
