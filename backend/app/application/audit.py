from typing import Protocol
from uuid import UUID

from app.domain.audit import AuditEvent, AuditRecord
from app.domain.authentication import UserAccount, UserRole
from app.domain.errors import ForbiddenException
from app.domain.operator import OperatorProfile


class AuditRepository(Protocol):
    async def record_event(self, record: AuditRecord) -> AuditEvent: ...

    async def list_events(
        self,
        *,
        church_id: UUID | None,
        offset: int,
        limit: int,
    ) -> list[AuditEvent]: ...


class OperatorRepository(Protocol):
    async def get_operator(self, operator_id: UUID) -> OperatorProfile | None: ...


class ListAudit:
    def __init__(self, audit: AuditRepository, operators: OperatorRepository) -> None:
        self._audit = audit
        self._operators = operators

    async def execute(
        self,
        actor: UserAccount,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[AuditEvent]:
        if actor.role is UserRole.ADMIN:
            church_id = None
        elif actor.role is UserRole.PASTOR:
            profile = await self._operators.get_operator(actor.id)
            if (
                profile is None
                or profile.role is not UserRole.PASTOR
                or not profile.active
                or profile.church_id is None
            ):
                raise ForbiddenException("El pastor no tiene iglesia activa asignada")
            church_id = profile.church_id
        else:
            raise ForbiddenException("Solo ADMIN o PASTOR pueden consultar auditoría")

        return await self._audit.list_events(
            church_id=church_id,
            offset=offset,
            limit=limit,
        )