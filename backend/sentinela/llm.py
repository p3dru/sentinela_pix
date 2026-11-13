"""Resumo do caso: LLM se houver chave; em qualquer erro, template determinístico."""
import json
import logging
from typing import Any

from .config import settings

PROMPT = (
    "Você apoia analistas de fraude em Pix. Com os dados do caso abaixo (JSON), escreva em português "
    "do Brasil exatamente 3 frases de resumo e, em seguida, 1 recomendação. Use só os dados fornecidos.\n\n"
)


def _template(caso: dict[str, Any]) -> str:
    tx, d = caso["transacao"], caso["decisao"]
    valor = f"R$ {tx['valor']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    motivos = "; ".join(m["rotulo"] for m in d["motivos"][:3]) or "sem motivos registrados"
    recomendacao = {
        "BLOQUEAR": "manter o bloqueio e contatar o titular da conta de origem.",
        "REVISAR": "confirmar a operação com o titular antes de liberar.",
    }.get(d["decisao"], "nenhuma ação adicional.")
    return (
        f"Transação de {valor} de {tx['origem']} para {tx['destino']}. "
        f"Score de risco {d['score']:.2f}, decisão {d['decisao']}. "
        f"Principais motivos: {motivos}. "
        f"Recomendação: {recomendacao}"
    )


def resumir(caso: dict[str, Any]) -> tuple[str, str]:
    """Retorna (resumo, fonte) com fonte `llm` ou `template`."""
    if settings.anthropic_api_key:
        try:
            import anthropic

            msg = anthropic.Anthropic(api_key=settings.anthropic_api_key).messages.create(
                model=settings.llm_model,
                max_tokens=400,
                messages=[
                    {"role": "user", "content": PROMPT + json.dumps(caso, ensure_ascii=False, default=str)}
                ],
            )
            return msg.content[0].text, "llm"
        except Exception:  # qualquer falha cai no template
            logging.getLogger(__name__).exception("Falha no LLM; usando template")
    return _template(caso), "template"
