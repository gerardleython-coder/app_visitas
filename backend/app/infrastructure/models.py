from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.authentication import UserRole
from app.infrastructure.database import Base


class DistrictModel(Base):
    __tablename__ = "distritos"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column("nombre", String(100), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        "created_at", DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ChurchModel(Base):
    __tablename__ = "iglesias"
    __table_args__ = (
        UniqueConstraint("distrito_id", "nombre", name="uq_iglesia_distrito_nombre"),
        UniqueConstraint("id", "distrito_id", name="uq_iglesia_id_distrito"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    district_id: Mapped[UUID] = mapped_column(
        "distrito_id", Uuid(as_uuid=True), ForeignKey("distritos.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column("nombre", String(150), nullable=False)
    address: Mapped[str | None] = mapped_column("direccion", Text)
    active: Mapped[bool] = mapped_column(
        "activo", Boolean, nullable=False, default=True, server_default=text("TRUE")
    )
    created_at: Mapped[datetime] = mapped_column(
        "created_at", DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class UserModel(Base):
    __tablename__ = "usuarios"
    __table_args__ = (
        ForeignKeyConstraint(
            ["iglesia_id", "distrito_id"],
            ["iglesias.id", "iglesias.distrito_id"],
            ondelete="RESTRICT",
            name="fk_usuario_iglesia_distrito",
        ),
        CheckConstraint(
            "es_pastor_principal = FALSE OR rol = 'PASTOR'",
            name="ck_usuario_pastor_principal_rol",
        ),
        CheckConstraint(
            "rol = 'HERMANO' OR (email IS NOT NULL AND password_hash IS NOT NULL)",
            name="ck_usuario_operativo_credenciales",
        ),
        CheckConstraint(
            "rol <> 'HERMANO' OR (telefono IS NOT NULL AND direccion IS NOT NULL "
            "AND distrito_id IS NOT NULL AND iglesia_id IS NOT NULL AND lider_id IS NOT NULL)",
            name="ck_hermano_datos_requeridos",
        ),
        CheckConstraint(
            "rol NOT IN ('PASTOR', 'LIDER') OR (distrito_id IS NOT NULL AND iglesia_id IS NOT NULL)",
            name="ck_usuario_operativo_asignacion",
        ),
        CheckConstraint(
            "rol IN ('ADMIN', 'PASTOR', 'LIDER', 'HERMANO')",
            name="ck_usuario_rol_valido",
        ),
        CheckConstraint("length(trim(nombre)) > 0", name="ck_usuario_nombre_no_vacio"),
        CheckConstraint("length(trim(apellido)) > 0", name="ck_usuario_apellido_no_vacio"),
        Index(
            "uq_pastor_principal_por_iglesia",
            "iglesia_id",
            unique=True,
            postgresql_where=text("rol = 'PASTOR' AND es_pastor_principal = TRUE AND activo = TRUE"),
            sqlite_where=text("rol = 'PASTOR' AND es_pastor_principal = 1 AND activo = 1"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    district_id: Mapped[UUID | None] = mapped_column(
        "distrito_id", Uuid(as_uuid=True), ForeignKey("distritos.id", ondelete="RESTRICT")
    )
    church_id: Mapped[UUID | None] = mapped_column(
        "iglesia_id", Uuid(as_uuid=True), ForeignKey("iglesias.id", ondelete="RESTRICT")
    )
    leader_id: Mapped[UUID | None] = mapped_column(
        "lider_id", Uuid(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column("nombre", String(100), nullable=False)
    surname: Mapped[str] = mapped_column("apellido", String(100), nullable=False)
    phone: Mapped[str | None] = mapped_column("telefono", String(30))
    address: Mapped[str | None] = mapped_column("direccion", Text)
    email: Mapped[str | None] = mapped_column(String(150), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(
        "rol",
        Enum(UserRole, name="rol_usuario", native_enum=True, create_constraint=False),
        nullable=False,
        default=UserRole.HERMANO,
    )
    is_primary_pastor: Mapped[bool] = mapped_column(
        "es_pastor_principal", Boolean, nullable=False, default=False, server_default=text("FALSE")
    )
    active: Mapped[bool] = mapped_column(
        "activo", Boolean, nullable=False, default=True, server_default=text("TRUE")
    )
    created_at: Mapped[datetime] = mapped_column(
        "created_at", DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RefreshSessionModel(Base):
    __tablename__ = "sesiones_refresh"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    family_id: Mapped[UUID] = mapped_column(
        "family_id", Uuid(as_uuid=True), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        "usuario_id", Uuid(as_uuid=True), ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    replaced_by_id: Mapped[UUID | None] = mapped_column(
        "reemplazado_por",
        Uuid(as_uuid=True),
        ForeignKey("sesiones_refresh.id", ondelete="SET NULL"),
    )
    expires_at: Mapped[datetime] = mapped_column(
        "expira_at", DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column("revocado_at", DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column("usado_at", DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        "created_at", DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class BrotherAssignmentModel(Base):
    __tablename__ = "asignaciones_hermano"
    __table_args__ = (
        Index(
            "uq_asignacion_vigente_hermano",
            "hermano_id",
            unique=True,
            postgresql_where=text("fecha_fin IS NULL"),
            sqlite_where=text("fecha_fin IS NULL"),
        ),
        Index("ix_asignacion_hermano_fecha", "hermano_id", "fecha_asignacion"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    brother_id: Mapped[UUID] = mapped_column(
        "hermano_id",
        Uuid(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=False,
    )
    leader_id: Mapped[UUID] = mapped_column(
        "lider_id",
        Uuid(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=False,
    )
    assigned_by_id: Mapped[UUID | None] = mapped_column(
        "asignado_por",
        Uuid(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
    )
    assigned_at: Mapped[datetime] = mapped_column(
        "fecha_asignacion", DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        "fecha_fin", DateTime(timezone=True)
    )


class VisitModel(Base):
    __tablename__ = "visitas"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('EVANGELISMO', 'ENSENANZA', 'CUIDADO_PASTORAL')",
            name="ck_visita_tipo_valido",
        ),
        CheckConstraint(
            "estado IN ('PROGRAMADA', 'COMPLETADA', 'CANCELADA')",
            name="ck_visita_estado_valido",
        ),
        CheckConstraint("duracion_minutos > 0", name="ck_visita_duracion_positiva"),
        CheckConstraint(
            "(estado = 'CANCELADA' AND motivo_cancelacion IS NOT NULL) "
            "OR (estado <> 'CANCELADA' AND motivo_cancelacion IS NULL)",
            name="ck_visita_cancelada_requiere_motivo",
        ),
        CheckConstraint(
            "(estado = 'COMPLETADA' AND fecha_completada IS NOT NULL) "
            "OR (estado <> 'COMPLETADA' AND fecha_completada IS NULL)",
            name="ck_visita_completada_requiere_fecha",
        ),
        Index(
            "uq_visita_programada_hermano_fecha",
            "hermano_id",
            "fecha_programada",
            unique=True,
            postgresql_where=text("estado = 'PROGRAMADA'"),
            sqlite_where=text("estado = 'PROGRAMADA'"),
        ),
        Index("ix_visita_lider_fecha", "lider_id", "fecha_programada"),
        Index("ix_visita_hermano_fecha", "hermano_id", "fecha_programada"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    leader_id: Mapped[UUID] = mapped_column(
        "lider_id", Uuid(as_uuid=True), ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False
    )
    brother_id: Mapped[UUID] = mapped_column(
        "hermano_id", Uuid(as_uuid=True), ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False
    )
    visit_type: Mapped[str] = mapped_column("tipo", String(30), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(
        "fecha_programada", DateTime(timezone=True), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        "fecha_completada", DateTime(timezone=True)
    )
    duration_minutes: Mapped[int] = mapped_column("duracion_minutos", nullable=False)
    location: Mapped[str] = mapped_column("ubicacion", Text, nullable=False)
    observations: Mapped[str] = mapped_column("observaciones", Text, nullable=False)
    status: Mapped[str] = mapped_column(
        "estado", String(20), nullable=False, default="PROGRAMADA", server_default=text("'PROGRAMADA'")
    )
    cancellation_reason: Mapped[str | None] = mapped_column("motivo_cancelacion", Text)
    created_by_id: Mapped[UUID] = mapped_column(
        "creado_por", Uuid(as_uuid=True), ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        "created_at", DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        "updated_at", DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class VisitHistoryModel(Base):
    __tablename__ = "visita_historial"
    __table_args__ = (
        Index("ix_visita_historial_visita_fecha", "visita_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    visit_id: Mapped[UUID] = mapped_column(
        "visita_id", Uuid(as_uuid=True), ForeignKey("visitas.id", ondelete="RESTRICT"), nullable=False
    )
    actor_id: Mapped[UUID] = mapped_column(
        "usuario_id", Uuid(as_uuid=True), ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False
    )
    action: Mapped[str] = mapped_column("accion", String(30), nullable=False)
    previous_status: Mapped[str | None] = mapped_column("estado_anterior", String(20))
    new_status: Mapped[str | None] = mapped_column("estado_nuevo", String(20))
    previous_scheduled_at: Mapped[datetime | None] = mapped_column(
        "fecha_anterior", DateTime(timezone=True)
    )
    new_scheduled_at: Mapped[datetime | None] = mapped_column(
        "fecha_nueva", DateTime(timezone=True)
    )
    previous_values: Mapped[dict[str, object] | None] = mapped_column(
        "datos_anteriores", JSON().with_variant(JSONB(), "postgresql")
    )
    new_values: Mapped[dict[str, object] | None] = mapped_column(
        "datos_nuevos", JSON().with_variant(JSONB(), "postgresql")
    )
    reason: Mapped[str | None] = mapped_column("motivo", Text)
    created_at: Mapped[datetime] = mapped_column(
        "created_at", DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AuditModel(Base):
    __tablename__ = "auditoria"
    __table_args__ = (
        Index("ix_auditoria_iglesia_fecha", "iglesia_id", "created_at"),
        Index("ix_auditoria_recurso", "recurso", "recurso_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    actor_id: Mapped[UUID] = mapped_column(
        "usuario_id", Uuid(as_uuid=True), ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False
    )
    resource: Mapped[str] = mapped_column("recurso", String(50), nullable=False)
    resource_id: Mapped[UUID] = mapped_column("recurso_id", Uuid(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column("accion", String(50), nullable=False)
    church_id: Mapped[UUID | None] = mapped_column(
        "iglesia_id", Uuid(as_uuid=True), ForeignKey("iglesias.id", ondelete="RESTRICT")
    )
    previous_values: Mapped[dict[str, object] | None] = mapped_column(
        "datos_anteriores", JSON().with_variant(JSONB(), "postgresql")
    )
    new_values: Mapped[dict[str, object] | None] = mapped_column(
        "datos_nuevos", JSON().with_variant(JSONB(), "postgresql")
    )
    reason: Mapped[str | None] = mapped_column("motivo", Text)
    created_at: Mapped[datetime] = mapped_column(
        "created_at", DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class NotificationOutboxModel(Base):
    __tablename__ = "notificaciones_outbox"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('PENDIENTE', 'PROCESANDO', 'ENVIADA')",
            name="ck_notificacion_outbox_estado",
        ),
        UniqueConstraint(
            "visita_id",
            "destinatario_email",
            "tipo",
            name="uq_notificacion_outbox_visita_destinatario_tipo",
        ),
        Index("ix_notificacion_outbox_estado_reintento", "estado", "reintentar_at"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    visit_id: Mapped[UUID] = mapped_column(
        "visita_id",
        Uuid(as_uuid=True),
        ForeignKey("visitas.id", ondelete="RESTRICT"),
        nullable=False,
    )
    recipient_email: Mapped[str] = mapped_column(
        "destinatario_email", String(150), nullable=False
    )
    notification_type: Mapped[str] = mapped_column("tipo", String(40), nullable=False)
    status: Mapped[str] = mapped_column(
        "estado", String(20), nullable=False, default="PENDIENTE", server_default=text("'PENDIENTE'")
    )
    attempt_count: Mapped[int] = mapped_column(
        "intentos", Integer, nullable=False, default=0, server_default=text("0")
    )
    last_error: Mapped[str | None] = mapped_column("ultimo_error", String(100))
    next_attempt_at: Mapped[datetime] = mapped_column(
        "reintentar_at", DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        "bloqueado_hasta", DateTime(timezone=True)
    )
    last_attempt_at: Mapped[datetime | None] = mapped_column(
        "ultimo_intento_at", DateTime(timezone=True)
    )
    sent_at: Mapped[datetime | None] = mapped_column("enviado_at", DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        "created_at", DateTime(timezone=True), server_default=func.now(), nullable=False
    )