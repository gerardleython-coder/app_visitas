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
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
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