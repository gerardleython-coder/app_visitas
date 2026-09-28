"""track church active status

Revision ID: 3ec9e67695c7
Revises: 886a10946119
Create Date: 2026-09-27 21:04:43.031735

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3ec9e67695c7'
down_revision: Union[str, Sequence[str], None] = '886a10946119'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "iglesias",
        sa.Column("activo", sa.Boolean(), server_default=sa.text("TRUE"), nullable=False),
    )

    if op.get_context().dialect.name == "postgresql":
        op.execute(
            """
            CREATE FUNCTION validar_usuario_iglesia_activa() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
                IF NEW.rol IN ('PASTOR', 'LIDER') AND NOT EXISTS (
                    SELECT 1 FROM iglesias
                    WHERE id = NEW.iglesia_id
                      AND distrito_id = NEW.distrito_id
                      AND activo = TRUE
                ) THEN
                    RAISE EXCEPTION 'Iglesia inactiva o fuera del distrito seleccionado'
                        USING ERRCODE = '23514';
                END IF;
                RETURN NEW;
            END;
            $$;
            """
        )
        op.execute(
            """
            CREATE TRIGGER trg_usuario_iglesia_activa
            BEFORE INSERT OR UPDATE OF rol, distrito_id, iglesia_id ON usuarios
            FOR EACH ROW EXECUTE FUNCTION validar_usuario_iglesia_activa();
            """
        )
        op.execute(
            """
            CREATE FUNCTION impedir_desactivar_iglesia_con_operadores() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
                IF OLD.activo AND NOT NEW.activo AND EXISTS (
                    SELECT 1 FROM usuarios
                    WHERE iglesia_id = OLD.id
                      AND rol IN ('PASTOR', 'LIDER')
                      AND activo = TRUE
                ) THEN
                    RAISE EXCEPTION 'No se puede desactivar una iglesia con operadores activos'
                        USING ERRCODE = '23514';
                END IF;
                RETURN NEW;
            END;
            $$;
            """
        )
        op.execute(
            """
            CREATE TRIGGER trg_iglesia_con_operadores_activos
            BEFORE UPDATE OF activo ON iglesias
            FOR EACH ROW EXECUTE FUNCTION impedir_desactivar_iglesia_con_operadores();
            """
        )


def downgrade() -> None:
    """Downgrade schema."""
    if op.get_context().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS trg_iglesia_con_operadores_activos ON iglesias")
        op.execute("DROP FUNCTION IF EXISTS impedir_desactivar_iglesia_con_operadores()")
        op.execute("DROP TRIGGER IF EXISTS trg_usuario_iglesia_activa ON usuarios")
        op.execute("DROP FUNCTION IF EXISTS validar_usuario_iglesia_activa()")

    op.drop_column("iglesias", "activo")
