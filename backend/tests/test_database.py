import pytest
from sqlalchemy import text

from app.infrastructure.database import create_database_engine


async def test_database_engine_uses_explicit_url() -> None:
    engine = create_database_engine("sqlite+aiosqlite:///:memory:")

    try:
        async with engine.connect() as connection:
            result = await connection.scalar(text("SELECT 1"))

        assert result == 1
    finally:
        await engine.dispose()


def test_database_engine_rejects_empty_explicit_url() -> None:
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        create_database_engine("")