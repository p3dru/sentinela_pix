import json
import os
from datetime import datetime
from pathlib import Path

import fakeredis
import numpy as np
from sqlalchemy import func, select

from sentinela.db import Decisao, SessionLocal
from sentinela.decisao import processar
from sentinela.features import FEATURES, EstadoRedis
from sentinela.modelo import Modelo
from sentinela.treino import average_precision

F = {
    "valor": 2500.0,
    "log_valor": 7.82,
    "hora": 3,
    "madrugada": 1,
    "qtd_origem_5m": 2,
    "qtd_origem_1h": 3,
    "soma_origem_1h": 4000.0,
    "destinatario_novo": 1,
    "dispositivo_novo": 1,
    "idade_conta_destino_dias": 5.0,
    "origens_distintas_destino_1h": 1,
    "razao_valor_media": 12.0,
    "grau_destino": 8,
    "dist_fraude_conhecida": 0,
}


def test_average_precision() -> None:
    assert average_precision(np.array([1, 0, 1, 0]), np.array([0.9, 0.8, 0.7, 0.1])) == (1 + 2 / 3) / 2
    assert average_precision(np.array([0, 0]), np.array([0.5, 0.1])) == 0.0


def test_meta_e_score(modelo_treinado: dict) -> None:
    assert modelo_treinado["features"] == FEATURES
    assert modelo_treinado["versao"].startswith("v")
    assert set(modelo_treinado["metricas"]["limiares"]) == {"0.4", "0.85"}
    assert 0.0 <= modelo_treinado["metricas"]["pr_auc"] <= 1.0
    assert 0.0 <= Modelo.pontuar(F) <= 1.0


def test_explicar(modelo_treinado: dict) -> None:
    motivos = Modelo.explicar(F)
    assert len(motivos) == 5
    for m in motivos:
        assert set(m) == {"feature", "rotulo", "valor", "impacto"}
        assert m["feature"] in FEATURES
    impactos = [abs(m["impacto"]) for m in motivos]
    assert impactos == sorted(impactos, reverse=True)


def test_processar_idempotente(modelo_treinado: dict, redis_fake: fakeredis.FakeRedis) -> None:
    tx = {
        "id": "tx-idempotente", "ts": datetime(2026, 1, 7, 3, 0), "origem": "conta-00001",
        "destino": "conta-00002", "valor": 2500.0, "dispositivo": "dev-novo",
    }
    estado = EstadoRedis(redis_fake)
    with SessionLocal() as s:
        primeira = processar(tx, estado, s)
        segunda = processar(tx, estado, s)
        total = s.scalar(select(func.count()).select_from(Decisao).where(Decisao.transacao_id == tx["id"]))
    assert primeira == segunda
    assert total == 1
    assert primeira["decisao"] == "BLOQUEAR"  # dispositivo novo de madrugada com valor > 2000
    assert primeira["motivos"][0]["feature"] == "regra"
    assert redis_fake.zcard("orig:conta-00001:ts") == 1  # registrou no estado uma única vez


def test_atualizar_recarrega_meta_alterado(modelo_treinado: dict) -> None:
    meta = Path(Modelo._caminhos[1])
    original = meta.read_text()
    try:
        meta.write_text(json.dumps({**json.loads(original), "versao": "v-novo"}))
        os.utime(meta, ns=(1, 1))
        assert Modelo.atualizar() and Modelo.versao() == "v-novo"
    finally:
        meta.write_text(original)
        assert Modelo.atualizar() and Modelo.versao() == modelo_treinado["versao"]
