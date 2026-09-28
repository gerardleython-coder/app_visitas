"""use JSONB for visit audit snapshots

Revision ID: b5f4a8c2d1e6
Revises: a891b376d2f0
Create Date: 2026-09-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b5f4a8c2d1e6"
down_revision: Union[str, Sequence[str], None] = "a891b376d2f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    for column in ("datos_anteriores", "datos_nuevos"):
        op.alter_column(
            "visita_historial",
            column,
            existing_type=sa.JSON(),
            type_=postgresql.JSONB(),
            postgresql_using=f"{column}::jsonb",
        )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    for column in ("datos_anteriores", "datos_nuevos"):
        op.alter_column(
            "visita_historial",
            column,
            existing_type=postgresql.JSONB(),
            type_=sa.JSON(),
            postgresql_using=f"{column}::json",
        )