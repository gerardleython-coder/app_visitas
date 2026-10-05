"""add visits and immutable audit history

Revision ID: a891b376d2f0
Revises: 77c81d294d3a
Create Date: 2026-09-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a891b376d2f0"
down_revision: Union[str, Sequence[str], None] = "77c81d294d3a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "visitas",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("(gen_random_uuid())"),
            nullable=False,
        ),
        sa.Column("lider_id", sa.Uuid(), nullable=False),
        sa.Column("hermano_id", sa.Uuid(), nullable=False),
        sa.Column("tipo", sa.String(length=30), nullable=False),
        sa.Column("fecha_programada", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fecha_completada", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duracion_minutos", sa.Integer(), nullable=False),
        sa.Column("ubicacion", sa.Text(), nullable=False),
        sa.Column("observaciones", sa.Text(), nullable=False),
        sa.Column(
            "estado",
            sa.String(length=20),
            server_default=sa.text("'PROGRAMADA'"),
            nullable=False,
        ),
        sa.Column("motivo_cancelacion", sa.Text(), nullable=True),
        sa.Column("creado_por", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "tipo IN ('EVANGELISMO', 'ENSENANZA', 'CUIDADO_PASTORAL')",
            name="ck_visita_tipo_valido",
        ),
        sa.CheckConstraint(
            "estado IN ('PROGRAMADA', 'COMPLETADA', 'CANCELADA')",
            name="ck_visita_estado_valido",
        ),
        sa.CheckConstraint(
            "duracion_minutos > 0", name="ck_visita_duracion_positiva"
        ),
        sa.CheckConstraint(
            "(estado = 'CANCELADA' AND motivo_cancelacion IS NOT NULL) "
            "OR (estado <> 'CANCELADA' AND motivo_cancelacion IS NULL)",
            name="ck_visita_cancelada_requiere_motivo",
        ),
        sa.CheckConstraint(
            "(estado = 'COMPLETADA' AND fecha_completada IS NOT NULL) "
            "OR (estado <> 'COMPLETADA' AND fecha_completada IS NULL)",
            name="ck_visita_completada_requiere_fecha",
        ),
        sa.ForeignKeyConstraint(
            ["lider_id"], ["usuarios.id"], ondelete="RESTRICT", name="fk_visita_lider"
        ),
        sa.ForeignKeyConstraint(
            ["hermano_id"], ["usuarios.id"], ondelete="RESTRICT", name="fk_visita_hermano"
        ),
        sa.ForeignKeyConstraint(
            ["creado_por"], ["usuarios.id"], ondelete="RESTRICT", name="fk_visita_creador"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_visita_programada_hermano_fecha",
        "visitas",
        ["hermano_id", "fecha_programada"],
        unique=True,
        postgresql_where=sa.text("estado = 'PROGRAMADA'"),
        sqlite_where=sa.text("estado = 'PROGRAMADA'"),
    )
    op.create_index("ix_visita_lider_fecha", "visitas", ["lider_id", "fecha_programada"])
    op.create_index("ix_visita_hermano_fecha", "visitas", ["hermano_id", "fecha_programada"])

    op.create_table(
        "visita_historial",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("(gen_random_uuid())"),
            nullable=False,
        ),
        sa.Column("visita_id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("accion", sa.String(length=30), nullable=False),
        sa.Column("estado_anterior", sa.String(length=20), nullable=True),
        sa.Column("estado_nuevo", sa.String(length=20), nullable=True),
        sa.Column("fecha_anterior", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fecha_nueva", sa.DateTime(timezone=True), nullable=True),
        sa.Column("datos_anteriores", sa.JSON(), nullable=True),
        sa.Column("datos_nuevos", sa.JSON(), nullable=True),
        sa.Column("motivo", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["visita_id"], ["visitas.id"], ondelete="RESTRICT", name="fk_visita_historial_visita"
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"], ["usuarios.id"], ondelete="RESTRICT", name="fk_visita_historial_actor"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_visita_historial_visita_fecha",
        "visita_historial",
        ["visita_id", "created_at"],
    )

    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute(
        """
        CREATE FUNCTION validar_alcance_visita() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM usuarios hermano
                JOIN usuarios lider ON lider.id = NEW.lider_id
                WHERE hermano.id = NEW.hermano_id
                  AND hermano.rol = 'HERMANO'
                  AND hermano.activo = TRUE
                  AND hermano.lider_id = lider.id
                  AND lider.rol = 'LIDER'
                  AND lider.activo = TRUE
                  AND lider.iglesia_id = hermano.iglesia_id
                  AND lider.distrito_id = hermano.distrito_id
            ) THEN
                RAISE EXCEPTION 'La visita requiere un hermano activo y su líder activo de la misma iglesia'
                    USING ERRCODE = '23514';
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM usuarios actor
                WHERE actor.id = NEW.creado_por
                  AND actor.activo = TRUE
                  AND actor.rol IN ('ADMIN', 'PASTOR', 'LIDER')
            ) THEN
                RAISE EXCEPTION 'El creador de la visita debe ser un usuario operativo activo'
                    USING ERRCODE = '23514';
            END IF;

            IF TG_OP = 'INSERT' AND NEW.estado <> 'PROGRAMADA' THEN
                RAISE EXCEPTION 'Las visitas nuevas deben iniciar PROGRAMADA'
                    USING ERRCODE = '23514';
            END IF;

            IF TG_OP = 'UPDATE' AND OLD.estado = 'CANCELADA' THEN
                RAISE EXCEPTION 'Una visita CANCELADA no puede modificarse ni reactivarse'
                    USING ERRCODE = '23514';
            END IF;

            IF TG_OP = 'UPDATE' AND OLD.estado = 'COMPLETADA'
               AND NEW.estado <> 'COMPLETADA' THEN
                RAISE EXCEPTION 'Una visita COMPLETADA no puede cambiar de estado'
                    USING ERRCODE = '23514';
            END IF;

            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_validar_alcance_visita
        BEFORE INSERT OR UPDATE OF lider_id, hermano_id, creado_por, estado ON visitas
        FOR EACH ROW EXECUTE FUNCTION validar_alcance_visita();
        """
    )
    op.execute(
        """
        CREATE FUNCTION impedir_eliminar_visita() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Las visitas no se eliminan; deben cancelarse con motivo'
                USING ERRCODE = '23514';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_impedir_eliminar_visita
        BEFORE DELETE ON visitas
        FOR EACH ROW EXECUTE FUNCTION impedir_eliminar_visita();
        """
    )
    op.execute(
        """
        CREATE FUNCTION proteger_historial_visita() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'El historial de visitas es inmutable'
                USING ERRCODE = '23514';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_proteger_historial_visita
        BEFORE UPDATE OR DELETE ON visita_historial
        FOR EACH ROW EXECUTE FUNCTION proteger_historial_visita();
        """
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS trg_proteger_historial_visita ON visita_historial")
        op.execute("DROP FUNCTION IF EXISTS proteger_historial_visita()")
        op.execute("DROP TRIGGER IF EXISTS trg_impedir_eliminar_visita ON visitas")
        op.execute("DROP FUNCTION IF EXISTS impedir_eliminar_visita()")
        op.execute("DROP TRIGGER IF EXISTS trg_validar_alcance_visita ON visitas")
        op.execute("DROP FUNCTION IF EXISTS validar_alcance_visita()")

    op.drop_index("ix_visita_historial_visita_fecha", table_name="visita_historial")
    op.drop_table("visita_historial")
    op.drop_index("ix_visita_hermano_fecha", table_name="visitas")
    op.drop_index("ix_visita_lider_fecha", table_name="visitas")
    op.drop_index(
        "uq_visita_programada_hermano_fecha",
        table_name="visitas",
        postgresql_where=sa.text("estado = 'PROGRAMADA'"),
        sqlite_where=sa.text("estado = 'PROGRAMADA'"),
    )
    op.drop_table("visitas")