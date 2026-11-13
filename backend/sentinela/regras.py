"""Regras de negócio aplicadas sobre o score do modelo."""
from typing import Any

LIMIAR_BLOQUEAR = 0.85
LIMIAR_REVISAR = 0.40


def decidir(score: float, f: dict[str, Any]) -> tuple[str, list[str]]:
    """Retorna (decisao, regras_disparadas). BLOQUEAR tem precedência sobre REVISAR."""
    bloquear = []
    if score >= LIMIAR_BLOQUEAR:
        bloquear.append(f"Score do modelo acima de {LIMIAR_BLOQUEAR:.2f}")
    if f["dispositivo_novo"] and f["madrugada"] and f["valor"] > 2000:
        bloquear.append("Dispositivo novo de madrugada com valor acima de R$ 2.000")
    if bloquear:
        return "BLOQUEAR", bloquear

    revisar = []
    if score >= LIMIAR_REVISAR:
        revisar.append(f"Score do modelo acima de {LIMIAR_REVISAR:.2f}")
    if f["origens_distintas_destino_1h"] >= 5:
        revisar.append("Destino recebeu de 5 ou mais origens distintas em 1 hora")
    if f["destinatario_novo"] and f["razao_valor_media"] >= 10:
        revisar.append("Destinatário novo com valor 10x acima da média da origem")
    if revisar:
        return "REVISAR", revisar
    return "APROVAR", []
