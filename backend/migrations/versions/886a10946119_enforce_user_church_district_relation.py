"""enforce user church district relation

Revision ID: 886a10946119
Revises: 12e39403107c
Create Date: 2026-09-27 20:58:03.357291

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '886a10946119'
down_revision: Union[str, Sequence[str], None] = '12e39403107c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("iglesias") as batch_operation:
        batch_operation.create_unique_constraint(
            "uq_iglesia_id_distrito", ["id", "distrito_id"]
        )

    with op.batch_alter_table("usuarios") as batch_operation:
        batch_operation.create_foreign_key(
            "fk_usuario_iglesia_distrito",
            "iglesias",
            ["iglesia_id", "distrito_id"],
            ["id", "distrito_id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("usuarios") as batch_operation:
        batch_operation.drop_constraint(
            "fk_usuario_iglesia_distrito", type_="foreignkey"
        )

    with op.batch_alter_table("iglesias") as batch_operation:
        batch_operation.drop_constraint("uq_iglesia_id_distrito", type_="unique")
