"""Settings de teste: SQLite em memória e Redis falso (definidos antes de importar sentinela)."""
import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["REDIS_URL"] = "redis://fake:6379/0"
os.environ["ANTHROPIC_API_KEY"] = ""

from datetime import datetime

import fakeredis
import pytest

from sentinela.db import SessionLocal, init_db
from sentinela.gerador import gerar_contas, gerar_transacoes
from sentinela.modelo import Modelo
from sentinela.seed import inserir
from sentinela.treino import treinar

INICIO = datetime(2026, 1, 1, 15, 30)


@pytest.fixture(scope="session")
def modelo_treinado(tmp_path_factory: pytest.TempPathFactory) -> dict:
    """Banco com 300 contas × 5 dias e modelo pequeno treinado em diretório tmp."""
    pasta = tmp_path_factory.mktemp("artifacts")
    caminho, meta_caminho = str(pasta / "modelo.txt"), str(pasta / "modelo_meta.json")
    init_db()
    contas = gerar_contas(300, seed=7, inicio=INICIO)
    with SessionLocal() as s:
        inserir(s, contas, gerar_transacoes(contas, INICIO, 5, seed=7))
        meta = treinar(s, n_estimators=30, model_path=caminho, meta_path=meta_caminho)
    assert Modelo.carregar(caminho, meta_caminho)
    return meta


@pytest.fixture
def redis_fake() -> fakeredis.FakeRedis:
    return fakeredis.FakeRedis(decode_responses=True)
