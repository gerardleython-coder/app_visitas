from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest

from app.application.create_operator import CreateOperator
from app.domain.audit import AuditRecord
from app.domain.authentication import UserAccount, UserRole
from app.domain.errors import DomainException, ForbiddenException
from app.domain.organization import Church


@dataclass
class FakeChurchRepository:
    church: Church | None

    async def get_by_id(self, church_id: UUID) -> Church | None:
        return self.church if self.church and self.church.id == church_id else None


@dataclass
class FakeOperatorRepository:
    accounts: list[UserAccount] = field(default_factory=list)

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
    ) -> UserAccount:
        account = UserAccount(
            id=uuid4(),
            email=email,
            password_hash=password_hash,
            role=role,
            active=True,
        )
        self.accounts.append(account)
        return account


@dataclass
class FakePasswordHasher:
    hash_calls: int = 0

    def hash(self, password: str) -> str:
        self.hash_calls += 1
        return "hashed-test-value"


@dataclass
class FakeAuditRepository:
    records: list[AuditRecord] = field(default_factory=list)

    async def record_event(self, record: AuditRecord) -> None:
        self.records.append(record)


@pytest.mark.parametrize("role", [UserRole.PASTOR, UserRole.LIDER])
async def test_admin_creates_operator_in_church_selected_from_district(role: UserRole) -> None:
    district_id = uuid4()
    church_id = uuid4()
    church = Church(id=church_id, district_id=district_id)
    operators = FakeOperatorRepository()
    passwords = FakePasswordHasher()
    audit = FakeAuditRepository()
    use_case = CreateOperator(
        churches=FakeChurchRepository(church),
        operators=operators,
        passwords=passwords,
        audit=audit,
    )

    account = await use_case.execute(
        actor_role=UserRole.ADMIN,
        actor_id=uuid4(),
        name="Ana",
        surname="Gomez",
        email="ana@example.test",
        password="test-only-value",
        role=role,
        district_id=district_id,
        church_id=church_id,
    )

    assert account.role is role
    assert account.active is True
    assert account.password_hash == "hashed-test-value"
    assert passwords.hash_calls == 1
    assert operators.accounts == [account]
    assert audit.records[0].resource_id == account.id
    assert audit.records[0].action == "CREADO"
    assert audit.records[0].new_values["role"] == role.value
    assert "password" not in audit.records[0].new_values


async def test_rejects_church_from_another_district_before_hashing_or_persisting() -> None:
    district_id = uuid4()
    church = Church(id=uuid4(), district_id=uuid4())
    operators = FakeOperatorRepository()
    passwords = FakePasswordHasher()
    audit = FakeAuditRepository()
    use_case = CreateOperator(
        churches=FakeChurchRepository(church),
        operators=operators,
        passwords=passwords,
        audit=audit,
    )

    with pytest.raises(DomainException, match="Iglesia fuera del distrito"):
        await use_case.execute(
            actor_role=UserRole.ADMIN,
            actor_id=uuid4(),
            name="Ana",
            surname="Gomez",
            email="ana@example.test",
            password="test-only-value",
            role=UserRole.LIDER,
            district_id=district_id,
            church_id=church.id,
        )

    assert passwords.hash_calls == 0
    assert operators.accounts == []
    assert audit.records == []


async def test_rejects_inactive_church_before_hashing_or_persisting() -> None:
    district_id = uuid4()
    church = Church(id=uuid4(), district_id=district_id, active=False)
    operators = FakeOperatorRepository()
    passwords = FakePasswordHasher()
    audit = FakeAuditRepository()
    use_case = CreateOperator(
        churches=FakeChurchRepository(church),
        operators=operators,
        passwords=passwords,
        audit=audit,
    )

    with pytest.raises(DomainException, match="Iglesia inactiva"):
        await use_case.execute(
            actor_role=UserRole.ADMIN,
            actor_id=uuid4(),
            name="Ana",
            surname="Gomez",
            email="ana@example.test",
            password="test-only-value",
            role=UserRole.LIDER,
            district_id=district_id,
            church_id=church.id,
        )

    assert passwords.hash_calls == 0
    assert operators.accounts == []
    assert audit.records == []


async def test_non_admin_cannot_create_operator() -> None:
    district_id = uuid4()
    church_id = uuid4()
    operators = FakeOperatorRepository()
    passwords = FakePasswordHasher()
    audit = FakeAuditRepository()
    use_case = CreateOperator(
        churches=FakeChurchRepository(Church(id=church_id, district_id=district_id)),
        operators=operators,
        passwords=passwords,
        audit=audit,
    )

    with pytest.raises(ForbiddenException):
        await use_case.execute(
            actor_role=UserRole.PASTOR,
            actor_id=uuid4(),
            name="Ana",
            surname="Gomez",
            email="ana@example.test",
            password="test-only-value",
            role=UserRole.LIDER,
            district_id=district_id,
            church_id=church_id,
        )

    assert passwords.hash_calls == 0
    assert operators.accounts == []
    assert audit.records == []
