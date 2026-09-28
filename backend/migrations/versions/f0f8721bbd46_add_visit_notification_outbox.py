"""add transactional visit notification outbox

Revision ID: f0f8721bbd46
Revises: d2f4e63b0a91
Create Date: 2026-09-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f0f8721bbd46"
down_revision: Union[str, Sequence[str], None] = "d2f4e63b0a91"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notificaciones_outbox",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("(gen_random_uuid())"),
            nullable=False,
        ),
        sa.Column("visita_id", sa.Uuid(), nullable=False),
        sa.Column("destinatario_email", sa.String(length=150), nullable=False),
        sa.Column("tipo", sa.String(length=40), nullable=False),
        sa.Column(
            "estado",
            sa.String(length=20),
            server_default=sa.text("'PENDIENTE'"),
            nullable=False,
        ),
        sa.Column("intentos", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("ultimo_error", sa.String(length=100), nullable=True),
        sa.Column(
            "reintentar_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("bloqueado_hasta", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ultimo_intento_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enviado_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "estado IN ('PENDIENTE', 'PROCESANDO', 'ENVIADA')",
            name="ck_notificacion_outbox_estado",
        ),
        sa.ForeignKeyConstraint(
            ["visita_id"], ["visitas.id"], ondelete="RESTRICT", name="fk_outbox_visita"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "visita_id",
            "destinatario_email",
            "tipo",
            name="uq_notificacion_outbox_visita_destinatario_tipo",
        ),
    )
    op.create_index(
        "ix_notificacion_outbox_estado_reintento",
        "notificaciones_outbox",
        ["estado", "reintentar_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_notificacion_outbox_estado_reintento",
        table_name="notificaciones_outbox",
    )
    op.drop_table("notificaciones_outbox")