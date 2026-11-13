"""Engine, sessão e modelos ORM."""
from datetime import datetime

import redis
from sqlalchemy import JSON, ForeignKey, create_engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

from .config import settings

if settings.database_url.startswith("sqlite"):
    # SQLite em memória (testes): uma única conexão compartilhada
    engine = create_engine(
        settings.database_url, connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
else:
    engine = create_engine(settings.database_url, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Conta(Base):
    __tablename__ = "contas"
    id: Mapped[str] = mapped_column(primary_key=True)
    criada_em: Mapped[datetime]
    tipo: Mapped[str]  # normal | laranja


class Transacao(Base):
    __tablename__ = "transacoes"
    id: Mapped[str] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(index=True)
    origem: Mapped[str] = mapped_column(index=True)
    destino: Mapped[str] = mapped_column(index=True)
    valor: Mapped[float]
    dispositivo: Mapped[str]
    is_fraude: Mapped[bool] = mapped_column(default=False)
    padrao: Mapped[str | None] = mapped_column(default=None)


class Decisao(Base):
    __tablename__ = "decisoes"
    transacao_id: Mapped[str] = mapped_column(ForeignKey("transacoes.id"), primary_key=True)
    score: Mapped[float]
    decisao: Mapped[str] = mapped_column(index=True)
    motivos: Mapped[list] = mapped_column(JSON)
    features: Mapped[dict] = mapped_column(JSON)
    modelo_versao: Mapped[str]
    latencia_ms: Mapped[float]
    criado_em: Mapped[datetime] = mapped_column(default=datetime.now)


class Rotulo(Base):
    __tablename__ = "rotulos"
    transacao_id: Mapped[str] = mapped_column(ForeignKey("transacoes.id"), primary_key=True)
    rotulo: Mapped[str]  # fraude | legitima
    analista: Mapped[str]
    criado_em: Mapped[datetime] = mapped_column(default=datetime.now)


def init_db() -> None:
    try:
        Base.metadata.create_all(engine)
    except DBAPIError:  # API e consumer criando as tabelas ao mesmo tempo: na 2ª elas já existem
        Base.metadata.create_all(engine)


def obter_redis() -> redis.Redis:
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)
