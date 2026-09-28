from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.domain.authentication import UserAccount, UserRole
from app.domain.brother import BrotherProfile
from app.domain.errors import ForbiddenException
from app.domain.operator import OperatorProfile
from app.domain.visit import Visit


@dataclass(frozen=True, slots=True)
class VisitScope:
    church_id: UUID | None = None
    leader_id: UUID | None = None


class VisitAccessStrategy(Protocol):
    def scope(self, actor: UserAccount, operator: OperatorProfile | None) -> VisitScope: ...

    def can_access(
        self,
        actor: UserAccount,
        operator: OperatorProfile | None,
        visit: Visit,
    ) -> bool: ...

    def can_create(
        self,
        actor: UserAccount,
        operator: OperatorProfile | None,
        brother: BrotherProfile,
    ) -> bool: ...

    def can_read_history(self) -> bool: ...


class AdminVisitStrategy:
    def scope(self, actor: UserAccount, operator: OperatorProfile | None) -> VisitScope:
        return VisitScope()

    def can_access(
        self,
        actor: UserAccount,
        operator: OperatorProfile | None,
        visit: Visit,
    ) -> bool:
        return True

    def can_create(
        self,
        actor: UserAccount,
        operator: OperatorProfile | None,
        brother: BrotherProfile,
    ) -> bool:
        return True

    def can_read_history(self) -> bool:
        return True


class PastorVisitStrategy:
    def scope(self, actor: UserAccount, operator: OperatorProfile | None) -> VisitScope:
        if operator is None or operator.church_id is None:
            raise ForbiddenException("El pastor no tiene iglesia asignada")
        return VisitScope(church_id=operator.church_id)

    def can_access(
        self,
        actor: UserAccount,
        operator: OperatorProfile | None,
        visit: Visit,
    ) -> bool:
        return self.scope(actor, operator).church_id == visit.church_id

    def can_create(
        self,
        actor: UserAccount,
        operator: OperatorProfile | None,
        brother: BrotherProfile,
    ) -> bool:
        return self.scope(actor, operator).church_id == brother.church_id

    def can_read_history(self) -> bool:
        return True


class LiderVisitStrategy:
    def scope(self, actor: UserAccount, operator: OperatorProfile | None) -> VisitScope:
        if operator is None or operator.church_id is None:
            raise ForbiddenException("El líder no tiene iglesia asignada")
        return VisitScope(leader_id=actor.id)

    def can_access(
        self,
        actor: UserAccount,
        operator: OperatorProfile | None,
        visit: Visit,
    ) -> bool:
        self.scope(actor, operator)
        return visit.leader_id == actor.id

    def can_create(
        self,
        actor: UserAccount,
        operator: OperatorProfile | None,
        brother: BrotherProfile,
    ) -> bool:
        self.scope(actor, operator)
        return brother.leader_id == actor.id

    def can_read_history(self) -> bool:
        return False


def strategy_for(role: UserRole) -> VisitAccessStrategy:
    strategies: dict[UserRole, VisitAccessStrategy] = {
        UserRole.ADMIN: AdminVisitStrategy(),
        UserRole.PASTOR: PastorVisitStrategy(),
        UserRole.LIDER: LiderVisitStrategy(),
    }
    strategy = strategies.get(role)
    if strategy is None:
        raise ForbiddenException("Permisos insuficientes")
    return strategy