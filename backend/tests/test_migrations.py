from io import StringIO
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


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

    assert {
        "distritos",
        "iglesias",
        "usuarios",
        "sesiones_refresh",
        "asignaciones_hermano",
        "visitas",
        "visita_historial",
        "auditoria",
    } <= tables


def test_refresh_family_migration_backfills_existing_sessions(tmp_path: Path) -> None:
    database_path = tmp_path / "refresh-family.db"
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database_path}")
    command.upgrade(config, "f6117ca1487e")

    session_id = uuid4()
    engine = create_engine(f"sqlite:///{database_path}")
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO sesiones_refresh "
                    "(id, usuario_id, token_hash, expira_at, created_at) "
                    "VALUES (:id, :user_id, :token_hash, :expires_at, :created_at)"
                ),
                {
                    "id": session_id.hex,
                    "user_id": uuid4().hex,
                    "token_hash": "legacy-refresh-hash",
                    "expires_at": "2030-01-01T00:00:00+00:00",
                    "created_at": "2026-01-01T00:00:00+00:00",
                },
            )
    finally:
        engine.dispose()

    command.upgrade(config, "head")

    engine = create_engine(f"sqlite:///{database_path}")
    try:
        with engine.connect() as connection:
            family_id = connection.scalar(
                text("SELECT family_id FROM sesiones_refresh WHERE id = :id"),
                {"id": session_id.hex},
            )
    finally:
        engine.dispose()

    assert family_id is not None
    assert session_id.hex == family_id.replace("-", "")


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
    command.downgrade(downgrade_config, "d2f4e63b0a91:base", sql=True)

    assert "DROP TYPE rol_usuario" in downgrade_output.getvalue()
    assert "DROP TRIGGER IF EXISTS trg_proteger_historial_visita ON visita_historial" in (
        downgrade_output.getvalue()
    )
    assert "DROP FUNCTION IF EXISTS proteger_historial_visita()" in (
        downgrade_output.getvalue()
    )
    assert "DROP TRIGGER IF EXISTS trg_validar_alcance_visita ON visitas" in (
        downgrade_output.getvalue()
    )
    assert "DROP FUNCTION IF EXISTS validar_alcance_visita()" in (
        downgrade_output.getvalue()
    )
    assert "DROP TABLE visita_historial" in downgrade_output.getvalue()
    assert "DROP TABLE visitas" in downgrade_output.getvalue()
    assert "DROP TRIGGER IF EXISTS trg_proteger_auditoria ON auditoria" in (
        downgrade_output.getvalue()
    )
    assert "DROP FUNCTION IF EXISTS proteger_auditoria()" in downgrade_output.getvalue()
    assert "DROP INDEX ix_auditoria_recurso" in downgrade_output.getvalue()
    assert "DROP INDEX ix_auditoria_iglesia_fecha" in downgrade_output.getvalue()
    assert "DROP TABLE auditoria" in downgrade_output.getvalue()
    assert "ALTER TABLE visita_historial ALTER COLUMN datos_anteriores TYPE JSON" in (
        downgrade_output.getvalue()
    )
    assert "ALTER TABLE visita_historial ALTER COLUMN datos_nuevos TYPE JSON" in (
        downgrade_output.getvalue()
    )
    assert "DROP TABLE asignaciones_hermano" in downgrade_output.getvalue()
    assert "DROP TRIGGER IF EXISTS trg_validar_lider_hermano ON usuarios" in (
        downgrade_output.getvalue()
    )
    assert "DROP FUNCTION IF EXISTS validar_lider_hermano()" in (
        downgrade_output.getvalue()
    )
    assert "DROP TRIGGER IF EXISTS trg_proteger_pastor_principal_unico ON usuarios" in (
        downgrade_output.getvalue()
    )
    assert "DROP FUNCTION IF EXISTS impedir_desactivar_pastor_principal_unico()" in (
        downgrade_output.getvalue()
    )
    assert "DROP INDEX ix_sesiones_refresh_family_id" in downgrade_output.getvalue()
    assert "DROP TRIGGER IF EXISTS trg_iglesia_con_operadores_activos ON iglesias" in (
        downgrade_output.getvalue()
    )
    assert "DROP FUNCTION IF EXISTS impedir_desactivar_iglesia_con_operadores()" in (
        downgrade_output.getvalue()
    )
    assert "DROP TRIGGER IF EXISTS trg_usuario_iglesia_activa ON usuarios" in (
        downgrade_output.getvalue()
    )
    assert "DROP FUNCTION IF EXISTS validar_usuario_iglesia_activa()" in (
        downgrade_output.getvalue()
    )
    assert "DROP TABLE sesiones_refresh" in downgrade_output.getvalue()


def test_postgresql_migration_rejects_operators_assigned_to_inactive_churches() -> None:
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

    assert "CREATE FUNCTION validar_usuario_iglesia_activa()" in generated_sql
    assert "CREATE TRIGGER trg_usuario_iglesia_activa" in generated_sql
    assert "CREATE FUNCTION impedir_desactivar_pastor_principal_unico()" in generated_sql
    assert "CREATE TRIGGER trg_proteger_pastor_principal_unico" in generated_sql
    assert "CREATE FUNCTION validar_lider_hermano()" in generated_sql
    assert "CREATE TRIGGER trg_validar_lider_hermano" in generated_sql
    assert "CREATE FUNCTION proteger_lider_con_hermanos()" in generated_sql
    assert "CREATE TRIGGER trg_proteger_lider_con_hermanos" in generated_sql
    assert "CREATE FUNCTION validar_historial_asignacion_hermano()" in generated_sql
    assert "CREATE FUNCTION validar_alcance_visita()" in generated_sql
    assert "CREATE TRIGGER trg_validar_alcance_visita" in generated_sql
    assert "CREATE FUNCTION impedir_eliminar_visita()" in generated_sql
    assert "CREATE TRIGGER trg_impedir_eliminar_visita" in generated_sql
    assert "CREATE FUNCTION proteger_historial_visita()" in generated_sql
    assert "CREATE TRIGGER trg_proteger_historial_visita" in generated_sql
    assert "CREATE TRIGGER trg_proteger_historial_visita" in generated_sql
    assert "CREATE UNIQUE INDEX uq_visita_programada_hermano_fecha" in generated_sql
    assert "CREATE TABLE visitas" in generated_sql
    assert "CREATE TABLE visita_historial" in generated_sql
    assert "ALTER TABLE visita_historial ALTER COLUMN datos_anteriores TYPE JSONB" in (
        generated_sql
    )
    assert "ALTER TABLE visita_historial ALTER COLUMN datos_nuevos TYPE JSONB" in (
        generated_sql
    )
    assert "CREATE TABLE auditoria" in generated_sql
    assert "CREATE TRIGGER trg_proteger_auditoria" in generated_sql
    assert "CREATE FUNCTION proteger_auditoria()" in generated_sql
    assert "ix_auditoria_iglesia_fecha" in generated_sql
    assert "ix_auditoria_recurso" in generated_sql