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
from app.domain.organization import Church


class OperatorRepository(Protocol):
    async def list_operators(
        self,
        role: UserRole,
        *,
        church_id: UUID | None = None,
    ) -> list[OperatorProfile]: ...

    async def get_operator(self, operator_id: UUID) -> OperatorProfile | None: ...

    async def update_operator(
        self,
        operator_id: UUID,
        changes: dict[str, object],
    ) -> OperatorProfile | None: ...

    async def lock_church(self, church_id: UUID) -> bool: ...

    async def has_active_primary_pastor(
        self,
        church_id: UUID,
        *,
        excluding_id: UUID,
    ) -> bool: ...

    async def set_primary_pastor(
        self,
        church_id: UUID,
        pastor_id: UUID,
    ) -> OperatorProfile | None: ...

    async def deactivate_operator(self, operator_id: UUID) -> OperatorProfile | None: ...


class ChurchRepository(Protocol):
    async def get_by_id(self, church_id: UUID) -> Church | None: ...


class OperatorManagement:
    _editable_fields = frozenset({"name", "surname", "email", "phone", "address"})

    def __init__(
        self,
        operators: OperatorRepository,
        churches: ChurchRepository,
        audit: AuditRepository,
    ) -> None:
        self._operators = operators
        self._churches = churches
        self._audit = audit

    async def list_operators(
        self,
        actor: UserAccount,
        role: UserRole,
    ) -> list[OperatorProfile]:
        if role is UserRole.PASTOR:
            if actor.role is not UserRole.ADMIN:
                raise ForbiddenException("Solo ADMIN puede consultar pastores")
            return await self._operators.list_operators(role)

        if role is not UserRole.LIDER:
            raise DomainException("Solo se pueden consultar pastores o líderes")
        if actor.role is UserRole.ADMIN:
            return await self._operators.list_operators(role)
        if actor.role is not UserRole.PASTOR:
            raise ForbiddenException("Permisos insuficientes")

        actor_profile = await self._operators.get_operator(actor.id)
        if actor_profile is None or actor_profile.church_id is None:
            raise ForbiddenException("El pastor no tiene iglesia asignada")
        return await self._operators.list_operators(
            role,
            church_id=actor_profile.church_id,
        )

    async def update_operator(
        self,
        actor: UserAccount,
        operator_id: UUID,
        role: UserRole,
        changes: dict[str, object],
    ) -> OperatorProfile:
        if not changes or not changes.keys() <= self._editable_fields:
            raise DomainException("Los datos editables están vacíos o no son válidos")

        operator = await self._get_authorized_operator(actor, operator_id, role)
        if not operator.active:
            raise NotFoundException("Operador no encontrado")

        updated = await self._operators.update_operator(operator_id, changes)
        if updated is None:
            raise NotFoundException("Operador no encontrado")
        await self._audit.record_event(
            AuditRecord(
                actor_id=actor.id,
                resource="USUARIO",
                resource_id=updated.id,
                action="MODIFICADO",
                church_id=updated.church_id,
                previous_values=self._operator_values(operator),
                new_values=self._operator_values(updated),
            )
        )
        return updated

    async def deactivate_operator(
        self,
        actor: UserAccount,
        operator_id: UUID,
        role: UserRole,
    ) -> OperatorProfile:
        operator = await self._get_authorized_operator(actor, operator_id, role)
        if not operator.active:
            return operator

        if operator.role is UserRole.PASTOR:
            if operator.church_id is None or not await self._operators.lock_church(
                operator.church_id
            ):
                raise NotFoundException("Operador no encontrado")
            operator = await self._get_authorized_operator(actor, operator_id, role)
            if (
                operator.active
                and operator.is_primary_pastor
                and not await self._operators.has_active_primary_pastor(
                    operator.church_id,
                    excluding_id=operator.id,
                )
            ):
                raise ConflictException(
                    "Asigne otro pastor principal antes de desactivar este pastor"
                )

        deactivated = await self._operators.deactivate_operator(operator_id)
        if deactivated is None:
            raise NotFoundException("Operador no encontrado")
        await self._audit.record_event(
            AuditRecord(
                actor_id=actor.id,
                resource="USUARIO",
                resource_id=deactivated.id,
                action="DESACTIVADO",
                church_id=deactivated.church_id,
                previous_values=self._operator_values(operator),
                new_values=self._operator_values(deactivated),
            )
        )
        return deactivated

    async def set_primary_pastor(
        self,
        actor: UserAccount,
        church_id: UUID,
        pastor_id: UUID,
    ) -> OperatorProfile:
        if actor.role is not UserRole.ADMIN:
            raise ForbiddenException("Solo ADMIN puede definir el pastor principal")

        church = await self._churches.get_by_id(church_id)
        if church is None or not church.active:
            raise NotFoundException("Iglesia no encontrada")
        if not await self._operators.lock_church(church_id):
            raise NotFoundException("Iglesia no encontrada")

        pastors = await self._operators.list_operators(UserRole.PASTOR, church_id=church_id)
        previous_primary = next(
            (pastor for pastor in pastors if pastor.is_primary_pastor and pastor.active),
            None,
        )

        pastor = await self._operators.get_operator(pastor_id)
        if (
            pastor is None
            or pastor.role is not UserRole.PASTOR
            or not pastor.active
            or pastor.church_id != church_id
        ):
            raise NotFoundException("Pastor activo de la iglesia no encontrado")

        primary = await self._operators.set_primary_pastor(church_id, pastor_id)
        if primary is None:
            raise NotFoundException("Pastor activo de la iglesia no encontrado")
        await self._audit.record_event(
            AuditRecord(
                actor_id=actor.id,
                resource="IGLESIA",
                resource_id=church_id,
                action="PASTOR_PRINCIPAL_ASIGNADO",
                church_id=church_id,
                previous_values=(
                    {"pastor_id": str(previous_primary.id)} if previous_primary else None
                ),
                new_values={"pastor_id": str(primary.id)},
            )
        )
        return primary

    async def _get_authorized_operator(
        self,
        actor: UserAccount,
        operator_id: UUID,
        role: UserRole,
    ) -> OperatorProfile:
        operator = await self._operators.get_operator(operator_id)
        if operator is None or operator.role is not role:
            raise NotFoundException("Operador no encontrado")

        if actor.role is UserRole.ADMIN:
            return operator
        if operator.role is UserRole.PASTOR:
            raise ForbiddenException("Solo ADMIN puede gestionar pastores")
        if actor.role is not UserRole.PASTOR:
            raise ForbiddenException("Permisos insuficientes")

        actor_profile = await self._operators.get_operator(actor.id)
        if actor_profile is None or actor_profile.church_id != operator.church_id:
            raise NotFoundException("Operador no encontrado")
        return operator

    @staticmethod
    def _operator_values(operator: OperatorProfile) -> dict[str, object]:
        return {
            "name": operator.name,
            "surname": operator.surname,
            "email": operator.email,
            "role": operator.role.value,
            "active": operator.active,
            "district_id": str(operator.district_id) if operator.district_id else None,
            "church_id": str(operator.church_id) if operator.church_id else None,
            "phone": operator.phone,
            "address": operator.address,
            "is_primary_pastor": operator.is_primary_pastor,
        }