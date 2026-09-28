from typing import Protocol
from uuid import UUID

from app.domain.authentication import UserAccount, UserRole
from app.domain.errors import DomainException, ForbiddenException
from app.domain.organization import Church


class ChurchRepository(Protocol):
    async def get_by_id(self, church_id: UUID) -> Church | None: ...


class OperatorRepository(Protocol):
    async def create_operator(
        self,
        *,
        name: str,
        surname: str,
        email: str,
        password_hash: str,
        role: UserRole,
        district_id: UUID,
        church_id: UUID,
    ) -> UserAccount: ...


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...


class CreateOperator:
    def __init__(
        self,
        churches: ChurchRepository,
        operators: OperatorRepository,
        passwords: PasswordHasher,
    ) -> None:
        self._churches = churches
        self._operators = operators
        self._passwords = passwords

    async def execute(
        self,
        *,
        actor_role: UserRole,
        name: str,
        surname: str,
        email: str,
        password: str,
        role: UserRole,
        district_id: UUID,
        church_id: UUID,
    ) -> UserAccount:
        if actor_role is not UserRole.ADMIN:
            raise ForbiddenException("Solo ADMIN puede asignar roles y territorio")

        if role not in (UserRole.PASTOR, UserRole.LIDER):
            raise DomainException("El rol asignado debe ser PASTOR o LIDER")

        church = await self._churches.get_by_id(church_id)
        if church is None:
            raise DomainException("Iglesia no encontrada")
        if not church.active:
            raise DomainException("Iglesia inactiva")
        if church.district_id != district_id:
            raise DomainException("Iglesia fuera del distrito seleccionado")

        password_hash = self._passwords.hash(password)
        return await self._operators.create_operator(
            name=name,
            surname=surname,
            email=email,
            password_hash=password_hash,
            role=role,
            district_id=district_id,
            church_id=church_id,
        )