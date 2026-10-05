from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest

from app.application.leader_ranking import GetLeaderRanking
from app.domain.authentication import UserAccount, UserRole
from app.domain.errors import DomainException, ForbiddenException
from app.domain.operator import OperatorProfile
from app.domain.ranking import LeaderRankingEntry, RankingPeriod


BOGOTA = ZoneInfo("America/Bogota")


@dataclass
class FakeRankingRepository:
    entries: list[LeaderRankingEntry] = field(default_factory=list)
    query: tuple[UUID, datetime, datetime] | None = None

    async def list_leader_ranking(
        self,
        *,
        church_id: UUID,
        starts_at: datetime,
        ends_at: datetime,
    ) -> list[LeaderRankingEntry]:
        self.query = (church_id, starts_at, ends_at)
        return self.entries


@dataclass
class FakeOperatorRepository:
    profile: OperatorProfile | None

    async def get_operator(self, operator_id: UUID) -> OperatorProfile | None:
        return self.profile if self.profile and self.profile.id == operator_id else None


def account(role: UserRole, account_id: UUID | None = None) -> UserAccount:
    return UserAccount(
        id=account_id or uuid4(),
        email="ranking@example.test",
        password_hash="test-only-hash",
        role=role,
        active=True,
    )


def operator(
    operator_id: UUID,
    church_id: UUID | None,
    *,
    role: UserRole = UserRole.PASTOR,
    active: bool = True,
) -> OperatorProfile:
    return OperatorProfile(
        id=operator_id,
        name="Pastor",
        surname="Ranking",
        email="pastor@example.test",
        role=role,
        active=active,
        district_id=uuid4(),
        church_id=church_id,
    )


async def test_admin_requests_monthly_ranking_with_bogota_calendar_bounds() -> None:
    church_id = uuid4()
    repository = FakeRankingRepository()
    query = GetLeaderRanking(repository, FakeOperatorRepository(None))

    result = await query.execute(
        account(UserRole.ADMIN),
        period=RankingPeriod.MES,
        church_id=church_id,
        reference_date=date(2026, 9, 30),
    )

    assert result == []
    assert repository.query == (
        church_id,
        datetime(2026, 9, 1, tzinfo=BOGOTA).astimezone(UTC),
        datetime(2026, 10, 1, tzinfo=BOGOTA).astimezone(UTC),
    )


async def test_pastor_ranking_uses_monday_to_monday_church_scope() -> None:
    pastor_id = uuid4()
    church_id = uuid4()
    entries = [
        LeaderRankingEntry(
            leader_id=uuid4(),
            leader_name="Ana Gomez",
            completed_visits=4,
            position=1,
        )
    ]
    repository = FakeRankingRepository(entries)
    query = GetLeaderRanking(
        repository,
        FakeOperatorRepository(operator(pastor_id, church_id)),
    )

    result = await query.execute(
        account(UserRole.PASTOR, pastor_id),
        period=RankingPeriod.SEMANA,
        reference_date=date(2026, 9, 30),
    )

    assert result == entries
    assert repository.query == (
        church_id,
        datetime(2026, 9, 28, tzinfo=BOGOTA).astimezone(UTC),
        datetime(2026, 10, 5, tzinfo=BOGOTA).astimezone(UTC),
    )


async def test_admin_must_choose_a_church() -> None:
    query = GetLeaderRanking(FakeRankingRepository(), FakeOperatorRepository(None))

    with pytest.raises(DomainException, match="iglesia"):
        await query.execute(account(UserRole.ADMIN), period=RankingPeriod.MES)


async def test_pastor_cannot_request_another_church_ranking() -> None:
    pastor_id = uuid4()
    church_id = uuid4()
    repository = FakeRankingRepository()
    query = GetLeaderRanking(
        repository,
        FakeOperatorRepository(operator(pastor_id, church_id)),
    )

    with pytest.raises(ForbiddenException):
        await query.execute(
            account(UserRole.PASTOR, pastor_id),
            period=RankingPeriod.MES,
            church_id=uuid4(),
        )

    assert repository.query is None


@pytest.mark.parametrize(
    "operator_profile",
    [
        None,
        "inactive",
        "wrong-role",
        "unassigned",
    ],
)
async def test_pastor_requires_an_active_pastor_profile_and_church(
    operator_profile: str | None,
) -> None:
    pastor_id = uuid4()
    profile = None
    if operator_profile == "inactive":
        profile = operator(pastor_id, uuid4(), active=False)
    elif operator_profile == "wrong-role":
        profile = operator(pastor_id, uuid4(), role=UserRole.LIDER)
    elif operator_profile == "unassigned":
        profile = operator(pastor_id, None)
    repository = FakeRankingRepository()
    query = GetLeaderRanking(repository, FakeOperatorRepository(profile))

    with pytest.raises(ForbiddenException):
        await query.execute(
            account(UserRole.PASTOR, pastor_id),
            period=RankingPeriod.MES,
        )

    assert repository.query is None


async def test_leader_cannot_request_ranking() -> None:
    repository = FakeRankingRepository()
    query = GetLeaderRanking(repository, FakeOperatorRepository(None))

    with pytest.raises(ForbiddenException):
        await query.execute(
            account(UserRole.LIDER),
            period=RankingPeriod.MES,
            church_id=uuid4(),
        )

    assert repository.query is None