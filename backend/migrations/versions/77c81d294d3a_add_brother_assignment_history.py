"""add brother leader assignment history

Revision ID: 77c81d294d3a
Revises: c4d98e16f731
Create Date: 2026-09-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "77c81d294d3a"
down_revision: Union[str, Sequence[str], None] = "c4d98e16f731"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "asignaciones_hermano",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("(gen_random_uuid())"),
            nullable=False,
        ),
        sa.Column("hermano_id", sa.Uuid(), nullable=False),
        sa.Column("lider_id", sa.Uuid(), nullable=False),
        sa.Column("asignado_por", sa.Uuid(), nullable=True),
        sa.Column(
            "fecha_asignacion",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("fecha_fin", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["hermano_id"], ["usuarios.id"], ondelete="RESTRICT", name="fk_asignacion_hermano"
        ),
        sa.ForeignKeyConstraint(
            ["lider_id"], ["usuarios.id"], ondelete="RESTRICT", name="fk_asignacion_lider"
        ),
        sa.ForeignKeyConstraint(
            ["asignado_por"], ["usuarios.id"], ondelete="RESTRICT", name="fk_asignacion_actor"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_asignacion_vigente_hermano",
        "asignaciones_hermano",
        ["hermano_id"],
        unique=True,
        postgresql_where=sa.text("fecha_fin IS NULL"),
        sqlite_where=sa.text("fecha_fin IS NULL"),
    )
    op.create_index(
        "ix_asignacion_hermano_fecha",
        "asignaciones_hermano",
        ["hermano_id", "fecha_asignacion"],
    )

    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM usuarios hermano
                LEFT JOIN usuarios lider ON lider.id = hermano.lider_id
                WHERE hermano.rol = 'HERMANO'
                  AND (
                    lider.id IS NULL
                    OR lider.rol <> 'LIDER'
                    OR lider.iglesia_id IS DISTINCT FROM hermano.iglesia_id
                  )
            ) THEN
                RAISE EXCEPTION 'Hay hermanos con líder inválido; corrija las asignaciones antes de migrar';
            END IF;
        END;
        $$;
        """
    )
    op.execute(
        """
        INSERT INTO asignaciones_hermano
            (id, hermano_id, lider_id, asignado_por, fecha_asignacion, fecha_fin)
        SELECT gen_random_uuid(), id, lider_id, NULL, created_at,
               CASE WHEN activo THEN NULL ELSE created_at END
        FROM usuarios
        WHERE rol = 'HERMANO';
        """
    )
    op.execute(
        """
        CREATE FUNCTION validar_lider_hermano() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.rol = 'HERMANO' AND NOT EXISTS (
                SELECT 1
                FROM usuarios lider
                WHERE lider.id = NEW.lider_id
                  AND lider.rol = 'LIDER'
                  AND lider.iglesia_id = NEW.iglesia_id
            ) THEN
                RAISE EXCEPTION 'El líder debe tener rol LIDER y pertenecer a la iglesia del hermano'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_validar_lider_hermano
        BEFORE INSERT OR UPDATE OF rol, lider_id, iglesia_id ON usuarios
        FOR EACH ROW
        EXECUTE FUNCTION validar_lider_hermano();
        """
    )
    op.execute(
        """
        CREATE FUNCTION proteger_lider_con_hermanos() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.rol = 'LIDER'
               AND (NEW.rol <> 'LIDER' OR NEW.iglesia_id IS DISTINCT FROM OLD.iglesia_id)
               AND EXISTS (
                   SELECT 1 FROM usuarios
                   WHERE rol = 'HERMANO' AND lider_id = OLD.id
               ) THEN
                RAISE EXCEPTION 'Reasigne los hermanos antes de cambiar el rol o la iglesia del líder'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_proteger_lider_con_hermanos
        BEFORE UPDATE OF rol, iglesia_id ON usuarios
        FOR EACH ROW
        EXECUTE FUNCTION proteger_lider_con_hermanos();
        """
    )
    op.execute(
        """
        CREATE FUNCTION validar_historial_asignacion_hermano() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM usuarios hermano
                JOIN usuarios lider ON lider.id = NEW.lider_id
                WHERE hermano.id = NEW.hermano_id
                  AND hermano.rol = 'HERMANO'
                  AND hermano.lider_id = NEW.lider_id
                  AND lider.rol = 'LIDER'
                  AND lider.iglesia_id = hermano.iglesia_id
            ) THEN
                RAISE EXCEPTION 'La asignación histórica no coincide con el líder actual del hermano'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_validar_historial_asignacion_hermano
        BEFORE INSERT ON asignaciones_hermano
        FOR EACH ROW
        EXECUTE FUNCTION validar_historial_asignacion_hermano();
        """
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "DROP TRIGGER IF EXISTS trg_validar_historial_asignacion_hermano "
            "ON asignaciones_hermano"
        )
        op.execute("DROP FUNCTION IF EXISTS validar_historial_asignacion_hermano()")
        op.execute("DROP TRIGGER IF EXISTS trg_proteger_lider_con_hermanos ON usuarios")
        op.execute("DROP FUNCTION IF EXISTS proteger_lider_con_hermanos()")
        op.execute("DROP TRIGGER IF EXISTS trg_validar_lider_hermano ON usuarios")
        op.execute("DROP FUNCTION IF EXISTS validar_lider_hermano()")
    op.drop_index("ix_asignacion_hermano_fecha", table_name="asignaciones_hermano")
    op.drop_index(
        "uq_asignacion_vigente_hermano",
        table_name="asignaciones_hermano",
        postgresql_where=sa.text("fecha_fin IS NULL"),
        sqlite_where=sa.text("fecha_fin IS NULL"),
    )
    op.drop_table("asignaciones_hermano")