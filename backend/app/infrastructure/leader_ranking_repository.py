from datetime import datetime
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.authentication import UserRole
from app.domain.ranking import LeaderRankingEntry
from app.domain.visit import VisitStatus
from app.infrastructure.models import UserModel, VisitModel


class SQLAlchemyLeaderRankingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_leader_ranking(
        self,
        *,
        church_id: UUID,
        starts_at: datetime,
        ends_at: datetime,
    ) -> list[LeaderRankingEntry]:
        completed_count = func.count(VisitModel.id)
        position = func.dense_rank().over(order_by=desc(completed_count)).label("position")
        statement = (
            select(
                UserModel.id,
                (UserModel.name + " " + UserModel.surname).label("leader_name"),
                completed_count.label("completed_visits"),
                position,
            )
            .join(VisitModel, VisitModel.leader_id == UserModel.id)
            .where(
                UserModel.church_id == church_id,
                UserModel.role == UserRole.LIDER,
                VisitModel.status == VisitStatus.COMPLETADA.value,
                VisitModel.completed_at >= starts_at,
                VisitModel.completed_at < ends_at,
            )
            .group_by(UserModel.id, UserModel.name, UserModel.surname)
            .order_by(position, UserModel.surname, UserModel.name, UserModel.id)
        )
        rows = (await self._session.execute(statement)).all()
        return [
            LeaderRankingEntry(
                leader_id=row.id,
                leader_name=row.leader_name,
                completed_visits=row.completed_visits,
                position=row.position,
            )
            for row in rows
        ]