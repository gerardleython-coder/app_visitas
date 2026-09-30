from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from app.application.audit import AuditRepository
from app.domain.audit import AuditRecord
from app.domain.authentication import UserAccount, UserRole
from app.domain.errors import (
    ConflictException,
    DomainException,
    ForbiddenException,
    NotFoundException,
)
from app.domain.operator import OperatorProfile


class AdministratorRepository(Protocol):
    async def lock_bootstrap(self) -> None: ...

    async def count_administrators(self) -> int: ...

    async def create_administrator(
        self,
        *,
        name: str,
        surname: str,
        email: str,
        password_hash: str,
    ) -> UserAccount: ...

    async def list_administrators(self) -> list[OperatorProfile]: ...

    async def get_operator(self, operator_id: UUID) -> OperatorProfile | None: ...

    async def update_operator(
        self,
        operator_id: UUID,
        changes: dict[str, object],
    ) -> OperatorProfile | None: ...

    async def lock_administrators(self) -> None: ...

    async def has_active_administrator(self, *, excluding_id: UUID) -> bool: ...

    async def deactivate_operator(self, operator_id: UUID) -> OperatorProfile | None: ...


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...


class RefreshSessionRepository(Protocol):
    async def revoke_for_user(self, user_id: UUID, revoked_at: datetime) -> None: ...


class BootstrapAdministrator:
    def __init__(
        self,
        administrators: AdministratorRepository,
        passwords: PasswordHasher,
        audit: AuditRepository,
    ) -> None:
        self._administrators = administrators
        self._passwords = passwords
        self._audit = audit

    async def execute(
        self,
        *,
        name: str,
        surname: str,
        email: str,
        password: str,
    ) -> UserAccount:
        await self._administrators.lock_bootstrap()
        if await self._administrators.count_administrators() > 0:
            raise ConflictException("El administrador inicial ya fue provisionado")

        administrator = await self._administrators.create_administrator(
            name=name,
            surname=surname,
            email=email,
            password_hash=self._passwords.hash(password),
        )
        await self._audit.record_event(
            AuditRecord(
                actor_id=administrator.id,
                resource="USUARIO",
                resource_id=administrator.id,
                action="ADMIN_INICIAL_CREADO",
                church_id=None,
                new_values=self._values(
                    name=name,
                    surname=surname,
                    email=email,
                    active=True,
                ),
            )
        )
        return administrator

    @staticmethod
    def _values(
        *,
        name: str,
        surname: str,
        email: str,
        active: bool,
    ) -> dict[str, object]:
        return {
            "name": name,
            "surname": surname,
            "email": email,
            "role": UserRole.ADMIN.value,
            "active": active,
        }


class AdministratorManagement:
    _editable_fields = frozenset({"name", "surname", "email"})

    def __init__(
        self,
        administrators: AdministratorRepository,
        passwords: PasswordHasher,
        audit: AuditRepository,
        sessions: RefreshSessionRepository,
    ) -> None:
        self._administrators = administrators
        self._passwords = passwords
        self._audit = audit
        self._sessions = sessions

    async def list(self, actor: UserAccount) -> list[OperatorProfile]:
        self._require_admin(actor)
        return await self._administrators.list_administrators()

    async def create(
        self,
        actor: UserAccount,
        *,
        name: str,
        surname: str,
        email: str,
        password: str,
    ) -> OperatorProfile:
        self._require_admin(actor)
        created = await self._administrators.create_administrator(
            name=name,
            surname=surname,
            email=email,
            password_hash=self._passwords.hash(password),
        )
        profile = await self._get_admin(created.id)
        await self._audit.record_event(
            AuditRecord(
                actor_id=actor.id,
                resource="USUARIO",
                resource_id=profile.id,
                action="CREADO",
                church_id=None,
                new_values=self._profile_values(profile),
            )
        )
        return profile

    async def update(
        self,
        actor: UserAccount,
        administrator_id: UUID,
        changes: dict[str, object],
    ) -> OperatorProfile:
        self._require_admin(actor)
        if not changes or not changes.keys() <= self._editable_fields:
            raise DomainException("Los datos editables están vacíos o no son válidos")

        previous = await self._get_admin(administrator_id)
        if not previous.active:
            raise NotFoundException("Administrador no encontrado")
        updated = await self._administrators.update_operator(administrator_id, changes)
        if updated is None:
            raise NotFoundException("Administrador no encontrado")
        await self._audit.record_event(
            AuditRecord(
                actor_id=actor.id,
                resource="USUARIO",
                resource_id=updated.id,
                action="MODIFICADO",
                church_id=None,
                previous_values=self._profile_values(previous),
                new_values=self._profile_values(updated),
            )
        )
        return updated

    async def deactivate(
        self,
        actor: UserAccount,
        administrator_id: UUID,
    ) -> OperatorProfile:
        self._require_admin(actor)
        if actor.id == administrator_id:
            raise ConflictException("No puede desactivarse a sí mismo")

        await self._administrators.lock_administrators()
        previous = await self._get_admin(administrator_id)
        if not previous.active:
            return previous
        if not await self._administrators.has_active_administrator(
            excluding_id=administrator_id
        ):
            raise ConflictException("No se puede desactivar al último ADMIN activo")

        deactivated = await self._administrators.deactivate_operator(administrator_id)
        if deactivated is None:
            raise NotFoundException("Administrador no encontrado")
        now = datetime.now(UTC)
        await self._sessions.revoke_for_user(administrator_id, now)
        await self._audit.record_event(
            AuditRecord(
                actor_id=actor.id,
                resource="USUARIO",
                resource_id=deactivated.id,
                action="DESACTIVADO",
                church_id=None,
                previous_values=self._profile_values(previous),
                new_values=self._profile_values(deactivated),
            )
        )
        return deactivated

    async def _get_admin(self, administrator_id: UUID) -> OperatorProfile:
        profile = await self._administrators.get_operator(administrator_id)
        if profile is None or profile.role is not UserRole.ADMIN:
            raise NotFoundException("Administrador no encontrado")
        return profile

    @staticmethod
    def _require_admin(actor: UserAccount) -> None:
        if actor.role is not UserRole.ADMIN or not actor.active:
            raise ForbiddenException("Solo ADMIN puede gestionar administradores")

    @staticmethod
    def _profile_values(profile: OperatorProfile) -> dict[str, object]:
        return {
            "name": profile.name,
            "surname": profile.surname,
            "email": profile.email,
            "role": profile.role.value,
            "active": profile.active,
        }