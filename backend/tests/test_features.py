from datetime import datetime, timedelta

import fakeredis
import pytest

from sentinela import grafo
from sentinela.features import FEATURES, ROTULOS_PT, EstadoMemoria, EstadoRedis, calcular_features
from sentinela.gerador import gerar_contas, gerar_transacoes

INICIO = datetime(2026, 1, 1, 15, 30)
T = datetime(2026, 3, 10, 14, 0)


def _tx(i: int, ts: datetime, origem: str, destino: str, valor: float, dev: str = "dev-a") -> dict:
    return {"id": f"tx-{i}", "ts": ts, "origem": origem, "destino": destino, "valor": valor, "dispositivo": dev}


def test_consistencia_online_offline(redis_fake: fakeredis.FakeRedis) -> None:
    contas = gerar_contas(300, seed=7, inicio=INICIO)
    txs = gerar_transacoes(contas, INICIO, 5, seed=7)[:500]
    criada_em = {c["id"]: c["criada_em"] for c in contas}
    metricas = grafo.calcular_metricas(grafo.construir(txs), {txs[0]["destino"], txs[10]["destino"]})

    memoria, online = EstadoMemoria(), EstadoRedis(redis_fake)
    memoria.grafo_metricas = metricas
    grafo.atualizar_redis(metricas, redis_fake)

    for tx in txs:
        f_mem = calcular_features(tx, memoria, criada_em)
        f_red = calcular_features(tx, online, criada_em)
        assert f_mem == f_red
        assert list(f_mem) == FEATURES
        memoria.registrar(tx)
        online.registrar(tx)
    assert set(ROTULOS_PT) == set(FEATURES)
    assert any(f_mem["dist_fraude_conhecida"] < 4 for f_mem in [calcular_features(t, memoria, criada_em) for t in txs])


@pytest.mark.parametrize("tipo", ["memoria", "redis"])
def test_janelas_caso_manual(tipo: str, redis_fake: fakeredis.FakeRedis) -> None:
    estado = EstadoMemoria() if tipo == "memoria" else EstadoRedis(redis_fake)
    historico = [
        _tx(1, T - timedelta(hours=2), "A", "B", 100.0),  # fora de 1h
        _tx(2, T - timedelta(minutes=50), "A", "B", 200.0),  # 1h
        _tx(3, T - timedelta(minutes=4), "A", "C", 300.0),  # 5m e 1h
        _tx(4, T - timedelta(minutes=1), "A", "B", 400.0),  # 5m e 1h
        _tx(5, T - timedelta(minutes=90), "X", "Z", 10.0),  # origem de Z fora de 1h
        _tx(6, T - timedelta(minutes=30), "Y", "Z", 10.0),
        _tx(7, T - timedelta(minutes=10), "W", "Z", 10.0),
        _tx(8, T - timedelta(minutes=5), "W", "Z", 10.0),  # mesma origem: não conta duas vezes
    ]
    for tx in sorted(historico, key=lambda t: t["ts"]):
        estado.registrar(tx)

    criada_em = {"Z": T - timedelta(days=10)}
    f = calcular_features(_tx(9, T, "A", "Z", 2500.0, dev="dev-novo"), estado, criada_em)
    assert f["qtd_origem_5m"] == 2
    assert f["qtd_origem_1h"] == 3
    assert f["soma_origem_1h"] == 900.0
    assert f["origens_distintas_destino_1h"] == 2
    assert f["destinatario_novo"] == 1
    assert f["dispositivo_novo"] == 1
    assert f["razao_valor_media"] == 10.0  # média das 4 tx de A = 250
    assert f["idade_conta_destino_dias"] == 10.0
    assert (f["hora"], f["madrugada"]) == (14, 0)
    assert (f["grau_destino"], f["dist_fraude_conhecida"]) == (0, 4)

    conhecido = calcular_features(_tx(10, T, "A", "B", 250.0), estado, criada_em)
    assert conhecido["destinatario_novo"] == 0
    assert conhecido["dispositivo_novo"] == 0
    assert conhecido["razao_valor_media"] == 1.0
