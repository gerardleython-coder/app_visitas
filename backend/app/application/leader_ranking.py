from datetime import UTC, date, datetime, time, timedelta
from typing import Protocol
from uuid import UUID
from zoneinfo import ZoneInfo

from app.domain.authentication import UserAccount, UserRole
from app.domain.errors import DomainException, ForbiddenException
from app.domain.operator import OperatorProfile
from app.domain.ranking import LeaderRankingEntry, RankingPeriod


BOGOTA = ZoneInfo("America/Bogota")


class LeaderRankingRepository(Protocol):
    async def list_leader_ranking(
        self,
        *,
        church_id: UUID,
        starts_at: datetime,
        ends_at: datetime,
    ) -> list[LeaderRankingEntry]: ...


class OperatorRepository(Protocol):
    async def get_operator(self, operator_id: UUID) -> OperatorProfile | None: ...


class GetLeaderRanking:
    def __init__(
        self,
        rankings: LeaderRankingRepository,
        operators: OperatorRepository,
    ) -> None:
        self._rankings = rankings
        self._operators = operators

    async def execute(
        self,
        actor: UserAccount,
        *,
        period: RankingPeriod,
        church_id: UUID | None = None,
        reference_date: date | None = None,
    ) -> list[LeaderRankingEntry]:
        if actor.role is UserRole.ADMIN:
            if church_id is None:
                raise DomainException("ADMIN debe indicar una iglesia para el ranking")
            selected_church_id = church_id
        elif actor.role is UserRole.PASTOR:
            profile = await self._operators.get_operator(actor.id)
            if (
                profile is None
                or profile.role is not UserRole.PASTOR
                or not profile.active
                or profile.church_id is None
            ):
                raise ForbiddenException("El pastor no tiene iglesia activa asignada")
            if church_id is not None and church_id != profile.church_id:
                raise ForbiddenException("El pastor no puede consultar otra iglesia")
            selected_church_id = profile.church_id
        else:
            raise ForbiddenException("Solo ADMIN o PASTOR pueden consultar rankings")

        starts_at, ends_at = self._period_bounds(period, reference_date)
        return await self._rankings.list_leader_ranking(
            church_id=selected_church_id,
            starts_at=starts_at,
            ends_at=ends_at,
        )

    @staticmethod
    def _period_bounds(
        period: RankingPeriod,
        reference_date: date | None,
    ) -> tuple[datetime, datetime]:
        selected_date = reference_date or datetime.now(BOGOTA).date()
        if period is RankingPeriod.SEMANA:
            start_date = selected_date - timedelta(days=selected_date.weekday())
            end_date = start_date + timedelta(days=7)
        else:
            start_date = selected_date.replace(day=1)
            if start_date.month == 12:
                end_date = start_date.replace(year=start_date.year + 1, month=1)
            else:
                end_date = start_date.replace(month=start_date.month + 1)

        return (
            datetime.combine(start_date, time.min, tzinfo=BOGOTA).astimezone(UTC),
            datetime.combine(end_date, time.min, tzinfo=BOGOTA).astimezone(UTC),
        )