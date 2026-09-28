"""add scoped immutable audit events

Revision ID: d2f4e63b0a91
Revises: b5f4a8c2d1e6
Create Date: 2026-09-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d2f4e63b0a91"
down_revision: Union[str, Sequence[str], None] = "b5f4a8c2d1e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "auditoria",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("(gen_random_uuid())"),
            nullable=False,
        ),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("recurso", sa.String(length=50), nullable=False),
        sa.Column("recurso_id", sa.Uuid(), nullable=False),
        sa.Column("accion", sa.String(length=50), nullable=False),
        sa.Column("iglesia_id", sa.Uuid(), nullable=True),
        sa.Column(
            "datos_anteriores",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column(
            "datos_nuevos",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column("motivo", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"], ["usuarios.id"], ondelete="RESTRICT", name="fk_auditoria_actor"
        ),
        sa.ForeignKeyConstraint(
            ["iglesia_id"], ["iglesias.id"], ondelete="RESTRICT", name="fk_auditoria_iglesia"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_auditoria_iglesia_fecha",
        "auditoria",
        ["iglesia_id", "created_at"],
    )
    op.create_index(
        "ix_auditoria_recurso",
        "auditoria",
        ["recurso", "recurso_id", "created_at"],
    )

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            CREATE FUNCTION proteger_auditoria() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
                RAISE EXCEPTION 'La auditoría es inmutable'
                    USING ERRCODE = '23514';
            END;
            $$;
            """
        )
        op.execute(
            """
            CREATE TRIGGER trg_proteger_auditoria
            BEFORE UPDATE OR DELETE ON auditoria
            FOR EACH ROW EXECUTE FUNCTION proteger_auditoria();
            """
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS trg_proteger_auditoria ON auditoria")
        op.execute("DROP FUNCTION IF EXISTS proteger_auditoria()")
    op.drop_index("ix_auditoria_recurso", table_name="auditoria")
    op.drop_index("ix_auditoria_iglesia_fecha", table_name="auditoria")
    op.drop_table("auditoria")