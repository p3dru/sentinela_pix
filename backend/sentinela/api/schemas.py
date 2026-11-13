"""Schemas de entrada e saída da API."""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class DecisaoEntrada(BaseModel):
    id: str | None = None
    ts: datetime | None = None
    origem: str
    destino: str
    valor: float = Field(gt=0)
    dispositivo: str


class DecisaoSaida(BaseModel):
    transacao_id: str
    score: float
    decisao: str
    motivos: list[dict[str, Any]]
    latencia_ms: float
    modelo_versao: str


class RotuloEntrada(BaseModel):
    rotulo: Literal["fraude", "legitima"]
    analista: str = Field(min_length=1)


class CasoItem(BaseModel):
    transacao_id: str
    ts: datetime
    origem: str
    destino: str
    valor: float
    score: float
    decisao: str
    rotulo: str | None


class CasosSaida(BaseModel):
    itens: list[CasoItem]
    total: int


class ResumoSaida(BaseModel):
    resumo: str
    fonte: Literal["llm", "template"]
