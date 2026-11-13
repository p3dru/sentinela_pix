"""Settings de teste: SQLite em memória e Redis falso (definidos antes de importar sentinela)."""
import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["REDIS_URL"] = "redis://fake:6379/0"
os.environ["ANTHROPIC_API_KEY"] = ""

import fakeredis
import pytest


@pytest.fixture
def redis_fake() -> fakeredis.FakeRedis:
    return fakeredis.FakeRedis(decode_responses=True)
