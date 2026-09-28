"""add hashed password recovery tokens

Revision ID: a5b617c8d902
Revises: f0f8721bbd46
Create Date: 2026-09-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a5b617c8d902"
down_revision: Union[str, Sequence[str], None] = "f0f8721bbd46"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tokens_recuperacion",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("(gen_random_uuid())"),
            nullable=False,
        ),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expira_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("usado_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuarios.id"],
            ondelete="RESTRICT",
            name="fk_token_recuperacion_usuario",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_token_recuperacion_hash"),
    )
    op.create_index(
        "ix_tokens_recuperacion_usuario",
        "tokens_recuperacion",
        ["usuario_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_tokens_recuperacion_usuario", table_name="tokens_recuperacion")
    op.drop_table("tokens_recuperacion")