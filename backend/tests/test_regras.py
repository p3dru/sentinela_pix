from sentinela.regras import decidir

BASE = {
    "dispositivo_novo": 0,
    "madrugada": 0,
    "valor": 100.0,
    "origens_distintas_destino_1h": 0,
    "destinatario_novo": 0,
    "razao_valor_media": 1.0,
}


def test_aprovar() -> None:
    assert decidir(0.1, BASE) == ("APROVAR", [])


def test_bloquear_por_score() -> None:
    decisao, regras = decidir(0.85, BASE)
    assert decisao == "BLOQUEAR" and len(regras) == 1


def test_bloquear_por_regra_de_dispositivo() -> None:
    f = {**BASE, "dispositivo_novo": 1, "madrugada": 1, "valor": 2000.01}
    decisao, regras = decidir(0.1, f)
    assert decisao == "BLOQUEAR" and "Dispositivo novo" in regras[0]
    assert decidir(0.1, {**f, "valor": 2000.0})[0] == "APROVAR"


def test_revisar_por_score() -> None:
    decisao, regras = decidir(0.4, BASE)
    assert decisao == "REVISAR" and len(regras) == 1
    assert decidir(0.39, BASE)[0] == "APROVAR"


def test_revisar_por_origens_distintas() -> None:
    decisao, regras = decidir(0.1, {**BASE, "origens_distintas_destino_1h": 5})
    assert decisao == "REVISAR" and "origens distintas" in regras[0]


def test_revisar_por_destinatario_novo_e_valor_atipico() -> None:
    f = {**BASE, "destinatario_novo": 1, "razao_valor_media": 10.0}
    decisao, regras = decidir(0.1, f)
    assert decisao == "REVISAR" and "Destinatário novo" in regras[0]
    assert decidir(0.1, {**f, "destinatario_novo": 0})[0] == "APROVAR"
