import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from sentinela.api.main import app, get_redis
from sentinela.db import Decisao, SessionLocal


@pytest.fixture
def cliente(modelo_treinado, redis_fake):
    app.dependency_overrides[get_redis] = lambda: redis_fake
    yield TestClient(app)  # sem `with`: o lifespan recarregaria o modelo dos caminhos padrão
    app.dependency_overrides.clear()


def _tx(id: str, valor: float = 3000.0) -> dict:
    """Madrugada + dispositivo novo + valor > 2000: BLOQUEAR pela regra, qualquer que seja o score."""
    return {
        "id": id, "ts": "2026-01-06T03:00:00", "origem": "conta-00001", "destino": "conta-00002",
        "valor": valor, "dispositivo": f"dev-{id}",
    }


def test_health(cliente):
    r = cliente.get("/health").json()
    assert r["status"] == "ok" and r["modelo_versao"].startswith("v")


def test_decisao_campos_e_idempotencia(cliente):
    a = cliente.post("/decisao", json=_tx("api-idem"))
    assert a.status_code == 200
    assert set(a.json()) == {"transacao_id", "score", "decisao", "motivos", "latencia_ms", "modelo_versao"}
    assert a.json()["decisao"] == "BLOQUEAR"
    assert cliente.post("/decisao", json=_tx("api-idem", valor=9999.0)).json() == a.json()
    with SessionLocal() as s:
        assert s.scalar(select(func.count()).where(Decisao.transacao_id == "api-idem")) == 1


def test_casos_ordenados_por_score(cliente):
    for i in range(4):
        cliente.post("/decisao", json=_tx(f"api-ord-{i}", valor=2500.0 + 700 * i))
    r = cliente.get("/casos", params={"decisao": "BLOQUEAR"}).json()
    scores = [c["score"] for c in r["itens"]]
    assert r["total"] >= 4 and scores == sorted(scores, reverse=True)
    assert {c["decisao"] for c in r["itens"]} == {"BLOQUEAR"}


def test_rotulo_detalhe_e_pendentes(cliente, redis_fake):
    cliente.post("/decisao", json=_tx("api-rot"))
    assert cliente.post("/casos/nao-existe/rotulo", json={"rotulo": "fraude", "analista": "a"}).status_code == 404
    assert cliente.get("/casos/nao-existe").status_code == 404
    for rotulo in ("legitima", "fraude"):  # upsert
        r = cliente.post("/casos/api-rot/rotulo", json={"rotulo": rotulo, "analista": "analista.demo"})
        assert r.status_code == 200
    d = cliente.get("/casos/api-rot").json()
    assert d["rotulo"]["rotulo"] == "fraude" and d["transacao"]["id"] == "api-rot"
    assert d["historico_origem"] and "conta-00002" in {n["id"] for n in d["grafo"]["nodes"]}
    assert redis_fake.sismember("contas_fraude", "conta-00002")
    pendentes = cliente.get("/casos", params={"pendentes": "true", "limit": 500}).json()["itens"]
    assert "api-rot" not in {c["transacao_id"] for c in pendentes}


def test_resumo_sem_chave_usa_template(cliente):
    cliente.post("/decisao", json=_tx("api-res"))
    r = cliente.post("/casos/api-res/resumo").json()
    assert r["fonte"] == "template" and "Recomendação" in r["resumo"]


def test_metricas(cliente):
    cliente.post("/decisao", json=_tx("api-met"))
    cliente.post("/casos/api-met/rotulo", json={"rotulo": "fraude", "analista": "analista.demo"})
    m = cliente.get("/metricas").json()
    assert m["total"] == sum(m["por_decisao"].values()) >= 1
    assert m["valor_bloqueado"] >= 3000 and m["rotulados"] >= 1
    assert 0 < m["precisao_rotulos"] <= 1
    assert set(m["latencia_ms"]) == {"p50", "p95", "p99"} and m["modelo"]["versao"]


def test_produtor_consumer(modelo_treinado, redis_fake):
    from sentinela import consumer, produtor
    from sentinela.config import settings

    with SessionLocal() as s:
        txs = produtor.gerar_ao_vivo(s, 30, seed_contas=7)
    assert produtor.publicar(redis_fake, txs, tps=0) == 30
    redis_fake.xadd(settings.stream_name, {"dados": "{"})  # inválida: descartada sem travar a fila
    assert consumer.consumir(redis_fake, max_msgs=31, block=10, recalcular_cada=10) == 31
    with SessionLocal() as s:
        ids = [t["id"] for t in txs]
        assert s.scalar(select(func.count()).where(Decisao.transacao_id.in_(ids))) == 30
    assert redis_fake.xpending(settings.stream_name, settings.consumer_group)["pending"] == 0
    assert redis_fake.exists(f"grafo:{txs[0]['destino']}")
