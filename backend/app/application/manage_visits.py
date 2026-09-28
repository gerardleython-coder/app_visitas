from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID
from zoneinfo import ZoneInfo

from app.application.visit_access import strategy_for
from app.application.visit_notifications import VisitNotificationQueue
from app.application.visit_commands import (
    CancelVisitCommand,
    CreateVisitCommand,
    UpdateVisitCommand,
)
from app.domain.authentication import UserAccount, UserRole
from app.domain.brother import BrotherProfile
from app.domain.errors import (
    ConflictException,
    DomainException,
    ForbiddenException,
    NotFoundException,
)
from app.domain.operator import OperatorProfile
from app.domain.visit import Visit, VisitHistoryEntry, VisitStatus, VisitType


BOGOTA = ZoneInfo("America/Bogota")


class VisitRepository(Protocol):
    async def list_visits(
        self,
        *,
        church_id: UUID | None = None,
        leader_id: UUID | None = None,
        brother_id: UUID | None = None,
    ) -> list[Visit]: ...

    async def get_visit(self, visit_id: UUID) -> Visit | None: ...

    async def create_visit(
        self,
        *,
        brother_id: UUID,
        leader_id: UUID,
        created_by_id: UUID,
        visit_type: VisitType,
        scheduled_at: datetime,
        duration_minutes: int,
        location: str,
        observations: str,
        created_at: datetime,
    ) -> Visit: ...

    async def update_visit(
        self,
        visit_id: UUID,
        *,
        changes: Mapping[str, object],
        actor_id: UUID,
        action: str,
        occurred_at: datetime,
        new_status: VisitStatus | None = None,
        completed_at: datetime | None = None,
        cancellation_reason: str | None = None,
    ) -> Visit | None: ...

    async def list_history(self, visit_id: UUID) -> list[VisitHistoryEntry]: ...


class BrotherRepository(Protocol):
    async def get_brother(self, brother_id: UUID) -> BrotherProfile | None: ...


class OperatorRepository(Protocol):
    async def get_operator(self, operator_id: UUID) -> OperatorProfile | None: ...


class ManageVisits:
    _editable_fields = frozenset(
        {"visit_type", "scheduled_at", "duration_minutes", "location", "observations"}
    )

    def __init__(
        self,
        visits: VisitRepository,
        brothers: BrotherRepository,
        operators: OperatorRepository,
        notifications: VisitNotificationQueue,
    ) -> None:
        self._visits = visits
        self._brothers = brothers
        self._operators = operators
        self._notifications = notifications

    async def create(self, command: CreateVisitCommand) -> Visit:
        actor = command.actor
        strategy = strategy_for(actor.role)
        actor_operator = await self._actor_operator(actor)
        brother = await self._brothers.get_brother(command.brother_id)
        if brother is None or not brother.active:
            raise NotFoundException("Hermano no encontrado")
        if not strategy.can_create(actor, actor_operator, brother):
            raise NotFoundException("Hermano no encontrado")

        self._ensure_future(command.scheduled_at)
        if command.duration_minutes <= 0:
            raise DomainException("La duración debe ser mayor que cero")
        self._ensure_text(command.location, "La ubicación es obligatoria")
        self._ensure_text(command.observations, "Las observaciones son obligatorias")

        leader = await self._operators.get_operator(brother.leader_id)
        if (
            leader is None
            or leader.role is not UserRole.LIDER
            or not leader.active
            or leader.church_id != brother.church_id
        ):
            raise DomainException("El hermano no tiene un líder activo en su iglesia")

        visit = await self._visits.create_visit(
            brother_id=brother.id,
            leader_id=leader.id,
            created_by_id=actor.id,
            visit_type=command.visit_type,
            scheduled_at=command.scheduled_at,
            duration_minutes=command.duration_minutes,
            location=command.location.strip(),
            observations=command.observations.strip(),
            created_at=datetime.now(UTC),
        )
        await self._notifications.enqueue_visit_created(visit)
        return visit

    async def list_visits(self, actor: UserAccount) -> list[Visit]:
        strategy = strategy_for(actor.role)
        actor_operator = await self._actor_operator(actor)
        scope = strategy.scope(actor, actor_operator)
        return await self._visits.list_visits(
            church_id=scope.church_id,
            leader_id=scope.leader_id,
        )

    async def get(self, actor: UserAccount, visit_id: UUID) -> Visit:
        visit = await self._visits.get_visit(visit_id)
        if visit is None or not await self._can_access(actor, visit):
            raise NotFoundException("Visita no encontrada")
        return visit

    async def update(self, command: UpdateVisitCommand) -> Visit:
        if not command.changes or not command.changes.keys() <= self._editable_fields | {"status"}:
            raise DomainException("Los datos de actualización no son válidos")
        visit = await self.get(command.actor, command.visit_id)
        actor = command.actor
        changes = dict(command.changes)
        new_status: VisitStatus | None = None
        completed_at: datetime | None = None
        action = "MODIFICADA"
        occurred_at = datetime.now(UTC)

        if visit.status is VisitStatus.CANCELADA:
            raise ConflictException("Una visita CANCELADA no puede modificarse")

        if visit.status is VisitStatus.COMPLETADA:
            if actor.role is not UserRole.ADMIN:
                raise ForbiddenException("Solo ADMIN puede modificar visitas completadas")
            if "status" in changes or "scheduled_at" in changes:
                raise ConflictException("Una visita completada no puede reprogramarse")
        elif "status" in changes:
            try:
                requested_status = VisitStatus(changes.pop("status"))
            except ValueError as error:
                raise DomainException("Estado de visita inválido") from error
            if requested_status is not VisitStatus.COMPLETADA:
                raise DomainException("Las visitas se cancelan con DELETE y motivo")
            self._ensure_completion_due(visit.scheduled_at)
            new_status = VisitStatus.COMPLETADA
            completed_at = occurred_at
            action = "COMPLETADA"

        if "scheduled_at" in changes:
            if visit.status is not VisitStatus.PROGRAMADA or new_status is not None:
                raise ConflictException("Solo una visita PROGRAMADA puede reprogramarse")
            scheduled_at = changes["scheduled_at"]
            if not isinstance(scheduled_at, datetime):
                raise DomainException("La fecha programada no es válida")
            self._ensure_future(scheduled_at)
            action = "REPROGRAMADA"

        if "duration_minutes" in changes and int(changes["duration_minutes"]) <= 0:
            raise DomainException("La duración debe ser mayor que cero")
        for field in ("location", "observations"):
            if field in changes:
                value = changes[field]
                if not isinstance(value, str):
                    raise DomainException(f"{field} no es válido")
                self._ensure_text(value, f"{field} es obligatorio")
                changes[field] = value.strip()
        if "visit_type" in changes:
            try:
                changes["visit_type"] = VisitType(changes["visit_type"])
            except ValueError as error:
                raise DomainException("Tipo de visita inválido") from error

        updated = await self._visits.update_visit(
            visit.id,
            changes=changes,
            actor_id=actor.id,
            action=action,
            occurred_at=occurred_at,
            new_status=new_status,
            completed_at=completed_at,
        )
        if updated is None:
            raise NotFoundException("Visita no encontrada")
        return updated

    async def cancel(self, command: CancelVisitCommand) -> Visit:
        reason = command.reason.strip()
        self._ensure_text(reason, "La cancelación requiere un motivo")
        visit = await self.get(command.actor, command.visit_id)
        if visit.status is not VisitStatus.PROGRAMADA:
            raise ConflictException("Solo una visita PROGRAMADA puede cancelarse")
        updated = await self._visits.update_visit(
            visit.id,
            changes={},
            actor_id=command.actor.id,
            action="CANCELADA",
            occurred_at=datetime.now(UTC),
            new_status=VisitStatus.CANCELADA,
            cancellation_reason=reason,
        )
        if updated is None:
            raise NotFoundException("Visita no encontrada")
        return updated

    async def history(
        self,
        actor: UserAccount,
        visit_id: UUID,
    ) -> list[VisitHistoryEntry]:
        strategy = strategy_for(actor.role)
        if not strategy.can_read_history():
            raise ForbiddenException("El historial solo está disponible para ADMIN y PASTOR")
        await self.get(actor, visit_id)
        return await self._visits.list_history(visit_id)

    async def _can_access(self, actor: UserAccount, visit: Visit) -> bool:
        strategy = strategy_for(actor.role)
        actor_operator = await self._actor_operator(actor)
        return strategy.can_access(actor, actor_operator, visit)

    async def _actor_operator(self, actor: UserAccount) -> OperatorProfile | None:
        if actor.role is UserRole.ADMIN:
            return None
        if actor.role not in (UserRole.PASTOR, UserRole.LIDER):
            raise ForbiddenException("Permisos insuficientes")
        profile = await self._operators.get_operator(actor.id)
        if profile is None or profile.role is not actor.role or not profile.active:
            raise ForbiddenException("La cuenta no tiene una asignación activa")
        return profile

    @staticmethod
    def _ensure_future(scheduled_at: datetime) -> None:
        if scheduled_at.tzinfo is None or scheduled_at.utcoffset() is None:
            raise DomainException("La fecha debe incluir zona horaria")
        if scheduled_at.astimezone(BOGOTA) <= datetime.now(BOGOTA):
            raise DomainException("La visita debe programarse en el futuro de America/Bogota")

    @staticmethod
    def _ensure_completion_due(scheduled_at: datetime) -> None:
        if scheduled_at.astimezone(BOGOTA) > datetime.now(BOGOTA):
            raise DomainException("No se puede completar una visita futura")

    @staticmethod
    def _ensure_text(value: str, message: str) -> None:
        if not value.strip():
            raise DomainException(message)