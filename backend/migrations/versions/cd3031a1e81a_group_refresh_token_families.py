"""group refresh token families

Revision ID: cd3031a1e81a
Revises: f6117ca1487e
Create Date: 2026-09-27 21:47:04.045923

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cd3031a1e81a'
down_revision: Union[str, Sequence[str], None] = 'f6117ca1487e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("sesiones_refresh", sa.Column("family_id", sa.Uuid(), nullable=True))
    op.execute("UPDATE sesiones_refresh SET family_id = id WHERE family_id IS NULL")

    with op.batch_alter_table("sesiones_refresh") as batch_operation:
        batch_operation.alter_column(
            "family_id",
            existing_type=sa.Uuid(),
            nullable=False,
        )

    op.create_index(
        "ix_sesiones_refresh_family_id",
        "sesiones_refresh",
        ["family_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_sesiones_refresh_family_id", table_name="sesiones_refresh")
    with op.batch_alter_table("sesiones_refresh") as batch_operation:
        batch_operation.drop_column("family_id")
