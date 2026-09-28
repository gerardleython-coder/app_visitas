from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_initial_migration_creates_territorial_and_user_tables(tmp_path: Path) -> None:
    database_path = tmp_path / "migration.db"
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database_path}")

    command.upgrade(config, "head")
    command.check(config)

    engine = create_engine(f"sqlite:///{database_path}")
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    assert {"distritos", "iglesias", "usuarios"} <= tables


def test_postgresql_migration_declares_uuid_extension_and_role_type() -> None:
    output = StringIO()
    config = Config(
        str(Path(__file__).resolve().parents[1] / "alembic.ini"),
        output_buffer=output,
    )
    config.set_main_option(
        "sqlalchemy.url",
        "postgresql+asyncpg://placeholder:placeholder@localhost/app_visitas_dev",
    )

    command.upgrade(config, "head", sql=True)
    generated_sql = output.getvalue()

    assert "CREATE EXTENSION IF NOT EXISTS pgcrypto" in generated_sql
    assert "CREATE TYPE rol_usuario AS ENUM" in generated_sql
    assert generated_sql.count("CONSTRAINT ck_usuario_rol_valido CHECK") == 1

    downgrade_output = StringIO()
    downgrade_config = Config(
        str(Path(__file__).resolve().parents[1] / "alembic.ini"),
        output_buffer=downgrade_output,
    )
    downgrade_config.set_main_option(
        "sqlalchemy.url",
        "postgresql+asyncpg://placeholder:placeholder@localhost/app_visitas_dev",
    )
    command.downgrade(downgrade_config, "12e39403107c:base", sql=True)

    assert "DROP TYPE rol_usuario" in downgrade_output.getvalue()