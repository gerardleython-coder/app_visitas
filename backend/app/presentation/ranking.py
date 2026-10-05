from datetime import date
from typing import NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.application.leader_ranking import GetLeaderRanking
from app.domain.authentication import UserAccount, UserRole
from app.domain.errors import DomainException, ForbiddenException
from app.domain.ranking import RankingPeriod
from app.presentation.dependencies import (
    get_leader_ranking as get_leader_ranking_query,
    require_roles,
)


class LeaderRankingResponse(BaseModel):
    leader_id: UUID
    leader_name: str
    completed_visits: int
    position: int


router = APIRouter(tags=["reports"])


def _raise_domain_http_error(error: DomainException) -> NoReturn:
    if isinstance(error, ForbiddenException):
        raise HTTPException(
            status_code=403,
            detail={"code": "forbidden", "message": "Permisos insuficientes"},
        ) from error
    raise HTTPException(
        status_code=422,
        detail={"code": "invalid_operation", "message": str(error)},
    ) from error


@router.get("/reports/ranking", response_model=list[LeaderRankingResponse])
async def get_leader_ranking(
    period: RankingPeriod,
    church_id: UUID | None = Query(default=None),
    reference_date: date | None = Query(default=None),
    actor: UserAccount = Depends(require_roles(UserRole.ADMIN, UserRole.PASTOR)),
    query: GetLeaderRanking = Depends(get_leader_ranking_query),
) -> list[LeaderRankingResponse]:
    try:
        entries = await query.execute(
            actor,
            period=period,
            church_id=church_id,
            reference_date=reference_date,
        )
    except DomainException as error:
        _raise_domain_http_error(error)
    return [
        LeaderRankingResponse(
            leader_id=entry.leader_id,
            leader_name=entry.leader_name,
            completed_visits=entry.completed_visits,
            position=entry.position,
        )
        for entry in entries
    ]