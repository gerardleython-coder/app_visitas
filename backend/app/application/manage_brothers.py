from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from app.application.brother_access import strategy_for
from app.application.audit import AuditRepository
from app.domain.audit import AuditRecord
from app.domain.authentication import UserAccount, UserRole
from app.domain.errors import DomainException, ForbiddenException, NotFoundException
from app.domain.operator import OperatorProfile
from app.domain.organization import Church
from app.domain.brother import BrotherProfile


class BrotherRepository(Protocol):
    async def list_brothers(
        self,
        *,
        church_id: UUID | None = None,
        leader_id: UUID | None = None,
    ) -> list[BrotherProfile]: ...

    async def get_brother(self, brother_id: UUID) -> BrotherProfile | None: ...

    async def create_brother(
        self,
        *,
        name: str,
        surname: str,
        phone: str,
        address: str,
        district_id: UUID,
        church_id: UUID,
        leader_id: UUID,
        assigned_by_id: UUID,
        assigned_at: datetime,
    ) -> BrotherProfile: ...

    async def update_brother(
        self,
        brother_id: UUID,
        changes: dict[str, object],
    ) -> BrotherProfile | None: ...

    async def deactivate_brother(
        self,
        brother_id: UUID,
        ended_at: datetime,
    ) -> BrotherProfile | None: ...

    async def reassign_leader(
        self,
        brother_id: UUID,
        *,
        leader_id: UUID,
        assigned_by_id: UUID,
        assigned_at: datetime,
    ) -> BrotherProfile | None: ...


class OperatorRepository(Protocol):
    async def get_operator(self, operator_id: UUID) -> OperatorProfile | None: ...


class ChurchRepository(Protocol):
    async def get_by_id(self, church_id: UUID) -> Church | None: ...


class ManageBrothers:
    _editable_fields = frozenset({"name", "surname", "phone", "address"})

    def __init__(
        self,
        brothers: BrotherRepository,
        operators: OperatorRepository,
        churches: ChurchRepository,
        audit: AuditRepository,
    ) -> None:
        self._brothers = brothers
        self._operators = operators
        self._churches = churches
        self._audit = audit

    async def list_brothers(self, actor: UserAccount) -> list[BrotherProfile]:
        strategy = strategy_for(actor.role)
        operator = await self._actor_operator(actor)
        scope = strategy.scope(actor, operator)
        return await self._brothers.list_brothers(
            church_id=scope.church_id,
            leader_id=scope.leader_id,
        )

    async def get_brother(
        self,
        actor: UserAccount,
        brother_id: UUID,
    ) -> BrotherProfile:
        brother = await self._brothers.get_brother(brother_id)
        if brother is None or not await self._can_access(actor, brother):
            raise NotFoundException("Hermano no encontrado")
        return brother

    async def create_brother(
        self,
        actor: UserAccount,
        *,
        name: str,
        surname: str,
        phone: str,
        address: str,
        district_id: UUID,
        church_id: UUID,
        leader_id: UUID | None = None,
    ) -> BrotherProfile:
        church = await self._churches.get_by_id(church_id)
        if church is None or not church.active:
            raise DomainException("Iglesia no encontrada o inactiva")
        if church.district_id != district_id:
            raise DomainException("El distrito no corresponde a la iglesia")

        strategy = strategy_for(actor.role)
        actor_profile = await self._actor_operator(actor)
        leader_id = strategy.assignment_leader_id(
            actor,
            actor_profile,
            district_id=district_id,
            church_id=church_id,
            requested_leader_id=leader_id,
        )

        leader = await self._operators.get_operator(leader_id)
        if (
            leader is None
            or leader.role is not UserRole.LIDER
            or not leader.active
            or leader.church_id != church_id
            or leader.district_id != district_id
        ):
            raise DomainException("El líder debe estar activo y pertenecer a la iglesia")

        brother = await self._brothers.create_brother(
            name=name,
            surname=surname,
            phone=phone,
            address=address,
            district_id=district_id,
            church_id=church_id,
            leader_id=leader.id,
            assigned_by_id=actor.id,
            assigned_at=datetime.now(UTC),
        )
        await self._audit.record_event(
            AuditRecord(
                actor_id=actor.id,
                resource="HERMANO",
                resource_id=brother.id,
                action="CREADO",
                church_id=brother.church_id,
                new_values=self._brother_values(brother),
            )
        )
        return brother

    async def update_brother(
        self,
        actor: UserAccount,
        brother_id: UUID,
        changes: dict[str, object],
    ) -> BrotherProfile:
        if not changes or not changes.keys() <= self._editable_fields:
            raise DomainException("Los datos editables están vacíos o no son válidos")
        brother = await self.get_brother(actor, brother_id)
        if not brother.active:
            raise NotFoundException("Hermano no encontrado")
        updated = await self._brothers.update_brother(brother_id, changes)
        if updated is None:
            raise NotFoundException("Hermano no encontrado")
        await self._audit.record_event(
            AuditRecord(
                actor_id=actor.id,
                resource="HERMANO",
                resource_id=updated.id,
                action="MODIFICADO",
                church_id=updated.church_id,
                previous_values=self._brother_values(brother),
                new_values=self._brother_values(updated),
            )
        )
        return updated

    async def deactivate_brother(
        self,
        actor: UserAccount,
        brother_id: UUID,
    ) -> BrotherProfile:
        brother = await self.get_brother(actor, brother_id)
        if not brother.active:
            return brother
        deactivated = await self._brothers.deactivate_brother(
            brother_id,
            datetime.now(UTC),
        )
        if deactivated is None:
            raise NotFoundException("Hermano no encontrado")
        await self._audit.record_event(
            AuditRecord(
                actor_id=actor.id,
                resource="HERMANO",
                resource_id=deactivated.id,
                action="DESACTIVADO",
                church_id=deactivated.church_id,
                previous_values=self._brother_values(brother),
                new_values=self._brother_values(deactivated),
            )
        )
        return deactivated

    async def reassign_leader(
        self,
        actor: UserAccount,
        brother_id: UUID,
        leader_id: UUID,
    ) -> BrotherProfile:
        if actor.role not in (UserRole.ADMIN, UserRole.PASTOR):
            strategy_for(actor.role).authorize_reassignment(actor, None)
        else:
            operator = await self._actor_operator(actor)
            strategy_for(actor.role).authorize_reassignment(actor, operator)
        brother = await self.get_brother(actor, brother_id)
        if not brother.active:
            raise NotFoundException("Hermano no encontrado")
        leader = await self._operators.get_operator(leader_id)
        if (
            leader is None
            or leader.role is not UserRole.LIDER
            or not leader.active
            or leader.church_id != brother.church_id
            or leader.district_id != brother.district_id
        ):
            raise DomainException("El líder debe estar activo en la iglesia del hermano")
        if brother.leader_id == leader.id:
            return brother

        reassigned = await self._brothers.reassign_leader(
            brother_id,
            leader_id=leader.id,
            assigned_by_id=actor.id,
            assigned_at=datetime.now(UTC),
        )
        if reassigned is None:
            raise NotFoundException("Hermano no encontrado")
        await self._audit.record_event(
            AuditRecord(
                actor_id=actor.id,
                resource="HERMANO",
                resource_id=reassigned.id,
                action="LIDER_REASIGNADO",
                church_id=reassigned.church_id,
                previous_values={"leader_id": str(brother.leader_id)},
                new_values={"leader_id": str(reassigned.leader_id)},
            )
        )
        return reassigned

    async def _can_access(self, actor: UserAccount, brother: BrotherProfile) -> bool:
        strategy = strategy_for(actor.role)
        operator = await self._actor_operator(actor)
        return strategy.can_access(actor, operator, brother)

    async def _actor_operator(self, actor: UserAccount) -> OperatorProfile | None:
        if actor.role is UserRole.ADMIN:
            return None
        if actor.role not in (UserRole.PASTOR, UserRole.LIDER):
            raise ForbiddenException("Permisos insuficientes")
        return await self._get_actor_operator(actor, actor.role)

    async def _get_actor_operator(
        self,
        actor: UserAccount,
        expected_role: UserRole,
    ) -> OperatorProfile:
        profile = await self._operators.get_operator(actor.id)
        if profile is None or profile.role is not expected_role or not profile.active:
            raise ForbiddenException("La cuenta no tiene una asignación activa")
        return profile

    @staticmethod
    def _brother_values(brother: BrotherProfile) -> dict[str, object]:
        return {
            "name": brother.name,
            "surname": brother.surname,
            "phone": brother.phone,
            "address": brother.address,
            "district_id": str(brother.district_id),
            "church_id": str(brother.church_id),
            "leader_id": str(brother.leader_id),
            "active": brother.active,
        }