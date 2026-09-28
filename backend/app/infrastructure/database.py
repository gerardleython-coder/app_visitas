from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str | None = None


class Base(DeclarativeBase):
    pass


def create_database_engine(database_url: str | None = None) -> AsyncEngine:
    resolved_url = database_url if database_url is not None else DatabaseSettings().database_url
    if not resolved_url:
        raise RuntimeError("DATABASE_URL debe configurarse en el entorno o en backend/.env")

    return create_async_engine(resolved_url, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)