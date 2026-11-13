from datetime import datetime
from itertools import pairwise

from sentinela.gerador import PADROES, gerar_contas, gerar_transacoes

INICIO = datetime(2026, 1, 1, 15, 30)


def _gerar(seed: int = 7) -> tuple[list[dict], list[dict]]:
    contas = gerar_contas(300, seed=seed, inicio=INICIO)
    return contas, gerar_transacoes(contas, INICIO, 5, seed=seed)


def test_determinismo() -> None:
    assert _gerar() == _gerar()
    assert _gerar(7)[1] != _gerar(8)[1]


def test_taxa_de_fraude_e_ordem() -> None:
    _, txs = _gerar()
    taxa = sum(t["is_fraude"] for t in txs) / len(txs)
    assert 0.005 <= taxa <= 0.05
    assert all(a["ts"] <= b["ts"] for a, b in pairwise(txs))
    assert all(1 <= t["valor"] for t in txs)


def test_tres_padroes_presentes() -> None:
    contas, txs = _gerar()
    assert {t["padrao"] for t in txs if t["is_fraude"]} == set(PADROES)
    laranjas = {c["id"] for c in contas if c["tipo"] == "laranja"}
    assert all(t["destino"] in laranjas for t in txs if t["is_fraude"])
    ato = [t for t in txs if t["padrao"] == "account_takeover"]
    assert all(t["ts"].hour < 5 for t in ato)
