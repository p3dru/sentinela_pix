"""Configuração lida de variáveis de ambiente / .env."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://sentinela:sentinela@localhost:5432/sentinela"
    redis_url: str = "redis://localhost:6379/0"
    stream_name: str = "pix:tx"
    consumer_group: str = "decisor"
    model_path: str = "artifacts/modelo.txt"
    model_meta_path: str = "artifacts/modelo_meta.json"
    anthropic_api_key: str = ""
    llm_model: str = "claude-haiku-5-5"
    cors_origins: str = "http://localhost:3000"


settings = Settings()
