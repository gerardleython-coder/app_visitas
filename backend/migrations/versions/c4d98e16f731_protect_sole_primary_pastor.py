"""protect the sole active primary pastor

Revision ID: c4d98e16f731
Revises: cd3031a1e81a
Create Date: 2026-09-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "c4d98e16f731"
down_revision: Union[str, Sequence[str], None] = "cd3031a1e81a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute(
        """
        CREATE FUNCTION impedir_desactivar_pastor_principal_unico() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.rol = 'PASTOR'
               AND OLD.activo = TRUE
               AND OLD.es_pastor_principal = TRUE
               AND NEW.activo = FALSE
               AND NOT EXISTS (
                   SELECT 1
                   FROM usuarios
                   WHERE iglesia_id = OLD.iglesia_id
                     AND id <> OLD.id
                     AND rol = 'PASTOR'
                     AND activo = TRUE
                     AND es_pastor_principal = TRUE
               ) THEN
                RAISE EXCEPTION 'Debe existir un pastor principal activo antes de desactivar'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_proteger_pastor_principal_unico
        BEFORE UPDATE OF activo ON usuarios
        FOR EACH ROW
        EXECUTE FUNCTION impedir_desactivar_pastor_principal_unico();
        """
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute(
        "DROP TRIGGER IF EXISTS trg_proteger_pastor_principal_unico ON usuarios"
    )
    op.execute("DROP FUNCTION IF EXISTS impedir_desactivar_pastor_principal_unico()")