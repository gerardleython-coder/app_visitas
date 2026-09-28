from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.domain.authentication import UserAccount, UserRole
from app.domain.brother import BrotherProfile
from app.domain.errors import DomainException, ForbiddenException
from app.domain.operator import OperatorProfile


@dataclass(frozen=True, slots=True)
class BrotherScope:
    church_id: UUID | None = None
    leader_id: UUID | None = None


class BrotherAccessStrategy(Protocol):
    def scope(
        self,
        actor: UserAccount,
        operator: OperatorProfile | None,
    ) -> BrotherScope: ...

    def assignment_leader_id(
        self,
        actor: UserAccount,
        operator: OperatorProfile | None,
        *,
        district_id: UUID,
        church_id: UUID,
        requested_leader_id: UUID | None,
    ) -> UUID: ...

    def can_access(
        self,
        actor: UserAccount,
        operator: OperatorProfile | None,
        brother: BrotherProfile,
    ) -> bool: ...

    def authorize_reassignment(
        self,
        actor: UserAccount,
        operator: OperatorProfile | None,
    ) -> None: ...


class AdminStrategy:
    def scope(
        self,
        actor: UserAccount,
        operator: OperatorProfile | None,
    ) -> BrotherScope:
        return BrotherScope()

    def assignment_leader_id(
        self,
        actor: UserAccount,
        operator: OperatorProfile | None,
        *,
        district_id: UUID,
        church_id: UUID,
        requested_leader_id: UUID | None,
    ) -> UUID:
        if requested_leader_id is None:
            raise DomainException("Debe asignar un líder")
        return requested_leader_id

    def can_access(
        self,
        actor: UserAccount,
        operator: OperatorProfile | None,
        brother: BrotherProfile,
    ) -> bool:
        return True

    def authorize_reassignment(
        self,
        actor: UserAccount,
        operator: OperatorProfile | None,
    ) -> None:
        return None


class PastorStrategy:
    def scope(
        self,
        actor: UserAccount,
        operator: OperatorProfile | None,
    ) -> BrotherScope:
        if operator is None or operator.church_id is None:
            raise ForbiddenException("El pastor no tiene iglesia asignada")
        return BrotherScope(church_id=operator.church_id)

    def assignment_leader_id(
        self,
        actor: UserAccount,
        operator: OperatorProfile | None,
        *,
        district_id: UUID,
        church_id: UUID,
        requested_leader_id: UUID | None,
    ) -> UUID:
        self.scope(actor, operator)
        if operator is None or operator.church_id != church_id:
            raise ForbiddenException("La asignación está fuera de su iglesia")
        if operator.district_id != district_id:
            raise ForbiddenException("El distrito está fuera de su iglesia")
        if requested_leader_id is None:
            raise DomainException("Debe asignar un líder")
        return requested_leader_id

    def can_access(
        self,
        actor: UserAccount,
        operator: OperatorProfile | None,
        brother: BrotherProfile,
    ) -> bool:
        return self.scope(actor, operator).church_id == brother.church_id

    def authorize_reassignment(
        self,
        actor: UserAccount,
        operator: OperatorProfile | None,
    ) -> None:
        self.scope(actor, operator)


class LiderStrategy:
    def scope(
        self,
        actor: UserAccount,
        operator: OperatorProfile | None,
    ) -> BrotherScope:
        if operator is None or operator.church_id is None or operator.district_id is None:
            raise ForbiddenException("El líder no tiene iglesia asignada")
        return BrotherScope(leader_id=actor.id)

    def assignment_leader_id(
        self,
        actor: UserAccount,
        operator: OperatorProfile | None,
        *,
        district_id: UUID,
        church_id: UUID,
        requested_leader_id: UUID | None,
    ) -> UUID:
        self.scope(actor, operator)
        if operator is None or operator.church_id != church_id:
            raise ForbiddenException("La asignación está fuera de su iglesia")
        if operator.district_id != district_id:
            raise ForbiddenException("El distrito está fuera de su iglesia")
        if requested_leader_id is not None and requested_leader_id != actor.id:
            raise ForbiddenException("Un líder solo puede asignar hermanos a sí mismo")
        return actor.id

    def can_access(
        self,
        actor: UserAccount,
        operator: OperatorProfile | None,
        brother: BrotherProfile,
    ) -> bool:
        self.scope(actor, operator)
        return brother.leader_id == actor.id

    def authorize_reassignment(
        self,
        actor: UserAccount,
        operator: OperatorProfile | None,
    ) -> None:
        raise ForbiddenException("Solo ADMIN o PASTOR pueden reasignar al líder")


def strategy_for(role: UserRole) -> BrotherAccessStrategy:
    strategies: dict[UserRole, BrotherAccessStrategy] = {
        UserRole.ADMIN: AdminStrategy(),
        UserRole.PASTOR: PastorStrategy(),
        UserRole.LIDER: LiderStrategy(),
    }
    strategy = strategies.get(role)
    if strategy is None:
        raise ForbiddenException("Permisos insuficientes")
    return strategy